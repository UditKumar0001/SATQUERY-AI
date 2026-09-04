"""Unit tests for SAM 2 segmentation integration in Geo Evidence Engine.

Verifies:
- SAM 2 module initialization and availability checks
- Satellite imagery preprocessing (multispectral bands and normalization)
- Candidate region input extraction from change mask
- Segmentation output and binary mask generation
- Pixel-to-geospatial coordinate conversion
- Georeferencing and CRS preservation
- Dynamic area calculation in hectares
- GeoJSON geometry generation
- Graceful failure when model/checkpoint is unavailable (no faking successful results)
- End-to-end connection with Phase 1 Geo Evidence Engine
- Selective execution: skips SAM 2 when no change is detected by Geo Evidence Engine
"""

import os
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, from_origin

from geo_engine import run_change_detection_pipeline
from geo_engine.segmentation import (
    SAM2NotAvailableError,
    SAM2Segmentor,
    extract_candidate_regions,
    is_sam2_available,
    pixel_to_geo_bbox,
    prepare_satellite_image_for_sam,
    refine_change_with_sam2,
)


# =====================================================================
# 1. INITIALIZATION & AVAILABILITY CHECKS
# =====================================================================

def test_sam2_module_initialization_mock_backend():
    """Verify SAM 2 segmentor initializes properly with mock backend."""
    segmentor = SAM2Segmentor(backend="mock")
    assert segmentor.is_available is True
    assert segmentor.backend == "mock"


def test_sam2_custom_predictor_override():
    """Verify SAM 2 segmentor supports custom predictor overrides for testing."""
    def dummy_predictor(image, candidate):
        h, w = image.shape[:2]
        m = np.zeros((h, w), dtype=np.uint8)
        m[2:4, 2:4] = 1
        return {"mask": m, "confidence": 0.99, "bbox": [2, 2, 3, 3]}

    segmentor = SAM2Segmentor(predictor_override=dummy_predictor)
    assert segmentor.is_available is True
    assert segmentor.backend == "override"

    res = segmentor.segment_candidate(
        image_rgb=np.zeros((10, 10, 3), dtype=np.uint8),
        candidate={"bbox": [2, 2, 4, 4]},
    )
    assert res["confidence"] == 0.99
    assert np.count_nonzero(res["mask"] == 1) == 4


def test_failure_when_checkpoint_unavailable():
    """Verify that when a checkpoint is missing, the module fails gracefully without faking success."""
    nonexistent = "C:/nonexistent_path/sam2_checkpoint_dummy.pt"
    avail, msg = is_sam2_available(checkpoint_path=nonexistent)
    assert avail is False
    assert "not found" in msg

    segmentor = SAM2Segmentor(checkpoint_path=nonexistent, backend="auto")
    assert segmentor.is_available is False

    # Calling segment_candidate must raise SAM2NotAvailableError with clear diagnostic
    with pytest.raises(SAM2NotAvailableError) as exc_info:
        segmentor.segment_candidate(
            image_rgb=np.zeros((10, 10, 3), dtype=np.uint8),
            candidate={"bbox": [0, 0, 5, 5]},
        )
    assert "not found" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()

    # Calling refine_candidates must return structured unavailable status
    result = segmentor.refine_candidates(
        image_rgb=np.zeros((10, 10, 3), dtype=np.uint8),
        candidates=[{"candidate_id": 1, "bbox": [0, 0, 5, 5]}],
        transform=from_origin(500000, 3000000, 10, 10),
        crs=CRS.from_epsg(32633),
    )
    assert result["segmentation_detected"] is False
    assert result["status"] == "unavailable"
    assert "error" in result


# =====================================================================
# 2. SATELLITE IMAGERY PREPROCESSING TESTS
# =====================================================================

def test_preprocessing_multispectral_raster():
    """Verify preprocessing handles multispectral satellite imagery safely without modifying originals."""
    # 5-band raster: (5, 20, 20) with large Digital Numbers (DN) like Sentinel-2
    raster_orig = np.random.uniform(500, 9000, size=(5, 20, 20)).astype(np.float32)
    raster_copy = raster_orig.copy()

    band_mapping = {"red": 1, "green": 2, "blue": 3, "nir": 4, "swir": 5}
    rgb = prepare_satellite_image_for_sam(raster_orig, band_mapping=band_mapping)

    # 1. Output shape must be (H, W, 3) uint8
    assert rgb.shape == (20, 20, 3)
    assert rgb.dtype == np.uint8
    assert np.min(rgb) >= 0
    assert np.max(rgb) <= 255

    # 2. Original raster must NOT have been modified
    assert np.array_equal(raster_orig, raster_copy)


def test_preprocessing_single_band_raster():
    """Verify preprocessing converts single-band raster to 3-channel RGB."""
    single_band = np.full((30, 30), 150.0, dtype=np.float32)
    rgb = prepare_satellite_image_for_sam(single_band)

    assert rgb.shape == (30, 30, 3)
    assert rgb.dtype == np.uint8


# =====================================================================
# 3. CANDIDATE REGION EXTRACTION TESTS
# =====================================================================

def test_extract_candidate_regions_from_change_mask():
    """Verify candidate regions are extracted with bounding boxes, centroids, and noise filtering."""
    mask = np.zeros((40, 40), dtype=np.uint8)

    # Candidate 1: 6x6 patch (area = 36 pixels) at [5:11, 5:11]
    mask[5:11, 5:11] = 1

    # Candidate 2: 4x4 patch (area = 16 pixels) at [25:29, 25:29]
    mask[25:29, 25:29] = 1

    # Noise: 1-pixel and 2-pixel isolated points (should be ignored with min_area_pixels=4)
    mask[2, 35] = 1
    mask[38, 2] = 1
    mask[38, 3] = 1

    candidates = extract_candidate_regions(mask, min_area_pixels=4, padding=2)

    # Should detect exactly 2 candidates
    assert len(candidates) == 2

    # Should be sorted by area descending: Candidate 1 (36 px) first
    assert candidates[0]["area_pixels"] == 36
    assert candidates[1]["area_pixels"] == 16

    # Verify bounding box with padding
    c1_bbox = candidates[0]["bbox"]  # [x_min, y_min, x_max, y_max]
    # Original patch is x in [5, 10], y in [5, 10]. With padding=2 -> [3, 3, 12, 12]
    assert c1_bbox[0] <= 5 and c1_bbox[2] >= 10
    assert c1_bbox[1] <= 5 and c1_bbox[3] >= 10

    # Centroid check
    cx, cy = candidates[0]["centroid"]
    assert np.isclose(cx, 7.5, atol=0.5)
    assert np.isclose(cy, 7.5, atol=0.5)


# =====================================================================
# 4. PIXEL TO GEOSPATIAL CONVERSION TESTS
# =====================================================================

def test_pixel_to_geo_bbox_conversion():
    """Verify pixel bounding box is converted to accurate geospatial coordinates."""
    # 20m resolution raster in UTM
    transform = from_origin(500000.0, 3000000.0, 20.0, 20.0)
    pixel_bbox = [10, 10, 20, 20]  # x_min=10, y_min=10, x_max=20, y_max=20

    geo_bbox = pixel_to_geo_bbox(pixel_bbox, transform)
    # geo_bbox = [geo_x_min, geo_y_min, geo_x_max, geo_y_max]
    # x_min = 500000 + 10 * 20 = 500200
    # x_max = 500000 + (20 + 1) * 20 = 500420
    # y_max = 3000000 - 10 * 20 = 2999800
    # y_min = 3000000 - (20 + 1) * 20 = 2999580
    assert np.isclose(geo_bbox[0], 500200.0, atol=1e-3)
    assert np.isclose(geo_bbox[2], 500420.0, atol=1e-3)
    assert np.isclose(geo_bbox[1], 2999580.0, atol=1e-3)
    assert np.isclose(geo_bbox[3], 2999800.0, atol=1e-3)


# =====================================================================
# 5. SEGMENTATION, GEOREFERENCING & AREA TESTS
# =====================================================================

def test_sam2_segmentation_output_and_georeferencing(tmp_path):
    """Verify SAM 2 segmentation produces georeferenced GeoTIFF and accurate area in hectares."""
    segmentor = SAM2Segmentor(backend="mock")

    height, width = 30, 30
    image_rgb = np.full((height, width, 3), 120, dtype=np.uint8)
    transform = from_origin(500000.0, 3000000.0, 20.0, 20.0)  # 20m pixels -> 400 m2 per pixel
    crs = CRS.from_epsg(32633)

    candidate = {
        "candidate_id": 1,
        "bbox": [5, 5, 20, 20],
        "centroid": [12.5, 12.5],
        "area_pixels": 256,
    }

    out_dir = str(tmp_path / "sam2_out")
    result = segmentor.refine_candidates(
        image_rgb=image_rgb,
        candidates=[candidate],
        transform=transform,
        crs=crs,
        output_dir=out_dir,
    )

    # 1. Structure verification
    assert result["segmentation_detected"] is True
    assert result["model"] == "SAM2"
    assert result["source"] == "geo_evidence_candidate"
    assert len(result["segments"]) == 1

    seg = result["segments"][0]
    assert seg["segment_id"] == 1
    assert "mask_path" in seg
    assert "area_ha" in seg
    assert "geojson" in seg
    assert "bbox" in seg
    assert "geo_bbox" in seg
    assert seg["confidence"] > 0.8
    assert seg["evidence_relation"] == "refined_candidate_segment"

    # 2. Area calculation (must match pixel_count * 400 m2 / 10000)
    expected_area_ha = (seg["pixel_count"] * 400.0) / 10000.0
    assert np.isclose(seg["area_ha"], expected_area_ha, atol=1e-3)

    # 3. Georeferencing preservation in GeoTIFF
    assert os.path.isfile(seg["mask_path"])
    with rasterio.open(seg["mask_path"]) as ds:
        assert ds.crs == crs
        assert ds.width == width
        assert ds.height == height
        assert np.allclose(list(ds.transform)[:6], list(transform)[:6])

    # 4. GeoJSON verification
    gj = seg["geojson"]
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) >= 1
    feat = gj["features"][0]
    assert feat["geometry"]["type"] == "Polygon"


# =====================================================================
# 6. INTEGRATION WITH PHASE 1 GEO EVIDENCE ENGINE
# =====================================================================

def test_sam2_integration_with_geo_evidence_pipeline(tmp_path):
    """Verify seamless handoff from Phase 1 Geo Evidence Engine to SAM 2 refinement."""
    t1_path = str(tmp_path / "t1.tif")
    t2_path = str(tmp_path / "t2.tif")

    height, width = 20, 20
    crs = CRS.from_epsg(32633)
    transform = from_origin(500000, 3000000, 20.0, 20.0)

    # 5 bands: 1=Red, 2=Green, 3=Blue, 4=NIR, 5=SWIR
    t1_data = np.full((5, height, width), 0.2, dtype=np.float32)
    t1_data[3, 5:11, 5:11] = 0.8  # NIR high in 6x6 block (high vegetation)

    t2_data = t1_data.copy()
    t2_data[3, 5:11, 5:11] = 0.2  # NIR dropped (vegetation decrease)
    t2_data[0, 5:11, 5:11] = 0.6  # Red rose

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

    # 1. Run Phase 1 Geo Evidence Engine
    geo_evidence_result = run_change_detection_pipeline(
        t1_path=t1_path,
        t2_path=t2_path,
        index="ndvi",
        threshold=0.3,
        direction="decrease",
        output_dir=str(tmp_path / "geo_out"),
    )

    assert geo_evidence_result["change_detected"] is True
    assert geo_evidence_result["change_type"] == "vegetation decrease"

    # 2. Run SAM 2 secondary refinement on candidate region
    mock_segmentor = SAM2Segmentor(backend="mock")
    sam2_result = refine_change_with_sam2(
        change_result=geo_evidence_result,
        t2_raster=t2_path,
        segmentor=mock_segmentor,
        output_dir=str(tmp_path / "sam2_out"),
    )

    # 3. Verify structured output matches Requirement 6
    assert sam2_result["segmentation_detected"] is True
    assert sam2_result["model"] == "SAM2"
    assert sam2_result["source"] == "geo_evidence_candidate"
    assert len(sam2_result["segments"]) >= 1

    seg = sam2_result["segments"][0]
    assert seg["area_ha"] > 0
    assert os.path.isfile(seg["mask_path"])
    assert seg["geojson"]["type"] == "FeatureCollection"


def test_sam2_skips_when_no_change_detected():
    """Verify performance optimization: SAM 2 is skipped when Geo Evidence Engine detects no change."""
    no_change_result = {
        "change_detected": False,
        "change_type": "none",
        "changed_pixels": 0,
        "changed_area_ha": 0.0,
        "change_percent": 0.0,
        "mask_path": None,
        "overlay_path": None,
        "geojson": {},
        "evidence_type": "spectral_difference",
    }

    dummy_image = np.zeros((3, 20, 20), dtype=np.float32)
    transform = from_origin(500000, 3000000, 10, 10)
    crs = CRS.from_epsg(32633)

    result = refine_change_with_sam2(
        change_result=no_change_result,
        t2_raster=dummy_image,
        transform=transform,
        crs=crs,
    )

    assert result["segmentation_detected"] is False
    assert result["status"] == "skipped"
    assert "skipped" in result["message"]
