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
