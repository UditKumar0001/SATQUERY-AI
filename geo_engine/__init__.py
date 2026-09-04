"""Geo Evidence Engine - Deterministic geospatial analysis module for SatQuery AI.

Provides modular, deterministic tools for spectral index calculation, bi-temporal
change detection, spatial quantification, mask filtering, and GeoJSON vectorization.
"""

import os
import tempfile
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import rasterio

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
    bbox_to_geojson,
)


def run_change_detection_pipeline(
    t1_path: str,
    t2_path: str,
    index: str = "ndvi",
    band_mapping: Optional[Dict[str, int]] = None,
    threshold: float = 0.2,
    direction: str = "auto",
    min_patch_size: int = 3,
    morphology_op: str = "opening",
    kernel_size: int = 3,
    output_dir: Optional[str] = None,
    overlay_color: Tuple[int, int, int] = (255, 0, 0),
    overlay_alpha: float = 0.45,
) -> Dict[str, Any]:
    """Execute end-to-end deterministic Geo Evidence Engine pipeline on two GeoTIFFs.

    Args:
        t1_path: Path to earlier GeoTIFF image (T1).
        t2_path: Path to later GeoTIFF image (T2).
        index: Spectral index ('ndvi', 'ndwi', 'ndbi').
        band_mapping: Mapping of band name to index (e.g. {'red': 1, 'green': 2, 'nir': 4, 'swir': 5}).
        threshold: Spectral difference threshold.
        direction: Change direction ('auto', 'increase', 'decrease', 'both').
        min_patch_size: Minimum pixel area for connected change clusters.
        morphology_op: Morphological cleanup operation ('opening', 'closing', 'open_close', 'none').
        kernel_size: Morphological kernel size.
        output_dir: Directory to save generated GeoTIFF mask and overlay.
        overlay_color: RGB tuple for change highlight color.
        overlay_alpha: Transparency factor for overlay.

    Returns:
        Dict[str, Any]: Structured result matching standard Geo Evidence Engine schema:
            {
                "change_detected": bool,
                "change_type": str,
                "changed_pixels": int,
                "changed_area_ha": float,
                "change_percent": float,
                "mask_path": str,
                "overlay_path": str,
                "geojson": dict,
                "evidence_type": "spectral_difference"
            }
    """
    with rasterio.open(t1_path) as ds_t1, rasterio.open(t2_path) as ds_t2:
        # 1. Compatibility verification
        validate_raster_compatibility(ds_t1, ds_t2)

        # Default band mapping if unspecified
        if band_mapping is None:
            band_mapping = {"red": 1, "green": 2, "blue": 3, "nir": 4, "swir": 5}

        # 2. Extract bands
        arr_t1 = ds_t1.read()
        arr_t2 = ds_t2.read()
        bands_t1 = extract_bands_from_raster(arr_t1, band_mapping)
        bands_t2 = extract_bands_from_raster(arr_t2, band_mapping)

        # 3. Compute spectral indices
        idx_t1 = calculate_index(index, bands_t1, nodata=ds_t1.nodata)
        idx_t2 = calculate_index(index, bands_t2, nodata=ds_t2.nodata)

        # 4. Spectral difference: T2 - T1
        diff = calculate_spectral_difference(idx_t1, idx_t2)

        # 5. Generate raw binary change mask
        raw_direction = direction if direction != "auto" else "both"
        raw_mask = generate_change_mask(diff, threshold=threshold, direction=raw_direction)

        # 6. Classify change type
        change_type = classify_change_type(
            index_name=index,
            direction=direction,
            difference=diff,
            mask=raw_mask,
        )

        # 7. Clean mask deterministically
        cleaned_mask = clean_binary_mask(
            raw_mask,
            min_patch_size=min_patch_size,
            kernel_size=kernel_size,
            morphology_op=morphology_op,
        )

        # 8. Quantification
        metrics = calculate_change_metrics(cleaned_mask, ds_t1.transform, ds_t1.crs)

        # 9. GeoJSON generation
        geojson_data = mask_to_geojson(
            cleaned_mask,
            ds_t1.transform,
            ds_t1.crs,
            to_wgs84=True,
            properties={"change_type": change_type, "index": index},
        )

        # 10. File persistence (mask & overlay)
        target_dir = output_dir if output_dir else tempfile.mkdtemp(prefix="geo_engine_")
        os.makedirs(target_dir, exist_ok=True)

        mask_filename = f"change_mask_{index}.tif"
        mask_path = os.path.join(target_dir, mask_filename)
        save_mask_to_geotiff(
            cleaned_mask,
            mask_path,
            ds_t1.transform,
            ds_t1.crs,
            metadata={
                "INDEX": index,
                "THRESHOLD": threshold,
                "CHANGE_TYPE": change_type,
            },
        )

        # Read RGB background for visual overlay if possible
        bg = None
        if "red" in bands_t2 and "green" in bands_t2 and "blue" in bands_t2:
            bg = np.stack([bands_t2["red"], bands_t2["green"], bands_t2["blue"]], axis=-1)
        elif arr_t2.shape[0] >= 3:
            bg = np.transpose(arr_t2[:3], (1, 2, 0))

        overlay_filename = f"change_overlay_{index}.png"
        overlay_path = os.path.join(target_dir, overlay_filename)
        create_overlay(
            cleaned_mask,
            background=bg,
            color=overlay_color,
            alpha=overlay_alpha,
            output_path=overlay_path,
        )

        change_detected = bool(metrics["changed_pixels"] > 0)

        return {
            "change_detected": change_detected,
            "change_type": change_type,
            "changed_pixels": metrics["changed_pixels"],
            "changed_area_ha": metrics["changed_area_ha"],
            "change_percent": metrics["change_percent"],
            "mask_path": mask_path,
            "overlay_path": overlay_path,
            "geojson": geojson_data,
            "evidence_type": "spectral_difference",
        }


__all__ = [
    # Indices
    "calculate_normalized_difference",
    "calculate_ndvi",
    "calculate_ndwi",
    "calculate_ndbi",
    "calculate_index",
    "extract_bands_from_raster",
    # Change detection
    "IncompatibleRastersError",
    "validate_raster_compatibility",
    "calculate_spectral_difference",
    "generate_change_mask",
    "classify_change_type",
    "detect_spectral_change",
    # Quantification
    "determine_utm_crs_from_bounds",
    "get_pixel_area_projected",
    "reproject_mask_to_metric",
    "calculate_change_metrics",
    # Mask
    "clean_binary_mask",
    "save_mask_to_geotiff",
    # Spatial
    "mask_to_polygons",
    "mask_to_geojson",
    "create_overlay",
    "bbox_to_geojson",
    # Pipeline
    "run_change_detection_pipeline",
]
