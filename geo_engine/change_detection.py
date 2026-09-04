"""Change detection module for Geo Evidence Engine.

Provides raster compatibility validation, bi-temporal spectral difference calculation,
configurable thresholding, binary change mask generation, and deterministic change classification.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.io import DatasetReader

from geo_engine.indices import calculate_index, extract_bands_from_raster


class IncompatibleRastersError(ValueError):
    """Raised when bi-temporal rasters (T1 and T2) are incompatible for change detection."""
    pass


def validate_raster_compatibility(
    t1: DatasetReader,
    t2: DatasetReader,
    required_bands: Optional[int] = None,
    rtol: float = 1e-4,
    atol: float = 1e-4,
) -> Dict[str, Any]:
    """Validate that two bi-temporal rasters are strictly compatible.

    Checks:
        1. CRS (Coordinate Reference System) equivalence.
        2. Raster dimensions (width and height).
        3. Affine transform and georeferencing (pixel resolution, origin).
        4. Sufficient band counts for analysis.

    Args:
        t1: Rasterio dataset reader for earlier image (T1).
        t2: Rasterio dataset reader for later image (T2).
        required_bands: Minimum number of bands required.
        rtol: Relative tolerance for affine transform comparison.
        atol: Absolute tolerance for affine transform comparison.

    Returns:
        Dict[str, Any]: Compatibility metadata summary.

    Raises:
        IncompatibleRastersError: If any compatibility check fails.
    """
    # 1. CRS validation
    if t1.crs is None or t2.crs is None:
        raise IncompatibleRastersError(
            f"Raster CRS missing: T1 CRS={t1.crs}, T2 CRS={t2.crs}. "
            "Both rasters must possess valid geospatial reference systems."
        )
    if t1.crs != t2.crs:
        raise IncompatibleRastersError(
            f"CRS mismatch: T1 has CRS '{t1.crs.to_string()}', "
            f"but T2 has CRS '{t2.crs.to_string()}'. Reprojection is required before comparison."
        )

    # 2. Dimensions validation
    if t1.width != t2.width or t1.height != t2.height:
        raise IncompatibleRastersError(
            f"Dimension mismatch: T1 is {t1.width}x{t1.height} (WxH), "
            f"but T2 is {t2.width}x{t2.height} (WxH)."
        )

    # 3. Transform / Georeferencing validation
    t1_trans = list(t1.transform)[:6]
    t2_trans = list(t2.transform)[:6]
    if not np.allclose(t1_trans, t2_trans, rtol=rtol, atol=atol):
        raise IncompatibleRastersError(
            f"Georeferencing / Transform mismatch:\n"
            f"  T1 transform: {t1.transform}\n"
            f"  T2 transform: {t2.transform}\n"
            f"Rasters do not align spatially."
        )

    # 4. Band count validation
    if required_bands is not None:
        if t1.count < required_bands:
            raise IncompatibleRastersError(
                f"T1 band count insufficient: requires {required_bands}, found {t1.count}."
            )
        if t2.count < required_bands:
            raise IncompatibleRastersError(
                f"T2 band count insufficient: requires {required_bands}, found {t2.count}."
            )

    return {
        "crs": t1.crs,
        "width": t1.width,
        "height": t1.height,
        "transform": t1.transform,
        "t1_bands": t1.count,
        "t2_bands": t2.count,
    }


def calculate_spectral_difference(
    index_t1: np.ndarray,
    index_t2: np.ndarray,
    nodata: float = np.nan,
) -> np.ndarray:
    """Calculate spectral/index difference: difference = index_T2 - index_T1.

    Args:
        index_t1: Earlier spectral index array (T1).
        index_t2: Later spectral index array (T2).
        nodata: Output value for pixels where either T1 or T2 is invalid/nodata.

    Returns:
        np.ndarray: Difference array (index_T2 - index_T1).
    """
    if index_t1.shape != index_t2.shape:
        raise ValueError(
            f"Index shape mismatch: T1 {index_t1.shape} vs T2 {index_t2.shape}"
        )

    t1 = index_t1.astype(np.float32, copy=False)
    t2 = index_t2.astype(np.float32, copy=False)

    diff = np.full(t1.shape, nodata, dtype=np.float32)
    valid_mask = np.isfinite(t1) & np.isfinite(t2)

    diff[valid_mask] = t2[valid_mask] - t1[valid_mask]
    return diff


def generate_change_mask(
    difference: np.ndarray,
    threshold: float = 0.2,
    direction: str = "both",
    min_threshold: Optional[float] = None,
    max_threshold: Optional[float] = None,
) -> np.ndarray:
    """Generate a binary change mask from spectral difference array.

    0 = unchanged
    1 = changed

    Args:
        difference: Spectral difference array (T2 - T1).
        threshold: Absolute difference threshold value.
        direction: 'both' (abs(diff) >= threshold),
                   'increase' (diff >= threshold),
                   'decrease' (diff <= -abs(threshold)),
                   'custom' (uses min_threshold and/or max_threshold).
        min_threshold: Optional lower bound for difference.
        max_threshold: Optional upper bound for difference.

    Returns:
        np.ndarray: Binary change mask of uint8 (0 or 1).
    """
    mask = np.zeros(difference.shape, dtype=np.uint8)
    finite_mask = np.isfinite(difference)

    dir_lower = direction.lower().strip()

    if min_threshold is not None or max_threshold is not None or dir_lower == "custom":
        condition = finite_mask.copy()
        if min_threshold is not None:
            condition &= (difference >= min_threshold)
        if max_threshold is not None:
            condition &= (difference <= max_threshold)
        mask[condition] = 1

    elif dir_lower == "increase":
        mask[finite_mask & (difference >= threshold)] = 1

    elif dir_lower == "decrease":
        mask[finite_mask & (difference <= -abs(threshold))] = 1

    elif dir_lower in ("both", "absolute", "abs"):
        mask[finite_mask & (np.abs(difference) >= abs(threshold))] = 1

    else:
        raise ValueError(
            f"Unsupported direction '{direction}'. Choose 'both', 'increase', 'decrease', or 'custom'."
        )

    return mask


def classify_change_type(
    index_name: str,
    direction: str = "auto",
    difference: Optional[np.ndarray] = None,
    mask: Optional[np.ndarray] = None,
) -> str:
    """Determine the semantic change type from spectral index and change direction.

    Avoids unsupported claims. If evidence only proves spectral change, returns 'spectral_change'.

    Recognized mappings:
        - NDVI:
            - decrease: "vegetation decrease"
            - increase: "vegetation increase"
        - NDWI:
            - increase: "water increase"
            - decrease: "water decrease"
        - NDBI:
            - increase: "built-up spectral increase"
            - decrease: "built-up spectral decrease"
        - Generic: "spectral_change"

    Args:
        index_name: Name of spectral index used.
        direction: 'auto', 'increase', 'decrease', or 'both'.
        difference: Difference array (required if direction='auto').
        mask: Binary change mask (required if direction='auto').

    Returns:
        str: Change classification string.
    """
    idx = index_name.lower().strip() if index_name else ""
    dir_mode = direction.lower().strip()

    resolved_dir = dir_mode
    if dir_mode in ("auto", "both") and difference is not None and mask is not None:
        changed_pixels = (mask == 1) & np.isfinite(difference)
        if np.any(changed_pixels):
            mean_diff = float(np.nanmean(difference[changed_pixels]))
            resolved_dir = "increase" if mean_diff > 0 else "decrease"
        else:
            resolved_dir = "none"

    if idx == "ndvi":
        if resolved_dir == "decrease":
            return "vegetation decrease"
        elif resolved_dir == "increase":
            return "vegetation increase"
        return "vegetation decrease" if dir_mode == "decrease" else "vegetation increase"

    elif idx == "ndwi":
        if resolved_dir == "increase":
            return "water increase"
        elif resolved_dir == "decrease":
            return "water decrease"
        return "water increase" if dir_mode == "increase" else "water decrease"

    elif idx == "ndbi":
        if resolved_dir == "increase":
            return "built_up_spectral_increase"
        elif resolved_dir == "decrease":
            return "built_up_spectral_decrease"
        return "built_up_spectral_increase" if dir_mode == "increase" else "built_up_spectral_decrease"

    return "spectral_change"


def detect_spectral_change(
    t1_raster: Union[str, DatasetReader],
    t2_raster: Union[str, DatasetReader],
    index: str = "ndvi",
    band_mapping: Optional[Dict[str, int]] = None,
    threshold: float = 0.2,
    direction: str = "auto",
    nodata: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute end-to-end bi-temporal spectral change detection between T1 and T2 rasters.

    Args:
        t1_raster: File path or open DatasetReader for T1 (earlier).
        t2_raster: File path or open DatasetReader for T2 (later).
        index: Spectral index to compute ('ndvi', 'ndwi', 'ndbi').
        band_mapping: Mapping of band names to 1-based or 0-based indices.
        threshold: Change detection threshold.
        direction: 'auto', 'increase', 'decrease', or 'both'.
        nodata: Value to treat as nodata.

    Returns:
        Dict[str, Any]: Dictionary containing difference array, change mask, change type,
                        and compatibility metadata.
    """
    # Open readers if paths were passed
    own_t1 = False
    own_t2 = False

    if isinstance(t1_raster, str):
        ds_t1 = rasterio.open(t1_raster)
        own_t1 = True
    else:
        ds_t1 = t1_raster

    if isinstance(t2_raster, str):
        ds_t2 = rasterio.open(t2_raster)
        own_t2 = True
    else:
        ds_t2 = t2_raster

    try:
        # 1. Compatibility validation
        meta = validate_raster_compatibility(ds_t1, ds_t2)

        # Default band mapping if not provided (assume standard 1-based order)
        if band_mapping is None:
            # 1-indexed defaults: red=1, green=2, blue=3, nir=4, swir=5
            band_mapping = {"red": 1, "green": 2, "blue": 3, "nir": 4, "swir": 5}

        # 2. Read raster arrays
        arr_t1 = ds_t1.read()
        arr_t2 = ds_t2.read()

        # Handle raster nodata if present
        raster_nodata = nodata if nodata is not None else ds_t1.nodata

        # 3. Extract bands
        bands_t1 = extract_bands_from_raster(arr_t1, band_mapping)
        bands_t2 = extract_bands_from_raster(arr_t2, band_mapping)

        # 4. Compute spectral indices
        idx_t1 = calculate_index(index, bands_t1, nodata=raster_nodata)
        idx_t2 = calculate_index(index, bands_t2, nodata=raster_nodata)

        # 5. Difference calculation
        diff = calculate_spectral_difference(idx_t1, idx_t2)

        # 6. Generate change mask
        dir_eval = direction if direction != "auto" else "both"
        raw_mask = generate_change_mask(diff, threshold=threshold, direction=dir_eval)

        # 7. Classify change type
        change_type = classify_change_type(
            index_name=index,
            direction=direction,
            difference=diff,
            mask=raw_mask,
        )

        return {
            "difference": diff,
            "mask": raw_mask,
            "change_type": change_type,
            "index_t1": idx_t1,
            "index_t2": idx_t2,
            "transform": ds_t1.transform,
            "crs": ds_t1.crs,
            "width": ds_t1.width,
            "height": ds_t1.height,
            "metadata": meta,
        }

    finally:
        if own_t1:
            ds_t1.close()
        if own_t2:
            ds_t2.close()
