"""Quantification module for Geo Evidence Engine.

Computes change metrics including pixel counts, area in hectares, and percentage change.
Never assumes a fixed 10m x 10m pixel size; dynamically computes pixel dimensions from
georeferencing/transform and CRS. Accurately handles geographic CRS (degrees) by
reprojecting to an appropriate metric projection (UTM) prior to area calculation.
"""

from typing import Any, Dict, Optional, Tuple
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, array_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject


def determine_utm_crs_from_bounds(
    left: float,
    bottom: float,
    right: float,
    top: float,
) -> CRS:
    """Determine the appropriate UTM metric CRS from geographic bounding coordinates (WGS84 lon/lat).

    Args:
        left: Westernmost longitude in degrees.
        bottom: Southernmost latitude in degrees.
        right: Easternmost longitude in degrees.
        top: Northernmost latitude in degrees.

    Returns:
        CRS: UTM Coordinate Reference System.
    """
    lon_center = (left + right) / 2.0
    lat_center = (bottom + top) / 2.0

    utm_zone = int((lon_center + 180) / 6.0) + 1
    utm_zone = max(1, min(60, utm_zone))

    epsg = 32600 + utm_zone if lat_center >= 0 else 32700 + utm_zone
    return CRS.from_epsg(epsg)


def get_pixel_area_projected(transform: Affine, crs: CRS) -> Tuple[float, float, float]:
    """Calculate pixel dimensions and area in square meters for a projected CRS.

    Args:
        transform: Affine transform of the raster.
        crs: Projected Coordinate Reference System.

    Returns:
        Tuple[float, float, float]: (pixel_width_m, pixel_height_m, pixel_area_m2)
    """
    # Linear unit conversion factor (e.g. 1.0 for metres, 0.3048 for feet)
    linear_factor = 1.0
    if hasattr(crs, "linear_units_factor") and crs.linear_units_factor:
        try:
            linear_factor = float(crs.linear_units_factor[1])
        except (IndexError, TypeError, ValueError):
            linear_factor = 1.0

    # Determinant of 2x2 affine matrix gives exact area of a pixel parallelogram
    det = abs(transform.a * transform.e - transform.b * transform.d)
    pixel_area_m2 = det * (linear_factor**2)

    pixel_width_m = np.hypot(transform.a, transform.b) * linear_factor
    pixel_height_m = np.hypot(transform.d, transform.e) * linear_factor

    return pixel_width_m, pixel_height_m, pixel_area_m2


def reproject_mask_to_metric(
    mask: np.ndarray,
    transform: Affine,
    src_crs: CRS,
    target_metric_crs: Optional[CRS] = None,
) -> Tuple[np.ndarray, Affine, CRS, float]:
    """Reproject a geographic (lat/lon) binary mask into a metric projection (UTM).

    Args:
        mask: 2D binary numpy array.
        transform: Geographic Affine transform.
        src_crs: Source geographic CRS (e.g., EPSG:4326).
        target_metric_crs: Optional target metric CRS. Auto-derived if None.

    Returns:
        Tuple[np.ndarray, Affine, CRS, float]:
            - Reprojected binary mask
            - Destination Affine transform
            - Destination metric CRS
            - Metric pixel area in square meters
    """
    height, width = mask.shape
    left, bottom, right, top = array_bounds(height, width, transform)

    if target_metric_crs is None:
        target_metric_crs = determine_utm_crs_from_bounds(left, bottom, right, top)

    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs,
        target_metric_crs,
        width,
        height,
        left=left,
        bottom=bottom,
        right=right,
        top=top,
    )

    dst_mask = np.zeros((dst_h, dst_w), dtype=np.uint8)
    reproject(
        source=mask,
        destination=dst_mask,
        src_transform=transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=target_metric_crs,
        resampling=Resampling.nearest,
    )

    metric_pixel_area_m2 = abs(
        dst_transform.a * dst_transform.e - dst_transform.b * dst_transform.d
    )

    return dst_mask, dst_transform, target_metric_crs, metric_pixel_area_m2


def calculate_change_metrics(
    mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    valid_mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Calculate deterministic change metrics from a binary change mask.

    Computes:
        - changed_pixels: Total number of changed pixels (mask == 1)
        - changed_area_ha: Total changed area in hectares
        - change_percent: Percentage of valid pixels that changed
        - pixel_area_m2: Area of a single pixel in square meters
        - pixel_area_ha: Area of a single pixel in hectares

    Args:
        mask: 2D binary mask array (0=unchanged, 1=changed).
        transform: Raster Affine transform.
        crs: Raster Coordinate Reference System.
        valid_mask: Optional boolean mask of valid (non-nodata) pixels.

    Returns:
        Dict[str, Any]: Quantification results dictionary.
    """
    if crs is None:
        raise ValueError("CRS is required to calculate geographic/metric area.")

    changed_pixels = int(np.count_nonzero(mask == 1))

    if valid_mask is not None:
        total_pixels = int(np.count_nonzero(valid_mask))
    else:
        total_pixels = int(mask.size)

    change_percent = (
        (changed_pixels / total_pixels * 100.0) if total_pixels > 0 else 0.0
    )

    is_geographic = getattr(crs, "is_geographic", False)

    if is_geographic:
        # DO NOT treat degrees as meters! Reproject to metric UTM CRS.
        (
            dst_mask,
            dst_transform,
            dst_crs,
            metric_pixel_area_m2,
        ) = reproject_mask_to_metric(mask, transform, crs)

        reprojected_changed_pixels = int(np.count_nonzero(dst_mask == 1))
        changed_area_m2 = reprojected_changed_pixels * metric_pixel_area_m2
        changed_area_ha = changed_area_m2 / 10000.0

        # Effective pixel area in source raster
        pixel_area_m2 = (
            (changed_area_m2 / changed_pixels)
            if changed_pixels > 0
            else metric_pixel_area_m2
        )
        pixel_area_ha = pixel_area_m2 / 10000.0
        used_crs_str = dst_crs.to_string()
    else:
        # Projected CRS with metric linear units
        _, _, pixel_area_m2 = get_pixel_area_projected(transform, crs)
        pixel_area_ha = pixel_area_m2 / 10000.0
        changed_area_m2 = changed_pixels * pixel_area_m2
        changed_area_ha = changed_area_m2 / 10000.0
        used_crs_str = crs.to_string()

    return {
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "changed_area_ha": round(changed_area_ha, 4),
        "changed_area_m2": round(changed_area_m2, 2),
        "change_percent": round(change_percent, 2),
        "pixel_area_m2": round(pixel_area_m2, 4),
        "pixel_area_ha": round(pixel_area_ha, 6),
        "is_geographic": is_geographic,
        "crs_used": used_crs_str,
    }
