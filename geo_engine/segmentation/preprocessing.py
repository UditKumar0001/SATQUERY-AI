"""Preprocessing module for SAM 2 segmentation in Geo Evidence Engine.

Prepares satellite imagery for SAM 2 consumption:
- Supports multispectral, panchromatic, and standard RGB rasters without assuming RGB.
- Performs safe contrast normalization (percentile stretching) without modifying original rasters.
- Extracts candidate changed regions from binary change masks as bounding boxes and centroids.
- Maps image/pixel coordinates back to georeferenced coordinates.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

from geo_engine.indices import extract_bands_from_raster


def prepare_satellite_image_for_sam(
    raster: np.ndarray,
    band_mapping: Optional[Dict[str, int]] = None,
    rgb_bands: Tuple[str, str, str] = ("red", "green", "blue"),
    clip_percentiles: Tuple[float, float] = (2.0, 98.0),
) -> np.ndarray:
    """Convert satellite raster array into 3-channel uint8 RGB format required by SAM 2.

    Safely normalizes pixel intensities using percentile contrast stretching.
    Does NOT modify the original raster array.

    Args:
        raster: 2D or 3D numpy array representing the satellite image.
        band_mapping: Optional dictionary mapping band names to indices (e.g. {'red': 1, 'green': 2, ...}).
        rgb_bands: Tuple of band names to use for (R, G, B) composite.
        clip_percentiles: Lower and upper percentiles for dynamic range contrast stretching.

    Returns:
        np.ndarray: 3-channel uint8 array of shape (height, width, 3) suitable for SAM 2.
    """
    if raster.ndim == 2:
        # Single-band (panchromatic / SAR amplitude / single index)
        # Shape: (H, W) -> replicate to (H, W, 3)
        channels = [raster, raster, raster]

    elif raster.ndim == 3:
        num_bands = raster.shape[0]

        if band_mapping is not None:
            # Extract requested RGB bands using configurable mapping
            extracted = extract_bands_from_raster(raster, band_mapping)
            r_band, g_band, b_band = rgb_bands
            if r_band in extracted and g_band in extracted and b_band in extracted:
                channels = [extracted[r_band], extracted[g_band], extracted[b_band]]
            else:
                # Fallback to first available bands
                avail = list(extracted.values())
                channels = [avail[0], avail[min(1, len(avail) - 1)], avail[min(2, len(avail) - 1)]]
        elif num_bands == 3:
            # Standard 3-channel raster: (3, H, W)
            channels = [raster[0], raster[1], raster[2]]
        elif num_bands == 1:
            channels = [raster[0], raster[0], raster[0]]
        elif num_bands >= 4:
            # Multispectral without mapping: default to Sentinel-2/Landsat typical RGB bands (e.g. bands 1, 2, 3 or 3, 2, 1)
            # Default to first 3 bands as conservative fallback
            channels = [raster[0], raster[1], raster[2]]
        else:
            raise ValueError(f"Unexpected raster channel count: {num_bands}")
    else:
        raise ValueError(f"Expected 2D or 3D raster array, got ndim={raster.ndim}")

    # Stack into (H, W, 3) float32 array
    rgb_float = np.stack(channels, axis=-1).astype(np.float32, copy=True)

    # Normalize each channel safely using robust percentile clipping
    rgb_uint8 = np.zeros(rgb_float.shape, dtype=np.uint8)

    for c in range(3):
        channel_data = rgb_float[:, :, c]
        finite_mask = np.isfinite(channel_data)

        if not np.any(finite_mask):
            rgb_uint8[:, :, c] = 0
            continue

        valid_vals = channel_data[finite_mask]
        p_low, p_high = np.percentile(valid_vals, clip_percentiles)

        if p_high > p_low:
            scaled = (channel_data - p_low) / (p_high - p_low) * 255.0
            rgb_uint8[:, :, c] = np.clip(scaled, 0, 255).astype(np.uint8)
        else:
            rgb_uint8[:, :, c] = np.zeros_like(channel_data, dtype=np.uint8)

    return rgb_uint8


def extract_candidate_regions(
    change_mask: np.ndarray,
    min_area_pixels: int = 4,
    max_candidates: int = 50,
    padding: int = 4,
) -> List[Dict[str, Any]]:
    """Extract candidate changed regions from a binary change mask for targeted SAM 2 prompting.

    Finds connected components of changed pixels (value=1). For each valid component,
    computes bounding boxes (with optional padding) and centroids in pixel coordinates.

    Args:
        change_mask: 2D binary numpy array (0=unchanged, 1=changed).
        min_area_pixels: Minimum pixel area required to consider a candidate change region.
        max_candidates: Maximum number of candidate regions to return (prioritized by area).
        padding: Pixel padding to add around candidate bounding box.

    Returns:
        List[Dict[str, Any]]: List of candidate dictionaries:
            [
                {
                    "candidate_id": 1,
                    "bbox": [x_min, y_min, x_max, y_max],  # pixel coordinates
                    "centroid": [cx, cy],                   # pixel coordinates [x, y]
                    "area_pixels": 25,
                    "crop_slice": (slice_y, slice_x),
                },
                ...
            ]
    """
    if change_mask.ndim != 2:
        raise ValueError(f"Expected 2D binary change mask, got ndim={change_mask.ndim}")

    height, width = change_mask.shape
    binary = (change_mask > 0).astype(np.uint8)

    if not np.any(binary):
        return []

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    candidates: List[Dict[str, Any]] = []

    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area < min_area_pixels:
            continue

        x = int(stats[label_idx, cv2.CC_STAT_LEFT])
        y = int(stats[label_idx, cv2.CC_STAT_TOP])
        w = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        h = int(stats[label_idx, cv2.CC_STAT_HEIGHT])

        # Apply padding clamped to raster boundary
        x_min = max(0, x - padding)
        y_min = max(0, y - padding)
        x_max = min(width - 1, x + w - 1 + padding)
        y_max = min(height - 1, y + h - 1 + padding)

        cx = float(centroids[label_idx][0])
        cy = float(centroids[label_idx][1])

        candidates.append({
            "candidate_id": len(candidates) + 1,
            "label_idx": label_idx,
            "area_pixels": area,
            "bbox": [x_min, y_min, x_max, y_max],
            "centroid": [cx, cy],
            "crop_slice": (slice(y_min, y_max + 1), slice(x_min, x_max + 1)),
        })

    # Sort candidates by area descending (largest change regions first)
    candidates.sort(key=lambda c: c["area_pixels"], reverse=True)

    # Limit to top max_candidates
    return candidates[:max_candidates]


def pixel_to_geo_bbox(
    pixel_bbox: List[int],
    transform: Affine,
) -> List[float]:
    """Convert a bounding box from pixel coordinates to geospatial coordinates.

    Args:
        pixel_bbox: [x_min, y_min, x_max, y_max] in image pixel coordinates.
        transform: Affine geotransform matrix.

    Returns:
        List[float]: [geo_x_min, geo_y_min, geo_x_max, geo_y_max] in native geospatial coordinates.
    """
    x_min, y_min, x_max, y_max = pixel_bbox

    # Upper-left coordinate of (x_min, y_min)
    top_left_x, top_left_y = rasterio.transform.xy(transform, y_min, x_min, offset="ul")
    # Lower-right coordinate of (x_max, y_max)
    bottom_right_x, bottom_right_y = rasterio.transform.xy(transform, y_max, x_max, offset="lr")

    geo_x_min = min(top_left_x, bottom_right_x)
    geo_x_max = max(top_left_x, bottom_right_x)
    geo_y_min = min(top_left_y, bottom_right_y)
    geo_y_max = max(top_left_y, bottom_right_y)

    return [geo_x_min, geo_y_min, geo_x_max, geo_y_max]
