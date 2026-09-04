# frontend/streamlit_app.py
import base64
from datetime import datetime
import html
import io
import os
from pathlib import Path
import uuid
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# Resolve default backend API URL from Streamlit Cloud Secrets, environment, or localhost
default_api_url = "http://localhost:8000"
try:
    if hasattr(st, "secrets") and "BACKEND_API_URL" in st.secrets:
        default_api_url = str(st.secrets["BACKEND_API_URL"]).rstrip("/")
    elif os.getenv("BACKEND_API_URL"):
        default_api_url = str(os.getenv("BACKEND_API_URL")).rstrip("/")
except Exception:
    default_api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="SatQuery AI — Ground Station EO Console",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Management ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "query_input_val" not in st.session_state:
    st.session_state.query_input_val = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "attached_images" not in st.session_state:
    st.session_state.attached_images = []

if "chat_query_input" not in st.session_state:
    st.session_state.chat_query_input = ""

if "chat_input_key" not in st.session_state:
    st.session_state.chat_input_key = 0

if "show_attach_popover" not in st.session_state:
    st.session_state.show_attach_popover = False

if "chat_opened" not in st.session_state:
    st.session_state.chat_opened = True

is_dark = (st.session_state.theme == "dark")

@st.cache_data
def get_hero_media() -> tuple[str, str]:
    assets_dir = Path(__file__).parent / "assets"
    vid_path = assets_dir / "hero_orbital_satellite.mp4"
    poster_path = assets_dir / "hero_video_poster.jpg"
    
    vid_src = "https://videos.pexels.com/video-files/31084229/13282948_1920_1080_25fps.mp4"
    poster_src = ""
    
    if vid_path.exists():
        try:
            with open(vid_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                vid_src = f"data:video/mp4;base64,{b64}"
        except Exception:
            pass
            
    if poster_path.exists():
        try:
            with open(poster_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
                poster_src = f"data:image/jpeg;base64,{b64_img}"
        except Exception:
            pass
            
    return vid_src, poster_src

hero_video_url, hero_poster_url = get_hero_media()

@st.cache_data
def get_card_images_b64() -> dict:
    assets_dir = Path(__file__).parent / "assets"
    card_map = {
        "optical": "card_task_a_optical.jpg",
        "change": "card_task_b_change.jpg",
        "sar": "card_task_c_sar.jpg",
        "lora": "card_task_d_lora.jpg",
    }
    res = {}
    for key, filename in card_map.items():
        fp = assets_dir / filename
        if fp.exists():
            try:
                with open(fp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    res[key] = f"data:image/jpeg;base64,{b64}"
            except Exception:
                res[key] = ""
        else:
            res[key] = ""
    return res

def make_thumbnail_b64(name: str, raw_bytes: bytes) -> str:
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        im.thumbnail((80, 80))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception:
        return ""

card_imgs = get_card_images_b64()
img_opt_url = card_imgs.get("optical", "")
img_chg_url = card_imgs.get("change", "")
img_sar_url = card_imgs.get("sar", "")
img_lor_url = card_imgs.get("lora", "")

@st.cache_data
def get_pipeline_thumb_images_b64() -> dict:
    assets_dir = Path(__file__).parent / "assets"
    thumb_map = {
        "tile": "thumb_stage1_tile.jpg",
        "geochat": "thumb_stage3_geochat.jpg",
        "geollava": "thumb_stage3_geollava.jpg",
        "earthgpt": "thumb_stage3_earthgpt.jpg",
        "pdf": "thumb_stage4_pdf.png",
    }
    res = {}
    for key, filename in thumb_map.items():
        fp = assets_dir / filename
        if fp.exists():
            try:
                mime = "image/png" if filename.endswith(".png") else "image/jpeg"
                with open(fp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    res[key] = f"data:{mime};base64,{b64}"
            except Exception:
                res[key] = ""
        else:
            res[key] = ""
    return res

pipe_thumbs = get_pipeline_thumb_images_b64()
thumb_tile = pipe_thumbs.get("tile", "")
thumb_geochat = pipe_thumbs.get("geochat", "")
thumb_geollava = pipe_thumbs.get("geollava", "")
thumb_earthgpt = pipe_thumbs.get("earthgpt", "")
thumb_pdf = pipe_thumbs.get("pdf", "")

# --- Mission Control Theme Variables (ISRO / Ground Station Spec) ---
theme_vars = {
    "dark": {
        "bg_app": "#070a0f",
        "bg_panel": "#0c1118",
        "bg_panel_sub": "#121924",
        "bg_input": "#090d14",
        "border_color": "#1e293b",
        "border_subtle": "#16202e",
        "border_focus": "#3B82F6",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent_primary": "#3B82F6",
        "accent_hover": "#60A5FA",
        "btn_primary_bg": "#1D6FD8",
        "btn_primary_text": "#ffffff",
        "btn_primary_hover": "#1754A8",
        "btn_secondary_bg": "#121924",
        "hero_card_bg": "#0c1118",
        "chip_bg": "#121924",
        "chip_text": "#cbd5e1",
        "chip_border": "#243247",
        "chip_hover_bg": "#1c2638",
        "chip_hover_text": "#60A5FA",
        "nav_bg": "#0c1118",
        "nav_border": "#1e293b",
        "sidebar_bg": "#080c13",
        "sidebar_border": "#1e293b",
        "footer_bg": "#080c13",
        "footer_border": "#1e293b",
        "metric_bg": "#0c1118",
        "metric_value": "#60A5FA",
        "result_bg": "#0a0e16",
        "result_border": "#1e293b",
        "status_tag_bg": "rgba(37, 99, 235, 0.18)",
        "status_tag_border": "rgba(96, 165, 250, 0.45)",
        "status_tag_text": "#60A5FA",
    },
    "light": {
        "bg_app": "#f8fafc",
        "bg_panel": "#ffffff",
        "bg_panel_sub": "#f1f5f9",
        "bg_input": "#ffffff",
        "border_color": "#e2e8f0",
        "border_subtle": "#e2e8f0",
        "border_focus": "#1D6FD8",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#64748b",
        "accent_primary": "#1D6FD8",
        "accent_hover": "#1E40AF",
        "btn_primary_bg": "#1D6FD8",
        "btn_primary_text": "#ffffff",
        "btn_primary_hover": "#1E40AF",
        "btn_secondary_bg": "#ffffff",
        "hero_card_bg": "#ffffff",
        "chip_bg": "#f1f5f9",
        "chip_text": "#0f172a",
        "chip_border": "#cbd5e1",
        "chip_hover_bg": "#e2e8f0",
        "chip_hover_text": "#1D6FD8",
        "nav_bg": "#ffffff",
        "nav_border": "#e2e8f0",
        "sidebar_bg": "#f8fafc",
        "sidebar_border": "#e2e8f0",
        "footer_bg": "#ffffff",
        "footer_border": "#e2e8f0",
        "metric_bg": "#ffffff",
        "metric_value": "#1D6FD8",
        "result_bg": "#f8fafc",
        "result_border": "#e2e8f0",
        "status_tag_bg": "rgba(37, 99, 235, 0.10)",
        "status_tag_border": "rgba(37, 99, 235, 0.30)",
        "status_tag_text": "#1D6FD8",
    }
}

t = theme_vars["dark" if is_dark else "light"]

# --- Strict CSS Architecture (Aerospace Ground Control Specification) ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    :root {{
        --bg-app: {t['bg_app']};
        --bg-panel: {t['bg_panel']};
        --bg-panel-sub: {t['bg_panel_sub']};
        --bg-input: {t['bg_input']};
        --border-color: {t['border_color']};
        --border-subtle: {t['border_subtle']};
        --border-focus: {t['border_focus']};
        --text-primary: {t['text_primary']};
        --text-secondary: {t['text_secondary']};
        --text-muted: {t['text_muted']};
        --accent-primary: {t['accent_primary']};
        --accent-hover: {t['accent_hover']};
        --btn-primary-bg: {t['btn_primary_bg']};
        --btn-primary-text: {t['btn_primary_text']};
        --btn-primary-hover: {t['btn_primary_hover']};
        --btn-secondary-bg: {t.get('btn_secondary_bg', t['bg_panel_sub'])};
        --hero-card-bg: {t.get('hero_card_bg', t['bg_panel'])};
        --chip-bg: {t['chip_bg']};
        --chip-text: {t['chip_text']};
        --chip-border: {t['chip_border']};
        --chip-hover-bg: {t['chip_hover_bg']};
        --chip-hover-text: {t['chip_hover_text']};
        --nav-bg: {t['nav_bg']};
        --nav-border: {t['nav_border']};
        --sidebar-bg: {t['sidebar_bg']};
        --sidebar-border: {t['sidebar_border']};
        --footer-bg: {t['footer_bg']};
        --footer-border: {t['footer_border']};
        --metric-bg: {t['metric_bg']};
        --metric-value: {t['metric_value']};
        --result-bg: {t['result_bg']};
        --result-border: {t['result_border']};
        --status-tag-bg: {t['status_tag_bg']};
        --status-tag-border: {t['status_tag_border']};
        --status-tag-text: {t['status_tag_text']};
    }}

    /* Global Typography & Canvas */
    html, body, .stApp, section.main, [data-testid="stMain"], [data-testid="stAppViewContainer"], .main {{
        font-family: 'Inter', -apple-system, sans-serif;
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }}
    
    section.main, [data-testid="stMain"], .main, div[data-testid="stAppViewContainer"] > section.main {{
        container-type: inline-size;
    }}
    
    .stApp {{
        background-color: var(--bg-app);
        color: var(--text-primary);
    }}

    /* Remove Streamlit Default Header & Gap to Pin Nav to Viewport Top */
    header[data-testid="stHeader"] {{
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    .element-container:has(style) {{
        display: none !important;
    }}
    div[data-testid="stMarkdownContainer"]:empty {{
        display: none !important;
    }}

    /* Container Max Width & Responsive Padding */
    html, body {{
        scroll-behavior: smooth;
        scroll-padding-top: 88px !important;
    }}
    [id^="section-"], .ref-stats-grid, .ingestion-hero-banner, .hud-step-header {{
        scroll-margin-top: 88px !important;
    }}
    .main, .stMainBlockContainer, .block-container, div[data-testid="stAppViewContainer"] > section.main {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}
    .main .block-container {{
        max-width: 1260px;
        padding-top: 0 !important;
        margin-top: 0 !important;
        padding-bottom: 3.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
        background-image: 
            radial-gradient(circle, rgba(45, 212, 191, 0.08) 1px, transparent 1px),
            radial-gradient(circle, rgba(96, 165, 250, 0.05) 1px, transparent 1px),
            linear-gradient(to right, rgba(255, 255, 255, 0.016) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.016) 1px, transparent 1px);
        background-size: 48px 48px, 96px 96px, 36px 36px, 36px 36px;
        background-position: 0 0, 24px 24px, 0 0, 0 0;
    }}
    @media (max-width: 768px) {{
        .main .block-container {{
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            padding-top: 0 !important;
        }}
    }}
    @media (max-width: 480px) {{
        .main .block-container {{
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-top: 0 !important;
        }}
    }}

    /* Planet.com Reference Top Navbar (Fixed to Viewport Top, Frosted Glass with Solid Bottom Border) */
    .planet-navbar {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        max-width: 100vw !important;
        height: 64px !important;
        background: rgba(8, 13, 23, 0.94) !important;
        backdrop-filter: blur(14px) !important;
        -webkit-backdrop-filter: blur(14px) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.09) !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45) !important;
        padding: 0 !important;
        margin: 0 !important;
        z-index: 99999 !important;
        box-sizing: border-box !important;
        display: flex !important;
        align-items: center !important;
    }}
    .planet-navbar-inner {{
        width: 100% !important;
        max-width: 1320px !important;
        margin: 0 auto !important;
        padding: 0 2rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        box-sizing: border-box !important;
        height: 100% !important;
    }}
    .planet-nav-brand {{
        display: flex;
        align-items: center;
        gap: 12px;
        text-decoration: none !important;
        border-bottom: none !important;
        outline: none !important;
    }}
    a.planet-nav-brand,
    a.planet-nav-brand:link,
    a.planet-nav-brand:visited,
    a.planet-nav-brand:hover,
    a.planet-nav-brand:active,
    a.planet-nav-brand:focus,
    .planet-navbar a.planet-nav-brand,
    .stMarkdown a.planet-nav-brand,
    div.stMarkdown a.planet-nav-brand,
    .planet-nav-brand,
    .planet-nav-title,
    .planet-nav-title *,
    .nav-brand-sat,
    .nav-brand-query,
    .planet-nav-dot {{
        text-decoration: none !important;
        text-decoration-line: none !important;
        -webkit-text-decoration: none !important;
        border-bottom: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}
    .planet-nav-logo {{
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(15, 23, 42, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.30);
        flex-shrink: 0;
        transition: border-color 0.2s ease, background 0.2s ease;
    }}
    .planet-nav-brand:hover .planet-nav-logo {{
        border-color: rgba(56, 189, 248, 0.50);
        background: rgba(30, 41, 59, 0.85);
    }}
    .ref-nav-logo {{
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        flex-shrink: 0;
        box-shadow: 0 0 10px rgba(37, 99, 235, 0.40);
    }}
    .planet-nav-title {{
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 1.24rem;
        line-height: 1;
        letter-spacing: -0.035em;
        display: inline-flex;
        align-items: baseline;
        text-decoration: none !important;
        user-select: none;
    }}
    .nav-brand-sat {{
        font-weight: 500;
        color: #94A3B8;
        transition: color 0.2s ease;
        text-decoration: none !important;
    }}
    .nav-brand-query {{
        font-weight: 700;
        color: #FFFFFF;
        letter-spacing: -0.04em;
        text-decoration: none !important;
    }}
    .planet-nav-brand:hover .nav-brand-sat {{
        color: #CBD5E1;
    }}
    .planet-nav-dot {{
        color: #38BDF8;
        font-weight: 800;
        font-size: 1.35rem;
        line-height: 0;
        margin-left: 1px;
        position: relative;
        bottom: -1px;
        text-shadow: 0 0 8px rgba(56, 189, 248, 0.60);
        display: inline-block;
        text-decoration: none !important;
    }}
    .planet-nav-right {{
        display: flex !important;
        align-items: center !important;
        gap: 22px !important;
    }}
    .planet-nav-text-link {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.88rem;
        font-weight: 500;
        color: rgba(255, 255, 255, 0.80);
        text-decoration: none !important;
        transition: color 0.15s ease;
        white-space: nowrap;
        letter-spacing: 0.01em;
        padding: 4px 6px;
    }}
    .planet-nav-text-link:hover {{
        color: #ffffff;
    }}
    a.planet-nav-btn-pill,
    .planet-nav-btn-pill,
    .planet-navbar a.planet-nav-btn-pill {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        color: #ffffff !important;
        text-decoration: none !important;
        padding: 7px 18px !important;
        border-radius: 9999px !important;
        border: 1px solid rgba(255, 255, 255, 0.45) !important;
        background: rgba(255, 255, 255, 0.05) !important;
        transition: all 0.2s ease !important;
        white-space: nowrap !important;
        letter-spacing: 0.01em !important;
        box-shadow: none !important;
    }}
    a.planet-nav-btn-pill:hover,
    .planet-nav-btn-pill:hover,
    .planet-navbar a.planet-nav-btn-pill:hover {{
        background: rgba(255, 255, 255, 0.14) !important;
        background-color: rgba(255, 255, 255, 0.14) !important;
        border-color: rgba(255, 255, 255, 0.90) !important;
        color: #ffffff !important;
        box-shadow: 0 0 14px rgba(255, 255, 255, 0.10) !important;
    }}
    .planet-nav-circle-btn {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.30);
        background: rgba(255, 255, 255, 0.04);
        color: rgba(255, 255, 255, 0.85);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        transition: all 0.2s ease;
        flex-shrink: 0;
        box-shadow: none;
    }}
    .planet-nav-circle-btn:hover {{
        background: rgba(56, 189, 248, 0.12);
        border-color: rgba(56, 189, 248, 0.65);
        color: #38BDF8;
    }}
    @media (max-width: 520px) {{
        .planet-navbar-inner {{
            padding: 0 1rem !important;
        }}
        .planet-nav-text-link {{
            display: none !important;
        }}
        .planet-nav-btn-pill {{
            padding: 6px 14px !important;
            font-size: 0.80rem !important;
        }}
    }}

    /* Native Sidebar Collapse Toggle Styling */
    [data-testid="collapsedControl"] {{
        color: var(--text-primary) !important;
    }}

    /* NASA Science Eyes Editorial Hero (Full Bleed, 1080p Real Video Scene) */
    .nasa-hero-wrap {{
        width: 100vw;
        position: relative;
        left: 50%;
        right: auto;
        margin-left: -50vw;
        margin-right: 0;
        width: 100cqw;
        max-width: 100cqw;
        margin-left: -50cqw;
        height: 100vh;
        min-height: 100vh;
        background-color: #020409;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        padding: 96px 0 36px !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        border-bottom: 1px solid var(--border-color);
        box-shadow: inset 0 0 120px rgba(0, 0, 0, 0.90);
        box-sizing: border-box;
    }}
    .nasa-hero-video {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        min-width: 100%;
        min-height: 100%;
        object-fit: cover;
        z-index: 1;
        opacity: 0.92;
        pointer-events: none;
    }}
    /* High-contrast Readability Gradient Mask */
    .nasa-hero-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: 
            linear-gradient(to bottom, rgba(2, 4, 9, 0.60) 0%, rgba(2, 4, 9, 0.15) 12%, transparent 26%),
            linear-gradient(to right, rgba(2, 4, 9, 0.94) 0%, rgba(2, 4, 9, 0.84) 38%, rgba(2, 4, 9, 0.32) 72%, rgba(2, 4, 9, 0.65) 100%),
            linear-gradient(to top, var(--bg-app) 0%, rgba(2, 4, 9, 0.35) 15%, transparent 35%);
        z-index: 2;
        pointer-events: none;
    }}
    .nasa-hero-inner {{
        max-width: 1260px;
        width: 100%;
        margin: 0 auto;
        padding: 0 2rem;
        box-sizing: border-box;
        position: relative;
        z-index: 3;
    }}
    .nasa-hero-eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #60A5FA;
        background: rgba(37, 99, 235, 0.18);
        border: 1px solid rgba(96, 165, 250, 0.45);
        padding: 6px 16px;
        border-radius: 9999px;
        margin-bottom: 24px;
        backdrop-filter: blur(8px);
    }}
    .nasa-hero-title {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: clamp(2.5rem, 6.2vw, 4.4rem);
        font-weight: 800;
        line-height: 1.08;
        letter-spacing: -0.03em;
        color: #ffffff;
        text-align: left;
        margin: 0 0 20px;
        text-shadow: 0 4px 20px rgba(0, 0, 0, 0.85);
        max-width: 800px;
    }}
    .nasa-hero-title-accent {{
        background: linear-gradient(135deg, #BFDBFE 0%, #60A5FA 50%, #2563EB 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
    }}
    .nasa-hero-desc {{
        font-family: 'Inter', sans-serif;
        font-size: clamp(1.0rem, 1.8vw, 1.2rem);
        line-height: 1.65;
        color: #cbd5e1;
        text-align: left;
        max-width: 620px;
        margin: 0 0 32px;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.8);
    }}
    .nasa-hero-actions {{
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
    }}
    .nasa-btn-primary {{
        background: var(--btn-primary-bg);
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.94rem;
        font-weight: 600;
        padding: 12px 26px;
        border-radius: 8px;
        text-decoration: none;
        border: 1px solid rgba(96, 165, 250, 0.40);
        box-shadow: 0 4px 18px rgba(29, 111, 216, 0.40);
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }}
    .nasa-btn-primary:hover {{
        background: var(--btn-primary-hover);
        border-color: rgba(96, 165, 250, 0.65);
        box-shadow: 0 6px 24px rgba(29, 111, 216, 0.55);
        transform: translateY(-1px);
    }}
    .nasa-btn-secondary {{
        background: rgba(15, 23, 42, 0.65);
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.94rem;
        font-weight: 600;
        padding: 12px 26px;
        border-radius: 8px;
        text-decoration: none;
        border: 1px solid rgba(255, 255, 255, 0.22);
        backdrop-filter: blur(12px);
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }}
    .nasa-btn-secondary:hover {{
        background: rgba(30, 41, 59, 0.85);
        border-color: rgba(255, 255, 255, 0.4);
        color: #ffffff !important;
        transform: translateY(-1px);
    }}
    .nasa-hero-bottom {{
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        padding-top: 48px;
    }}
    .nasa-hero-meta {{
        font-family: 'Space Grotesk', 'JetBrains Mono', monospace;
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(226, 232, 240, 0.72);
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .nasa-hero-ctrl-btn {{
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(96, 165, 250, 0.40);
        color: #60A5FA;
        display: flex;
        align-items: center;
        justify-content: center;
        backdrop-filter: blur(10px);
        transition: all 0.2s ease;
        cursor: pointer;
        text-decoration: none;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
    }}
    .nasa-hero-ctrl-btn:hover {{
        background: rgba(30, 41, 59, 0.95);
        border-color: #60A5FA;
        transform: scale(1.06);
        color: #ffffff;
    }}
    @media (max-width: 768px) {{
        .nasa-hero-wrap {{
            min-height: 72vh;
            padding: 36px 0 28px;
        }}
        .nasa-hero-inner {{
            padding: 0 1.25rem !important;
        }}
        .nasa-hero-title {{
            font-size: clamp(2.1rem, 7vw, 3.0rem);
        }}
        .nasa-hero-bottom {{
            padding-top: 32px;
        }}
    }}
    @media (max-width: 500px) {{
        .nasa-hero-wrap {{
            height: auto;
            min-height: 100vh;
            padding: 80px 0 24px !important;
        }}
        .nasa-hero-inner {{
            padding: 0 0.85rem !important;
        }}
        .nasa-hero-actions {{
            flex-direction: column;
            width: 100%;
        }}
        .nasa-btn-primary, .nasa-btn-secondary {{
            width: 100%;
            justify-content: center;
            box-sizing: border-box;
        }}
        .nasa-hero-bottom {{
            flex-direction: column;
            align-items: flex-start;
            gap: 14px;
        }}
    }}

    /* Planet.com Featured Highlight Cards (Hero Anchor Row) */
    .planet-highlights-wrap {{
        width: 100vw;
        position: relative;
        left: 50%;
        right: auto;
        margin-left: -50vw;
        margin-right: 0;
        width: 100cqw;
        max-width: 100cqw;
        margin-left: -50cqw;
        margin-top: 0 !important;
        padding-top: 24px;
        margin-bottom: 32px;
        z-index: 15;
        box-sizing: border-box;
    }}
    .planet-highlights-inner {{
        max-width: 1260px;
        margin: 0 auto;
        padding: 0 2rem;
        box-sizing: border-box;
    }}
    .planet-highlights-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }}
    .planet-feat-card {{
        position: relative;
        height: 210px;
        border-radius: 10px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 16px;
        text-decoration: none !important;
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45);
        transition: transform 0.25s ease, box-shadow 0.25s ease, filter 0.25s ease, border-color 0.25s ease;
        box-sizing: border-box;
        cursor: pointer;
    }}
    .planet-feat-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.65);
        filter: brightness(1.10);
        border-color: rgba(255, 255, 255, 0.35);
    }}
    .card-optical {{
        background-color: #0c1527;
        background-image: 
            linear-gradient(to top, rgba(3, 7, 18, 0.95) 0%, rgba(3, 7, 18, 0.45) 55%, rgba(3, 7, 18, 0.15) 100%),
            url('{img_opt_url}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    .card-change {{
        background-color: #170b16;
        background-image: 
            linear-gradient(to top, rgba(3, 7, 18, 0.95) 0%, rgba(3, 7, 18, 0.45) 55%, rgba(3, 7, 18, 0.15) 100%),
            url('{img_chg_url}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    .card-fusion {{
        background-color: #18151c;
        background-image: 
            linear-gradient(to top, rgba(3, 7, 18, 0.95) 0%, rgba(3, 7, 18, 0.45) 55%, rgba(3, 7, 18, 0.15) 100%),
            url('{img_sar_url}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    .card-lora {{
        background-color: #140b24;
        background-image: 
            linear-gradient(to top, rgba(3, 7, 18, 0.95) 0%, rgba(3, 7, 18, 0.45) 55%, rgba(3, 7, 18, 0.15) 100%),
            url('{img_lor_url}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}
    .planet-card-badge-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .planet-card-tag {{
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.64rem;
        font-weight: 700;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        backdrop-filter: blur(4px);
    }}
    .tag-cyan {{
        background: rgba(29, 111, 216, 0.92);
        color: #ffffff;
        box-shadow: 0 0 10px rgba(37, 99, 235, 0.40);
    }}
    .tag-rose {{
        background: rgba(244, 63, 94, 0.90);
        color: #ffffff;
        box-shadow: 0 0 8px rgba(244, 63, 94, 0.4);
    }}
    .tag-amber {{
        background: rgba(245, 158, 11, 0.90);
        color: #ffffff;
        box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
    }}
    .tag-purple {{
        background: rgba(168, 85, 247, 0.90);
        color: #ffffff;
        box-shadow: 0 0 8px rgba(168, 85, 247, 0.4);
    }}
    .planet-card-content {{
        display: flex;
        flex-direction: column;
    }}
    .planet-card-title {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 4px;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
        letter-spacing: -0.01em;
    }}
    .planet-card-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        color: #cbd5e1;
        line-height: 1.4;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.85);
    }}
    @media (max-width: 960px) {{
        .planet-highlights-wrap {{
            margin-top: -24px;
        }}
        .planet-highlights-grid {{
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
        }}
    }}
    @media (max-width: 520px) {{
        .planet-highlights-wrap {{
            margin-top: -16px;
        }}
        .planet-highlights-inner {{
            padding: 0 1rem;
        }}
        .planet-highlights-grid {{
            grid-template-columns: 1fr;
            gap: 12px;
        }}
        .planet-feat-card {{
            height: 170px;
        }}
    }}

    /* =====================================================================
       CLEAN 2-SECTION PIPELINE ARCHITECTURE (REFERENCE LAYOUT STYLE)
       Section A: 4-Stage Cards Grid (Calm, Minimal, Paragraph Text)
       Section B: Numbered Flow Row (Flat Circles, Thin Connectors)
       ===================================================================== */
    .pipeline-section-clean {{
        width: 100%;
        margin-top: 20px;
        margin-bottom: 36px;
    }}

    /* Section Headers */
    .pipeline-section-header {{
        margin-bottom: 24px;
    }}
    .pipeline-section-header.flow-header {{
        margin-top: 52px;
        margin-bottom: 24px;
    }}
    .pipeline-section-kicker {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #60A5FA;
        margin-bottom: 6px;
    }}
    .pipeline-section-heading {{
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 1.50rem;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.02em;
        margin-top: 0;
        margin-bottom: 8px;
        line-height: 1.25;
    }}
    .pipeline-section-subheading {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.88rem;
        color: #94A3B8;
        line-height: 1.55;
        max-width: 780px;
        margin: 0;
    }}

    /* Section A: 4 Stage Cards Grid */
    .stage-cards-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 18px;
        width: 100%;
    }}
    .stage-clean-card {{
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 10px;
        padding: 18px 18px 16px;
        display: flex;
        flex-direction: column;
        transition: border-color 0.2s ease, background 0.2s ease;
    }}
    .stage-clean-card:hover {{
        border-color: rgba(59, 130, 246, 0.40);
        background: rgba(15, 23, 42, 0.75);
    }}
    .stage-card-icon {{
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: rgba(59, 130, 246, 0.10);
        border: 1px solid rgba(59, 130, 246, 0.30);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 12px;
    }}
    .stage-card-title {{
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.015em;
        margin-bottom: 3px;
        line-height: 1.25;
    }}
    .stage-card-label {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.62rem;
        font-weight: 600;
        color: #94A3B8;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }}
    .stage-card-body {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.81rem;
        color: #94A3B8;
        line-height: 1.5;
        margin: 0;
    }}

    /* Section B: Horizontal Numbered Flow Row */
    .flow-row-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(15, 23, 42, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 22px 26px;
        width: 100%;
        box-sizing: border-box;
    }}
    .flow-step-item {{
        display: flex;
        align-items: center;
        gap: 14px;
        flex: 1;
        min-width: 0;
    }}
    .flow-step-circle {{
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: rgba(59, 130, 246, 0.12);
        border: 1.5px solid #3B82F6;
        color: #60A5FA;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.90rem;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .flow-step-content {{
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
    }}
    .flow-step-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.90rem;
        font-weight: 700;
        color: #F8FAFC;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .flow-step-subtitle {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.73rem;
        color: #94A3B8;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .flow-step-connector {{
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 14px;
        flex-shrink: 0;
        gap: 2px;
    }}
    .flow-connector-line {{
        width: 36px;
        height: 1px;
        background: rgba(255, 255, 255, 0.15);
    }}
    .flow-connector-arrow {{
        color: #64748B;
        flex-shrink: 0;
    }}

    /* Responsive Stacking */
    @media (max-width: 1024px) {{
        .stage-cards-grid {{
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
        }}
        .flow-row-container {{
            flex-direction: column;
            align-items: flex-start;
            gap: 16px;
            padding: 20px;
        }}
        .flow-step-connector {{
            display: none;
        }}
    }}
    @media (max-width: 640px) {{
        .stage-cards-grid {{
            grid-template-columns: 1fr;
        }}
    }}

    /* Full Bleed Tech Ticker Strip (Aerospace Telemetry Palette: Dark Navy + Muted Steel-Blue Accent) */
    .tech-ticker-wrap {{
        width: 100vw !important;
        position: relative !important;
        left: 50% !important;
        right: auto !important;
        margin-left: -50vw !important;
        margin-right: 0 !important;
        width: 100cqw !important;
        max-width: 100cqw !important;
        margin-left: -50cqw !important;
        box-sizing: border-box !important;
        background: {"#080c14" if is_dark else "#f1f5f9"} !important;
        border-top: 1px solid {"rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.08)"} !important;
        border-bottom: 1px solid {"rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.08)"} !important;
        overflow: hidden !important;
        white-space: nowrap !important;
        padding: 12px 0 !important;
        margin-top: 4px !important;
        margin-bottom: 34px !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 2px 10px rgba(0, 0, 0, 0.25) !important;
        z-index: 10;
    }}
    div[data-testid="stElementContainer"]:has(.tech-ticker-wrap),
    .element-container:has(.tech-ticker-wrap),
    div[data-testid="stMarkdownContainer"]:has(.tech-ticker-wrap) {{
        width: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }}
    @keyframes ticker {{
        0% {{ transform: translate3d(0, 0, 0); }}
        100% {{ transform: translate3d(-50%, 0, 0); }}
    }}
    .tech-ticker-track {{
        display: inline-flex;
        animation: ticker 32s linear infinite;
        will-change: transform;
    }}
    .tech-ticker-track:hover {{
        animation-play-state: paused;
    }}
    .ticker-item {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.80rem;
        font-weight: 600;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: {"#7E99B8" if is_dark else "#3B6998"};
        padding: 0 18px;
        white-space: nowrap;
        transition: color 0.15s ease;
    }}
    .ticker-item:hover {{
        color: {"#F1F5F9" if is_dark else "#0F172A"};
    }}
    .ticker-sep {{
        color: {"rgba(126, 153, 184, 0.40)" if is_dark else "rgba(59, 105, 152, 0.40)"};
        font-size: 0.68rem;
        vertical-align: middle;
    }}

    /* Sidebar Precision Instrumentation */
    [data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding-top: 1.5rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
    }}

    /* Technical Telemetry Banner */
    .telemetry-banner {{
        background: var(--bg-panel);
        border: 1px solid var(--border-color);
        border-left: 4px solid var(--accent-primary);
        border-radius: 2px;
        padding: 22px 24px;
        margin-bottom: 24px;
    }}
    .telemetry-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--status-tag-text);
        background: var(--status-tag-bg);
        border: 1px solid var(--status-tag-border);
        padding: 2px 8px;
        border-radius: 2px;
        display: inline-block;
        margin-bottom: 10px;
    }}
    .telemetry-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        margin: 0 0 8px 0;
        color: var(--text-primary);
    }}
    .telemetry-desc {{
        font-family: 'Inter', sans-serif;
        color: var(--text-secondary);
        font-size: 0.95rem;
        line-height: 1.5;
        max-width: 860px;
        margin: 0;
    }}

    /* Section Headers */
    .section-header-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--text-primary);
        background: var(--bg-panel);
        border: 1px solid var(--border-color);
        border-left: 3px solid var(--accent-primary);
        padding: 8px 14px;
        margin: 28px 0 16px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    /* Sub-Headers */
    .tile-sub-title {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-primary);
        margin-bottom: 2px;
    }}
    .tile-sub-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        margin-bottom: 8px;
    }}

    /* Section Titles and Card Headers */
    /* Aerospace Product Clean UI: Ingestion & Mission Directives (Planet / ESA / NASA JPL Eyes standard) */
    .ingestion-hero-banner {{
        position: relative;
        background-color: #0b1220;
        background-image: 
            linear-gradient(135deg, rgba(7, 11, 20, 0.95) 0%, rgba(10, 16, 28, 0.90) 55%, rgba(15, 23, 42, 0.85) 100%),
            url('{img_opt_url}');
        background-size: cover;
        background-position: center;
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 12px;
        padding: 28px 32px 24px;
        margin-bottom: 32px;
        overflow: hidden;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
        scroll-margin-top: 88px !important;
    }}
    .hud-step-header {{
        position: relative;
        margin-bottom: 24px;
        padding-bottom: 4px;
        scroll-margin-top: 88px !important;
    }}
    .hud-scanline {{
        display: none !important;
    }}
    .ref-section-kicker {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #60A5FA;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .section-kicker-pill {{
        display: inline-block;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #60A5FA;
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.25);
        padding: 2px 7px;
        border-radius: 4px;
        margin-right: 4px;
    }}
    .hud-dot, .hud-bracket {{
        display: none !important;
    }}
    .hud-step-num {{
        color: #60A5FA;
        font-weight: 700;
    }}
    .ref-section-title {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: 1.55rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 8px;
        letter-spacing: -0.01em;
    }}
    .ref-section-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.90rem;
        color: var(--text-secondary);
        margin-bottom: 18px;
        line-height: 1.6;
        max-width: 820px;
    }}
    .hud-telemetry-row {{
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 14px;
        margin-top: 22px;
        padding: 13px 20px;
        background: rgba(6, 10, 19, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 1px solid rgba(96, 165, 250, 0.35);
        border-radius: 12px;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.5), 0 2px 8px rgba(0, 0, 0, 0.25);
    }}
    .hud-telemetry-meta {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.80rem;
        color: #94A3B8;
        display: flex;
        align-items: center;
        gap: 14px;
        flex-wrap: wrap;
        margin: 0;
        width: 100%;
    }}
    .hud-telemetry-tag {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.30);
        padding: 3px 10px;
        border-radius: 9999px;
        color: #34D399;
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }}
    .telemetry-live-dot {{
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background-color: #10B981;
        box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
    }}
    .telemetry-item {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}
    .telemetry-label {{
        color: #94A3B8;
        font-weight: 500;
    }}
    .telemetry-val {{
        color: #FFFFFF;
        font-weight: 600;
    }}
    .telemetry-sep {{
        color: rgba(255, 255, 255, 0.25);
        user-select: none;
    }}
    .hud-telemetry-ticks, .hud-tick {{
        display: none !important;
    }}

    /* Decorative Corner Brackets Removed */
    .hud-corner-tl, .hud-corner-tr, .hud-corner-bl, .hud-corner-br {{
        display: none !important;
    }}

    /* Tile Card Headers - Clean Solid Dark Aerospace Slate (No thumbnail image artifacts) */
    .tile-header-banner {{
        position: relative;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 14px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.30);
        background-color: #0B111E;
        background-image: linear-gradient(180deg, rgba(17, 24, 39, 0.65) 0%, rgba(11, 17, 30, 0.95) 100%);
    }}
    .tile-banner-a {{
        border-left: 3px solid #3B82F6;
    }}
    .tile-banner-b {{
        border-left: 3px solid #0D9488;
    }}
    .ref-card-header {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.98rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        letter-spacing: -0.01em;
    }}
    .ref-card-desc {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.82rem;
        color: var(--text-secondary);
        margin: 6px 0 0 0;
        line-height: 1.5;
    }}

    /* Chip & Dynamic Status Badges (Enhanced Contrast) */
    .hud-chip-tag {{
        display: none !important;
    }}
    .hud-status-tag {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.76rem;
        font-weight: 500;
        letter-spacing: 0.02em;
        padding: 4px 11px;
        border-radius: 9999px;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        text-transform: none;
    }}
    .tag-standby {{
        color: #E2E8F0;
        background: rgba(148, 163, 184, 0.14);
        border: 1px solid rgba(226, 232, 240, 0.28);
    }}
    .tag-active {{
        color: #34D399;
        background: rgba(16, 185, 129, 0.14);
        border: 1px solid rgba(52, 211, 153, 0.35);
    }}
    .hud-status-dot {{
        width: 6px;
        height: 6px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }}
    .dot-standby {{
        background: #94A3B8;
        box-shadow: 0 0 5px rgba(148, 163, 184, 0.5);
    }}
    .dot-active {{
        background: #10B981;
        box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
    }}

    /* Drag-and-Drop Zones - Clean Professional Surface */
    [data-testid="stFileUploader"] section {{
        background: rgba(11, 17, 30, 0.60) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.10) !important;
        border-radius: 12px !important;
        padding: 28px 22px !important;
        position: relative !important;
        overflow: hidden !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25) !important;
        transition: border-color 0.2s ease, background 0.2s ease !important;
    }}
    [data-testid="stFileUploader"] section:hover {{
        border-color: rgba(96, 165, 250, 0.45) !important;
        background: rgba(15, 23, 42, 0.75) !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35) !important;
    }}
    [data-testid="stFileUploader"] button {{
        background: rgba(30, 41, 59, 0.75) !important;
        color: #F1F5F9 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        padding: 8px 18px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.20) !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stFileUploader"] button:hover {{
        border-color: rgba(96, 165, 250, 0.50) !important;
        color: #FFFFFF !important;
        background: rgba(51, 65, 85, 0.90) !important;
    }}

    /* Clean Aerospace Preset Buttons */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: rgba(15, 23, 42, 0.60) !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.86rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.01em !important;
        text-transform: none !important;
        padding: 11px 18px !important;
        width: 100% !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.20) !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: rgba(30, 41, 59, 0.85) !important;
        color: #FFFFFF !important;
        border-color: rgba(96, 165, 250, 0.45) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.30) !important;
    }}

    /* Focused Clean Text Input Field */
    [data-testid="stTextInput"] input {{
        background: rgba(11, 17, 30, 0.70) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.92rem !important;
        padding: 13px 16px !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.30) !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18), inset 0 1px 3px rgba(0, 0, 0, 0.20) !important;
        background: rgba(15, 23, 42, 0.90) !important;
    }}

    /* Clean Authoritative Primary Action Button */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: linear-gradient(135deg, #2563EB 0%, #0284C7 50%, #0D9488 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.20) !important;
        border-radius: 8px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
        text-transform: none !important;
        padding: 14px 28px !important;
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.30) !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        background: linear-gradient(135deg, #1D4ED8 0%, #0369A1 50%, #0F766E 100%) !important;
        border-color: rgba(255, 255, 255, 0.30) !important;
        box-shadow: 0 6px 22px rgba(37, 99, 235, 0.45) !important;
        transform: translateY(-1px) !important;
    }}

    /* NASA Eye Telemetry Status Cards */
    .telemetry-status-card {{
        background: rgba(12, 18, 28, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 12px;
        padding: 18px 22px;
        margin: 14px 0 20px;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }}
    .status-card-warn {{
        border-left: 4px solid #f59e0b;
        background: linear-gradient(90deg, rgba(245, 158, 11, 0.08) 0%, rgba(12, 18, 28, 0.75) 100%);
    }}
    .status-card-error {{
        border-left: 4px solid #ef4444;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.08) 0%, rgba(12, 18, 28, 0.75) 100%);
    }}
    .telemetry-status-icon-warn {{
        width: 38px;
        height: 38px;
        border-radius: 8px;
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.30);
        color: #f59e0b;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .telemetry-status-icon-error {{
        width: 38px;
        height: 38px;
        border-radius: 8px;
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.30);
        color: #ef4444;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}

    /* LED Indicators */
    .telemetry-led {{
        width: 7px;
        height: 7px;
        border-radius: 1px;
        display: inline-block;
        margin-right: 6px;
    }}
    .led-green {{
        background-color: #10b981;
        box-shadow: 0 0 5px #10b981;
    }}
    .led-red {{
        background-color: #ef4444;
        box-shadow: 0 0 5px #ef4444;
    }}
    .led-amber {{
        background-color: #f59e0b;
        box-shadow: 0 0 5px #f59e0b;
    }}

    /* Metric Panels */
    [data-testid="stMetric"] {{
        background: var(--metric-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        padding: 12px 16px !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--text-secondary) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.70rem !important;
        letter-spacing: 0.10em !important;
        text-transform: uppercase !important;
    }}
    [data-testid="stMetricValue"] {{
        font-family: 'Space Grotesk', monospace !important;
        color: var(--metric-value) !important;
        font-size: 1.55rem !important;
        font-weight: 700 !important;
    }}

    /* Synthesized Intelligence Output Panel */
    .result-terminal {{
        background: var(--result-bg);
        border: 1px solid var(--result-border);
        border-left: 3px solid var(--accent-primary);
        border-radius: 2px;
        padding: 18px 20px;
        margin: 16px 0;
    }}
    .result-terminal-header {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent-primary);
        margin-bottom: 8px;
    }}
    .result-terminal-body {{
        font-family: 'Inter', sans-serif;
        font-size: 0.98rem;
        line-height: 1.6;
        color: var(--text-primary);
    }}

    /* Mission Chat Console & Conversation Stream (Aerospace Dark Navy Spec) */
    .chat-console-header {{
        margin-top: 24px;
        margin-bottom: 20px;
    }}
    /* State 1: Minimal Call-to-Action Card */
    .chat-cta-card {{
        background: linear-gradient(135deg, rgba(12, 18, 28, 0.85) 0%, rgba(8, 12, 19, 0.95) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 38px 28px;
        text-align: center;
        margin: 14px 0 24px 0;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
    }}
    .chat-cta-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.45rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.02em;
        margin-bottom: 8px;
    }}
    .chat-cta-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        color: var(--text-secondary);
        max-width: 580px;
        margin: 0 auto 22px auto;
        line-height: 1.55;
    }}
    .chat-conversation-stream {{
        display: flex;
        flex-direction: column;
        gap: 18px;
        margin-bottom: 28px;
        min-height: 200px;
    }}
    /* z.ai-style Empty State: Large elegant serif display heading & simple muted subtitle */
    .zai-empty-state-header {{
        text-align: center !important;
        margin: 18px auto 26px auto !important;
        max-width: 760px !important;
        padding: 0 16px !important;
    }}
    .zai-empty-heading {{
        font-family: 'Playfair Display', Georgia, 'Times New Roman', serif !important;
        font-size: 2.75rem !important;
        font-weight: 600 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.025em !important;
        line-height: 1.2 !important;
        text-align: center !important;
        margin: 0 auto 12px auto !important;
    }}
    @media (max-width: 768px) {{
        .zai-empty-heading {{
            font-size: 2.05rem !important;
        }}
    }}
    .zai-empty-subtitle {{
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.96rem !important;
        font-weight: 400 !important;
        color: #94A3B8 !important;
        text-align: center !important;
        margin: 0 auto !important;
        letter-spacing: -0.01em !important;
        line-height: 1.5 !important;
    }}
    .chat-empty-state {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 10px 20px 8px 20px !important;
        text-align: center !important;
        margin: 0 auto !important;
        max-width: 620px !important;
    }}
    .chat-row {{
        display: flex;
        width: 100%;
        margin-bottom: 4px;
    }}
    .user-row {{
        justify-content: flex-end;
    }}
    .ai-row {{
        justify-content: flex-start;
    }}
    .chat-bubble {{
        max-width: 84%;
        border-radius: 12px;
        padding: 16px 20px;
        box-sizing: border-box;
        transition: border-color 0.2s ease;
    }}
    [data-testid="stChatMessage"] {{
        background: rgba(15, 23, 42, 0.70) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(8px);
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
        border-color: rgba(59, 130, 246, 0.3) !important;
        background: linear-gradient(135deg, rgba(20, 30, 48, 0.85) 0%, rgba(12, 18, 28, 0.85) 100%) !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
        border-left: 3px solid #1D6FD8 !important;
        background: rgba(12, 17, 24, 0.85) !important;
    }}
    .user-bubble {{
        background: linear-gradient(135deg, rgba(20, 30, 48, 0.95) 0%, rgba(12, 18, 28, 0.95) 100%);
        border: 1px solid rgba(126, 153, 184, 0.35);
        color: #F8FAFC;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
    }}
    .ai-bubble {{
        background: rgba(12, 17, 24, 0.90);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-left: 3px solid #1D6FD8;
        color: var(--text-primary);
        width: 100%;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.30);
    }}
    .ai-bubble-rejection {{
        border-left: 3px solid #EF4444 !important;
        background: rgba(239, 68, 68, 0.08) !important;
    }}
    .rejection-badge-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }}
    .ai-rejection-msg {{
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        color: #EF4444;
        line-height: 1.5;
    }}
    .chat-bubble-text {{
        font-family: 'Inter', sans-serif;
        font-size: 0.96rem;
        line-height: 1.55;
        word-break: break-word;
    }}
    .chat-bubble-meta {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.70rem;
        color: var(--text-muted);
        margin-top: 8px;
        text-align: right;
    }}
    .msg-imgs-wrap {{
        display: flex;
        gap: 8px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }}
    .msg-img-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 6px;
        padding: 4px 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.74rem;
        color: #CBD5E1;
    }}
    .msg-img-thumb {{
        width: 26px;
        height: 26px;
        border-radius: 4px;
        object-fit: cover;
    }}
    .ai-bubble-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 12px;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        flex-wrap: wrap;
        gap: 8px;
    }}
    .chat-conf-pill {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: #7E99B8;
        background: rgba(126, 153, 184, 0.10);
        padding: 2px 8px;
        border-radius: 4px;
    }}
    .chat-record-pill {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.74rem;
        color: var(--text-muted);
    }}
    .ai-bubble-answer {{
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        line-height: 1.6;
        color: var(--text-primary);
        white-space: pre-wrap;
    }}

    /* Compact Pill-Shaped Preset Suggestion Tabs */
    div[class*="st-key-preset_pill_"] > button,
    div[data-testid="stButton"] > button[key^="preset_pill_"],
    button[data-testid*="preset_pill_"] {{
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 9999px !important;
        color: #94A3B8 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.80rem !important;
        font-weight: 500 !important;
        padding: 5px 16px !important;
        height: 34px !important;
        min-height: 34px !important;
        width: 100% !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
    }}
    /* =====================================================================
       Z.AI Style Preset Suggestion Pills (Compact, rounded-full, natural spacing)
       ===================================================================== */
    div[class*="preset_pill_"] > button,
    div[data-testid="stButton"] > button[key*="preset_pill_"] {{
        border-radius: 9999px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.80rem !important;
        font-weight: 500 !important;
        padding: 5px 16px !important;
        height: 32px !important;
        min-height: 32px !important;
        width: 100% !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        transition: all 0.2s ease !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
    }}
    /* Selected Preset Pill: filled / darker background */
    div[class*="_sel"] > button,
    div[data-testid="stButton"] > button[key*="_sel"] {{
        background: #1E293B !important;
        border: 1px solid rgba(255, 255, 255, 0.28) !important;
        color: #F8FAFC !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35) !important;
    }}
    /* Outlined / Muted Preset Pills */
    div[class*="_idle"] > button,
    div[data-testid="stButton"] > button[key*="_idle"] {{
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #94A3B8 !important;
    }}
    div[class*="_idle"] > button:hover,
    div[data-testid="stButton"] > button[key*="_idle"]:hover {{
        background: rgba(255, 255, 255, 0.06) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
        color: #F8FAFC !important;
        transform: translateY(-1px) !important;
    }}

    /* =====================================================================
       Elevated Dark Input Card (Theme-Harmonized Floating Bar)
       ===================================================================== */
    .chat-engine-tag-bar {{
        max-width: 760px;
        margin: 0 auto 10px auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 8px;
    }}
    .chat-engine-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 600;
        color: #60A5FA;
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.35);
        border-radius: 9999px;
        padding: 3px 10px;
        letter-spacing: 0.04em;
    }}
    .chat-engine-dot {{
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #3B82F6;
        box-shadow: 0 0 6px rgba(59, 130, 246, 0.6);
        display: inline-block;
    }}
    .chat-engine-models {{
        font-family: 'Inter', sans-serif;
        font-size: 0.76rem;
        color: #94A3B8;
        letter-spacing: -0.01em;
    }}
    [data-testid="stChatInput"] {{
        max-width: 760px !important;
        margin: 0 auto !important;
        border-radius: 22px !important;
        background: #0F172A !important;
        border: 1px solid rgba(245, 158, 11, 0.28) !important;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.55), 0 2px 8px rgba(0, 0, 0, 0.35) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        padding: 12px 16px 10px 16px !important;
        position: relative !important;
    }}
    [data-testid="stChatInput"]:focus-within {{
        border-color: rgba(245, 158, 11, 0.65) !important;
        box-shadow: 0 16px 44px rgba(0, 0, 0, 0.65), 0 0 18px rgba(245, 158, 11, 0.20) !important;
        background: #111C33 !important;
    }}
    [data-testid="stChatInput"] > div {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        align-items: flex-end !important;
    }}
    [data-testid="stChatInput"] textarea {{
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.98rem !important;
        font-weight: 400 !important;
        color: #F8FAFC !important;
        background: transparent !important;
        line-height: 1.55 !important;
        padding: 6px 12px 6px 8px !important;
        min-height: 44px !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: #94A3B8 !important;
        font-size: 0.96rem !important;
        font-weight: 400 !important;
    }}
    /* Seamless Attach Button (Left) */
    [data-testid="stChatInputFileUploadButton"] {{
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 50% !important;
        width: 34px !important;
        height: 34px !important;
        min-width: 34px !important;
        color: #CBD5E1 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.15s ease !important;
        box-shadow: none !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stChatInputFileUploadButton"]:hover {{
        background: rgba(245, 158, 11, 0.18) !important;
        border-color: rgba(245, 158, 11, 0.50) !important;
        color: #FBBF24 !important;
        transform: scale(1.05) !important;
    }}
    [data-testid="stChatInputFileUploadButton"] svg {{
        width: 17px !important;
        height: 17px !important;
        stroke: #CBD5E1 !important;
    }}
    /* Context / Globe Icon next to attach button */
    [data-testid="stChatInputFileUploadButton"]::after {{
        content: "";
        display: inline-block;
        width: 18px;
        height: 18px;
        margin-left: 10px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%2394A3B8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'%3E%3C/circle%3E%3Cline x1='2' y1='12' x2='22' y2='12'%3E%3C/line%3E%3Cpath d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'%3E%3C/path%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
        cursor: default;
        opacity: 0.85;
    }}
    /* Circular Blue Send Button with Up-Arrow (Right) */
    [data-testid="stChatInputSubmitButton"] {{
        background: #1D6FD8 !important;
        border: none !important;
        border-radius: 50% !important;
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 10px rgba(29, 111, 216, 0.40) !important;
        transition: all 0.18s ease !important;
        margin-bottom: 2px !important;
    }}
    [data-testid="stChatInputSubmitButton"]:hover {{
        background: #3B82F6 !important;
        transform: scale(1.06) !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.55) !important;
    }}
    [data-testid="stChatInputSubmitButton"] svg {{
        fill: #FFFFFF !important;
        stroke: #FFFFFF !important;
        width: 16px !important;
        height: 16px !important;
    }}
    /* Uploaded Files Chips inside dark box */
    [data-testid="stChatInputFile"] {{
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
    }}
    [data-testid="stChatInputFileName"] {{
        color: #F8FAFC !important;
        font-weight: 500 !important;
    }}

    /* =====================================================================
       Z.AI Style Preview Thumbnail Cards (2 Columns)
       ===================================================================== */
    .chat-previews-container {{
        max-width: 760px;
        margin: 20px auto 0 auto;
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }}
    @media (max-width: 768px) {{
        .chat-previews-container {{
            grid-template-columns: 1fr;
        }}
    }}
    .chat-preview-card {{
        position: relative;
        height: 106px;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #1E293B;
        background: #0B111E;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
        transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
    }}
    .chat-preview-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(245, 158, 11, 0.50);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
    }}
    .chat-preview-img {{
        width: 100%;
        height: 100%;
        background-size: cover;
        background-position: center;
        transition: transform 0.3s ease;
    }}
    .chat-preview-card:hover .chat-preview-img {{
        transform: scale(1.05);
    }}
    .chat-preview-overlay {{
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 24px 12px 10px 12px;
        background: linear-gradient(180deg, transparent 0%, rgba(8, 13, 23, 0.85) 55%, rgba(8, 13, 23, 0.98) 100%);
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
    }}
    .chat-preview-title {{
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        color: #F8FAFC;
        line-height: 1.25;
        margin-bottom: 2px;
    }}
    .chat-preview-sub {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        color: #94A3B8;
        letter-spacing: -0.01em;
    }}
    button[kind="primaryFormSubmit"],
    button[data-testid="stBaseButton-primaryFormSubmit"] {{
        background: var(--btn-primary-bg) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.20) !important;
        border-radius: 8px !important;
        height: 44px !important;
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 10px rgba(29, 111, 216, 0.35) !important;
        line-height: 1 !important;
    }}
    button[kind="primaryFormSubmit"]:hover,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
        background: var(--btn-primary-hover) !important;
        box-shadow: 0 4px 16px rgba(29, 111, 216, 0.50) !important;
        transform: translateY(-1px) !important;
    }}
    button[kind="primaryFormSubmit"]:disabled,
    button[data-testid="stBaseButton-primaryFormSubmit"]:disabled {{
        opacity: 0.40 !important;
        cursor: not-allowed !important;
        box-shadow: none !important;
        transform: none !important;
    }}
    /* Preset Chips Buttons */
    [data-testid="stHorizontalBlock"]:has(button[key^="preset_"]) button {{
        background: rgba(15, 23, 42, 0.70) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        color: #94A3B8 !important;
        border-radius: 9999px !important;
        padding: 5px 16px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.80rem !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
        white-space: nowrap !important;
    }}
    [data-testid="stHorizontalBlock"]:has(button[key^="preset_"]) button:hover {{
        border-color: rgba(56, 189, 248, 0.50) !important;
        color: #F8FAFC !important;
        background: rgba(30, 41, 59, 0.85) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    }}

    /* Clean Sidebar Styling */
    .ref-sidebar-kicker {{
        font-family: 'Inter', sans-serif;
        font-size: 0.70rem;
        font-weight: 700;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-top: 14px;
        margin-bottom: 8px;
    }}
    .ref-status-pill {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 12px;
    }}
    .status-pill-online {{
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #10b981;
    }}
    .status-pill-offline {{
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #ef4444;
    }}
    .ref-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }}
    .ref-dot-green {{
        background: #10b981;
        box-shadow: 0 0 6px #10b981;
    }}
    .ref-dot-red {{
        background: #ef4444;
        box-shadow: 0 0 6px #ef4444;
    }}

    /* Clean Expanders */
    div[data-testid="stExpander"] {{
        background: var(--hero-card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        transition: border-color 0.15s ease !important;
    }}
    div[data-testid="stExpander"]:hover {{
        border-color: var(--accent-primary) !important;
    }}
    div[data-testid="stExpander"] > details > summary {{
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        padding: 10px 14px !important;
    }}

    /* Action Links & Download Buttons */
    div[data-testid="stDownloadButton"] > button {{
        background: var(--btn-secondary-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 8px 16px !important;
        transition: all 0.15s ease !important;
    }}
    div[data-testid="stDownloadButton"] > button:hover {{
        border-color: var(--accent-primary) !important;
        color: var(--accent-primary) !important;
    }}

    a[data-testid="stLinkButton"] {{
        background: var(--btn-secondary-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.80rem !important;
        font-weight: 600 !important;
        padding: 6px 12px !important;
        transition: all 0.15s ease !important;
    }}
    a[data-testid="stLinkButton"]:hover {{
        border-color: var(--accent-primary) !important;
        color: var(--accent-primary) !important;
    }}

    /* Upload Cards Responsive Stacking */
    @media (max-width: 768px) {{
        [data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"]) {{
            flex-direction: column !important;
            gap: 16px !important;
        }}
        [data-testid="stHorizontalBlock"]:has([data-testid="stFileUploader"]) > [data-testid="column"] {{
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }}
    }}

    /* Preset Chips Responsive Stacking */
    @media (max-width: 640px) {{
        [data-testid="stHorizontalBlock"]:has(button[key^="preset_"]),
        [data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) {{
            flex-direction: column !important;
            gap: 8px !important;
        }}
        [data-testid="stHorizontalBlock"]:has(button[key^="preset_"]) > [data-testid="column"],
        [data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) > [data-testid="column"] {{
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }}
    }}

    /* Ticker Strip Responsive Adjustments */
    @media (max-width: 768px) {{
        .ticker-item {{
            font-size: 0.72rem !important;
            padding: 0 14px !important;
        }}
        .tech-ticker-wrap {{
            padding: 10px 0 !important;
            margin-bottom: 22px !important;
        }}
    }}

    /* History Entry Card (Responsive & Overflow-Safe) */
    .ref-history-card {{
        background: var(--hero-card-bg);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
    }}
    .ref-history-card:hover {{
        border-color: var(--accent-primary);
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.10);
    }}
    .ref-history-query {{
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 6px 0;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
    }}
    .ref-history-meta {{
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}
    @media (max-width: 640px) {{
        .ref-history-card {{
            padding: 14px 14px !important;
        }}
        .ref-history-meta {{
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 4px !important;
        }}
        [data-testid="stHorizontalBlock"]:has([data-testid="stLinkButton"]) {{
            flex-direction: column !important;
            gap: 8px !important;
        }}
        [data-testid="stHorizontalBlock"]:has([data-testid="stLinkButton"]) > [data-testid="column"] {{
            width: 100% !important;
            min-width: 100% !important;
        }}
    }}
    .ref-task-badge {{
        display: inline-block;
        background: var(--status-tag-bg);
        color: var(--status-tag-text);
        border: 1px solid var(--status-tag-border);
        font-family: 'Inter', sans-serif;
        font-size: 0.70rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 9999px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        white-space: nowrap;
    }}

    /* Reference Footer Styles (Fully Responsive) */
    /* Planet.com Reference Footer Styles */
    .ref-footer-wrap {{
        width: 100vw;
        position: relative;
        left: 50%;
        right: 50%;
        margin-left: -50vw;
        margin-right: -50vw;
        background: #060910;
        border-top: 1px solid var(--border-color);
        padding: 56px 0 32px;
        margin-top: 64px;
        overflow: hidden;
        box-sizing: border-box;
    }}
    .footer-bg-orbital {{
        position: absolute;
        right: -70px;
        bottom: -50px;
        width: 620px;
        height: 620px;
        pointer-events: none;
        opacity: 0.16;
        z-index: 0;
        color: #2dd4bf;
    }}
    @media (max-width: 900px) {{
        .footer-bg-orbital {{
            width: 440px;
            height: 440px;
            right: -40px;
            bottom: -30px;
            opacity: 0.12;
        }}
    }}
    .ref-footer-inner {{
        max-width: 1260px;
        margin: 0 auto;
        padding: 0 2rem;
        position: relative;
        box-sizing: border-box;
    }}
    @media (max-width: 768px) {{
        .ref-footer-inner {{
            padding: 0 1.25rem !important;
        }}
    }}
    .ref-footer-strip,
    .ref-footer-grid,
    .ref-footer-divider,
    .ref-footer-bottom {{
        position: relative;
        z-index: 2;
    }}
    .ref-footer-strip {{
        background: rgba(12, 17, 24, 0.85);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 44px;
        backdrop-filter: blur(8px);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
    }}
    @media (max-width: 768px) {{
        .ref-footer-strip {{
            flex-direction: column !important;
            gap: 16px !important;
            align-items: flex-start !important;
        }}
        .ref-footer-input {{
            width: 100% !important;
        }}
    }}
    .ref-footer-input {{
        background: var(--bg-input);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        color: var(--text-primary);
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        padding: 8px 14px;
        width: 240px;
        outline: none;
        transition: border-color 0.15s ease;
    }}
    .ref-footer-input:focus {{
        border-color: var(--accent-primary);
    }}
    .ref-footer-grid {{
        display: grid;
        grid-template-columns: 1.8fr 1fr 1fr 1.1fr 1.1fr;
        gap: 32px;
        margin-bottom: 32px;
    }}
    @media (max-width: 1024px) {{
        .ref-footer-grid {{
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 28px !important;
        }}
    }}
    @media (max-width: 640px) {{
        .ref-footer-grid {{
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 22px !important;
        }}
    }}
    @media (max-width: 440px) {{
        .ref-footer-grid {{
            grid-template-columns: 1fr !important;
            gap: 20px !important;
        }}
    }}
    /* Footer Links & Interactive Elements Reset against Streamlit defaults */
    .ref-footer-wrap a,
    .ref-footer-wrap a:link,
    .ref-footer-wrap a:visited,
    .stMarkdown .ref-footer-wrap a,
    div.stMarkdown .ref-footer-wrap a,
    [data-testid="stMarkdownContainer"] .ref-footer-wrap a {{
        text-decoration: none !important;
        outline: none !important;
    }}

    .ref-footer-col-title {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 16px;
    }}

    /* Column Links */
    a.ref-footer-link,
    .ref-footer-link,
    .ref-footer-wrap a.ref-footer-link,
    .stMarkdown .ref-footer-wrap a.ref-footer-link,
    div.stMarkdown .ref-footer-wrap a.ref-footer-link {{
        display: block !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        color: var(--text-secondary) !important;
        text-decoration: none !important;
        margin-bottom: 10px !important;
        transition: color 0.15s ease, transform 0.15s ease, text-decoration 0.15s ease !important;
    }}
    a.ref-footer-link:hover,
    .ref-footer-link:hover,
    .ref-footer-wrap a.ref-footer-link:hover,
    .stMarkdown .ref-footer-wrap a.ref-footer-link:hover,
    div.stMarkdown .ref-footer-wrap a.ref-footer-link:hover {{
        color: #7E99B8 !important;
        text-decoration: underline !important;
        text-underline-offset: 3px !important;
        transform: translateX(2px) !important;
    }}

    /* GitHub & Swagger Action Chips */
    a.ref-btn-secondary,
    .ref-btn-secondary,
    .ref-footer-wrap a.ref-btn-secondary,
    .stMarkdown .ref-footer-wrap a.ref-btn-secondary {{
        display: inline-flex !important;
        align-items: center !important;
        gap: 4px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.76rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        text-decoration: none !important;
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        padding: 5px 12px !important;
        transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease, transform 0.15s ease !important;
        white-space: nowrap !important;
    }}
    a.ref-btn-secondary:hover,
    .ref-btn-secondary:hover,
    .ref-footer-wrap a.ref-btn-secondary:hover,
    .stMarkdown .ref-footer-wrap a.ref-btn-secondary:hover {{
        color: #7E99B8 !important;
        border-color: rgba(126, 153, 184, 0.45) !important;
        background: rgba(126, 153, 184, 0.08) !important;
        text-decoration: none !important;
        transform: translateY(-1px) !important;
    }}

    /* Connect Action Button */
    a.ref-btn-primary,
    .ref-btn-primary,
    .ref-footer-wrap a.ref-btn-primary,
    .stMarkdown .ref-footer-wrap a.ref-btn-primary {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        color: #ffffff !important;
        text-decoration: none !important;
        background: var(--btn-primary-bg) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25) !important;
        transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease !important;
        white-space: nowrap !important;
    }}
    a.ref-btn-primary:hover,
    .ref-btn-primary:hover,
    .ref-footer-wrap a.ref-btn-primary:hover,
    .stMarkdown .ref-footer-wrap a.ref-btn-primary:hover {{
        background: var(--btn-primary-hover) !important;
        color: #ffffff !important;
        text-decoration: none !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(29, 111, 216, 0.35) !important;
    }}

    .ref-footer-divider {{
        height: 1px;
        background: var(--border-subtle);
        margin: 36px 0 22px;
        border: none;
    }}
    .ref-footer-bottom {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.80rem;
        color: var(--text-muted);
        gap: 16px;
        flex-wrap: wrap;
    }}
    .ref-footer-legal {{
        display: flex;
        align-items: center;
        gap: 14px;
        flex-wrap: wrap;
    }}

    /* Legal Links (Privacy Policy, Terms of Use, Security Notice, Sitemap) */
    a.ref-footer-legal-link,
    .ref-footer-legal-link,
    .ref-footer-wrap a.ref-footer-legal-link,
    .stMarkdown .ref-footer-wrap a.ref-footer-legal-link,
    div.stMarkdown .ref-footer-wrap a.ref-footer-legal-link {{
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.80rem !important;
        color: var(--text-muted) !important;
        text-decoration: none !important;
        transition: color 0.15s ease, text-decoration 0.15s ease !important;
    }}
    a.ref-footer-legal-link:hover,
    .ref-footer-legal-link:hover,
    .ref-footer-wrap a.ref-footer-legal-link:hover,
    .stMarkdown .ref-footer-wrap a.ref-footer-legal-link:hover,
    div.stMarkdown .ref-footer-wrap a.ref-footer-legal-link:hover {{
        color: #7E99B8 !important;
        text-decoration: underline !important;
        text-underline-offset: 3px !important;
    }}

    .ref-footer-socials {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    a.ref-footer-icon-btn,
    .ref-footer-icon-btn,
    .ref-footer-wrap a.ref-footer-icon-btn,
    .stMarkdown .ref-footer-wrap a.ref-footer-icon-btn {{
        width: 32px !important;
        height: 32px !important;
        border-radius: 50% !important;
        border: 1px solid var(--border-color) !important;
        background: rgba(255, 255, 255, 0.03) !important;
        color: var(--text-secondary) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
    }}
    a.ref-footer-icon-btn:hover,
    .ref-footer-icon-btn:hover,
    .ref-footer-wrap a.ref-footer-icon-btn:hover,
    .stMarkdown .ref-footer-wrap a.ref-footer-icon-btn:hover {{
        border-color: rgba(126, 153, 184, 0.40) !important;
        color: #7E99B8 !important;
        background: rgba(126, 153, 184, 0.08) !important;
        transform: translateY(-2px) !important;
    }}
    @media (max-width: 680px) {{
        .ref-footer-bottom {{
            flex-direction: column !important;
            gap: 14px !important;
            align-items: flex-start !important;
        }}
    }}
</style>
""", unsafe_allow_html=True)


# --- Top Navigation Bar (Planet.com Reference Style) ---
navbar_html = f"""<header class="planet-navbar">
<div class="planet-navbar-inner">
<a href="#" class="planet-nav-brand" style="text-decoration: none !important; border-bottom: none !important; outline: none !important;">
<div class="planet-nav-logo">
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="9.5" y="7" width="5" height="10" rx="0.8" fill="#FFFFFF"/>
<rect x="2" y="8" width="5.5" height="8" rx="0.8" fill="#38BDF8"/>
<rect x="16.5" y="8" width="5.5" height="8" rx="0.8" fill="#38BDF8"/>
<line x1="7.5" y1="12" x2="9.5" y2="12" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round"/>
<line x1="14.5" y1="12" x2="16.5" y2="12" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round"/>
<line x1="2" y1="12" x2="7.5" y2="12" stroke="rgba(11, 17, 30, 0.45)" stroke-width="0.8"/>
<line x1="16.5" y1="12" x2="22" y2="12" stroke="rgba(11, 17, 30, 0.45)" stroke-width="0.8"/>
<line x1="12" y1="7" x2="12" y2="3.5" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round"/>
<circle cx="12" cy="3.5" r="1.2" fill="#38BDF8"/>
<circle cx="12" cy="14" r="1.2" fill="#38BDF8"/>
</svg>
</div>
<span class="planet-nav-title" style="text-decoration: none !important;"><span class="nav-brand-sat" style="text-decoration: none !important;">sat</span><span class="nav-brand-query" style="text-decoration: none !important;">query</span><span class="planet-nav-dot" style="text-decoration: none !important;">.</span></span>
</a>
<div class="planet-nav-right">
<a href="#section-audit" class="planet-nav-text-link">History</a>
<a href="#section-ingestion" class="planet-nav-btn-pill">Try Live Demo</a>
<a href="#section-query" class="planet-nav-circle-btn" title="Search Queries & Directives">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="8"></circle>
<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>
</a>
</div>
</div>
</header>"""

st.markdown(navbar_html, unsafe_allow_html=True)


# --- Sidebar: System Diagnostics & Health ---
with st.sidebar:
    theme_label = "☀️ Switch to Light Mode" if is_dark else "🌙 Switch to Dark Mode"
    if st.button(theme_label, key="theme_toggle_btn", use_container_width=True):
        st.session_state.theme = "light" if is_dark else "dark"
        st.rerun()

    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding: 2px 0;">
        <div class="ref-nav-logo" style="width: 28px; height: 28px;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"></circle>
                <path d="m4.93 4.93 4.24 4.24"></path>
                <path d="m14.83 9.17 4.24-4.24"></path>
                <path d="m14.83 14.83 4.24 4.24"></path>
                <path d="m9.17 14.83-4.24 4.24"></path>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>
        </div>
        <div>
            <div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">SatQuery AI</div>
            <div style="font-family: 'Inter', sans-serif; font-size: 0.72rem; color: var(--text-muted);">Control & Diagnostics</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙️ Connection Settings", expanded=False):
        API_URL = st.text_input(
            "Backend API URL",
            value=default_api_url,
            help="Target FastAPI orchestrator endpoint"
        ).rstrip("/")
        if st.button("🧹 Purge Stale Uploads (24h)", key="btn_admin_purge", use_container_width=True):
            try:
                cl_resp = requests.post(f"{API_URL}/admin/cleanup?max_age_hours=24", timeout=5)
                if cl_resp.status_code == 200:
                    st.success("Stale cache and uploads purged.")
                else:
                    st.warning(f"Purge returned status {cl_resp.status_code}")
            except Exception as e:
                st.error(f"Purge error: {e}")

    st.markdown("<div class='ref-sidebar-kicker'>SYSTEM HEALTH</div>", unsafe_allow_html=True)
    
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=3)
        if health_resp.status_code == 200:
            health = health_resp.json()
            st.markdown("""
            <div class="ref-status-pill status-pill-online">
                <span class="ref-dot ref-dot-green"></span>
                <span>Backend Online (200 OK)</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"<div style='font-family: \"Inter\", sans-serif; font-size: 0.82rem; margin-bottom: 6px;'>Database: <strong>{health.get('database', 'Connected')}</strong></div>", unsafe_allow_html=True)
            hw = health.get("hardware", {})
            st.markdown(f"<div style='font-family: \"Inter\", sans-serif; font-size: 0.82rem; margin-bottom: 6px;'>Compute: <strong>{hw.get('device_name', 'Unknown')}</strong> ({hw.get('configured_device', 'cpu')})</div>", unsafe_allow_html=True)
            router_ready = health.get("router_llm_ready", False)
            if router_ready:
                st.markdown("<div style='font-family: \"Inter\", sans-serif; font-size: 0.82rem; margin-bottom: 12px;'>Router LLM: <span class='ref-task-badge'>Ready</span></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-family: \"Inter\", sans-serif; font-size: 0.82rem; margin-bottom: 12px;'>Router LLM: <span style='background: rgba(245, 158, 11, 0.12); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 8px; border-radius: 9999px; font-size: 0.70rem; font-weight: 600;'>Domain Fallback</span></div>", unsafe_allow_html=True)

            try:
                tools_list = health.get("registered_tools", [])
                if tools_list:
                    with st.expander("Active Tool Registry", expanded=False):
                        for tool in tools_list:
                            if isinstance(tool, dict):
                                t_task = tool.get("task", "unknown")
                                t_wrapper = tool.get("model_wrapper") or tool.get("model") or "N/A"
                                st.code(f"{t_task} -> {t_wrapper}", language="bash")
                            else:
                                st.code(str(tool), language="bash")
            except Exception:
                pass
        else:
            st.markdown(f"""
            <div class="ref-status-pill status-pill-offline">
                <span class="ref-dot ref-dot-red"></span>
                <span>HTTP {health_resp.status_code} Degraded</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.markdown(f"""
        <div class="ref-status-pill status-pill-offline">
            <span class="ref-dot ref-dot-red"></span>
            <span>Backend Offline</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Waiting for backend at `{API_URL}`. Start it with:\n`uvicorn backend.main:app --port 8000`")

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    st.caption("© 2026 Team Debuggers Den • SatQuery v1.0")


# --- Hero Section (NASA Science Eyes Editorial Style with 1080p Real Video Scene) ---
hero_html = f"""<div class="nasa-hero-wrap">
<video class="nasa-hero-video" autoplay loop muted playsinline poster="{hero_poster_url}">
<source src="{hero_video_url}" type="video/mp4">
<source src="https://videos.pexels.com/video-files/31084229/13282948_1920_1080_25fps.mp4" type="video/mp4">
</video>
<div class="nasa-hero-overlay"></div>
<div class="nasa-hero-inner">
<div class="nasa-hero-eyebrow">
<span style="font-size: 0.85rem; color: #60A5FA;">✦</span> MISSION DIRECTIVE • LOW EARTH ORBIT OBSERVATION
</div>
<h1 class="nasa-hero-title">
SatQuery AI<br/>
<span class="nasa-hero-title-accent">Earth Observation Intelligence</span>
</h1>
<p class="nasa-hero-desc">
Instant intelligence from orbit. Natural language reasoning, automated change detection, and cross-sensor fusion at planetary scale.
</p>
<div class="nasa-hero-actions">
<a href="#section-ingestion" class="nasa-btn-primary">
<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 8 12 12 14 14"></polyline></svg>
Explore Sensor Studio ↓
</a>
</div>
<div class="nasa-hero-bottom">
<div class="nasa-hero-meta">
<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span>
<span>YOU ARE EXPLORING EARTH OBSERVATION CONSTELLATION DATA</span>
<span style="opacity: 0.5;">•</span>
<span>ORBIT: 705 KM SSO</span>
<span style="opacity: 0.5;">•</span>
<span>ISRO EO-AI BENCHMARK</span>
</div>
<a href="#section-ingestion" class="nasa-hero-ctrl-btn" title="Live Sensor Feeds: Active // Click to Ingest">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
</a>
</div>
</div>
</div>"""

st.markdown(hero_html, unsafe_allow_html=True)


# --- Featured Highlight Cards (Planet.com Reference Row) ---
highlights_html = f"""<div class="planet-highlights-wrap">
<div class="planet-highlights-inner">
<div class="planet-highlights-grid">
<a href="#section-ingestion" class="planet-feat-card card-optical">
<div class="planet-card-badge-row">
<span class="planet-card-tag tag-cyan">TASK A</span>
</div>
<div class="planet-card-content">
<div class="planet-card-title">VQA, Caption & Grounding</div>
<div class="planet-card-desc">GeoChat • Visual QA, Scene Understanding & Coordinate Grounding</div>
</div>
</a>
<a href="#section-ingestion" class="planet-feat-card card-change">
<div class="planet-card-badge-row">
<span class="planet-card-tag tag-rose">TASK B</span>
</div>
<div class="planet-card-content">
<div class="planet-card-title">Bi-Temporal Change Analysis</div>
<div class="planet-card-desc">GeoLLaVA • Multi-Epoch Topological & Infrastructure Delta</div>
</div>
</a>
<a href="#section-ingestion" class="planet-feat-card card-fusion">
<div class="planet-card-badge-row">
<span class="planet-card-tag tag-amber">TASK C</span>
</div>
<div class="planet-card-content">
<div class="planet-card-title">Optical-SAR Fusion</div>
<div class="planet-card-desc">EarthGPT • Cross-Sensor Optical RGB & Radar Backscatter Reasoning</div>
</div>
</a>
<a href="#section-audit" class="planet-feat-card card-lora">
<div class="planet-card-badge-row">
<span class="planet-card-tag tag-purple">FINE-TUNED</span>
</div>
<div class="planet-card-content">
<div class="planet-card-title">LoRA on BigEarthNet</div>
<div class="planet-card-desc">PEFT Adapters • Macro Land Cover Classification on Multispectral Bands</div>
</div>
</a>
</div>
</div>
</div>"""

st.markdown(highlights_html, unsafe_allow_html=True)


# --- Clean 2-Section Pipeline Architecture (Reference Layout Style) ---
pipeline_html = """<div id="section-stats" class="pipeline-section-clean">
<div class="pipeline-section-header">
<div class="pipeline-section-kicker">SYSTEM ARCHITECTURE</div>
<h2 class="pipeline-section-heading">Specialized 4-Stage Autonomous Pipeline</h2>
<p class="pipeline-section-subheading">A deterministic multimodal pipeline engineered for sub-meter earth observation and verifiable telemetry.</p>
</div>
<div class="stage-cards-grid">
<div class="stage-clean-card">
<div class="stage-card-icon">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"></circle><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path></svg>
</div>
<div class="stage-card-title">Sensor Ingestion</div>
<div class="stage-card-label">MULTISPECTRAL &amp; SAR UPLINK</div>
<p class="stage-card-body">Accepts high-resolution optical and SAR raster tiles, validated for coordinate accuracy and radiometric calibration.</p>
</div>
<div class="stage-clean-card">
<div class="stage-card-icon">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
</div>
<div class="stage-card-title">Deterministic Router</div>
<div class="stage-card-label">LANGGRAPH FINITE STATE MACHINE</div>
<p class="stage-card-body">A zero-drift state machine that classifies queries and dispatches them to the optimal vision engine in 6ms.</p>
</div>
<div class="stage-clean-card">
<div class="stage-card-icon">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
</div>
<div class="stage-card-title">Model Orchestration</div>
<div class="stage-card-label">PARALLEL MULTIMODAL INFERENCE</div>
<p class="stage-card-body">Coordinates GeoChat, GeoLLaVA, and EarthGPT in parallel for VQA, change detection, and sensor fusion.</p>
</div>
<div class="stage-clean-card">
<div class="stage-card-icon">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>
</div>
<div class="stage-card-title">Verified Output</div>
<div class="stage-card-label">TELEMETRY AUDIT &amp; ATTESTATION</div>
<p class="stage-card-body">Every result is cryptographically signed and logged to an immutable telemetry ledger, exportable as a PDF audit report.</p>
</div>
</div>
<div class="pipeline-section-header flow-header">
<div class="pipeline-section-kicker">END-TO-END WORKFLOW</div>
<h2 class="pipeline-section-heading">End-to-End Processing Flow</h2>
<p class="pipeline-section-subheading">A sequential, verified execution path connecting initial raster telemetry uplink to finalized mission intelligence.</p>
</div>
<div class="flow-row-container">
<div class="flow-step-item">
<div class="flow-step-circle">1</div>
<div class="flow-step-content">
<div class="flow-step-title">Sensor Uplink</div>
<div class="flow-step-subtitle">Dual-Tile Raster Upload (Optical/SAR)</div>
</div>
</div>
<div class="flow-step-connector">
<div class="flow-connector-line"></div>
<svg class="flow-connector-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="flow-step-item">
<div class="flow-step-circle">2</div>
<div class="flow-step-content">
<div class="flow-step-title">Deterministic Routing</div>
<div class="flow-step-subtitle">LangGraph Zero-Drift State Machine</div>
</div>
</div>
<div class="flow-step-connector">
<div class="flow-connector-line"></div>
<svg class="flow-connector-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="flow-step-item">
<div class="flow-step-circle">3</div>
<div class="flow-step-content">
<div class="flow-step-title">Model Orchestration</div>
<div class="flow-step-subtitle">GeoChat, GeoLLaVA &amp; EarthGPT Dispatch</div>
</div>
</div>
<div class="flow-step-connector">
<div class="flow-connector-line"></div>
<svg class="flow-connector-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="flow-step-item">
<div class="flow-step-circle">4</div>
<div class="flow-step-content">
<div class="flow-step-title">Verified Output</div>
<div class="flow-step-subtitle">SHA-256 Telemetry &amp; PDF Report</div>
</div>
</div>
</div>
</div>"""

st.markdown(pipeline_html, unsafe_allow_html=True)


# --- Full-Bleed Tech-Stack Ticker Strip ---
ticker_items = [
    "LANGGRAPH ORCHESTRATION", "GEOCHAT (OPTICAL VQA)", "GEOLLAVA (CHANGE DETECTION)",
    "EARTHGPT (OPTICAL-SAR FUSION)", "FASTAPI DISPATCH", "DOCKER READY",
    "PYTORCH ACCELERATION", "REPORTLAB PDF EXPORT", "VRSBENCH BENCHMARKED",
    "SQLITE AUDIT BUS"
]
ticker_content = " <span class='ticker-sep'>✦</span> ".join([f"<span class='ticker-item'>{item}</span>" for item in ticker_items])
ticker_track = f"{ticker_content} <span class='ticker-sep'>✦</span> {ticker_content}"

st.markdown(f"""
<div class="tech-ticker-wrap">
    <div class="tech-ticker-track">
        {ticker_track}
    </div>
</div>
""", unsafe_allow_html=True)


# --- Section 1 & 2: Chat-Style Mission Intelligence Console ---
st.markdown("""
<div id="section-ingestion" class="chat-console-header">
    <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
        <div>
            <div class="ref-section-kicker"><span class="section-kicker-pill">INTELLIGENCE CONSOLE</span> Mission Interactive Reasoning</div>
            <div class="ref-section-title">Satellite Imagery Chat &amp; Multimodal Directive</div>
            <div class="ref-section-desc">Upload primary or comparative raster tiles, ask geospatial analysis questions, and inspect verified telemetry responses.</div>
        </div>
    </div>
    <div class="hud-telemetry-row" style="margin-top: 14px;">
        <div class="hud-telemetry-meta">
            <span class="hud-telemetry-tag"><span class="telemetry-live-dot"></span>SENSOR BUS ACTIVE</span>
            <span class="telemetry-item"><span class="telemetry-label">Coord:</span> <span class="telemetry-val">28.6139° N, 77.2090° E</span></span>
            <span class="telemetry-sep">•</span>
            <span class="telemetry-item"><span class="telemetry-label">Band:</span> <span class="telemetry-val">Multispectral-Optical / SAR</span></span>
            <span class="telemetry-sep">•</span>
            <span class="telemetry-item"><span class="telemetry-label">GSD:</span> <span class="telemetry-val">0.5m / px</span></span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


def dispatch_query_to_backend(query_text_to_send: str, files_list: list, api_url: str):
    """Submits imagery files and prompt to FastAPI backend /query endpoint."""
    with st.spinner("Dispatching to orchestrator: routing multi-modal reasoning pipeline..."):
        try:
            files_payload = []
            user_imgs = []
            for item in files_list:
                name, raw_b, ctype = item[0], item[1], item[2]
                files_payload.append(("files", (name, raw_b, ctype)))
                user_imgs.append({
                    "name": name,
                    "size_kb": round(len(raw_b) / 1024, 1),
                    "thumb_b64": make_thumbnail_b64(name, raw_b)
                })

            data_payload = {"query": query_text_to_send}
            response = requests.post(f"{api_url}/query", data=data_payload, files=files_payload, timeout=120)

            if response.status_code != 200:
                st.error(f"[SYSTEM FAULT] HTTP {response.status_code}: {response.text}")
                return

            resp = response.json()
            is_rejected = (
                not resp.get("validation_ok", True)
                or resp.get("selected_task") == "reject"
                or resp.get("status") == "rejected"
            )

            pdf_bytes = None
            query_id = resp.get("query_id")
            if query_id and not is_rejected:
                st.session_state["last_query_id"] = query_id
                try:
                    rep_resp = requests.get(f"{api_url}/report/{query_id}", timeout=10)
                    if rep_resp.status_code == 200:
                        pdf_bytes = rep_resp.content
                except Exception:
                    pass

            vis_url = resp.get("visual_output_url")
            vis_bytes = None
            if vis_url and not is_rejected:
                try:
                    vis_resp = requests.get(f"{api_url}{vis_url}", timeout=10)
                    if vis_resp.status_code == 200:
                        vis_bytes = vis_resp.content
                except Exception:
                    pass

            result_data = resp.get("result", {})
            answer_text = result_data.get("text") if isinstance(result_data, dict) else str(result_data)
            conf = resp.get("trace", {}).get("output_confidence")
            conf_val = f"{conf:.0%}" if isinstance(conf, (int, float)) else "N/A"

            new_turn = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
                "user": {
                    "text": query_text_to_send,
                    "images": user_imgs
                },
                "response": {
                    "is_rejected": is_rejected,
                    "is_chat": False,
                    "validation_msg": resp.get("validation_msg") or resp.get("guardrail_message") or "Request geometry or sensor modality incompatible with tool registry.",
                    "selected_task": resp.get("selected_task", "N/A"),
                    "model_used": resp.get("model_used", "N/A"),
                    "confidence": conf_val,
                    "query_id": query_id,
                    "answer": answer_text or "No textual telemetry generated.",
                    "trace": resp.get("trace", {}),
                    "pdf_data": pdf_bytes,
                    "visual_output_url": vis_url,
                    "visual_output_bytes": vis_bytes
                }
            }
            st.session_state.chat_history.append(new_turn)
            st.session_state.chat_opened = True
            st.rerun()

        except requests.exceptions.RequestException as req_err:
            st.error(f"[BUS FAULT] Communication error with API daemon: {req_err}")


def dispatch_chat_to_backend(message: str, api_url: str):
    """Sends conversational message to FastAPI /chat endpoint."""
    with st.spinner("Dispatching to SatQuery AI Assistant..."):
        try:
            chat_session_id = st.session_state.setdefault("chat_session_id", uuid.uuid4().hex[:12])
            last_qid = st.session_state.get("last_query_id")
            chat_payload = {
                "message": message,
                "session_id": chat_session_id,
                "query_id": last_qid
            }
            response = requests.post(f"{api_url}/chat", json=chat_payload, timeout=60)
            if response.status_code != 200:
                st.error(f"[CHAT FAULT] HTTP {response.status_code}: {response.text}")
                return

            c_data = response.json()
            st.session_state.chat_session_id = c_data.get("session_id", chat_session_id)
            new_turn = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
                "user": {
                    "text": message,
                    "images": []
                },
                "response": {
                    "is_rejected": False,
                    "is_chat": True,
                    "validation_msg": "",
                    "selected_task": "Conversational Assistant",
                    "model_used": "OpenAI LLM",
                    "confidence": "Verified",
                    "query_id": c_data.get("query_id"),
                    "answer": c_data.get("response", "No response received."),
                    "trace": {},
                    "pdf_data": None,
                    "visual_output_url": None,
                    "visual_output_bytes": None
                }
            }
            st.session_state.chat_history.append(new_turn)
            st.session_state.chat_opened = True
            st.rerun()
        except requests.exceptions.RequestException as req_err:
            st.error(f"[BUS FAULT] Communication error with API daemon: {req_err}")


def load_session_into_chat(session_id: str, api_url: str):
    """Loads a past multi-turn chat session into active Streamlit chat state."""
    try:
        resp = requests.get(f"{api_url}/chat/{session_id}", timeout=10)
        if resp.status_code == 200:
            c_data = resp.json()
            messages = c_data.get("messages", [])
            new_history = []
            i = 0
            while i < len(messages):
                msg = messages[i]
                if msg["role"] == "user":
                    user_text = msg["content"]
                    ts = msg.get("created_at", "")[:19].replace("T", " ") if msg.get("created_at") else ""
                    ans_text = ""
                    qid = msg.get("query_id")
                    if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                        ans_text = messages[i + 1]["content"]
                        qid = qid or messages[i + 1].get("query_id")
                        i += 2
                    else:
                        i += 1
                    new_history.append({
                        "id": str(uuid.uuid4()),
                        "timestamp": ts,
                        "user": {"text": user_text, "images": []},
                        "response": {
                            "is_rejected": False,
                            "is_chat": True,
                            "validation_msg": "",
                            "selected_task": "Conversational Assistant",
                            "model_used": "SatQuery AI",
                            "confidence": "Verified",
                            "query_id": qid,
                            "answer": ans_text,
                            "trace": {},
                            "pdf_data": None,
                            "visual_output_url": None,
                            "visual_output_bytes": None
                        }
                    })
                else:
                    new_history.append({
                        "id": str(uuid.uuid4()),
                        "timestamp": msg.get("created_at", "")[:19].replace("T", " ") if msg.get("created_at") else "",
                        "user": {"text": "(Context)", "images": []},
                        "response": {
                            "is_rejected": False,
                            "is_chat": True,
                            "validation_msg": "",
                            "selected_task": "Conversational Assistant",
                            "model_used": "SatQuery AI",
                            "confidence": "Verified",
                            "query_id": msg.get("query_id"),
                            "answer": msg["content"],
                            "trace": {},
                            "pdf_data": None,
                            "visual_output_url": None,
                            "visual_output_bytes": None
                        }
                    })
                    i += 1
            st.session_state.chat_history = new_history
            st.session_state.chat_session_id = session_id
            st.session_state.chat_opened = True
            st.rerun()
        else:
            st.error(f"Failed to load session {session_id}: HTTP {resp.status_code}")
    except Exception as e:
        st.error(f"Error loading session: {e}")


# Check whether chat is active (either user explicitly opened it, or conversation history exists)
is_chat_opened = st.session_state.get("chat_opened", False) or bool(st.session_state.get("chat_history"))

if not is_chat_opened:
    # ==================== STATE 1 (Default / Collapsed): Minimal Call-to-Action Card ====================
    st.markdown("""
    <div class="chat-cta-card">
        <div class="chat-cta-title">Ready to analyze your imagery?</div>
        <div class="chat-cta-desc">Launch the multimodal mission intelligence console to query satellite raster tiles, detect spatial features, and orchestrate reasoning pipelines.</div>
    </div>
    """, unsafe_allow_html=True)

    col_cta_l, col_cta_btn, col_cta_r = st.columns([0.34, 0.32, 0.34])
    with col_cta_btn:
        if st.button("⚡  Open Sensor Studio", key="open_chat_studio_btn", type="primary", use_container_width=True, help="Launch interactive mission intelligence chat"):
            st.session_state.chat_opened = True
            st.rerun()

else:
    # ==================== STATE 2 (Expanded / Active): Full Chat Interface ====================
    col_hist_info, col_top_actions = st.columns([0.76, 0.24])
    with col_top_actions:
        if st.session_state.chat_history:
            sub_c1, sub_c2 = st.columns(2, gap="small")
            with sub_c1:
                if st.button("↺ Clear", key="clear_chat_history_btn", use_container_width=True, help="Clear conversation history"):
                    st.session_state.chat_history = []
                    st.rerun()
            with sub_c2:
                if st.button("▾ Minimize", key="minimize_chat_btn", use_container_width=True, help="Minimize chat console"):
                    st.session_state.chat_opened = False
                    st.rerun()
        else:
            if st.button("▾ Minimize Console", key="minimize_chat_btn_empty", use_container_width=True, help="Minimize chat console"):
                st.session_state.chat_opened = False
                st.rerun()

    # --- Z.AI-Style Empty State vs Conversation Stream ---
    if not st.session_state.chat_history:
        # 1. Large, elegant serif heading and single-line subtitle
        st.markdown("""<div class="zai-empty-state-header">
<h1 class="zai-empty-heading">What can I analyze for you?</h1>
<p class="zai-empty-subtitle">Interact with SatQuery AI and explore satellite intelligence.</p>
</div>""", unsafe_allow_html=True)

        # 2. Multimodal VLM Tag & Elevated Dark Input Card
        st.markdown("""<div class="chat-engine-tag-bar">
<span class="chat-engine-badge"><span class="chat-engine-dot"></span>MULTIMODAL VLM ROUTER</span>
<span class="chat-engine-models">GeoChat • GeoLLaVA • EarthGPT</span>
</div>""", unsafe_allow_html=True)

        chat_col, _ = st.columns([0.999, 0.001])
        with chat_col:
            prompt = st.chat_input(
                placeholder="How can I help you today?",
                accept_file="multiple",
                file_type=["tif", "tiff", "png", "jpg", "jpeg"],
                key="main_chat_input"
            )

        # 3. Preset Suggestion Pills (Row of compact pill buttons below input card, one selected)
        if st.session_state.get("selected_preset") == "air":
            st.session_state["selected_preset"] = "land"
        selected_preset = st.session_state.setdefault("selected_preset", "land")
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        c_pad_l, c_p1, c_p2, c_pad_r = st.columns([0.28, 0.22, 0.22, 0.28], gap="small")
        with c_p1:
            is_sel = (selected_preset == "land")
            k = "preset_pill_land_sel" if is_sel else "preset_pill_land_idle"
            if st.button("🗺  Land Classification", key=k, use_container_width=True, help="Macro land-cover and surface categorization"):
                st.session_state.selected_preset = "land"
                st.rerun()
        with c_p2:
            is_sel = (selected_preset == "change")
            k = "preset_pill_change_sel" if is_sel else "preset_pill_change_idle"
            if st.button("Δ  Change Analysis", key=k, use_container_width=True, help="Topological delta detection across epochs"):
                st.session_state.selected_preset = "change"
                st.rerun()

        # 4. Preview Thumbnail Cards (2 small satellite imagery sample thumbnails with dark overlay captions)
        card_imgs = get_card_images_b64()
        previews_html = f"""<div class="chat-previews-container">
<div class="chat-preview-card">
<div class="chat-preview-img" style="background-image: url('{card_imgs.get('change', '')}');"></div>
<div class="chat-preview-overlay">
<div class="chat-preview-title">Urban Expansion Delta</div>
<div class="chat-preview-sub">Change Detection • GeoLLaVA</div>
</div>
</div>
<div class="chat-preview-card">
<div class="chat-preview-img" style="background-image: url('{card_imgs.get('sar', '')}');"></div>
<div class="chat-preview-overlay">
<div class="chat-preview-title">Radar-Optical Fusion</div>
<div class="chat-preview-sub">SAR Modality • EarthGPT</div>
</div>
</div>
</div>"""
        st.markdown(previews_html, unsafe_allow_html=True)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        col_d1, col_d2, col_d3 = st.columns(3, gap="small")
        with col_d1:
            if st.button("▶  Run Optical VQA Demo", key="btn_run_demo_optical", use_container_width=True, help="Analyze runway aircraft sample using GeoChat"):
                demo_path = os.path.join("data", "raw", "vrsbench", "sample_001.png")
                if os.path.exists(demo_path):
                    with open(demo_path, "rb") as df:
                        raw_b = df.read()
                    dispatch_query_to_backend("Detect and count the aircraft parked at the airport terminals.", [("sample_001.png", raw_b, "image/png")], API_URL)
                else:
                    st.warning("Demo image not found at data/raw/vrsbench/sample_001.png")
        with col_d2:
            if st.button("▶  Run Change Detection Demo", key="btn_run_demo_change", use_container_width=True, help="Analyze bi-temporal urban delta using GeoLLaVA"):
                p1 = os.path.join("data", "raw", "cdvqa", "pair_004_before.png")
                p2 = os.path.join("data", "raw", "cdvqa", "pair_004_after.png")
                if os.path.exists(p1) and os.path.exists(p2):
                    with open(p1, "rb") as f1, open(p2, "rb") as f2:
                        b1 = f1.read()
                        b2 = f2.read()
                    dispatch_query_to_backend("Compare both images and identify newly constructed buildings or infrastructure.", [("before.png", b1, "image/png"), ("after.png", b2, "image/png")], API_URL)
                else:
                    st.warning("Demo images not found in data/raw/cdvqa/")
        with col_d3:
            if st.button("▶  Run Optical-SAR Fusion Demo", key="btn_run_demo_fusion", use_container_width=True, help="Analyze joint Optical and SAR backscatter using EarthGPT"):
                p_opt = os.path.join("data", "raw", "bigearthnet", "tile_001_s2_optical.png")
                p_sar = os.path.join("data", "raw", "bigearthnet", "tile_001_s1_sar.png")
                if os.path.exists(p_opt) and os.path.exists(p_sar):
                    with open(p_opt, "rb") as f1, open(p_sar, "rb") as f2:
                        b_opt = f1.read()
                        b_sar = f2.read()
                    dispatch_query_to_backend("Perform joint optical and radar fusion over this scene.", [("optical.png", b_opt, "image/png"), ("sar.png", b_sar, "image/png")], API_URL)
                else:
                    st.warning("Demo images not found in data/raw/bigearthnet/")

    else:
        for idx, turn in enumerate(st.session_state.chat_history):
            user_turn = turn["user"]
            ts = turn.get("timestamp", "")

            # 1. Native Streamlit User Chat Message
            with st.chat_message("user"):
                if user_turn.get("images"):
                    img_cols = st.columns(min(len(user_turn["images"]), 3))
                    for idx_img, img_info in enumerate(user_turn["images"]):
                        with img_cols[idx_img % len(img_cols)]:
                            if img_info.get("thumb_b64"):
                                st.image(img_info["thumb_b64"], caption=f"{img_info['name']} ({img_info.get('size_kb', 0)} KB)", width=140)
                            else:
                                st.caption(f"📁 {img_info['name']}")
                st.markdown(user_turn.get("text", ""))
                if ts:
                    st.caption(f"🕒 {ts}")

            # 2. Native Streamlit Assistant Chat Message
            resp_data = turn["response"]
            with st.chat_message("assistant", avatar="🛰️"):
                if resp_data.get("is_rejected"):
                    val_msg = str(resp_data.get("validation_msg", "Request geometry or sensor modality incompatible with tool registry."))
                    st.error(f"🛡️ **Guardrail Notice:** {val_msg}")
                    if resp_data.get("trace"):
                        with st.expander("Audit Telemetry Trace", expanded=False):
                            st.json(resp_data["trace"])
                else:
                    # Model & Task telemetry pill row (for VLM or query tasks)
                    meta_parts = []
                    t_task = resp_data.get("selected_task")
                    if t_task and t_task not in ["N/A", "Conversational Assistant"]:
                        meta_parts.append(f"**Task:** `{t_task}`")
                    t_model = resp_data.get("model_used")
                    if t_model and t_model not in ["N/A", "OpenAI LLM", "SatQuery AI"]:
                        meta_parts.append(f"**Model:** `{t_model}`")
                    t_conf = resp_data.get("confidence")
                    if t_conf and t_conf not in ["N/A", "Verified"]:
                        meta_parts.append(f"**Confidence:** `{t_conf}`")
                    t_qid = resp_data.get("query_id")
                    if t_qid:
                        meta_parts.append(f"**Record:** `#{t_qid}`")

                    if meta_parts:
                        st.caption(" • ".join(meta_parts))

                    # Markdown Assistant Response
                    ans_text = resp_data.get("answer", "")
                    st.markdown(ans_text)

                    # Spatial visualization
                    if resp_data.get("visual_output_bytes"):
                        st.image(resp_data["visual_output_bytes"], caption="🎯 Spatial Detection & Telemetry Visualization", use_container_width=True)
                    elif resp_data.get("visual_output_url"):
                        st.image(f"{API_URL}{resp_data['visual_output_url']}", caption="🎯 Spatial Detection & Telemetry Visualization", use_container_width=True)

                    # PDF report export
                    if resp_data.get("pdf_data"):
                        st.download_button(
                            label="📥 Export Audit Report (PDF)",
                            data=resp_data["pdf_data"],
                            file_name=f"satquery_audit_report_{resp_data.get('query_id')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{turn['id']}",
                            use_container_width=False
                        )

                    # Execution trace expander
                    if resp_data.get("trace"):
                        with st.expander(f"Audit Telemetry Trace (Record #{t_qid or idx+1})", expanded=False):
                            st.json(resp_data["trace"])

                if ts:
                    st.caption(f"🕒 {ts}")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown("""<div class="chat-engine-tag-bar">
<span class="chat-engine-badge"><span class="chat-engine-dot"></span>MULTIMODAL VLM ROUTER</span>
<span class="chat-engine-models">GeoChat • GeoLLaVA • EarthGPT</span>
</div>""", unsafe_allow_html=True)

        chat_col, _ = st.columns([0.999, 0.001])
        with chat_col:
            prompt = st.chat_input(
                placeholder="How can I help you today? Ask questions or upload satellite imagery...",
                accept_file="multiple",
                file_type=["tif", "tiff", "png", "jpg", "jpeg"],
                key="main_chat_input"
            )

        if st.session_state.get("selected_preset") == "air":
            st.session_state["selected_preset"] = "land"
        selected_preset = st.session_state.setdefault("selected_preset", "land")
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        c_pad_l, c_p1, c_p2, c_pad_r = st.columns([0.28, 0.22, 0.22, 0.28], gap="small")
        with c_p1:
            is_sel = (selected_preset == "land")
            k = "preset_pill_land_hist_sel" if is_sel else "preset_pill_land_hist_idle"
            if st.button("🗺  Land Classification", key=k, use_container_width=True):
                st.session_state.selected_preset = "land"
                st.rerun()
        with c_p2:
            is_sel = (selected_preset == "change")
            k = "preset_pill_change_hist_sel" if is_sel else "preset_pill_change_hist_idle"
            if st.button("Δ  Change Analysis", key=k, use_container_width=True):
                st.session_state.selected_preset = "change"
                st.rerun()

    # --- Chat Input Submission Execution with Immediate User Display & Spinner ---
    if prompt:
        effective_query = (prompt.text or "").strip()
        attached_files = prompt.files or []

        if not effective_query and not attached_files:
            st.warning("⚠️ Please enter a directive or attach satellite imagery tiles before submitting.")
        elif not attached_files:
            # 1. Immediately render User message
            with st.chat_message("user"):
                st.markdown(effective_query)

            # 2. Immediately render Assistant response with spinner
            with st.chat_message("assistant", avatar="🛰️"):
                with st.spinner("SatQuery AI is formulating response..."):
                    chat_session_id = st.session_state.setdefault("chat_session_id", uuid.uuid4().hex[:12])
                    last_qid = st.session_state.get("last_query_id")
                    chat_payload = {
                        "message": effective_query,
                        "session_id": chat_session_id,
                        "query_id": last_qid
                    }
                    try:
                        response = requests.post(f"{API_URL}/chat", json=chat_payload, timeout=60)
                        if response.status_code == 200:
                            c_data = response.json()
                            st.session_state.chat_session_id = c_data.get("session_id", chat_session_id)
                            ans = c_data.get("response", "No response received.")
                            st.markdown(ans)
                            new_turn = {
                                "id": str(uuid.uuid4()),
                                "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
                                "user": {
                                    "text": effective_query,
                                    "images": []
                                },
                                "response": {
                                    "is_rejected": False,
                                    "is_chat": True,
                                    "validation_msg": "",
                                    "selected_task": "Conversational Assistant",
                                    "model_used": "SatQuery AI",
                                    "confidence": "Verified",
                                    "query_id": c_data.get("query_id"),
                                    "answer": ans,
                                    "trace": {},
                                    "pdf_data": None,
                                    "visual_output_url": None,
                                    "visual_output_bytes": None
                                }
                            }
                            st.session_state.chat_history.append(new_turn)
                            st.session_state.chat_opened = True
                            st.rerun()
                        else:
                            st.error(f"[CHAT FAULT] HTTP {response.status_code}: {response.text}")
                    except requests.exceptions.RequestException as req_err:
                        st.error(f"[BUS FAULT] Communication error with API daemon: {req_err}")
        else:
            preset_prompts = {
                "land": "Identify the dominant land cover and vegetation types across this scene.",
                "change": "Compare both images and identify newly constructed buildings or infrastructure."
            }
            query_text_to_send = effective_query if effective_query else preset_prompts.get(st.session_state.get("selected_preset", "land"), "Analyze attached imagery.")
            files_payload_tuples = [
                (f.name, f.getvalue(), f.type or "application/octet-stream")
                for f in attached_files[:2]
            ]
            # 1. Immediately render User message with uploaded imagery
            with st.chat_message("user"):
                u_imgs = []
                col_imgs = st.columns(min(len(attached_files), 3))
                for idx_f, f in enumerate(attached_files[:3]):
                    fb = f.getvalue()
                    with col_imgs[idx_f]:
                        st.caption(f"📁 {f.name} ({len(fb) // 1024} KB)")
                    u_imgs.append({
                        "name": f.name,
                        "size_kb": round(len(fb) / 1024, 1),
                        "thumb_b64": make_thumbnail_b64(f.name, fb)
                    })
                st.markdown(query_text_to_send)

            # 2. Immediately render Assistant response with spinner
            with st.chat_message("assistant", avatar="🛰️"):
                with st.spinner("SatQuery AI orchestrator: routing multi-modal reasoning pipeline..."):
                    try:
                        multipart_files = []
                        for item in files_payload_tuples:
                            name, raw_b, ctype = item[0], item[1], item[2]
                            multipart_files.append(("files", (name, raw_b, ctype)))

                        data_payload = {"query": query_text_to_send}
                        response = requests.post(f"{API_URL}/query", data=data_payload, files=multipart_files, timeout=120)
                        if response.status_code != 200:
                            st.error(f"[SYSTEM FAULT] HTTP {response.status_code}: {response.text}")
                        else:
                            resp = response.json()
                            is_rejected = (
                                not resp.get("validation_ok", True)
                                or resp.get("selected_task") == "reject"
                                or resp.get("status") == "rejected"
                            )
                            pdf_bytes = None
                            query_id = resp.get("query_id")
                            if query_id and not is_rejected:
                                st.session_state["last_query_id"] = query_id
                                try:
                                    rep_resp = requests.get(f"{API_URL}/report/{query_id}", timeout=10)
                                    if rep_resp.status_code == 200:
                                        pdf_bytes = rep_resp.content
                                except Exception:
                                    pass

                            vis_url = resp.get("visual_output_url")
                            vis_bytes = None
                            if vis_url and not is_rejected:
                                try:
                                    vis_resp = requests.get(f"{API_URL}{vis_url}", timeout=10)
                                    if vis_resp.status_code == 200:
                                        vis_bytes = vis_resp.content
                                except Exception:
                                    pass

                            result_data = resp.get("result", {})
                            answer_text = result_data.get("text") if isinstance(result_data, dict) else str(result_data)
                            conf = resp.get("trace", {}).get("output_confidence")
                            conf_val = f"{conf:.0%}" if isinstance(conf, (int, float)) else "N/A"

                            new_turn = {
                                "id": str(uuid.uuid4()),
                                "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
                                "user": {
                                    "text": query_text_to_send,
                                    "images": u_imgs
                                },
                                "response": {
                                    "is_rejected": is_rejected,
                                    "is_chat": False,
                                    "validation_msg": resp.get("validation_msg") or resp.get("guardrail_message") or "Request geometry or sensor modality incompatible with tool registry.",
                                    "selected_task": resp.get("selected_task", "N/A"),
                                    "model_used": resp.get("model_used", "N/A"),
                                    "confidence": conf_val,
                                    "query_id": query_id,
                                    "answer": answer_text or "No textual telemetry generated.",
                                    "trace": resp.get("trace", {}),
                                    "pdf_data": pdf_bytes,
                                    "visual_output_url": vis_url,
                                    "visual_output_bytes": vis_bytes
                                }
                            }
                            st.session_state.chat_history.append(new_turn)
                            st.session_state.chat_opened = True
                            st.rerun()
                    except requests.exceptions.RequestException as req_err:
                        st.error(f"[BUS FAULT] Communication error with API daemon: {req_err}")


# --- Section 3: History & Audit Log ---
st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div id="section-audit" class="hud-step-header">
    <div class="ref-section-kicker"><span class="hud-dot"></span> <span class="hud-bracket">[</span> <span class="hud-step-num">03</span> <span class="hud-bracket">]</span> • AUDIT & CONVERSATIONS</div>
    <div class="ref-section-title">Session History & Telemetry Log</div>
    <div class="ref-section-desc">Review previous multi-turn chat sessions, reopen past conversations in the console, or inspect pipeline telemetry audit traces.</div>
    <div class="hud-scanline"></div>
</div>
""", unsafe_allow_html=True)

tab_conversations, tab_telemetry = st.tabs(["💬 Chat Sessions", "🛰️ Pipeline Audit & Telemetry"])

with tab_conversations:
    try:
        conv_resp = requests.get(f"{API_URL}/conversations?limit=15", timeout=5)
        if conv_resp.status_code == 200:
            conv_data = conv_resp.json()
            conv_list = conv_data.get("conversations", [])
            if not conv_list:
                st.caption("No chat conversations recorded yet. Start a conversation in the chat console above!")
            else:
                for c in conv_list:
                    s_id = c.get("session_id")
                    preview = c.get("preview", "Conversation session")
                    msg_count = c.get("message_count", 0)
                    created = c.get("created_at", "")[:19].replace("T", " ") if c.get("created_at") else ""

                    st.markdown(f"""
                    <div class="ref-history-card">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                            <span class="ref-task-badge">SESSION: {s_id[:8]}</span>
                            <span style="font-family: 'Inter', sans-serif; font-size: 0.76rem; color: var(--text-muted);">{msg_count} messages • {created} UTC</span>
                        </div>
                        <div class="ref-history-query" style="font-size: 0.94rem;">💬 {html.escape(preview)}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    col_c1, col_c2 = st.columns([0.72, 0.28])
                    with col_c2:
                        if st.button("💬 Reopen in Chat", key=f"btn_reopen_{s_id}", use_container_width=True, help="Load this conversation session into the chat console"):
                            load_session_into_chat(s_id, API_URL)
                    with col_c1:
                        with st.expander(f"Preview Transcript ({s_id[:8]}...)", expanded=False):
                            try:
                                sess_resp = requests.get(f"{API_URL}/chat/{s_id}", timeout=5)
                                if sess_resp.status_code == 200:
                                    s_msgs = sess_resp.json().get("messages", [])
                                    for m in s_msgs:
                                        m_role = m.get("role", "user")
                                        m_content = m.get("content", "")
                                        m_time = m.get("created_at", "")[:19].replace("T", " ") if m.get("created_at") else ""
                                        if m_role == "user":
                                            st.markdown(f"**👤 User** *({m_time})*:\n{m_content}")
                                        else:
                                            st.markdown(f"**🛰️ SatQuery AI** *({m_time})*:\n{m_content}")
                                        st.divider()
                                else:
                                    st.caption("Unable to fetch transcript.")
                            except Exception as ex_t:
                                st.caption(f"Error: {ex_t}")

                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        else:
            st.warning(f"Could not retrieve conversations: HTTP {conv_resp.status_code}")
    except Exception as ex_c:
        st.caption(f"Conversations bus offline: {ex_c}")

with tab_telemetry:
    try:
        hist_resp = requests.get(f"{API_URL}/history?limit=10", timeout=5)
        if hist_resp.status_code == 200:
            hist_data = hist_resp.json()
            entries = hist_data.get("history", [])
            if not entries:
                st.caption("No historical records detected in the audit database.")
            else:
                for item in entries:
                    task = item.get("selected_task", "unknown")
                    model = item.get("model_used", "unknown")
                    conf = item.get("output_confidence") or item.get("router_confidence") or 0.0
                    qid = item.get("id")
                    created = item.get("created_at", "")[:19].replace("T", " ")

                    st.markdown(f"""
                    <div class="ref-history-card">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                            <span class="ref-task-badge">{task.replace('_', ' ')}</span>
                            <span style="font-family: 'Inter', sans-serif; font-size: 0.76rem; color: var(--text-muted);">Record #{qid:04d}</span>
                        </div>
                        <div class="ref-history-query">{item.get('query_text')}</div>
                        <div class="ref-history-meta">
                            <span>Confidence: <strong>{conf:.0%}</strong></span>
                            <span>•</span>
                            <span>Model: <strong>{model}</strong></span>
                            <span>•</span>
                            <span>{created} UTC</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    col_h1, col_h2 = st.columns([4, 1])
                    with col_h1:
                        if item.get("trace"):
                            with st.expander(f"View Execution Trace (#{qid:04d})", expanded=False):
                                st.json(item["trace"])
                        if item.get("visual_output_url"):
                            with st.expander(f"View Spatial Telemetry Visualization (#{qid:04d})", expanded=False):
                                st.image(f"{API_URL}{item['visual_output_url']}", caption=f"Visual Telemetry — Record #{qid:04d}", use_container_width=True)
                    with col_h2:
                        if qid:
                            st.link_button("📄 PDF Report", f"{API_URL}/report/{qid}", use_container_width=True)
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="telemetry-status-card status-card-warn">
                <div style="display: flex; align-items: flex-start; gap: 14px;">
                    <div class="telemetry-status-icon-warn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                            <line x1="12" y1="9" x2="12" y2="13"/>
                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.96rem; font-weight: 700; color: #f59e0b; letter-spacing: 0.02em;">
                            TELEMETRY BUS DEGRADED (HTTP {hist_resp.status_code})
                        </div>
                        <div style="font-family: 'Inter', sans-serif; font-size: 0.84rem; color: var(--text-secondary); margin-top: 3px;">
                            The audit bus returned a non-200 status code while querying the execution log.
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    except Exception as ex:
        st.markdown(f"""
        <div class="telemetry-status-card status-card-warn">
            <div style="display: flex; align-items: flex-start; gap: 14px;">
                <div class="telemetry-status-icon-warn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <div style="flex: 1;">
                    <div style="font-family: 'Space Grotesk', sans-serif; font-size: 0.96rem; font-weight: 700; color: #f59e0b; letter-spacing: 0.02em;">
                        TELEMETRY CONNECTION STANDBY
                    </div>
                    <div style="font-family: 'Inter', sans-serif; font-size: 0.84rem; color: var(--text-secondary); margin-top: 3px;">
                        Audit database daemon is currently initializing or awaiting live query telemetry dispatch.
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander("Telemetry Diagnostics Detail", expanded=False):
            st.code(f"Daemon trace: {ex}", language="bash")


# --- Reference Product Footer (Planet.com Reference Style) ---
footer_html = f"""<div class="ref-footer-wrap">
<div class="ref-footer-inner">
<!-- 3D Wireframe Spherical Globe with Sweeping Dotted Orbital Arc -->
<svg class="footer-bg-orbital" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
<!-- Outer Telemetry Coordinate Ring -->
<circle cx="330" cy="310" r="245" stroke="#2dd4bf" stroke-width="0.8" stroke-dasharray="3 8"/>
<!-- Outer Globe Silhouette Sphere -->
<circle cx="330" cy="310" r="210" stroke="#2dd4bf" stroke-width="1.2"/>
<!-- Parallels of Latitude (Horizontal Curved Spherical Slices) -->
<ellipse cx="330" cy="310" rx="210" ry="68" stroke="#2dd4bf" stroke-width="1.1"/>
<ellipse cx="330" cy="255" rx="202" ry="58" stroke="#2dd4bf" stroke-width="0.95"/>
<ellipse cx="330" cy="205" rx="180" ry="48" stroke="#2dd4bf" stroke-width="0.9"/>
<ellipse cx="330" cy="160" rx="145" ry="36" stroke="#2dd4bf" stroke-width="0.85"/>
<ellipse cx="330" cy="125" rx="95" ry="22" stroke="#2dd4bf" stroke-width="0.8"/>
<ellipse cx="330" cy="365" rx="202" ry="58" stroke="#2dd4bf" stroke-width="0.95"/>
<ellipse cx="330" cy="415" rx="180" ry="48" stroke="#2dd4bf" stroke-width="0.9"/>
<ellipse cx="330" cy="460" rx="145" ry="36" stroke="#2dd4bf" stroke-width="0.85"/>
<ellipse cx="330" cy="495" rx="95" ry="22" stroke="#2dd4bf" stroke-width="0.8"/>
<!-- Meridians of Longitude (Vertical Spherical Slices) -->
<line x1="330" y1="100" x2="330" y2="520" stroke="#2dd4bf" stroke-width="1.1"/>
<ellipse cx="330" cy="310" rx="60" ry="210" stroke="#2dd4bf" stroke-width="0.95"/>
<ellipse cx="330" cy="310" rx="120" ry="210" stroke="#2dd4bf" stroke-width="0.95"/>
<ellipse cx="330" cy="310" rx="170" ry="210" stroke="#2dd4bf" stroke-width="0.9"/>
<!-- Dynamic Sweeping Dotted Orbital Arc across & beyond the Globe -->
<path d="M 40,460 C 110,130 520,70 595,290" stroke="#2dd4bf" stroke-width="2" stroke-dasharray="7 6"/>
<path d="M 120,570 C 230,360 440,180 540,25" stroke="#2dd4bf" stroke-width="1.4" stroke-dasharray="5 6"/>
<!-- Orbital Satellite Nodes with Solar Panel Array -->
<circle cx="485" cy="148" r="5" fill="#2dd4bf"/>
<circle cx="485" cy="148" r="10" stroke="#2dd4bf" stroke-width="1.2" stroke-dasharray="2 3"/>
<line x1="471" y1="148" x2="499" y2="148" stroke="#2dd4bf" stroke-width="1.8"/>
<circle cx="215" cy="370" r="4" fill="#2dd4bf"/>
<circle cx="215" cy="370" r="8" stroke="#2dd4bf" stroke-width="0.9"/>
</svg>
<div class="ref-footer-strip">
<div style="display: flex; align-items: center; gap: 14px;">
<div class="ref-nav-logo" style="width: 36px; height: 36px; border-radius: 8px;">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
<polyline points="22,6 12,13 2,6"></polyline>
</svg>
</div>
<div>
<div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">Have questions about SatQuery AI?</div>
<div style="font-family: 'Inter', sans-serif; font-size: 0.82rem; color: var(--text-secondary);">Connect with the engineering team or explore architecture guides.</div>
</div>
</div>
<div style="display: flex; align-items: center; gap: 8px;">
<input type="text" placeholder="Enter your email..." class="ref-footer-input" readonly value="team@debuggersden.space"/>
<a href="mailto:team@debuggersden.space" class="ref-btn-primary">Connect</a>
</div>
</div>
<div class="ref-footer-grid">
<div>
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
<div class="ref-nav-logo" style="width: 26px; height: 26px; border-radius: 5px;">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="9"></circle>
<path d="m4.93 4.93 4.24 4.24"></path>
<path d="m14.83 9.17 4.24-4.24"></path>
<circle cx="12" cy="12" r="3"></circle>
</svg>
</div>
<span style="font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">SatQuery AI</span>
<span class="ref-nav-pill" style="font-size: 0.62rem; padding: 2px 6px;">ORCHESTRATOR</span>
</div>
<p style="font-family: 'Inter', sans-serif; font-size: 0.82rem; color: var(--text-secondary); line-height: 1.55; max-width: 280px; margin: 0 0 16px 0;">
Autonomous multimodal Earth Observation reasoning and deterministic audit trail platform built for defense and spaceborne monitoring.
</p>
<div style="display: flex; align-items: center; gap: 10px;">
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-btn-secondary">GitHub ↗</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-btn-secondary">Swagger ↗</a>
</div>
</div>
<div>
<div class="ref-footer-col-title">CAPABILITIES</div>
<a href="#section-ingestion" class="ref-footer-link">Visual Question Answering</a>
<a href="#section-ingestion" class="ref-footer-link">Grounding & Captioning</a>
<a href="#section-ingestion" class="ref-footer-link">Bi-Temporal Change</a>
<a href="#section-ingestion" class="ref-footer-link">Optical-SAR Fusion</a>
<a href="#section-audit" class="ref-footer-link">Audit Trail Verification</a>
</div>
<div>
<div class="ref-footer-col-title">MODELS & PIPELINE</div>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">GeoChat 7B Weights</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">EarthGPT Architecture</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">GeoLLaVA Vision Stack</a>
<a href="#section-query" class="ref-footer-link">Deterministic Routing</a>
<a href="#section-audit" class="ref-footer-link">Telemetry State Machine</a>
</div>
<div>
<div class="ref-footer-col-title">RESOURCES & DOCS</div>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">FastAPI Documentation</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">Swagger Interactive UI</a>
<a href="#section-ingestion" class="ref-footer-link">Sensor Studio Workspace</a>
<a href="{default_api_url}/health" target="_blank" class="ref-footer-link">System Health Bus</a>
<a href="https://github.com/UditKumar0001/SATQUERY-AI/issues" target="_blank" class="ref-footer-link">Submit Feedback</a>
</div>
<div>
<div class="ref-footer-col-title">TEAM & SUPPORT</div>
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">Team Debuggers Den</a>
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">Source Repository</a>
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">Architecture Guide</a>
<a href="mailto:team@debuggersden.space" class="ref-footer-link">Direct Inquiries</a>
<a href="https://github.com/UditKumar0001/SATQUERY-AI/issues" target="_blank" class="ref-footer-link">Report an Issue</a>
</div>
</div>
<div class="ref-footer-divider"></div>
<div class="ref-footer-bottom">
<div class="ref-footer-legal">
<span>© 2026 Team Debuggers Den. All rights reserved.</span>
<span style="opacity: 0.3;">|</span>
<a href="#" class="ref-footer-legal-link">Privacy Policy</a>
<span style="opacity: 0.3;">•</span>
<a href="#" class="ref-footer-legal-link">Terms of Use</a>
<span style="opacity: 0.3;">•</span>
<a href="#" class="ref-footer-legal-link">Security Notice</a>
<span style="opacity: 0.3;">•</span>
<a href="#" class="ref-footer-legal-link">Sitemap</a>
</div>
<div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
<span class="ref-hero-badge" style="margin-bottom: 0; padding: 4px 12px; font-size: 0.70rem; letter-spacing: 0.08em;">✦ BUILT FOR ISRO</span>
<div class="ref-footer-socials">
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-icon-btn" title="GitHub Repository">
<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
</svg>
</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-footer-icon-btn" title="API Documentation & Swagger">
<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<polyline points="16 18 22 12 16 6"></polyline>
<polyline points="8 6 2 12 8 18"></polyline>
</svg>
</a>
<a href="mailto:team@debuggersden.space" class="ref-footer-icon-btn" title="Engineering Contact">
<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<rect width="20" height="16" x="2" y="4" rx="2"></rect>
<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
</svg>
</a>
</div>
</div>
</div>
</div>
</div>"""

st.markdown(footer_html, unsafe_allow_html=True)
