# orchestrator/visualization.py
import os
import uuid
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False


def _get_font(size: int = 14):
    """Load a default or truetype font gracefully."""
    try:
        # Try Windows standard font if available
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def render_grounding_box(image_path: str, bbox: list, label: str = None, out_path: str = None) -> str:
    """Render high-contrast bounding box and label banner over satellite image.

    Args:
        image_path: Path to the original input image.
        bbox: Normalized [ymin, xmin, ymax, xmax] or pixel coordinates [y1, x1, y2, x2].
        label: Text to display in the banner above the bounding box.
        out_path: Custom output filepath. If None, auto-generates in data/processed/visualizations/.

    Returns:
        Path to the rendered PNG visualization image.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Source image not found: {image_path}")

    if out_path is None:
        vis_id = uuid.uuid4().hex[:8]
        out_dir = os.path.join("data", "processed", "visualizations")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"grounding_{vis_id}.png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # 1. Load image and convert to RGBA
    with Image.open(image_path) as src_img:
        img = src_img.convert("RGBA")
    w, h = img.size

    # 2. Denormalize coordinates if in 0.0-1.0 range
    if not bbox or len(bbox) < 4:
        bbox = [0.2, 0.2, 0.8, 0.8]

    if all(0.0 <= float(c) <= 1.0 for c in bbox):
        y1 = int(float(bbox[0]) * h)
        x1 = int(float(bbox[1]) * w)
        y2 = int(float(bbox[2]) * h)
        x2 = int(float(bbox[3]) * w)
    else:
        y1, x1, y2, x2 = [int(c) for c in bbox[:4]]

    # Ensure valid coordinates within boundaries
    x1, x2 = max(0, min(x1, x2)), min(w - 1, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h - 1, max(y1, y2))
    if x2 <= x1:
        x2 = min(w - 1, x1 + 20)
    if y2 <= y1:
        y2 = min(h - 1, y1 + 20)

    # 3. Create semi-transparent overlay for box fill
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Amber-red tinted fill inside the box (alpha = 60 / ~24%)
    overlay_draw.rectangle([x1, y1, x2, y2], fill=(239, 68, 68, 55))

    # Composite fill onto base image
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 4. Draw high-contrast solid border (vibrant crimson red, stroke width = 3)
    border_color = (220, 38, 38, 255)
    draw.rectangle([x1, y1, x2, y2], outline=border_color, width=3)

    # 5. Draw decorative high-tech corner brackets
    bracket_len = min(24, max(8, (x2 - x1) // 5), max(8, (y2 - y1) // 5))
    bracket_color = (255, 255, 255, 255)
    b_width = 4
    # Top-Left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=bracket_color, width=b_width)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=bracket_color, width=b_width)
    # Top-Right
    draw.line([(x2, y1), (x2 - bracket_len, y1)], fill=bracket_color, width=b_width)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=bracket_color, width=b_width)
    # Bottom-Left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=bracket_color, width=b_width)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=bracket_color, width=b_width)
    # Bottom-Right
    draw.line([(x2, y2), (x2 - bracket_len, y2)], fill=bracket_color, width=b_width)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=bracket_color, width=b_width)

    # 6. Draw label banner
    text_content = label if label else "Grounding Target"
    font = _get_font(13)

    # Calculate text bounding box
    bbox_text = draw.textbbox((0, 0), text_content, font=font)
    text_w = bbox_text[2] - bbox_text[0]
    text_h = bbox_text[3] - bbox_text[1]

    banner_pad_x = 8
    banner_pad_y = 4
    banner_w = text_w + 2 * banner_pad_x
    banner_h = text_h + 2 * banner_pad_y

    # Position banner above box if space permits, else inside top of box
    if y1 >= banner_h + 4:
        banner_y1 = y1 - banner_h - 2
        banner_y2 = y1 - 2
    else:
        banner_y1 = y1 + 2
        banner_y2 = y1 + banner_h + 2

    banner_x1 = max(2, min(x1, w - banner_w - 2))
    banner_x2 = banner_x1 + banner_w

    # Banner background & outline
    draw.rectangle([banner_x1, banner_y1, banner_x2, banner_y2], fill=(15, 23, 42, 230), outline=(239, 68, 68, 255), width=1)
    draw.text((banner_x1 + banner_pad_x, banner_y1 + banner_pad_y - 1), text_content, fill=(255, 255, 255, 255), font=font)

    # 7. Save output as PNG
    img.convert("RGB").save(out_path, format="PNG")
    return out_path


def render_change_heatmap(img1_path: str, img2_path: str, change_mask=None, out_path: str = None) -> str:
    """Render publication-grade 3-panel comparative visual: [T1: Before] | [T2: After] | [Change Overlay].

    Args:
        img1_path: Path to earlier timestamp image (T1).
        img2_path: Path to later timestamp image (T2).
        change_mask: Optional 2D boolean or float change mask array/list.
        out_path: Custom output filepath. If None, auto-generates in data/processed/visualizations/.

    Returns:
        Path to the 3-panel comparative PNG image.
    """
    if not os.path.exists(img1_path):
        raise FileNotFoundError(f"T1 image not found: {img1_path}")
    if not os.path.exists(img2_path):
        raise FileNotFoundError(f"T2 image not found: {img2_path}")

    if out_path is None:
        vis_id = uuid.uuid4().hex[:8]
        out_dir = os.path.join("data", "processed", "visualizations")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"change_{vis_id}.png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # 1. Load both images and resize to standard panel dimensions (e.g. 512x512)
    panel_size = (512, 512)
    with Image.open(img1_path) as im1:
        pil1 = im1.convert("RGB").resize(panel_size, Image.Resampling.BILINEAR)
    with Image.open(img2_path) as im2:
        pil2 = im2.convert("RGB").resize(panel_size, Image.Resampling.BILINEAR)

    arr1 = np.array(pil1, dtype=np.float32)
    arr2 = np.array(pil2, dtype=np.float32)

    # 2. Compute pixel-level differential metrics
    diff_rgb = arr2 - arr1
    diff_mag = np.mean(np.abs(diff_rgb), axis=2)

    # Differentiate positive changes (new structures/paving) vs negative (cleared/demolished)
    mean_diff = np.mean(diff_rgb, axis=2)
    if change_mask is not None:
        mask_np = np.array(change_mask, dtype=bool)
        if mask_np.shape != panel_size:
            mask_pil = Image.fromarray(mask_np.astype(np.uint8) * 255).resize(panel_size, Image.Resampling.NEAREST)
            mask_np = np.array(mask_pil) > 0
    else:
        mask_np = diff_mag > 28.0

    new_built = mask_np & (mean_diff >= 0)
    demolished = mask_np & (mean_diff < 0)

    # 3. Create Overlay over T2 (later image)
    overlay_img = pil2.convert("RGBA")
    overlay_layer = Image.new("RGBA", panel_size, (0, 0, 0, 0))
    overlay_pixels = np.array(overlay_layer)

    # Green tint for new infrastructure / additions (55% opacity = 140 alpha)
    overlay_pixels[new_built] = [34, 197, 94, 140]
    # Red tint for demolished / cleared areas (55% opacity = 140 alpha)
    overlay_pixels[demolished] = [239, 68, 68, 140]

    overlay_layer = Image.fromarray(overlay_pixels, mode="RGBA")
    composite_panel = Image.alpha_composite(overlay_img, overlay_layer).convert("RGB")

    # 4. Construct 3-Panel Side-by-Side Canvas
    header_h = 40
    footer_h = 32
    margin = 8
    total_w = panel_size[0] * 3 + margin * 4
    total_h = panel_size[1] + header_h + footer_h + margin * 2

    canvas = Image.new("RGB", (total_w, total_h), color=(15, 23, 42))  # Dark slate background
    draw = ImageDraw.Draw(canvas)
    font_header = _get_font(14)
    font_sub = _get_font(12)

    panels = [
        ("T1: Earlier Acquisition", pil1),
        ("T2: Subsequent Acquisition", pil2),
        ("Bi-Temporal Change Overlay", composite_panel)
    ]

    for idx, (title, p_img) in enumerate(panels):
        x = margin + idx * (panel_size[0] + margin)
        y = margin + header_h

        # Paste panel
        canvas.paste(p_img, (x, y))

        # Panel border
        draw.rectangle([x, y, x + panel_size[0], y + panel_size[1]], outline=(51, 65, 85), width=2)

        # Title header above panel
        tb = draw.textbbox((0, 0), title, font=font_header)
        tx = x + (panel_size[0] - (tb[2] - tb[0])) // 2
        ty = margin + (header_h - (tb[3] - tb[1])) // 2
        draw.text((tx, ty), title, fill=(248, 250, 252), font=font_header)

    # 5. Draw bottom legend on panel 3
    legend_y = total_h - footer_h - margin + 6
    p3_x = margin + 2 * (panel_size[0] + margin)
    # Green swatch: New structures
    draw.rectangle([p3_x + 30, legend_y + 2, p3_x + 44, legend_y + 16], fill=(34, 197, 94), outline=(255, 255, 255))
    draw.text((p3_x + 50, legend_y), "New Construction / Added", fill=(226, 232, 240), font=font_sub)
    # Red swatch: Demolished / Cleared
    draw.rectangle([p3_x + 270, legend_y + 2, p3_x + 284, legend_y + 16], fill=(239, 68, 68), outline=(255, 255, 255))
    draw.text((p3_x + 290, legend_y), "Demolished / Cleared", fill=(226, 232, 240), font=font_sub)

    canvas.save(out_path, format="PNG")
    return out_path


def render_fused_composite(optical_path: str, sar_path: str, out_path: str = None) -> str:
    """Render calibrated multi-spectral false-color optical+SAR composite visual.

    Renders a 3-panel comparative presentation: [Optical RGB] | [SAR Radar] | [Fused Optical+SAR Composite].

    Args:
        optical_path: Path to optical imagery (RGB or multi-band).
        sar_path: Path to SAR radar imagery (grayscale backscatter intensity).
        out_path: Custom output filepath. If None, auto-generates in data/processed/visualizations/.

    Returns:
        Path to the rendered composite PNG image.
    """
    if not os.path.exists(optical_path):
        raise FileNotFoundError(f"Optical image not found: {optical_path}")
    if not os.path.exists(sar_path):
        raise FileNotFoundError(f"SAR image not found: {sar_path}")

    if out_path is None:
        vis_id = uuid.uuid4().hex[:8]
        out_dir = os.path.join("data", "processed", "visualizations")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"fusion_{vis_id}.png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    panel_size = (512, 512)
    with Image.open(optical_path) as op_img:
        opt_pil = op_img.convert("RGB").resize(panel_size, Image.Resampling.BILINEAR)
    with Image.open(sar_path) as s_img:
        sar_pil = s_img.convert("L").resize(panel_size, Image.Resampling.BILINEAR)

    opt_arr = np.array(opt_pil, dtype=np.float32)
    sar_arr = np.array(sar_pil, dtype=np.float32)

    # 1. Enhance SAR contrast via adaptive histogram equalization or percentile stretching
    if CV2_AVAILABLE:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        sar_enhanced = clahe.apply(sar_arr.astype(np.uint8))
    else:
        # High-performance percentile contrast stretch
        p2, p98 = np.percentile(sar_arr, (2, 98))
        sar_enhanced = np.clip((sar_arr - p2) / max(1.0, (p98 - p2)) * 255.0, 0, 255).astype(np.uint8)

    # 2. Build Fused Composite: R=Optical Red/NIR, G=Optical Green, B=SAR Radar Intensity
    fused_arr = np.zeros((panel_size[1], panel_size[0], 3), dtype=np.uint8)
    fused_arr[..., 0] = np.clip(opt_arr[..., 0], 0, 255).astype(np.uint8)  # Red reflectance
    fused_arr[..., 1] = np.clip(opt_arr[..., 1], 0, 255).astype(np.uint8)  # Green reflectance
    fused_arr[..., 2] = sar_enhanced  # SAR Radar backscatter

    fused_pil = Image.fromarray(fused_arr, mode="RGB")
    sar_display_pil = Image.fromarray(sar_enhanced, mode="L").convert("RGB")

    # 3. Construct 3-Panel Presentation Canvas
    header_h = 40
    footer_h = 32
    margin = 8
    total_w = panel_size[0] * 3 + margin * 4
    total_h = panel_size[1] + header_h + footer_h + margin * 2

    canvas = Image.new("RGB", (total_w, total_h), color=(15, 23, 42))
    draw = ImageDraw.Draw(canvas)
    font_header = _get_font(14)
    font_sub = _get_font(12)

    panels = [
        ("Sensor 1: Optical RGB", opt_pil),
        ("Sensor 2: SAR Radar Backscatter", sar_display_pil),
        ("Synergistic Fused Composite (Opt + SAR)", fused_pil)
    ]

    for idx, (title, p_img) in enumerate(panels):
        x = margin + idx * (panel_size[0] + margin)
        y = margin + header_h

        canvas.paste(p_img, (x, y))
        draw.rectangle([x, y, x + panel_size[0], y + panel_size[1]], outline=(51, 65, 85), width=2)

        tb = draw.textbbox((0, 0), title, font=font_header)
        tx = x + (panel_size[0] - (tb[2] - tb[0])) // 2
        ty = margin + (header_h - (tb[3] - tb[1])) // 2
        draw.text((tx, ty), title, fill=(248, 250, 252), font=font_header)

    # Bottom legend on fused panel
    legend_y = total_h - footer_h - margin + 6
    p3_x = margin + 2 * (panel_size[0] + margin)
    draw.text(
        (p3_x + 20, legend_y),
        "Red: Optical Red | Green: Optical Green | Blue: SAR Radar Intensity",
        fill=(148, 163, 184),
        font=font_sub
    )

    canvas.save(out_path, format="PNG")
    return out_path
