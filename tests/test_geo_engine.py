"""Comprehensive unit tests for Geo Evidence Engine.

Verifies:
- NDVI calculation
- NDWI calculation
- NDBI calculation
- T1/T2 difference
- thresholding
- binary change mask
- changed pixel count
- pixel area (dynamically calculated, not assuming 10m)
- total changed area
- change percentage
- CRS handling and incompatibility reporting
- geographic CRS area calculation (degree != meter, UTM reprojection)
- mask cleanup (morphological and connected-component noise removal)
- GeoJSON vectorization and preservation
- End-to-end pipeline execution with synthetic GeoTIFFs
"""

import os
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, from_origin

import geo_engine
from geo_engine.indices import (
    calculate_normalized_difference,
    calculate_ndvi,
    calculate_ndwi,
    calculate_ndbi,
    calculate_index,
    extract_bands_from_raster,
)
from geo_engine.change_detection import (
    IncompatibleRastersError,
    validate_raster_compatibility,
    calculate_spectral_difference,
    generate_change_mask,
    classify_change_type,
    detect_spectral_change,
)
from geo_engine.quantification import (
    determine_utm_crs_from_bounds,
    get_pixel_area_projected,
    reproject_mask_to_metric,
    calculate_change_metrics,
)
from geo_engine.mask import (
    clean_binary_mask,
    save_mask_to_geotiff,
)
from geo_engine.spatial import (
    mask_to_polygons,
    mask_to_geojson,
    create_overlay,
)
from geo_engine import run_change_detection_pipeline


# =====================================================================
# 1. INDICES TESTS (NDVI, NDWI, NDBI, Division by Zero, Nodata)
# =====================================================================

def test_ndvi_calculation_exact_values():
    """Verify exact manual NDVI values: (NIR - Red) / (NIR + Red)."""
    # NIR = 0.8, Red = 0.2 -> (0.8 - 0.2) / (0.8 + 0.2) = 0.6 / 1.0 = 0.6
    # NIR = 0.5, Red = 0.5 -> (0.5 - 0.5) / 1.0 = 0.0
    # NIR = 0.1, Red = 0.3 -> (0.1 - 0.3) / 0.4 = -0.5
    nir = np.array([[0.8, 0.5], [0.1, 0.7]], dtype=np.float32)
    red = np.array([[0.2, 0.5], [0.3, 0.3]], dtype=np.float32)

    ndvi = calculate_ndvi(red=red, nir=nir)

    assert np.isclose(ndvi[0, 0], 0.6, atol=1e-5)
    assert np.isclose(ndvi[0, 1], 0.0, atol=1e-5)
    assert np.isclose(ndvi[1, 0], -0.5, atol=1e-5)
    assert np.isclose(ndvi[1, 1], 0.4, atol=1e-5)


def test_ndvi_division_by_zero_and_nodata():
    """Verify that division by zero and nodata produce NaN without warnings or crash."""
    nir = np.array([[0.0, 0.6], [0.5, -9999.0]], dtype=np.float32)
    red = np.array([[0.0, 0.2], [-9999.0, 0.4]], dtype=np.float32)

    ndvi = calculate_ndvi(red=red, nir=nir, nodata=-9999.0)

    # (0, 0) is 0 / 0 -> division by zero handled -> np.nan
    assert np.isnan(ndvi[0, 0])
    # (0, 1) is (0.6 - 0.2)/(0.6 + 0.2) = 0.5
    assert np.isclose(ndvi[0, 1], 0.5, atol=1e-5)
    # (1, 0) has red == nodata -> np.nan
    assert np.isnan(ndvi[1, 0])
    # (1, 1) has nir == nodata -> np.nan
    assert np.isnan(ndvi[1, 1])


def test_ndwi_calculation():
    """Verify NDWI calculation for McFeeters and Gao formulas."""
    green = np.array([[0.6, 0.2]], dtype=np.float32)
    nir = np.array([[0.2, 0.6]], dtype=np.float32)
    swir = np.array([[0.1, 0.3]], dtype=np.float32)

    # McFeeters: (Green - NIR) / (Green + NIR)
    # (0, 0): (0.6 - 0.2) / 0.8 = 0.5
    # (0, 1): (0.2 - 0.6) / 0.8 = -0.5
    ndwi_mcfeeters = calculate_ndwi(green=green, nir=nir, formula="mcfeeters")
    assert np.isclose(ndwi_mcfeeters[0, 0], 0.5, atol=1e-5)
    assert np.isclose(ndwi_mcfeeters[0, 1], -0.5, atol=1e-5)

    # Gao: (NIR - SWIR) / (NIR + SWIR)
    # (0, 0): (0.2 - 0.1) / 0.3 = 0.33333
    # (0, 1): (0.6 - 0.3) / 0.9 = 0.33333
    ndwi_gao = calculate_ndwi(green=green, nir=nir, swir=swir, formula="gao")
    assert np.isclose(ndwi_gao[0, 0], 1.0 / 3.0, atol=1e-5)
    assert np.isclose(ndwi_gao[0, 1], 1.0 / 3.0, atol=1e-5)


def test_ndbi_calculation():
    """Verify NDBI calculation: (SWIR - NIR) / (SWIR + NIR)."""
    # (0, 0): (0.7 - 0.3) / (0.7 + 0.3) = 0.4
    # (0, 1): (0.2 - 0.6) / (0.2 + 0.6) = -0.5
    swir = np.array([[0.7, 0.2]], dtype=np.float32)
    nir = np.array([[0.3, 0.6]], dtype=np.float32)

    ndbi = calculate_ndbi(swir=swir, nir=nir)
    assert np.isclose(ndbi[0, 0], 0.4, atol=1e-5)
    assert np.isclose(ndbi[0, 1], -0.5, atol=1e-5)


def test_calculate_index_dispatcher_and_band_extraction():
    """Verify generic index calculation and configurable band extraction."""
    # 4 bands: [B1_red, B2_green, B3_nir, B4_swir]
    raster = np.zeros((4, 2, 2), dtype=np.float32)
    raster[0] = 0.2  # red
    raster[1] = 0.3  # green
    raster[2] = 0.8  # nir
    raster[3] = 0.4  # swir

    band_mapping_0_indexed = {"red": 0, "green": 1, "nir": 2, "swir": 3}
    bands = extract_bands_from_raster(raster, band_mapping_0_indexed)

    ndvi = calculate_index("ndvi", bands)
    # (0.8 - 0.2) / 1.0 = 0.6
    assert np.allclose(ndvi, 0.6)

    ndbi = calculate_index("ndbi", bands)
    # (0.4 - 0.8) / 1.2 = -0.333333
    assert np.allclose(ndbi, -1.0 / 3.0)

    # Test 1-indexed band mapping
    band_mapping_1_indexed = {"red": 1, "green": 2, "nir": 3, "swir": 4}
    bands_1 = extract_bands_from_raster(raster, band_mapping_1_indexed)
    assert np.allclose(bands_1["red"], 0.2)


# =====================================================================
# 2. CHANGE DETECTION & THRESHOLDING & BINARY MASK TESTS
# =====================================================================

def test_spectral_difference():
    """Verify difference = index_T2 - index_T1."""
    t1 = np.array([[0.7, 0.4], [0.6, 0.3]], dtype=np.float32)
    t2 = np.array([[0.2, 0.4], [0.9, np.nan]], dtype=np.float32)

    diff = calculate_spectral_difference(t1, t2)

    assert np.isclose(diff[0, 0], -0.5, atol=1e-5)  # 0.2 - 0.7 = -0.5
    assert np.isclose(diff[0, 1], 0.0, atol=1e-5)   # 0.4 - 0.4 = 0.0
    assert np.isclose(diff[1, 0], 0.3, atol=1e-5)   # 0.9 - 0.6 = +0.3
    assert np.isnan(diff[1, 1])                     # NaN - 0.3 = NaN


def test_thresholding_and_binary_change_mask():
    """Verify binary change mask generation with configurable thresholds and directions."""
    diff = np.array([
        [-0.35, -0.15],
        [0.05, 0.30],
    ], dtype=np.float32)

    # Threshold = 0.20
    # Direction: decrease (<= -0.20)
    mask_dec = generate_change_mask(diff, threshold=0.20, direction="decrease")
    expected_dec = np.array([[1, 0], [0, 0]], dtype=np.uint8)
    assert np.array_equal(mask_dec, expected_dec)

    # Direction: increase (>= 0.20)
    mask_inc = generate_change_mask(diff, threshold=0.20, direction="increase")
    expected_inc = np.array([[0, 0], [0, 1]], dtype=np.uint8)
    assert np.array_equal(mask_inc, expected_inc)

    # Direction: both (abs >= 0.20)
    mask_both = generate_change_mask(diff, threshold=0.20, direction="both")
    expected_both = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    assert np.array_equal(mask_both, expected_both)

    # Verify binary values only (0 and 1)
    assert set(np.unique(mask_both)).issubset({0, 1})
    assert mask_both.dtype == np.uint8


def test_classify_change_type_labels():
    """Verify semantic change type classification matches requirements."""
    # NDVI decrease -> "vegetation decrease"
    diff_veg_dec = np.array([[-0.4]], dtype=np.float32)
    mask_one = np.array([[1]], dtype=np.uint8)
    assert classify_change_type("ndvi", direction="auto", difference=diff_veg_dec, mask=mask_one) == "vegetation decrease"

    # NDVI increase -> "vegetation increase"
    diff_veg_inc = np.array([[0.4]], dtype=np.float32)
    assert classify_change_type("ndvi", direction="auto", difference=diff_veg_inc, mask=mask_one) == "vegetation increase"

    # NDWI increase -> "water increase"
    assert classify_change_type("ndwi", direction="increase") == "water increase"
    # NDWI decrease -> "water decrease"
    assert classify_change_type("ndwi", direction="decrease") == "water decrease"

    # NDBI increase -> "built_up_spectral_increase"
    assert classify_change_type("ndbi", direction="increase") == "built_up_spectral_increase"
    # NDBI decrease -> "built_up_spectral_decrease"
    assert classify_change_type("ndbi", direction="decrease") == "built_up_spectral_decrease"

    # Generic or unknown index -> "spectral_change"
    assert classify_change_type("custom_index", direction="increase") == "spectral_change"


# =====================================================================
# 3. QUANTIFICATION & AREA (CRITICAL: MUST NOT ASSUME 10m PIXELS)
# =====================================================================

def test_quantification_pixel_count_and_percentage():
    """Verify exact changed pixel count and change percentage calculation."""
    # 10x10 raster = 100 pixels
    mask = np.zeros((10, 10), dtype=np.uint8)
    # Set exactly 25 pixels to 1
    mask[:5, :5] = 1

    transform = from_origin(500000, 3000000, 20.0, 20.0)
    crs = CRS.from_epsg(32633)  # UTM zone 33N (projected, meters)

    metrics = calculate_change_metrics(mask, transform, crs)

    assert metrics["changed_pixels"] == 25
    assert metrics["total_pixels"] == 100
    assert metrics["change_percent"] == 25.0


def test_quantification_pixel_area_dynamic_resolution():
    """Verify pixel area is computed from transform and NOT assumed to be 10m x 10m.

    Tests with 20m x 20m and 30m x 30m pixels.
    Must fail if hardcoded to 10m x 10m.
    """
    # 1. Test 20m x 20m raster
    transform_20m = from_origin(500000, 3000000, 20.0, 20.0)
    crs_utm = CRS.from_epsg(32633)

    width_m, height_m, area_m2 = get_pixel_area_projected(transform_20m, crs_utm)
    assert np.isclose(width_m, 20.0, atol=1e-5)
    assert np.isclose(height_m, 20.0, atol=1e-5)
    assert np.isclose(area_m2, 400.0, atol=1e-5)

    # Explicit failure check if 10m assumed
    assert area_m2 != 100.0, "FAILED: Implementation assumed 10m x 10m (100 m2) pixels!"

    # 2. Test 30m x 30m raster (e.g. Landsat-like resolution)
    transform_30m = from_origin(500000, 3000000, 30.0, 30.0)
    width_30m, height_30m, area_30m2 = get_pixel_area_projected(transform_30m, crs_utm)
    assert np.isclose(width_30m, 30.0, atol=1e-5)
    assert np.isclose(height_30m, 30.0, atol=1e-5)
    assert np.isclose(area_30m2, 900.0, atol=1e-5)
    assert area_30m2 != 100.0, "FAILED: Implementation assumed 10m x 10m pixels for 30m raster!"


def test_quantification_total_changed_area_hectares():
    """Verify total changed area in hectares for 20m x 20m pixels.

    25 pixels * 400 m2/pixel = 10,000 m2 = 1.0000 hectare.
    (If 10m x 10m were assumed, it would calculate 25 * 100 = 2,500 m2 = 0.25 ha).
    """
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[:5, :5] = 1  # 25 pixels

    transform_20m = from_origin(500000, 3000000, 20.0, 20.0)
    crs = CRS.from_epsg(32633)

    metrics = calculate_change_metrics(mask, transform_20m, crs)

    # 25 * 400 m2 = 10,000 m2 = 1.0 ha
    assert np.isclose(metrics["changed_area_m2"], 10000.0, atol=1e-2)
    assert np.isclose(metrics["changed_area_ha"], 1.0, atol=1e-4)
    # Check that it did NOT produce 0.25 ha (which would happen with a 10m assumption)
    assert metrics["changed_area_ha"] != 0.25, "FAILED: 10m x 10m pixel size was incorrectly assumed!"


def test_quantification_geographic_crs_lat_lon():
    """Verify that geographic CRS (degrees) is NOT treated as meters and is reprojected to UTM.

    In EPSG:4326, pixel size is ~0.0002 degrees (~22 meters).
    If degrees were treated as meters, pixel area would be 0.0002 * 0.0002 = 4e-8 m2.
    Area calculation must reproject to UTM and produce realistic metric hectares.
    """
    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[10:30, 10:30] = 1  # 20x20 = 400 changed pixels

    # New Delhi coordinates in degrees: lon 77.20, lat 28.60
    pixel_deg = 0.0002  # roughly 22.2 meters at equator, ~19.5m in lat
    transform_geo = from_origin(77.20, 28.60, pixel_deg, pixel_deg)
    crs_wgs84 = CRS.from_epsg(4326)

    metrics = calculate_change_metrics(mask, transform_geo, crs_wgs84)

    assert metrics["is_geographic"] is True
    # Verify that pixel area is NOT 4e-8 m2 (which would happen if treating degrees as meters)
    assert metrics["pixel_area_m2"] > 10.0, "FAILED: Degrees were treated as meters!"
    # Realistic pixel area for 0.0002 deg at 28.6 N is ~420 m2
    assert 300.0 < metrics["pixel_area_m2"] < 600.0
    # 400 pixels of ~420 m2 = ~168,000 m2 = ~16.8 ha
    assert 12.0 < metrics["changed_area_ha"] < 22.0
    assert metrics["changed_pixels"] == 400


# =====================================================================
# 4. COMPATIBILITY & CRS HANDLING TESTS
# =====================================================================

def test_compatibility_validation_detects_crs_mismatch(tmp_path):
    """Verify that incompatible CRS between T1 and T2 raises IncompatibleRastersError."""
    p1 = str(tmp_path / "t1.tif")
    p2 = str(tmp_path / "t2.tif")

    profile1 = {
        "driver": "GTiff",
        "height": 10,
        "width": 10,
        "count": 1,
        "dtype": rasterio.float32,
        "crs": CRS.from_epsg(32633),
        "transform": from_origin(500000, 3000000, 10, 10),
    }
    profile2 = dict(profile1, crs=CRS.from_epsg(4326))

    with rasterio.open(p1, "w", **profile1) as d1:
        d1.write(np.zeros((1, 10, 10), dtype=np.float32))

    with rasterio.open(p2, "w", **profile2) as d2:
        d2.write(np.zeros((1, 10, 10), dtype=np.float32))

    with rasterio.open(p1) as d1, rasterio.open(p2) as d2:
        with pytest.raises(IncompatibleRastersError) as exc_info:
            validate_raster_compatibility(d1, d2)
        assert "CRS mismatch" in str(exc_info.value)


def test_compatibility_validation_detects_dimension_mismatch(tmp_path):
    """Verify that incompatible dimensions raise IncompatibleRastersError."""
    p1 = str(tmp_path / "t1_dim.tif")
    p2 = str(tmp_path / "t2_dim.tif")

    profile1 = {
        "driver": "GTiff",
        "height": 10,
        "width": 10,
        "count": 1,
        "dtype": rasterio.float32,
        "crs": CRS.from_epsg(32633),
        "transform": from_origin(500000, 3000000, 10, 10),
    }
    profile2 = dict(profile1, width=20)

    with rasterio.open(p1, "w", **profile1) as d1:
        d1.write(np.zeros((1, 10, 10), dtype=np.float32))
    with rasterio.open(p2, "w", **profile2) as d2:
        d2.write(np.zeros((1, 10, 20), dtype=np.float32))

    with rasterio.open(p1) as d1, rasterio.open(p2) as d2:
        with pytest.raises(IncompatibleRastersError) as exc_info:
            validate_raster_compatibility(d1, d2)
        assert "Dimension mismatch" in str(exc_info.value)


# =====================================================================
# 5. MASK CLEANUP TESTS
# =====================================================================

def test_mask_cleanup_noise_removal():
    """Verify morphological and connected-component cleanup removes isolated noise."""
    mask = np.zeros((20, 20), dtype=np.uint8)

    # 1. Genuine 5x5 change patch
    mask[5:10, 5:10] = 1

    # 2. Single isolated noise pixels (salt)
    mask[1, 1] = 1
    mask[18, 18] = 1
    mask[2, 17] = 1

    # Before cleanup: 25 + 3 = 28 pixels
    assert np.count_nonzero(mask == 1) == 28

    # Clean with min_patch_size = 4
    cleaned = clean_binary_mask(mask, min_patch_size=4, kernel_size=3, morphology_op="opening")

    # Isolated pixels should be gone, genuine 5x5 patch preserved
    assert cleaned[1, 1] == 0
    assert cleaned[18, 18] == 0
    assert cleaned[2, 17] == 0
    assert np.all(cleaned[6:9, 6:9] == 1)


# =====================================================================
# 6. SPATIAL VECTORIZATION & GEOJSON TESTS
# =====================================================================

def test_mask_to_geojson_generation():
    """Verify GeoJSON FeatureCollection generation and polygon structure."""
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:6, 2:6] = 1  # 4x4 block

    transform = from_origin(500000, 3000000, 20.0, 20.0)
    crs = CRS.from_epsg(32633)

    geojson = mask_to_geojson(mask, transform, crs, to_wgs84=False, properties={"change_type": "vegetation decrease"})

    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    feature = geojson["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["change_type"] == "vegetation decrease"

    # Coordinates must be list of coordinate rings
    coords = feature["geometry"]["coordinates"]
    assert len(coords) >= 1
    assert len(coords[0]) >= 4  # Closed polygon ring has at least 4 points


def test_create_overlay_generation(tmp_path):
    """Verify visual overlay generation as RGBA image and file export."""
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 1

    out_file = str(tmp_path / "overlay.png")
    overlay = create_overlay(
        mask=mask,
        background=None,
        color=(255, 0, 0),
        alpha=0.5,
        output_path=out_file,
    )

    assert overlay.shape == (20, 20, 4)
    # Unchanged pixel is transparent
    assert overlay[0, 0, 3] == 0
    # Changed pixel has red color and alpha 127
    assert overlay[10, 10, 0] == 255
    assert overlay[10, 10, 1] == 0
    assert overlay[10, 10, 2] == 0
    assert overlay[10, 10, 3] == 127

    assert os.path.exists(out_file)


# =====================================================================
# 7. END-TO-END PIPELINE WITH SYNTHETIC GEOTIFFS
# =====================================================================

def test_end_to_end_pipeline_with_synthetic_geotiffs(tmp_path):
    """End-to-end integration test of Geo Evidence Engine.

    Creates synthetic bi-temporal 5-band GeoTIFFs:
    T1: Dense vegetation in a 4x4 region (high NIR, low Red -> high NDVI)
    T2: Cleared vegetation in that 4x4 region (low NIR, high Red -> low NDVI)
    Resolution: 20m x 20m.
    Verifies exact structured result output schema, pixel counts, area in hectares,
    GeoTIFF mask preservation, and GeoJSON.
    """
    t1_path = str(tmp_path / "synthetic_t1.tif")
    t2_path = str(tmp_path / "synthetic_t2.tif")
    out_dir = str(tmp_path / "output")

    height, width = 20, 20
    # 5 bands: 1=Red, 2=Green, 3=Blue, 4=NIR, 5=SWIR
    num_bands = 5
    crs = CRS.from_epsg(32633)  # UTM Zone 33N
    # 20m x 20m pixel resolution
    res = 20.0
    transform = from_origin(500000, 3000000, res, res)

    # Initialize T1 arrays (all bands = 0.2 except NIR = 0.8 inside 4x4 block)
    t1_data = np.full((num_bands, height, width), 0.2, dtype=np.float32)
    # Region of interest: [5:9, 5:9] is 4x4 = 16 pixels
    t1_data[3, 5:9, 5:9] = 0.8  # Band 4 (NIR) is high -> NDVI ~ (0.8 - 0.2)/(0.8 + 0.2) = 0.60
    t1_data[0, 5:9, 5:9] = 0.2  # Band 1 (Red) is low

    # Initialize T2 arrays (NIR dropped to 0.2, Red increased to 0.6 in region -> NDVI ~ -0.50)
    t2_data = t1_data.copy()
    t2_data[3, 5:9, 5:9] = 0.2  # Band 4 (NIR) drops
    t2_data[0, 5:9, 5:9] = 0.6  # Band 1 (Red) increases

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": num_bands,
        "dtype": rasterio.float32,
        "crs": crs,
        "transform": transform,
    }

    with rasterio.open(t1_path, "w", **profile) as ds1:
        ds1.write(t1_data)

    with rasterio.open(t2_path, "w", **profile) as ds2:
        ds2.write(t2_data)

    # Run the pipeline
    result = run_change_detection_pipeline(
        t1_path=t1_path,
        t2_path=t2_path,
        index="ndvi",
        threshold=0.3,
        direction="decrease",
        min_patch_size=2,
        output_dir=out_dir,
    )

    # Verify structured result schema exactly matching Requirement 6
    required_keys = {
        "change_detected",
        "change_type",
        "changed_pixels",
        "changed_area_ha",
        "change_percent",
        "mask_path",
        "overlay_path",
        "geojson",
        "evidence_type",
    }
    assert required_keys.issubset(result.keys())

    # 1. Change detected
    assert result["change_detected"] is True

    # 2. Semantic change type
    assert result["change_type"] == "vegetation decrease"

    # 3. Changed pixel count: exactly 16 pixels
    assert result["changed_pixels"] == 16

    # 4. Changed area: 16 pixels * (20m * 20m) = 16 * 400 m2 = 6,400 m2 = 0.64 ha
    assert np.isclose(result["changed_area_ha"], 0.64, atol=1e-3)
    # Check that 10m x 10m was NOT assumed (which would give 0.16 ha)
    assert result["changed_area_ha"] != 0.16

    # 5. Change percent: 16 / 400 pixels = 4.0%
    assert np.isclose(result["change_percent"], 4.0, atol=1e-2)

    # 6. Evidence type
    assert result["evidence_type"] == "spectral_difference"

    # 7. Mask file verification: preserved CRS and dimensions
    assert os.path.exists(result["mask_path"])
    with rasterio.open(result["mask_path"]) as mask_ds:
        assert mask_ds.crs == crs
        assert mask_ds.width == width
        assert mask_ds.height == height
        mask_arr = mask_ds.read(1)
        assert np.count_nonzero(mask_arr == 1) == 16

    # 8. Overlay file verification
    assert os.path.exists(result["overlay_path"])

    # 9. GeoJSON verification
    assert result["geojson"]["type"] == "FeatureCollection"
    assert len(result["geojson"]["features"]) >= 1


def test_ndbi_built_up_increase_classification(tmp_path):
    """Verify built-up increase classification when NDBI rises."""
    t1_path = str(tmp_path / "ndbi_t1.tif")
    t2_path = str(tmp_path / "ndbi_t2.tif")

    height, width = 10, 10
    crs = CRS.from_epsg(32633)
    transform = from_origin(500000, 3000000, 10.0, 10.0)

    # Band 4=NIR, Band 5=SWIR
    t1_data = np.full((5, height, width), 0.2, dtype=np.float32)
    t1_data[3, 2:6, 2:6] = 0.6  # NIR high
    t1_data[4, 2:6, 2:6] = 0.2  # SWIR low -> NDBI low

    t2_data = t1_data.copy()
    t2_data[3, 2:6, 2:6] = 0.2  # NIR drops
    t2_data[4, 2:6, 2:6] = 0.7  # SWIR rises -> NDBI increases

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 5,
        "dtype": rasterio.float32,
        "crs": crs,
        "transform": transform,
    }

    with rasterio.open(t1_path, "w", **profile) as d1:
        d1.write(t1_data)
    with rasterio.open(t2_path, "w", **profile) as d2:
        d2.write(t2_data)

    result = run_change_detection_pipeline(
        t1_path=t1_path,
        t2_path=t2_path,
        index="ndbi",
        threshold=0.3,
        direction="increase",
        output_dir=str(tmp_path / "out_ndbi"),
    )

    assert result["change_detected"] is True
    assert result["change_type"] == "built_up_spectral_increase"
    assert result["changed_pixels"] == 16
