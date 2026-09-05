# orchestrator/metadata.py
import os
from PIL import Image, ExifTags

try:
    import rasterio
except ImportError:
    rasterio = None


def extract_metadata(filepath: str) -> dict:
    """Extract raster metadata: bands, crs, bounds, driver format, acquisition timestamp, and modality.
    Returns structured error dict if file is empty or corrupted.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        return {
            "error": f"File is empty (0 bytes): {os.path.basename(filepath)}",
            "corrupted": True,
            "bands": 0,
            "crs": None,
            "bounds": None,
            "format": "EMPTY",
            "timestamp": None,
            "modality": "invalid",
            "filepath": filepath
        }

    bands = 1
    crs = None
    bounds = None
    driver = "UNKNOWN"
    timestamp = None
    opened_successfully = False
    width = None
    height_px = None
    transform_list = None
    resolution = None
    center_latlon = None
    bounds_latlon = None

    if rasterio is not None:
        try:
            with rasterio.open(filepath) as src:
                bands = src.count
                crs = str(src.crs) if src.crs else None
                bounds = tuple(src.bounds) if src.bounds else None
                driver = src.driver
                tags = src.tags()
                timestamp = (
                    tags.get("TIFFTAG_DATETIME")
                    or tags.get("acquisition_date")
                    or tags.get("DATETIME")
                )
                width = src.width
                height_px = src.height
                transform_list = list(src.transform)[:6] if src.transform else None
                resolution = abs(float(src.transform.a)) if src.transform else None
                if src.crs and src.bounds:
                    try:
                        from rasterio.crs import CRS as _CRS
                        from rasterio.warp import transform as _warp_transform
                        _wgs84 = _CRS.from_epsg(4326)
                        if src.crs.is_geographic:
                            _cx = (src.bounds.left + src.bounds.right) / 2.0
                            _cy = (src.bounds.bottom + src.bounds.top) / 2.0
                            center_latlon = [round(_cy, 6), round(_cx, 6)]
                            bounds_latlon = [
                                round(src.bounds.left, 6),
                                round(src.bounds.bottom, 6),
                                round(src.bounds.right, 6),
                                round(src.bounds.top, 6),
                            ]
                        else:
                            _xs, _ys = _warp_transform(
                                src.crs, _wgs84,
                                [src.bounds.left, src.bounds.right],
                                [src.bounds.bottom, src.bounds.top],
                            )
                            bounds_latlon = [
                                round(min(_xs), 6),
                                round(min(_ys), 6),
                                round(max(_xs), 6),
                                round(max(_ys), 6),
                            ]
                            center_latlon = [
                                round((min(_ys) + max(_ys)) / 2.0, 6),
                                round((min(_xs) + max(_xs)) / 2.0, 6),
                            ]
                    except Exception:
                        pass
                opened_successfully = True
        except Exception:
            opened_successfully = False

    if not opened_successfully:
        # Resilient fallback via PIL
        try:
            with Image.open(filepath) as img:
                img.verify()
            with Image.open(filepath) as img:
                driver = img.format or "UNKNOWN"
                bands = len(img.getbands()) if hasattr(img, "getbands") else 1
                exif = img.getexif() if hasattr(img, "getexif") else None
                if exif:
                    for tag_id, val in exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        if "Date" in str(tag_name) or "Time" in str(tag_name):
                            timestamp = str(val)
                            break
            opened_successfully = True
        except Exception as e:
            return {
                "error": f"Corrupted or unsupported image file: {os.path.basename(filepath)} ({str(e)})",
                "corrupted": True,
                "bands": 0,
                "crs": None,
                "bounds": None,
                "format": "CORRUPTED",
                "timestamp": None,
                "modality": "invalid",
                "filepath": filepath
            }

    if not opened_successfully:
        return {
            "error": f"Unable to decode image file: {os.path.basename(filepath)}",
            "corrupted": True,
            "bands": 0,
            "crs": None,
            "bounds": None,
            "format": "CORRUPTED",
            "timestamp": None,
            "modality": "invalid",
            "filepath": filepath
        }

    # Modality heuristic: 1 or 2 bands -> SAR (VV/VH); 3 or more -> optical (RGB/multispectral)
    filename = os.path.basename(filepath).lower()
    if "_sar" in filename or "s1" in filename:
        modality = "SAR"
    elif "_optical" in filename or "s2" in filename:
        modality = "optical"
    elif bands in (1, 2):
        modality = "SAR"
    elif bands >= 3:
        modality = "optical"
    else:
        modality = "unknown"

    return {
        "bands": bands,
        "crs": crs,
        "bounds": bounds,
        "format": driver,
        "timestamp": timestamp,
        "modality": modality,
        "filepath": filepath,
        "width": width,
        "height": height_px,
        "transform": transform_list,
        "resolution": resolution,
        "center_latlon": center_latlon,
        "bounds_latlon": bounds_latlon,
    }
