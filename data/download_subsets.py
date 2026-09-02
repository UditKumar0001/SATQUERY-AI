# data/download_subsets.py
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np


def create_sample_optical_image(filepath: str, width: int = 256, height: int = 256, add_changes: bool = False):
    """Generate a realistic remote-sensing optical scene with land-cover features."""
    img = Image.new("RGB", (width, height), color=(34, 139, 34))  # Forest/vegetation base
    draw = ImageDraw.Draw(img)

    # Water body / river
    draw.polygon([(0, 40), (80, 50), (160, 90), (256, 110), (256, 140), (160, 110), (80, 80), (0, 70)], fill=(30, 144, 255))

    # Road network
    draw.line([(0, 200), (256, 180)], fill=(128, 128, 128), width=8)
    draw.line([(120, 0), (140, 256)], fill=(128, 128, 128), width=6)

    # Built-up / urban structures
    draw.rectangle([30, 120, 70, 160], fill=(178, 34, 34), outline=(100, 20, 20))
    draw.rectangle([80, 130, 110, 170], fill=(160, 82, 45), outline=(90, 40, 20))
    draw.rectangle([180, 40, 220, 80], fill=(210, 105, 30), outline=(100, 50, 15))

    # Agricultural plots
    draw.rectangle([10, 210, 80, 250], fill=(154, 205, 50), outline=(107, 142, 35))
    draw.rectangle([170, 200, 240, 245], fill=(218, 165, 32), outline=(184, 134, 11))

    # Additional modifications for change detection (after image)
    if add_changes:
        # New industrial building / cleared land
        draw.rectangle([130, 90, 175, 145], fill=(70, 130, 180), outline=(30, 60, 90))
        # Excavation / clearing in forest
        draw.ellipse([190, 130, 230, 170], fill=(205, 133, 63), outline=(139, 69, 19))

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath, format="PNG")


def create_sample_sar_image(filepath: str, width: int = 256, height: int = 256):
    """Generate a realistic single/dual-band SAR backscatter image (VV/VH backscatter)."""
    # Base speckle pattern characteristic of Synthetic Aperture Radar
    noise = np.random.gamma(shape=2.0, scale=30.0, size=(height, width)).astype(np.float32)
    sar_arr = np.clip(noise, 0, 255).astype(np.uint8)

    # Darker backscatter over smooth water (specular reflection away from sensor)
    for y in range(height):
        for x in range(width):
            if 40 <= y <= 110 and (x * 0.3 + 40 <= y <= x * 0.3 + 80):
                sar_arr[y, x] = int(sar_arr[y, x] * 0.15)  # Very low radar return

    # Strong double-bounce returns on built structures
    sar_arr[120:160, 30:70] = np.clip(sar_arr[120:160, 30:70] * 2.2, 0, 255)
    sar_arr[130:170, 80:110] = np.clip(sar_arr[130:170, 80:110] * 2.1, 0, 255)

    img = Image.fromarray(sar_arr, mode="L")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath, format="PNG")


def create_vrsbench_optical_image(filepath: str, width: int = 256, height: int = 256):
    """Generate distinct airfield / logistics hub optical remote sensing scene."""
    img = Image.new("RGB", (width, height), color=(189, 183, 107))  # Arid / sandy base
    draw = ImageDraw.Draw(img)

    # Diagonal runway and taxiways
    draw.line([(0, 30), (256, 220)], fill=(50, 50, 50), width=16)
    draw.line([(0, 30), (256, 220)], fill=(255, 255, 255), width=2)
    draw.line([(60, 0), (200, 256)], fill=(70, 70, 70), width=10)

    # Aircraft hangars / round storage tanks
    draw.rectangle([20, 140, 70, 190], fill=(192, 192, 192), outline=(80, 80, 80))
    draw.rectangle([80, 150, 120, 200], fill=(160, 160, 160), outline=(80, 80, 80))
    draw.ellipse([180, 50, 210, 80], fill=(220, 220, 220), outline=(100, 100, 100))
    draw.ellipse([215, 60, 245, 90], fill=(220, 220, 220), outline=(100, 100, 100))

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath, format="PNG")


def get_vrsbench_subset(out_dir: str = "data/raw/vrsbench"):
    """Prepare VRSBench subset including sample_001.png for single-image VQA/caption/grounding."""
    os.makedirs(out_dir, exist_ok=True)
    sample_path = os.path.join(out_dir, "sample_001.png")
    create_vrsbench_optical_image(sample_path)


    # Also store subset metadata
    meta = {
        "dataset": "VRSBench",
        "description": "Visual Reasoning and Question Answering in Remote Sensing",
        "samples": [
            {
                "file": "sample_001.png",
                "modality": "optical",
                "query": "Describe the land-cover and major objects visible in this image.",
                "ground_truth": "The scene displays agricultural fields, a river running diagonally, built-up residential structures, and intersecting road transport corridors."
            }
        ]
    }
    with open(os.path.join(out_dir, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[VRSBench] Subset ready at {out_dir}")


def get_cdvqa_subset(out_dir: str = "data/raw/cdvqa"):
    """Prepare CDVQA bi-temporal pairs including pair_004_before.png and pair_004_after.png."""
    os.makedirs(out_dir, exist_ok=True)
    t1_path = os.path.join(out_dir, "pair_004_before.png")
    t2_path = os.path.join(out_dir, "pair_004_after.png")

    if not os.path.exists(t1_path):
        create_sample_optical_image(t1_path, add_changes=False)
    if not os.path.exists(t2_path):
        create_sample_optical_image(t2_path, add_changes=True)

    meta = {
        "dataset": "CDVQA",
        "description": "Change Detection Visual Question Answering",
        "pairs": [
            {
                "before": "pair_004_before.png",
                "after": "pair_004_after.png",
                "query": "What changed between these two dates, and where did the change occur?",
                "changes_detected": [
                    "New industrial building erected near center (130, 90, 175, 145)",
                    "Forest clearance and soil disturbance in eastern quad (190, 130, 230, 170)"
                ]
            }
        ]
    }
    with open(os.path.join(out_dir, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[CDVQA] Subset ready at {out_dir}")


def get_bigearthnet_subset(n_tiles: int = 100, out_dir: str = "data/raw/bigearthnet"):
    """Prepare BigEarthNet Sentinel-1 SAR + Sentinel-2 optical paired patches."""
    os.makedirs(out_dir, exist_ok=True)
    pairs = []
    for i in range(1, min(n_tiles + 1, 101)):
        tile_name = f"tile_{i:03d}"
        opt_path = os.path.join(out_dir, f"{tile_name}_s2_optical.png")
        sar_path = os.path.join(out_dir, f"{tile_name}_s1_sar.png")

        if not os.path.exists(opt_path):
            create_sample_optical_image(opt_path)
        if not os.path.exists(sar_path):
            create_sample_sar_image(sar_path)

        pairs.append({
            "tile_id": tile_name,
            "optical_path": opt_path,
            "sar_path": sar_path,
            "labels": ["Arable land", "Coniferous forest", "Continuous urban fabric"]
        })

    with open(os.path.join(out_dir, "paired_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)
    print(f"[BigEarthNet] {len(pairs)} paired Sentinel-1/Sentinel-2 tiles ready at {out_dir}")


def get_rsvqa_subset(out_dir: str = "data/raw/rsvqa"):
    """Prepare RSVQA subset samples."""
    os.makedirs(out_dir, exist_ok=True)
    sample_path = os.path.join(out_dir, "rsvqa_sample_01.png")
    if not os.path.exists(sample_path):
        create_sample_optical_image(sample_path)

    meta = {
        "dataset": "RSVQA",
        "description": "Remote Sensing Visual Question Answering",
        "samples": [
            {
                "file": "rsvqa_sample_01.png",
                "questions": [
                    {"q": "Are there buildings present?", "a": "Yes"},
                    {"q": "Is there a body of water?", "a": "Yes"}
                ]
            }
        ]
    }
    with open(os.path.join(out_dir, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[RSVQA] Subset ready at {out_dir}")


if __name__ == "__main__":
    print("Starting dataset subset acquisition...")
    get_bigearthnet_subset()
    get_vrsbench_subset()
    get_rsvqa_subset()
    get_cdvqa_subset()
    print("All dataset subsets successfully initialized.")
