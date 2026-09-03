# orchestrator/compatibility.py
import os
import torch
import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

try:
    from transformers import AutoProcessor, CLIPVisionModelWithProjection
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False

SAME_LOCATION_THRESHOLD = 0.75

# Lazy-loaded CLIP vision model
_clip_model = None
_clip_processor = None


def _get_clip():
    global _clip_model, _clip_processor
    if _clip_model is None and CLIP_AVAILABLE:
        try:
            configured = os.getenv("MODEL_DEVICE")
            if configured:
                device = configured.lower()
            else:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                if torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] > 9:
                    device = "cpu"  # CPU fallback for sm_120
            model_id = "openai/clip-vit-base-patch32"
            _clip_processor = AutoProcessor.from_pretrained(model_id)
            _clip_model = CLIPVisionModelWithProjection.from_pretrained(model_id).to(device)
            _clip_model.eval()
        except Exception as e:
            print(f"[Compatibility] CLIP lazy load fallback: {e}")
            _clip_model = False
    return _clip_model, _clip_processor


def _to_pil(img) -> Image.Image:
    if isinstance(img, str):
        return Image.open(img).convert("RGB")
    elif isinstance(img, Image.Image):
        return img.convert("RGB")
    elif isinstance(img, np.ndarray):
        return Image.fromarray(img).convert("RGB")
    elif isinstance(img, torch.Tensor):
        arr = img.detach().cpu().numpy()
        if arr.ndim == 3 and arr.shape[0] in (1, 3):
            arr = np.transpose(arr, (1, 2, 0))
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
    raise ValueError(f"Cannot convert {type(img)} to PIL Image")


def same_location_score(img1, img2) -> float:
    """Compute visual/structural cosine similarity between two images to verify co-location."""
    im1 = _to_pil(img1)
    im2 = _to_pil(img2)

    clip_model, clip_processor = _get_clip()
    if clip_model and clip_processor:
        try:
            device = next(clip_model.parameters()).device
            inputs = clip_processor(images=[im1, im2], return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = clip_model(**inputs)
                embeds = outputs.image_embeds
                # Normalized cosine similarity
                norm_embeds = embeds / embeds.norm(dim=-1, keepdim=True)
                score = torch.nn.functional.cosine_similarity(norm_embeds[0:1], norm_embeds[1:2]).item()
                return float(max(0.0, min(1.0, score)))
        except Exception as e:
            print(f"[Compatibility] Neural embedding comparison failed: {e}. Using structural fallback.")

    # High-fidelity structural cross-correlation fallback
    im1_gray = np.array(im1.resize((128, 128)).convert("L"), dtype=np.float32)
    im2_gray = np.array(im2.resize((128, 128)).convert("L"), dtype=np.float32)

    # Normalize
    im1_norm = (im1_gray - np.mean(im1_gray)) / (np.std(im1_gray) + 1e-6)
    im2_norm = (im2_gray - np.mean(im2_gray)) / (np.std(im2_gray) + 1e-6)

    # Pearson correlation coefficient across the scene
    correlation = float(np.mean(im1_norm * im2_norm))
    # Rescale [-1, 1] to [0, 1]
    score = (correlation + 1.0) / 2.0
    return float(max(0.0, min(1.0, score)))
