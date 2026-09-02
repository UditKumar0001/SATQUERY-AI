# orchestrator/metadata.py
import os
from PIL import Image, ExifTags
import rasterio


def extract_metadata(filepath: str) -> dict:
    """Extract raster metadata: bands, crs, bounds, driver format, acquisition timestamp, and modality."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    bands = 1
    crs = None
    bounds = None
    driver = "UNKNOWN"
    timestamp = None

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
    except Exception:
        # Resilient fallback via PIL
        try:
            with Image.open(filepath) as img:
                driver = img.format or "UNKNOWN"
                bands = len(img.getbands()) if hasattr(img, "getbands") else 1
                # Try EXIF tags for timestamp
                exif = img.getexif() if hasattr(img, "getexif") else None
                if exif:
                    for tag_id, val in exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        if "Date" in str(tag_name) or "Time" in str(tag_name):
                            timestamp = str(val)
                            break
        except Exception:
            pass

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
