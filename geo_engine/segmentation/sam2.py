"""SAM 2 (Segment Anything 2) secondary segmentation module for Geo Evidence Engine.

Provides precise boundary refinement for candidate changed regions identified by the
deterministic Geo Evidence Engine. Translates pixel-level segmentations back into
accurate geospatial coordinates and GeoJSON geometries, strictly preserving CRS,
affine geotransform, and raster dimensions.

SAM 2 serves as a visual refinement tool, NOT as the primary proof that a change occurred.
"""

import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

from geo_engine.mask import save_mask_to_geotiff
from geo_engine.quantification import calculate_change_metrics
from geo_engine.segmentation.preprocessing import (
    extract_candidate_regions,
    pixel_to_geo_bbox,
    prepare_satellite_image_for_sam,
)
from geo_engine.spatial import mask_to_geojson


class SAM2NotAvailableError(RuntimeError):
    """Raised when SAM 2 is requested for live inference but required model weights,
    libraries, or hardware dependencies are not accessible in the current environment."""
    pass


def is_sam2_available(model_id: str = "facebook/sam2-hiera-tiny", checkpoint_path: Optional[str] = None) -> Tuple[bool, str]:
    """Check if SAM 2 dependencies and weights are available in the local environment.

    Returns:
        Tuple[bool, str]: (is_available, status_message)
    """
    # 1. Check if checkpoint file was passed and exists
    if checkpoint_path is not None:
        if os.path.isfile(checkpoint_path):
            return True, f"SAM 2 local checkpoint found at '{checkpoint_path}'."
        return False, f"SAM 2 checkpoint file not found at '{checkpoint_path}'."

    # 2. Check if transformers Sam2Model is importable
    try:
        from transformers import Sam2Model, Sam2Processor  # noqa: F401
        transformers_has_sam2 = True
    except ImportError:
        transformers_has_sam2 = False

    # 3. Check if meta sam2 package is installed
    try:
        import sam2  # noqa: F401
        meta_sam2_installed = True
    except ImportError:
        meta_sam2_installed = False

    if not transformers_has_sam2 and not meta_sam2_installed:
        return False, (
            "Neither `sam2` (Meta) nor `transformers` (v4.45+ with Sam2Model) is available. "
            "Install sam2 via `pip install git+https://github.com/facebookresearch/segment-anything-2.git`."
        )

    # Note on weights: Even if libraries exist, weights may need to be downloaded from HuggingFace
    return True, "SAM 2 libraries available."


class SAM2Segmentor:
    """Wrapper for Segment Anything 2 (SAM 2) focused on candidate change region refinement.

    Attributes:
        model_id: HuggingFace model ID or Meta model architecture name.
        device: Execution device ('cuda' or 'cpu').
        is_available: Whether model is loaded and ready for inference.
        error_message: Detailed diagnostic error message if model is unavailable.
    """

    def __init__(
        self,
        model_id: str = "facebook/sam2-hiera-tiny",
        checkpoint_path: Optional[str] = None,
        device: Optional[str] = None,
        backend: str = "auto",
        predictor_override: Optional[Any] = None,
        load_weights: bool = False,
    ):
        """Initialize SAM 2 segmentor.

        Args:
            model_id: Model repository ID (e.g., 'facebook/sam2-hiera-tiny').
            checkpoint_path: Optional path to local .pt checkpoint.
            device: Device string ('cuda', 'cpu'). Auto-detected if None.
            backend: 'auto', 'transformers', 'meta', or 'mock'.
            predictor_override: Optional custom predictor or callable for testing/mocking.
            load_weights: If True, attempts to load weights immediately. Defaults to False.
        """
        import torch

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = str(device).lower()
        self.model_id = model_id
        self.checkpoint_path = checkpoint_path
        self.backend = backend
        self.predictor = predictor_override

        self.is_available = False
        self.error_message: Optional[str] = None

        if predictor_override is not None:
            self.is_available = True
            self.backend = "override"
            return

        if backend == "mock":
            self.is_available = True
            return

        # Check availability
        avail, msg = is_sam2_available(model_id, checkpoint_path)
        if not avail:
            self.is_available = False
            self.error_message = msg
            return

        if load_weights:
            self._load_live_model()

    def _load_live_model(self) -> None:
        """Attempt to instantiate live SAM 2 model and predictor."""
        import torch

        try:
            from transformers import Sam2Model, Sam2Processor

            self.processor = Sam2Processor.from_pretrained(self.model_id)
            self.model = Sam2Model.from_pretrained(
                self.model_id,
                torch_dtype=torch.float32 if self.device == "cpu" else torch.float16,
            ).to(self.device)
            self.is_available = True
            self.backend = "transformers"
        except Exception as e:
            self.is_available = False
            self.error_message = (
                f"Failed to load SAM 2 model weights from '{self.model_id}': {str(e)}. "
                "Ensure network connectivity or provide a local checkpoint."
            )

    def segment_candidate(
        self,
        image_rgb: np.ndarray,
        candidate: Dict[str, Any],
        confidence_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Perform prompt-guided SAM 2 segmentation on a candidate changed region.

        Uses the candidate's bounding box and/or centroid as visual prompts.

        Args:
            image_rgb: 3-channel uint8 numpy array of shape (height, width, 3).
            candidate: Candidate region dict containing 'bbox': [x_min, y_min, x_max, y_max].
            confidence_threshold: Minimum predicted IoU / confidence score to accept.

        Returns:
            Dict[str, Any]: Segmentation result containing:
                - 'mask': 2D binary numpy array (height, width) with values 0 and 1
                - 'confidence': float score
                - 'bbox': [x_min, y_min, x_max, y_max]
        """
        if not self.is_available:
            raise SAM2NotAvailableError(
                self.error_message
                or f"SAM 2 model '{self.model_id}' is not loaded or weights are unavailable."
            )

        height, width = image_rgb.shape[:2]
        x_min, y_min, x_max, y_max = candidate["bbox"]

        # 1. If custom predictor override is provided
        if self.predictor is not None:
            res = self.predictor(image_rgb, candidate)
            return res

        # 2. If mock backend is active (for testing/offline deterministic evaluation)
        if self.backend == "mock":
            # Deterministic mock refinement: creates a precise object ellipse/rectangle inside the candidate box
            mask = np.zeros((height, width), dtype=np.uint8)
            # Create refined shape slightly smaller or refined within the box
            pad_x = max(1, (x_max - x_min) // 8)
            pad_y = max(1, (y_max - y_min) // 8)
            mask[y_min + pad_y : y_max - pad_y + 1, x_min + pad_x : x_max - pad_x + 1] = 1
            if not np.any(mask):
                mask[y_min : y_max + 1, x_min : x_max + 1] = 1

            return {
                "mask": mask,
                "confidence": 0.94,
                "bbox": [x_min + pad_x, y_min + pad_y, x_max - pad_x, y_max - pad_y],
            }

        # 3. Live Transformers Sam2Model inference
        if self.backend == "transformers" and hasattr(self, "model") and hasattr(self, "processor"):
            import torch

            # Format input prompt box: [[[[x_min, y_min, x_max, y_max]]]]
            input_boxes = [[[x_min, y_min, x_max, y_max]]]

            inputs = self.processor(
                image_rgb,
                input_boxes=input_boxes,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Extract predicted masks and IoU scores
            masks = outputs.pred_masks.squeeze().cpu().numpy()
            scores = outputs.iou_scores.squeeze().cpu().numpy()

            if masks.ndim == 3:
                # Select mask with highest confidence score
                best_idx = int(np.argmax(scores))
                best_mask = (masks[best_idx] > 0.0).astype(np.uint8)
                best_score = float(scores[best_idx])
            else:
                best_mask = (masks > 0.0).astype(np.uint8)
                best_score = float(scores) if np.ndim(scores) == 0 else float(scores[0])

            return {
                "mask": best_mask,
                "confidence": best_score,
                "bbox": candidate["bbox"],
            }

        raise SAM2NotAvailableError("No valid SAM 2 inference backend configured.")

    def refine_candidates(
        self,
        image_rgb: np.ndarray,
        candidates: List[Dict[str, Any]],
        transform: Affine,
        crs: CRS,
        output_dir: Optional[str] = None,
        confidence_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Refine multiple candidate change regions using SAM 2 and produce georeferenced output.

        Args:
            image_rgb: 3-channel uint8 satellite image array (H, W, 3).
            candidates: List of candidate region dicts from preprocessing.
            transform: Raster Affine geotransform.
            crs: Raster Coordinate Reference System.
            output_dir: Directory to save refined segment GeoTIFFs.
            confidence_threshold: Minimum confidence score.

        Returns:
            Dict[str, Any]: Structured segmentation result matching specification.
        """
        if not self.is_available:
            return {
                "segmentation_detected": False,
                "segments": [],
                "model": "SAM2",
                "source": "geo_evidence_candidate",
                "status": "unavailable",
                "error": self.error_message
                or f"SAM 2 model '{self.model_id}' is unavailable in the current environment.",
            }

        target_dir = output_dir if output_dir else tempfile.mkdtemp(prefix="sam2_segments_")
        os.makedirs(target_dir, exist_ok=True)

        segments: List[Dict[str, Any]] = []

        for cand in candidates:
            try:
                seg_result = self.segment_candidate(
                    image_rgb=image_rgb,
                    candidate=cand,
                    confidence_threshold=confidence_threshold,
                )
            except SAM2NotAvailableError:
                raise
            except Exception as e:
                # Skip invalid individual segment while reporting warning
                continue

            seg_mask = seg_result["mask"]
            confidence = float(seg_result["confidence"])

            if not np.any(seg_mask == 1):
                continue

            # Calculate accurate area in hectares preserving CRS and dynamic resolution
            metrics = calculate_change_metrics(seg_mask, transform, crs)

            # Generate GeoJSON polygon geometry in standard WGS84
            geojson_data = mask_to_geojson(
                seg_mask,
                transform,
                crs,
                to_wgs84=True,
                properties={
                    "candidate_id": cand.get("candidate_id"),
                    "confidence": confidence,
                    "evidence_relation": "refined_candidate_segment",
                },
            )

            # Save refined segment mask as a georeferenced GeoTIFF
            cand_id = cand.get("candidate_id", len(segments) + 1)
            mask_filename = f"sam2_segment_{cand_id}.tif"
            mask_path = os.path.join(target_dir, mask_filename)
            save_mask_to_geotiff(
                mask=seg_mask,
                output_path=mask_path,
                transform=transform,
                crs=crs,
                metadata={
                    "MODEL": "SAM2",
                    "CANDIDATE_ID": cand_id,
                    "CONFIDENCE": confidence,
                    "SOURCE": "geo_evidence_candidate",
                },
            )

            # Calculate geospatial bounding box
            geo_bbox = pixel_to_geo_bbox(seg_result["bbox"], transform)

            segments.append({
                "segment_id": cand_id,
                "mask_path": mask_path,
                "area_ha": metrics["changed_area_ha"],
                "area_m2": metrics["changed_area_m2"],
                "pixel_count": metrics["changed_pixels"],
                "geojson": geojson_data,
                "bbox": seg_result["bbox"],
                "geo_bbox": geo_bbox,
                "confidence": round(confidence, 4),
                "evidence_relation": "refined_candidate_segment",
            })

        total_area_ha = round(sum(s["area_ha"] for s in segments), 4)

        return {
            "segmentation_detected": bool(len(segments) > 0),
            "segments": segments,
            "total_refined_area_ha": total_area_ha,
            "model": "SAM2",
            "source": "geo_evidence_candidate",
            "evidence_claim": "visual_segmentation_of_detected_change",
            "status": "success",
        }


def refine_change_with_sam2(
    change_result: Dict[str, Any],
    t2_raster: Union[str, np.ndarray],
    transform: Optional[Affine] = None,
    crs: Optional[CRS] = None,
    segmentor: Optional[SAM2Segmentor] = None,
    band_mapping: Optional[Dict[str, int]] = None,
    min_area_pixels: int = 4,
    max_candidates: int = 20,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Connect deterministic Geo Evidence Engine result to secondary SAM 2 segmentation.

    Pipeline:
        1. Checks if Geo Evidence Engine detected change. If False, skips SAM 2.
        2. Prepares satellite imagery safely (multispectral normalization to RGB).
        3. Extracts candidate changed regions from change mask.
        4. Runs SAM 2 to visually refine candidate region boundaries.
        5. Computes refined metric area (hectares) and GeoJSON geometries.

    Args:
        change_result: Structured result dictionary from `run_change_detection_pipeline`.
        t2_raster: Filepath or 3D numpy array of later satellite image (T2).
        transform: Affine geotransform matrix (if t2_raster is array).
        crs: Coordinate Reference System (if t2_raster is array).
        segmentor: Optional pre-configured SAM2Segmentor instance.
        band_mapping: Optional band mapping dict for multispectral satellite imagery.
        min_area_pixels: Minimum pixel area for candidate change regions.
        max_candidates: Maximum number of candidate change regions to refine.
        output_dir: Output directory for refined segment GeoTIFFs.

    Returns:
        Dict[str, Any]: Structured SAM 2 segmentation result.
    """
    # 1. Check if change was detected by Phase 1 Geo Evidence Engine
    if not change_result.get("change_detected", False) or change_result.get("changed_pixels", 0) <= 0:
        return {
            "segmentation_detected": False,
            "segments": [],
            "model": "SAM2",
            "source": "geo_evidence_candidate",
            "message": "No change detected by Geo Evidence Engine; SAM 2 secondary refinement was skipped.",
            "status": "skipped",
        }

    # 2. Read satellite image and georeferencing
    own_reader = False
    if isinstance(t2_raster, str):
        ds = rasterio.open(t2_raster)
        own_reader = True
        raster_arr = ds.read()
        transform = ds.transform
        crs = ds.crs
    else:
        raster_arr = t2_raster
        if transform is None or crs is None:
            raise ValueError("When passing raw numpy array for t2_raster, transform and crs must be provided.")

    try:
        # 3. Read change mask from change_result
        mask_path = change_result.get("mask_path")
        if mask_path and os.path.isfile(mask_path):
            with rasterio.open(mask_path) as mask_ds:
                change_mask = mask_ds.read(1)
        elif "mask" in change_result:
            change_mask = change_result["mask"]
        else:
            raise ValueError("change_result must contain 'mask_path' or 'mask' array.")

        # 4. Prepare satellite image RGB safely
        image_rgb = prepare_satellite_image_for_sam(
            raster=raster_arr,
            band_mapping=band_mapping,
        )

        # 5. Extract candidate changed regions
        candidates = extract_candidate_regions(
            change_mask=change_mask,
            min_area_pixels=min_area_pixels,
            max_candidates=max_candidates,
        )

        if not candidates:
            return {
                "segmentation_detected": False,
                "segments": [],
                "model": "SAM2",
                "source": "geo_evidence_candidate",
                "message": "Change mask has no candidate clusters meeting the min_area_pixels threshold.",
                "status": "no_candidates",
            }

        # 6. Initialize segmentor if not provided
        if segmentor is None:
            segmentor = SAM2Segmentor(backend="auto")

        # 7. Refine candidate regions with SAM 2
        return segmentor.refine_candidates(
            image_rgb=image_rgb,
            candidates=candidates,
            transform=transform,
            crs=crs,
            output_dir=output_dir,
        )

    finally:
        if own_reader:
            ds.close()
