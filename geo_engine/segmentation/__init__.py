"""SAM 2 Segmentation package for Geo Evidence Engine.

Provides secondary visual boundary refinement for candidate change regions
detected by the deterministic Geo Evidence Engine.
"""

from geo_engine.segmentation.preprocessing import (
    prepare_satellite_image_for_sam,
    extract_candidate_regions,
    pixel_to_geo_bbox,
)
from geo_engine.segmentation.sam2 import (
    SAM2Segmentor,
    SAM2NotAvailableError,
    is_sam2_available,
    refine_change_with_sam2,
)

__all__ = [
    "SAM2Segmentor",
    "SAM2NotAvailableError",
    "is_sam2_available",
    "refine_change_with_sam2",
    "prepare_satellite_image_for_sam",
    "extract_candidate_regions",
    "pixel_to_geo_bbox",
]
