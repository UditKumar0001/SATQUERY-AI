"""Spectral indices module for Geo Evidence Engine.

Computes configurable remote sensing indices including NDVI, NDWI, and NDBI.
Handles division by zero, invalid pixels, and nodata values deterministically
without hardcoding satellite-specific bands or sensors.
"""

from typing import Any, Dict, Optional, Union
import numpy as np


# Common default band requirements for spectral indices
INDEX_REQUIRED_BANDS = {
    "ndvi": ("nir", "red"),
    "ndwi": ("green", "nir"),
    "ndbi": ("swir", "nir"),
}


def calculate_normalized_difference(
    band_a: np.ndarray,
    band_b: np.ndarray,
    nodata: Optional[float] = None,
    out_nodata: float = np.nan,
) -> np.ndarray:
    """Calculate normalized difference index: (band_a - band_b) / (band_a + band_b).

    Args:
        band_a: First spectral band array (e.g., NIR for NDVI).
        band_b: Second spectral band array (e.g., Red for NDVI).
        nodata: Optional nodata value in input bands to mask out.
        out_nodata: Value to assign to invalid/nodata/zero-denom pixels. Defaults to np.nan.

    Returns:
        np.ndarray: Calculated index as float32 array with range [-1.0, 1.0] for valid pixels.
    """
    if band_a.shape != band_b.shape:
        raise ValueError(
            f"Band shape mismatch: band_a {band_a.shape} vs band_b {band_b.shape}"
        )

    a = band_a.astype(np.float32, copy=False)
    b = band_b.astype(np.float32, copy=False)

    numerator = a - b
    denominator = a + b

    # Determine valid pixels
    # 1. Finite values (not NaN or Inf)
    valid_mask = np.isfinite(a) & np.isfinite(b)

    # 2. Denominator must not be zero
    valid_mask &= np.abs(denominator) > 1e-7

    # 3. Handle input nodata value if provided
    if nodata is not None:
        if np.isnan(nodata):
            valid_mask &= ~np.isnan(band_a) & ~np.isnan(band_b)
        else:
            valid_mask &= (band_a != nodata) & (band_b != nodata)

    # Allocate output initialized to out_nodata
    out = np.full(a.shape, out_nodata, dtype=np.float32)

    # Vectorized division only where denominator and inputs are valid
    np.divide(numerator, denominator, out=out, where=valid_mask)

    # Clip mathematically valid results to [-1.0, 1.0] to guard against floating-point precision drift
    out[valid_mask] = np.clip(out[valid_mask], -1.0, 1.0)

    return out


def calculate_ndvi(
    red: np.ndarray,
    nir: np.ndarray,
    nodata: Optional[float] = None,
    out_nodata: float = np.nan,
) -> np.ndarray:
    """Calculate Normalized Difference Vegetation Index (NDVI).

    NDVI = (NIR - Red) / (NIR + Red)

    Args:
        red: Red band array.
        nir: Near-infrared band array.
        nodata: Optional nodata value.
        out_nodata: Output nodata replacement value.

    Returns:
        np.ndarray: NDVI array.
    """
    return calculate_normalized_difference(
        band_a=nir,
        band_b=red,
        nodata=nodata,
        out_nodata=out_nodata,
    )


def calculate_ndwi(
    green: np.ndarray,
    nir: Optional[np.ndarray] = None,
    swir: Optional[np.ndarray] = None,
    formula: str = "mcfeeters",
    nodata: Optional[float] = None,
    out_nodata: float = np.nan,
) -> np.ndarray:
    """Calculate Normalized Difference Water Index (NDWI).

    Formulas:
        - "mcfeeters" (default, water bodies): (Green - NIR) / (Green + NIR)
        - "gao" (vegetation canopy water / NDMI): (NIR - SWIR) / (NIR + SWIR)

    Args:
        green: Green band array.
        nir: Near-infrared band array.
        swir: Shortwave infrared band array (required if formula is 'gao').
        formula: 'mcfeeters' or 'gao'.
        nodata: Optional nodata value.
        out_nodata: Output nodata replacement value.

    Returns:
        np.ndarray: NDWI array.
    """
    formula_lower = formula.lower()
    if formula_lower == "mcfeeters":
        if nir is None:
            raise ValueError("McFeeters NDWI requires green and nir bands.")
        return calculate_normalized_difference(
            band_a=green,
            band_b=nir,
            nodata=nodata,
            out_nodata=out_nodata,
        )
    elif formula_lower in ("gao", "ndmi"):
        if nir is None or swir is None:
            raise ValueError("Gao NDWI / NDMI requires nir and swir bands.")
        return calculate_normalized_difference(
            band_a=nir,
            band_b=swir,
            nodata=nodata,
            out_nodata=out_nodata,
        )
    else:
        raise ValueError(
            f"Unsupported NDWI formula '{formula}'. Choose 'mcfeeters' or 'gao'."
        )


def calculate_ndbi(
    swir: np.ndarray,
    nir: np.ndarray,
    nodata: Optional[float] = None,
    out_nodata: float = np.nan,
) -> np.ndarray:
    """Calculate Normalized Difference Built-up Index (NDBI).

    NDBI = (SWIR - NIR) / (SWIR + NIR)

    Args:
        swir: Shortwave infrared band array.
        nir: Near-infrared band array.
        nodata: Optional nodata value.
        out_nodata: Output nodata replacement value.

    Returns:
        np.ndarray: NDBI array.
    """
    return calculate_normalized_difference(
        band_a=swir,
        band_b=nir,
        nodata=nodata,
        out_nodata=out_nodata,
    )


def extract_bands_from_raster(
    raster: np.ndarray,
    band_mapping: Dict[str, int],
) -> Dict[str, np.ndarray]:
    """Extract named 2D band arrays from a 3D raster array using configurable band mapping.

    Args:
        raster: 3D numpy array of shape (num_bands, height, width).
        band_mapping: Mapping of band name to index, e.g. {'red': 0, 'green': 1, 'nir': 2, 'swir': 3}
                      or 1-indexed {'red': 1, 'green': 2, 'nir': 3, 'swir': 4}.

    Returns:
        Dict[str, np.ndarray]: Dictionary mapping normalized band names to 2D numpy arrays.
    """
    if raster.ndim != 3:
        raise ValueError(
            f"Expected 3D raster array (bands, height, width), got ndim={raster.ndim}"
        )

    num_bands = raster.shape[0]
    extracted: Dict[str, np.ndarray] = {}

    # Check if mapping is 1-indexed (common in GIS/rasterio) or 0-indexed
    min_idx = min(band_mapping.values()) if band_mapping else 0
    max_idx = max(band_mapping.values()) if band_mapping else 0
    is_1_indexed = (min_idx >= 1) and (max_idx <= num_bands)

    for band_name, band_idx in band_mapping.items():
        actual_idx = band_idx - 1 if is_1_indexed else band_idx
        if actual_idx < 0 or actual_idx >= num_bands:
            raise IndexError(
                f"Band index {band_idx} (resolved to {actual_idx}) out of range for raster with {num_bands} bands."
            )
        extracted[band_name.lower().strip()] = raster[actual_idx]

    return extracted


def calculate_index(
    index_name: str,
    bands: Dict[str, np.ndarray],
    nodata: Optional[float] = None,
    out_nodata: float = np.nan,
    **kwargs: Any,
) -> np.ndarray:
    """Dispatch spectral index calculation dynamically based on index name and provided bands.

    Args:
        index_name: Name of index ('ndvi', 'ndwi', 'ndbi').
        bands: Dictionary of available band arrays (keys lowercase, e.g. 'red', 'green', 'nir', 'swir').
        nodata: Optional input nodata value.
        out_nodata: Output nodata replacement value.
        **kwargs: Additional parameters passed to specific index functions (e.g. formula='mcfeeters').

    Returns:
        np.ndarray: Computed spectral index array.
    """
    normalized_name = index_name.lower().strip()
    normalized_bands = {k.lower().strip(): v for k, v in bands.items()}

    if normalized_name == "ndvi":
        if "nir" not in normalized_bands or "red" not in normalized_bands:
            raise ValueError(
                f"NDVI requires 'nir' and 'red' bands. Available bands: {list(normalized_bands.keys())}"
            )
        return calculate_ndvi(
            red=normalized_bands["red"],
            nir=normalized_bands["nir"],
            nodata=nodata,
            out_nodata=out_nodata,
        )

    elif normalized_name == "ndwi":
        formula = kwargs.get("formula", "mcfeeters").lower()
        if formula == "gao":
            if "nir" not in normalized_bands or "swir" not in normalized_bands:
                raise ValueError(
                    f"Gao NDWI requires 'nir' and 'swir' bands. Available bands: {list(normalized_bands.keys())}"
                )
            return calculate_ndwi(
                green=normalized_bands.get("green", normalized_bands["nir"]),
                nir=normalized_bands["nir"],
                swir=normalized_bands["swir"],
                formula="gao",
                nodata=nodata,
                out_nodata=out_nodata,
            )
        else:
            if "green" not in normalized_bands or "nir" not in normalized_bands:
                raise ValueError(
                    f"McFeeters NDWI requires 'green' and 'nir' bands. Available bands: {list(normalized_bands.keys())}"
                )
            return calculate_ndwi(
                green=normalized_bands["green"],
                nir=normalized_bands["nir"],
                formula="mcfeeters",
                nodata=nodata,
                out_nodata=out_nodata,
            )

    elif normalized_name == "ndbi":
        if "swir" not in normalized_bands or "nir" not in normalized_bands:
            raise ValueError(
                f"NDBI requires 'swir' and 'nir' bands. Available bands: {list(normalized_bands.keys())}"
            )
        return calculate_ndbi(
            swir=normalized_bands["swir"],
            nir=normalized_bands["nir"],
            nodata=nodata,
            out_nodata=out_nodata,
        )

    else:
        raise ValueError(
            f"Unsupported spectral index '{index_name}'. Supported indices: 'ndvi', 'ndwi', 'ndbi'."
        )
