"""Spatial vectorization and overlay generation module for Geo Evidence Engine.

Converts cleaned change masks into valid GeoJSON geometries (preserving CRS or
transforming to standard WGS84 GeoJSON), and generates georeferenced or visual
overlays for displaying on top of satellite imagery.
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import rasterio
from rasterio.crs import CRS
from rasterio.features import shapes
from rasterio.transform import Affine
from rasterio.warp import transform_geom


def mask_to_polygons(
    mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    to_wgs84: bool = False,
) -> List[Dict[str, Any]]:
    """Convert contiguous change mask regions (value=1) into GeoJSON polygon geometries.

    Args:
        mask: 2D binary numpy array (0=unchanged, 1=changed).
        transform: Affine geotransform.
        crs: Coordinate Reference System.
        to_wgs84: If True, transforms coordinates to EPSG:4326 (WGS84).
                  If False, retains coordinates in the native raster CRS.

    Returns:
        List[Dict[str, Any]]: List of GeoJSON geometry dictionaries.
    """
    if mask.ndim != 2:
        raise ValueError(f"Expected 2D binary mask, got ndim={mask.ndim}")

    wgs84_crs = CRS.from_epsg(4326)
    need_reproject = to_wgs84 and (crs != wgs84_crs)

    polygon_geoms: List[Dict[str, Any]] = []

    # Extract polygon shapes from binary mask where mask == 1
    shapes_generator = shapes(
        mask.astype(np.uint8),
        mask=(mask == 1),
        transform=transform,
        connectivity=8,
    )

    for geom, value in shapes_generator:
        if value != 1:
            continue
        if need_reproject:
            geom = transform_geom(crs, wgs84_crs, geom)
        polygon_geoms.append(geom)

    return polygon_geoms


def mask_to_geojson(
    mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    to_wgs84: bool = True,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert binary change mask into a GeoJSON FeatureCollection.

    Args:
        mask: 2D binary numpy array (0=unchanged, 1=changed).
        transform: Affine geotransform matrix.
        crs: Coordinate Reference System.
        to_wgs84: If True, projects coordinates to standard WGS84 (EPSG:4326).
        properties: Optional common properties dictionary added to each feature.

    Returns:
        Dict[str, Any]: GeoJSON FeatureCollection dictionary.
    """
    polygons = mask_to_polygons(mask, transform, crs, to_wgs84=to_wgs84)

    features: List[Dict[str, Any]] = []
    for idx, poly in enumerate(polygons):
        feat_props = {
            "feature_id": idx + 1,
            "change_detected": True,
        }
        if properties:
            feat_props.update(properties)

        features.append({
            "type": "Feature",
            "id": idx + 1,
            "geometry": poly,
            "properties": feat_props,
        })

    crs_name = "urn:ogc:def:crs:OGC:1.3:CRS84" if to_wgs84 else crs.to_string()
    geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": crs_name},
        },
        "features": features,
    }

    return geojson


def create_overlay(
    mask: np.ndarray,
    background: Optional[np.ndarray] = None,
    color: Tuple[int, int, int] = (255, 0, 0),
    alpha: float = 0.45,
    output_path: Optional[str] = None,
    transform: Optional[Affine] = None,
    crs: Optional[CRS] = None,
) -> np.ndarray:
    """Generate a visual overlay suitable for displaying on top of satellite imagery.

    If background is provided, creates an RGB image with change regions highlighted.
    If background is None, creates a transparent RGBA image with colored change pixels.

    Args:
        mask: 2D binary numpy array (0=unchanged, 1=changed).
        background: Optional 2D or 3D numpy array representing the satellite image (RGB).
        color: RGB color tuple for highlighting changes, e.g. (255, 0, 0) for red.
        alpha: Blending transparency (0.0=fully transparent, 1.0=fully opaque).
        output_path: Optional filepath to save the overlay (PNG or GeoTIFF).
        transform: Optional Affine geotransform (for GeoTIFF export).
        crs: Optional Coordinate Reference System (for GeoTIFF export).

    Returns:
        np.ndarray: Overlay image array (RGB or RGBA uint8).
    """
    height, width = mask.shape
    change_idx = (mask == 1)

    if background is not None:
        # Normalize background array to (H, W, 3) uint8
        bg = background.copy()
        if bg.ndim == 2:
            bg = np.stack([bg, bg, bg], axis=-1)
        elif bg.ndim == 3:
            if bg.shape[0] in (1, 3, 4) and bg.shape[-1] not in (1, 3, 4):
                # (C, H, W) -> (H, W, C)
                bg = np.transpose(bg, (1, 2, 0))
            if bg.shape[-1] == 1:
                bg = np.repeat(bg, 3, axis=-1)
            elif bg.shape[-1] > 3:
                bg = bg[:, :, :3]

        if bg.dtype != np.uint8:
            bg_min, bg_max = float(np.nanmin(bg)), float(np.nanmax(bg))
            if bg_max > bg_min:
                bg = np.clip((bg - bg_min) / (bg_max - bg_min) * 255.0, 0, 255).astype(np.uint8)
            else:
                bg = np.zeros_like(bg, dtype=np.uint8)

        # Blend change color onto background
        overlay = bg.astype(np.float32)
        color_arr = np.array(color, dtype=np.float32)

        overlay[change_idx] = (1.0 - alpha) * overlay[change_idx] + alpha * color_arr
        result_img = np.clip(overlay, 0, 255).astype(np.uint8)

    else:
        # Transparent RGBA overlay
        result_img = np.zeros((height, width, 4), dtype=np.uint8)
        result_img[change_idx, 0] = color[0]
        result_img[change_idx, 1] = color[1]
        result_img[change_idx, 2] = color[2]
        result_img[change_idx, 3] = int(np.clip(alpha * 255.0, 0, 255))

    # Save to file if output_path requested
    if output_path:
        abs_output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
        ext = os.path.splitext(abs_output_path)[1].lower()

        if ext in (".tif", ".tiff") and transform is not None and crs is not None:
            channels = result_img.shape[2] if result_img.ndim == 3 else 1
            with rasterio.open(
                abs_output_path,
                "w",
                driver="GTiff",
                height=height,
                width=width,
                count=channels,
                dtype=rasterio.uint8,
                crs=crs,
                transform=transform,
                compress="deflate",
            ) as dst:
                for c in range(channels):
                    dst.write(result_img[:, :, c], c + 1)
        else:
            pil_img = Image.fromarray(result_img)
            pil_img.save(abs_output_path)

    return result_img


def bbox_to_geojson(
    bbox: Any = None,
    transform: Optional[Affine] = None,
    crs: Optional[CRS] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    image_path: Optional[str] = None,
    label: Optional[str] = None,
    model: str = "GeoChat",
    source: Optional[str] = None,
    to_wgs84: bool = True,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """Convert a normalized bounding box [ymin, xmin, ymax, xmax] into a GeoJSON FeatureCollection.

    If transform and crs are provided, converts pixel coordinates to geographic coordinates.
    If image_path is provided, extracts transform, crs, width, height from the raster.
    If the image lacks spatial georeferencing (CRS/transform), returns None (adheres to Rule 6).

    Args:
        bbox: Normalized coordinates [ymin, xmin, ymax, xmax] in [0.0, 1.0].
        transform: Affine geotransform matrix.
        crs: Coordinate Reference System.
        width: Image width in pixels.
        height: Image height in pixels.
        image_path: Path to georeferenced raster file.
        label: Target object label (e.g. "Airport Terminal", "Runway").
        model: Model name that produced the detection (default "GeoChat").
        source: Optional alias for model source.
        to_wgs84: If True, reprojects coordinates to EPSG:4326 (WGS84).

    Returns:
        Optional[Dict[str, Any]]: GeoJSON FeatureCollection dictionary, or None if not georeferenced.
    """
    if source:
        model = source

    if isinstance(bbox, str):
        # Called as bbox_to_geojson(image_path, bbox, ...)
        image_path, bbox = bbox, transform
        transform = None

    if not bbox or len(bbox) < 4:
        return None

    if image_path and (transform is None or crs is None or width is None or height is None):
        try:
            with rasterio.open(image_path) as src:
                if crs is None and src.crs:
                    crs = src.crs
                if transform is None and src.transform:
                    transform = src.transform
                if width is None:
                    width = src.width
                if height is None:
                    height = src.height
        except Exception:
            pass

    if crs is None or transform is None or width is None or height is None:
        return None

    ymin, xmin, ymax, xmax = [float(c) for c in bbox[:4]]
    ymin = max(0.0, min(1.0, ymin))
    xmin = max(0.0, min(1.0, xmin))
    ymax = max(0.0, min(1.0, ymax))
    xmax = max(0.0, min(1.0, xmax))

    px_y1 = ymin * height
    px_x1 = xmin * width
    px_y2 = ymax * height
    px_x2 = xmax * width

    # 4 corners in native coordinates using exact continuous coordinates (offset="ul")
    ul_x, ul_y = rasterio.transform.xy(transform, px_y1, px_x1, offset="ul")
    ur_x, ur_y = rasterio.transform.xy(transform, px_y1, px_x2, offset="ul")
    lr_x, lr_y = rasterio.transform.xy(transform, px_y2, px_x2, offset="ul")
    ll_x, ll_y = rasterio.transform.xy(transform, px_y2, px_x1, offset="ul")

    # Calculate physical area in hectares
    area_ha = None
    try:
        if crs.is_projected:
            w_m = float(np.hypot(ur_x - ul_x, ur_y - ul_y))
            h_m = float(np.hypot(ll_x - ul_x, ll_y - ul_y))
            area_ha = round((w_m * h_m) / 10000.0, 3)
        else:
            from geo_engine.quantification import determine_utm_crs_from_bounds
            utm_crs = determine_utm_crs_from_bounds((min(ul_x, lr_x), min(ul_y, lr_y), max(ul_x, lr_x), max(ul_y, lr_y)))
            from rasterio.warp import transform as warp_transform
            xs, ys = warp_transform(crs, utm_crs, [ul_x, ur_x, lr_x, ll_x], [ul_y, ur_y, lr_y, ll_y])
            w_m = float(np.hypot(xs[1] - xs[0], ys[1] - ys[0]))
            h_m = float(np.hypot(xs[3] - xs[0], ys[3] - ys[0]))
            area_ha = round((w_m * h_m) / 10000.0, 3)
    except Exception:
        pass

    raw_polygon = {
        "type": "Polygon",
        "coordinates": [[[ul_x, ul_y], [ur_x, ur_y], [lr_x, lr_y], [ll_x, ll_y], [ul_x, ul_y]]]
    }

    wgs84_crs = CRS.from_epsg(4326)
    need_reproject = to_wgs84 and (crs != wgs84_crs)
    if need_reproject:
        try:
            poly_geom = transform_geom(crs, wgs84_crs, raw_polygon)
        except Exception:
            poly_geom = raw_polygon
    else:
        poly_geom = raw_polygon

    feature = {
        "type": "Feature",
        "id": 1,
        "geometry": poly_geom,
        "properties": {
            "feature_id": 1,
            "layer_type": "grounding",
            "label": label or "Target Object",
            "model": model,
            "source": model,
            "bbox_normalized": [round(c, 4) for c in [ymin, xmin, ymax, xmax]],
            "area_ha": area_ha,
        }
    }

    crs_name = "urn:ogc:def:crs:OGC:1.3:CRS84" if to_wgs84 else crs.to_string()
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": crs_name}},
        "features": [feature]
    }
