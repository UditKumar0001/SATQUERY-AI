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
        "filepath": filepath
    }
