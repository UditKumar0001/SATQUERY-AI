# frontend/streamlit_app.py
import base64
import io
import os
from pathlib import Path
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

card_imgs = get_card_images_b64()
img_opt_url = card_imgs.get("optical", "")
img_chg_url = card_imgs.get("change", "")
img_sar_url = card_imgs.get("sar", "")
img_lor_url = card_imgs.get("lora", "")

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
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

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
    .planet-nav-menu {{
        display: flex !important;
        align-items: center !important;
        gap: 40px !important;
        margin-left: 44px !important;
    }}
    .planet-nav-item {{
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.015em !important;
        color: rgba(255, 255, 255, 0.88) !important;
        text-decoration: none !important;
        transition: color 0.15s ease, opacity 0.15s ease !important;
        white-space: nowrap !important;
        padding: 4px 0 !important;
    }}
    .planet-nav-item:hover {{
        color: #ffffff !important;
    }}
    .planet-chevron {{
        opacity: 0.65;
        transition: transform 0.15s ease;
    }}
    .planet-nav-item:hover .planet-chevron {{
        transform: translateY(1px);
        opacity: 1;
    }}
    .planet-nav-right {{
        display: flex;
        align-items: center;
        gap: 20px;
    }}
    .planet-nav-text-link {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.86rem;
        font-weight: 400;
        color: rgba(255, 255, 255, 0.85);
        text-decoration: none;
        transition: color 0.15s ease;
        white-space: nowrap;
        letter-spacing: 0.01em;
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
        font-weight: 400 !important;
        color: #ffffff !important;
        text-decoration: none !important;
        padding: 7px 20px !important;
        border-radius: 9999px !important;
        border: 1px solid rgba(255, 255, 255, 0.50) !important;
        background: transparent !important;
        background-color: transparent !important;
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
        box-shadow: none !important;
    }}
    .planet-nav-circle-btn {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.35);
        background: transparent;
        color: rgba(255, 255, 255, 0.85);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        transition: all 0.2s ease;
        flex-shrink: 0;
        box-shadow: none;
    }}
    .planet-nav-circle-btn:hover {{
        background: rgba(255, 255, 255, 0.10);
        border-color: rgba(255, 255, 255, 0.80);
        color: #ffffff;
    }}
    @media (max-width: 1080px) {{
        .planet-nav-menu {{
            gap: 24px !important;
            margin-left: 24px !important;
        }}
        .planet-nav-item {{
            font-size: 0.84rem !important;
        }}
    }}
    @media (max-width: 860px) {{
        .planet-nav-menu {{
            display: none !important;
        }}
    }}
    @media (max-width: 520px) {{
        .planet-navbar-inner {{
            padding: 0 1rem;
        }}
        .planet-nav-text-link {{
            display: none;
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

    /* Reference Style Stats Grid (4 Cards - Responsive) */
    .ref-stats-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-top: 36px;
        margin-bottom: 32px;
        scroll-margin-top: 88px !important;
    }}
    @media (max-width: 960px) {{
        .ref-stats-grid {{
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            margin-top: 28px;
        }}
    }}
    @media (max-width: 520px) {{
        .ref-stats-grid {{
            grid-template-columns: 1fr;
            gap: 12px;
            margin-top: 24px;
        }}
    }}
    .ref-stat-card {{
        background: rgba(11, 17, 30, 0.70);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 22px 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.20);
    }}
    .ref-stat-label {{
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 8px;
    }}
    .ref-stat-val {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.65rem, 4vw, 2.1rem);
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 6px;
    }}
    .val-green {{ color: #10b981; }}
    .val-blue {{ color: #60A5FA; }}
    .val-purple {{ color: #8b5cf6; }}
    .val-orange {{ color: #f59e0b; }}
    .ref-stat-sub {{
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        line-height: 1.4;
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
    .ref-footer-col-title {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 16px;
    }}
    .ref-footer-link {{
        display: block;
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.85rem;
        color: var(--text-secondary);
        text-decoration: none;
        margin-bottom: 10px;
        transition: color 0.15s ease, transform 0.15s ease;
    }}
    .ref-footer-link:hover {{
        color: #60A5FA;
        transform: translateX(2px);
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
    .ref-footer-legal-link {{
        color: var(--text-muted);
        text-decoration: none;
        transition: color 0.15s ease;
    }}
    .ref-footer-legal-link:hover {{
        color: var(--text-primary);
    }}
    .ref-footer-socials {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .ref-footer-icon-btn {{
        width: 32px;
        height: 32px;
        border-radius: 50%;
        border: 1px solid var(--border-color);
        background: rgba(255, 255, 255, 0.03);
        color: var(--text-secondary);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        transition: all 0.2s ease;
    }}
    .ref-footer-icon-btn:hover {{
        border-color: #60A5FA;
        color: #ffffff;
        background: rgba(96, 165, 250, 0.12);
        transform: translateY(-2px);
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
<div style="display: flex; align-items: center;">
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
<nav class="planet-nav-menu" style="display: flex; align-items: center; gap: 40px; margin-left: 44px;">
<a href="#section-ingestion" class="planet-nav-item" style="color: rgba(255, 255, 255, 0.88); text-decoration: none; font-size: 0.88rem; font-weight: 400;">Overview <svg class="planet-chevron" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="6 9 12 15 18 9"></polyline></svg></a>
<a href="#section-query" class="planet-nav-item" style="color: rgba(255, 255, 255, 0.88); text-decoration: none; font-size: 0.88rem; font-weight: 400;">Models <svg class="planet-chevron" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="6 9 12 15 18 9"></polyline></svg></a>
<a href="#section-ingestion" class="planet-nav-item" style="color: rgba(255, 255, 255, 0.88); text-decoration: none; font-size: 0.88rem; font-weight: 400;">Pipeline <svg class="planet-chevron" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="6 9 12 15 18 9"></polyline></svg></a>
<a href="{default_api_url}/docs" target="_blank" class="planet-nav-item" style="color: rgba(255, 255, 255, 0.88); text-decoration: none; font-size: 0.88rem; font-weight: 400;">Docs <svg class="planet-chevron" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="6 9 12 15 18 9"></polyline></svg></a>
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="planet-nav-item" style="color: rgba(255, 255, 255, 0.88); text-decoration: none; font-size: 0.88rem; font-weight: 400;">Team <svg class="planet-chevron" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="6 9 12 15 18 9"></polyline></svg></a>
</nav>
</div>
<div class="planet-nav-right" style="display: flex; align-items: center; gap: 20px;">
<a href="#section-audit" class="planet-nav-text-link" style="color: rgba(255, 255, 255, 0.85); text-decoration: none; font-size: 0.86rem; font-weight: 400;">History</a>
<a href="#section-ingestion" class="planet-nav-btn-pill" style="display: inline-flex; align-items: center; justify-content: center; font-family: 'Inter', -apple-system, sans-serif; font-size: 0.84rem; font-weight: 400; color: #ffffff !important; text-decoration: none; padding: 7px 20px; border-radius: 9999px; border: 1px solid rgba(255, 255, 255, 0.50); background: transparent !important; background-color: transparent !important; box-shadow: none !important; white-space: nowrap;">Try Live Demo</a>
<a href="#section-query" class="planet-nav-circle-btn" title="Search Queries & Directives" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255, 255, 255, 0.35); background: transparent; color: rgba(255, 255, 255, 0.85); display: inline-flex; align-items: center; justify-content: center; text-decoration: none; box-shadow: none;">
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
                st.markdown("<div style='font-family: \"Inter\", sans-serif; font-size: 0.82rem; margin-bottom: 12px;'>Router LLM: <span style='background: rgba(245, 158, 11, 0.12); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 8px; border-radius: 9999px; font-size: 0.70rem; font-weight: 600;'>Key Pending</span></div>", unsafe_allow_html=True)

            with st.expander("Active Tool Registry", expanded=False):
                for tool in health.get("registered_tools", []):
                    st.code(f"{tool['task']} -> {tool['model_wrapper']}", language="bash")
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
Deterministic multi-modal reasoning across high-resolution satellite constellations and aerial sensors. Orchestrates visual question answering, bi-temporal change detection, and cross-sensor fusion powered by <strong>GeoChat</strong>, <strong>GeoLLaVA</strong>, and <strong>EarthGPT</strong>.
</p>
<div class="nasa-hero-actions">
<a href="#section-ingestion" class="nasa-btn-primary">
<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 8 12 12 14 14"></polyline></svg>
Explore Sensor Studio ↓
</a>
<a href="{default_api_url}/docs" target="_blank" class="nasa-btn-secondary">
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
API Documentation ↗
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


# --- Reference Stats Bar (4 Metric Cards) ---
st.markdown("""
<div id="section-stats" class="ref-stats-grid">
    <div class="ref-stat-card">
        <div class="ref-stat-label">ROUTING ACCURACY</div>
        <div class="ref-stat-val val-green">100%</div>
        <div class="ref-stat-sub">Cross-validated on VRSBench & CDVQA</div>
    </div>
    <div class="ref-stat-card">
        <div class="ref-stat-label">MEAN LATENCY</div>
        <div class="ref-stat-val val-blue">6.0 ms</div>
        <div class="ref-stat-sub">Deterministic state machine dispatch</div>
    </div>
    <div class="ref-stat-card">
        <div class="ref-stat-label">TASK F1 SCORE</div>
        <div class="ref-stat-val val-purple">0.63</div>
        <div class="ref-stat-sub">Multi-task benchmark evaluation</div>
    </div>
    <div class="ref-stat-card">
        <div class="ref-stat-label">MODELS ORCHESTRATED</div>
        <div class="ref-stat-val val-orange">3 EO-VLMs</div>
        <div class="ref-stat-sub">GeoChat • GeoLLaVA • EarthGPT</div>
    </div>
</div>
""", unsafe_allow_html=True)


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


# --- Section 1: Ingestion ---
has_img1 = bool(st.session_state.get("uploader_img1"))
has_img2 = bool(st.session_state.get("uploader_img2"))

if has_img1:
    status_tag_a = '<span class="hud-status-tag tag-active"><span class="hud-status-dot dot-active"></span>File Loaded</span>'
else:
    status_tag_a = '<span class="hud-status-tag tag-standby"><span class="hud-status-dot dot-standby"></span>Awaiting Upload</span>'

if has_img2:
    status_tag_b = '<span class="hud-status-tag tag-active"><span class="hud-status-dot dot-active"></span>File Loaded</span>'
else:
    status_tag_b = '<span class="hud-status-tag tag-standby"><span class="hud-status-dot dot-standby"></span>Awaiting Upload</span>'

st.markdown(f"""
<div id="section-ingestion" class="ingestion-hero-banner">
    <div class="ref-section-kicker"><span class="section-kicker-pill">STEP 01</span> Sensor Ingestion Pipeline</div>
    <div class="ref-section-title">Imagery Ingestion &amp; Tile Registration</div>
    <div class="ref-section-desc">Upload primary observation raster tile and an optional secondary / temporal pair for automated multi-modal reasoning.</div>
    <div class="hud-telemetry-row">
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

col_up1, col_up2 = st.columns(2, gap="large")

with col_up1:
    st.markdown(f"""
    <div class="tile-header-banner tile-banner-a">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px;">
            <div class="ref-card-header">Tile A — Primary Observation</div>
            <div>
                {status_tag_a}
            </div>
        </div>
        <div class="ref-card-desc">High-resolution optical raster tile, multispectral band, or base SAR backscatter (GeoTIFF, PNG, JPG).</div>
    </div>
    """, unsafe_allow_html=True)
    img1_file = st.file_uploader(
        "Upload primary satellite/aerial tile",
        type=["tif", "tiff", "png", "jpg", "jpeg"],
        key="uploader_img1",
        label_visibility="collapsed"
    )
    if img1_file:
        try:
            pil_img1 = Image.open(img1_file)
            st.image(pil_img1, caption=f"Tile A: {img1_file.name} ({pil_img1.width}×{pil_img1.height}px)", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img1_file.name} (GeoTIFF/Multi-band Sensor Tile)")

with col_up2:
    st.markdown(f"""
    <div class="tile-header-banner tile-banner-b">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px;">
            <div class="ref-card-header">Tile B — Secondary / Temporal Pair</div>
            <div>
                {status_tag_b}
            </div>
        </div>
        <div class="ref-card-desc">Post-event comparative tile for change detection or co-registered SAR for cross-sensor fusion.</div>
    </div>
    """, unsafe_allow_html=True)
    img2_file = st.file_uploader(
        "Upload comparison image for bi-temporal tasks",
        type=["tif", "tiff", "png", "jpg", "jpeg"],
        key="uploader_img2",
        label_visibility="collapsed"
    )
    if img2_file:
        try:
            pil_img2 = Image.open(img2_file)
            st.image(pil_img2, caption=f"Tile B: {img2_file.name} ({pil_img2.width}×{pil_img2.height}px)", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img2_file.name} (GeoTIFF/Multi-band Sensor Tile)")


# --- Section 2: Query Specification ---
st.markdown("<div style='height: 48px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div class="hud-step-header">
    <div class="ref-section-kicker"><span class="section-kicker-pill">STEP 02</span> Directive &amp; Instruction</div>
    <div class="ref-section-title">Mission Instruction &amp; Query Directive</div>
    <div class="ref-section-desc">Choose a pre-configured analysis template or enter custom natural language instructions.</div>
</div>
""", unsafe_allow_html=True)

# Preset Technical Buttons with Aerospace Symbols
col_p1, col_p2, col_p3 = st.columns(3, gap="medium")
with col_p1:
    if st.button("✈  Aircraft Recognition", key="preset_air", help="Target detection and runway inventory via optical VQA"):
        st.session_state.query_input_val = "Detect and count the aircraft parked at the airport terminals."
with col_p2:
    if st.button("🗺  Land Cover Classification", key="preset_land", help="Macro land-cover and surface categorization"):
        st.session_state.query_input_val = "Identify the dominant land cover and vegetation types across this scene."
with col_p3:
    if st.button("Δ  Bi-Temporal Change Delta", key="preset_change", help="Topological delta detection across epochs"):
        st.session_state.query_input_val = "Compare both images and identify newly constructed buildings or infrastructure."

# Query Input Field
st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
query_input = st.text_input(
    "Query Specification Input",
    value=st.session_state.query_input_val,
    placeholder="Enter your observation question (e.g. 'Detect and count aircraft', 'Identify newly constructed infrastructure')...",
    label_visibility="collapsed"
)

# Analyze Button
st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
analyze_clicked = st.button("⚡  Analyze Imagery & Orchestrate Pipeline", type="primary", use_container_width=True)

# --- Analysis Execution ---
if analyze_clicked:
    if not img1_file:
        st.warning("Please upload Tile A (Primary Observation) before initiating analysis.")
    elif not query_input.strip():
        st.warning("Please enter a query instruction or choose a preset analysis template.")
    else:
        with st.spinner("Dispatching to orchestrator: routing multi-modal reasoning pipeline..."):
            try:
                files_payload = [
                    ("files", (img1_file.name, img1_file.getvalue(), img1_file.type or "application/octet-stream"))
                ]
                if img2_file:
                    files_payload.append(
                        ("files", (img2_file.name, img2_file.getvalue(), img2_file.type or "application/octet-stream"))
                    )

                data_payload = {"query": query_input}
                response = requests.post(f"{API_URL}/query", data=data_payload, files=files_payload, timeout=120)

                if response.status_code != 200:
                    st.error(f"[SYSTEM FAULT] HTTP {response.status_code}: {response.text}")
                else:
                    resp = response.json()
                    is_rejected = (
                        not resp.get("validation_ok", True)
                        or resp.get("selected_task") == "reject"
                        or resp.get("status") == "rejected"
                    )

                    if is_rejected:
                        st.markdown(f"""
                        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-left: 4px solid #ef4444; padding: 14px 18px; margin: 16px 0;">
                            <div style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #ef4444; font-size: 0.90rem; letter-spacing: 0.08em; text-transform: uppercase;">
                                [GUARDRAIL REJECTION // REQUEST TERMINATED]
                            </div>
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: var(--text-primary); margin-top: 4px;">
                                {resp.get('validation_msg', 'Request geometry or sensor modality incompatible with tool registry.')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        if "trace" in resp and resp["trace"]:
                            with st.expander("[AUDIT TELEMETRY TRACE]"):
                                st.json(resp["trace"])
                    else:
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

                        # KPI Header Cards
                        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                        with kpi1:
                            st.metric("ROUTED TASK", resp.get("selected_task", "N/A"))
                        with kpi2:
                            st.metric("MODEL DEPLOYED", resp.get("model_used", "N/A"))
                        with kpi3:
                            conf = resp.get("trace", {}).get("output_confidence")
                            conf_val = f"{conf:.0%}" if isinstance(conf, (int, float)) else "N/A"
                            st.metric("CONFIDENCE SCORE", conf_val)
                        with kpi4:
                            st.metric("QUERY RECORD ID", f"#{resp.get('query_id')}")

                        # Answer Terminal Section
                        result_data = resp.get("result", {})
                        answer_text = result_data.get("text") if isinstance(result_data, dict) else str(result_data)

                        st.markdown(f"""
                        <div class="result-terminal">
                            <div class="result-terminal-header">
                                [SYNTHESIZED INTELLIGENCE RESULT // INFERENCE VERIFIED]
                            </div>
                            <div class="result-terminal-body">
                                {answer_text or 'No textual telemetry generated.'}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Report Download Action
                        query_id = resp.get("query_id")
                        if query_id:
                            try:
                                report_resp = requests.get(f"{API_URL}/report/{query_id}", timeout=10)
                                if report_resp.status_code == 200:
                                    st.download_button(
                                        label="[ EXPORT AUDIT REPORT (PDF) ]",
                                        data=report_resp.content,
                                        file_name=f"satquery_audit_report_{query_id}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                            except Exception as err:
                                st.caption(f"Report export note: {err}")

                        # Auditable Execution Trace Details
                        with st.expander("[AUDITABLE EXECUTION TRACE & TELEMETRY RECORD]"):
                            st.json(resp.get("trace", {}))

            except requests.exceptions.RequestException as req_err:
                st.error(f"[BUS FAULT] Communication error with API daemon: {req_err}")


# --- Section 3: History & Audit Log ---
st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div id="section-audit" class="hud-step-header">
    <div class="ref-section-kicker"><span class="hud-dot"></span> <span class="hud-bracket">[</span> <span class="hud-step-num">03</span> <span class="hud-bracket">]</span> • TELEMETRY AUDIT</div>
    <div class="ref-section-title">Recent Queries & Audit Log</div>
    <div class="ref-section-desc">Historical pipeline execution records, verified task traces, and generated PDF audit reports.</div>
    <div class="hud-scanline"></div>
</div>
""", unsafe_allow_html=True)

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
<a href="mailto:team@debuggersden.space" class="ref-btn-primary" style="padding: 8px 18px; font-size: 0.84rem; text-decoration: none;">Connect</a>
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
<a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-btn-secondary" style="padding: 5px 12px; font-size: 0.76rem;">GitHub ↗</a>
<a href="{default_api_url}/docs" target="_blank" class="ref-btn-secondary" style="padding: 5px 12px; font-size: 0.76rem;">Swagger ↗</a>
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
