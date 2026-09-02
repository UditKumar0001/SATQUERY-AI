# data/preprocess.py
import os
import numpy as np
from PIL import Image
import rasterio
import torch


def load_geotiff(path: str):
    """Load a raster / GeoTIFF file into a PyTorch tensor (C, H, W) and metadata dictionary."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Raster file not found: {path}")

    try:
        with rasterio.open(path) as src:
            arr = src.read()  # Shape: (bands, height, width)
            meta = src.meta.copy()
            # Ensure metadata keys are serializable/standardized
            meta["crs"] = str(src.crs)
            meta["bounds"] = tuple(src.bounds) if src.bounds else None
            meta["count"] = src.count
            meta["driver"] = src.driver
        tensor = torch.from_numpy(arr.astype(np.float32))
        return tensor, meta
    except Exception:
        # Fallback for image formats where rasterio might lack GDAL driver support on some systems
        pil_img = Image.open(path)
        arr = np.array(pil_img)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]  # (1, H, W)
        elif arr.ndim == 3:
            arr = np.transpose(arr, (2, 0, 1))  # (C, H, W)
        meta = {
            "driver": pil_img.format,
            "count": arr.shape[0],
            "width": pil_img.width,
            "height": pil_img.height,
            "crs": None,
            "bounds": None
        }
        return torch.from_numpy(arr.astype(np.float32)), meta


def normalize_optical(tensor: torch.Tensor) -> torch.Tensor:
    """Normalize optical imagery (zero mean, unit variance)."""
    if not isinstance(tensor, torch.Tensor):
        tensor = torch.tensor(tensor, dtype=torch.float32)
    return (tensor - tensor.mean()) / (tensor.std() + 1e-6)


def normalize_sar(tensor: torch.Tensor) -> torch.Tensor:
    """Normalize SAR backscatter: log1p-transformed for exponential distribution, then standardized."""
    if not isinstance(tensor, torch.Tensor):
        tensor = torch.tensor(tensor, dtype=torch.float32)
    clamped = torch.clamp(tensor, min=0.0)
    log_transformed = torch.log1p(clamped)
    return (log_transformed - log_transformed.mean()) / (log_transformed.std() + 1e-6)


def preprocess_image_for_model(path: str, modality: str = "optical") -> torch.Tensor:
    """Convenience pipeline to load and apply modality-specific normalization."""
    tensor, _ = load_geotiff(path)
    if modality.lower() == "sar":
        return normalize_sar(tensor)
    return normalize_optical(tensor)


def process_all_subsets(raw_dir: str = "data/raw", processed_dir: str = "data/processed"):
    """Process raw imagery and generate standardized tensors and instruction datasets."""
    import json
    os.makedirs(processed_dir, exist_ok=True)

    # 1. Process BigEarthNet into normalized tensors and instruction dataset for LoRA (Step 13)
    ben_raw = os.path.join(raw_dir, "bigearthnet")
    ben_proc = os.path.join(processed_dir, "bigearthnet")
    os.makedirs(ben_proc, exist_ok=True)

    manifest_path = os.path.join(ben_raw, "paired_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        instructions = []
        for item in manifest[:50]:  # Process subset
            opt_p = item["optical_path"]
            sar_p = item["sar_path"]
            if os.path.exists(opt_p) and os.path.exists(sar_p):
                opt_tensor, _ = load_geotiff(opt_p)
                sar_tensor, _ = load_geotiff(sar_p)
                norm_opt = normalize_optical(opt_tensor)
                norm_sar = normalize_sar(sar_tensor)

                tile_id = item["tile_id"]
                torch.save(norm_opt, os.path.join(ben_proc, f"{tile_id}_opt_norm.pt"))
                torch.save(norm_sar, os.path.join(ben_proc, f"{tile_id}_sar_norm.pt"))

                labels_str = ", ".join(item["labels"])
                instructions.append({
                    "tile_id": tile_id,
                    "optical_path": opt_p,
                    "sar_path": sar_p,
                    "instruction": f"[fusion] Analyze the multisensor optical and SAR characteristics for {tile_id}.",
                    "answer": f"Multisensor fusion indicates active land-cover composition: {labels_str}."
                })

        with open(os.path.join(ben_proc, "instructions.jsonl"), "w", encoding="utf-8") as f:
            for inst in instructions:
                f.write(json.dumps(inst) + "\n")
        print(f"[Preprocess] Generated {len(instructions)} instruction records at {ben_proc}/instructions.jsonl")

    # 2. Preprocess VRSBench sample
    vrs_raw = os.path.join(raw_dir, "vrsbench", "sample_001.png")
    vrs_proc = os.path.join(processed_dir, "vrsbench")
    os.makedirs(vrs_proc, exist_ok=True)
    if os.path.exists(vrs_raw):
        t, meta = load_geotiff(vrs_raw)
        norm_t = normalize_optical(t)
        torch.save(norm_t, os.path.join(vrs_proc, "sample_001_norm.pt"))
        print(f"[Preprocess] VRSBench normalized tensor saved at {vrs_proc}/sample_001_norm.pt")

    # 3. Preprocess CDVQA pairs
    cd_raw_1 = os.path.join(raw_dir, "cdvqa", "pair_004_before.png")
    cd_raw_2 = os.path.join(raw_dir, "cdvqa", "pair_004_after.png")
    cd_proc = os.path.join(processed_dir, "cdvqa")
    os.makedirs(cd_proc, exist_ok=True)
    if os.path.exists(cd_raw_1) and os.path.exists(cd_raw_2):
        t1, _ = load_geotiff(cd_raw_1)
        t2, _ = load_geotiff(cd_raw_2)
        torch.save(normalize_optical(t1), os.path.join(cd_proc, "pair_004_before_norm.pt"))
        torch.save(normalize_optical(t2), os.path.join(cd_proc, "pair_004_after_norm.pt"))
        print(f"[Preprocess] CDVQA normalized pairs saved at {cd_proc}")


if __name__ == "__main__":
    process_all_subsets()

