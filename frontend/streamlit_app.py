# frontend/streamlit_app.py
import io
import os
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
    page_title="SatQuery AI — Earth Observation Intelligence",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Management ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "query_input_val" not in st.session_state:
    st.session_state.query_input_val = ""

# --- Theme Definitions ---
is_dark = (st.session_state.theme == "dark")

theme_vars = {
    "dark": {
        "bg_app": "radial-gradient(circle at 15% 15%, #0d1527 0%, #060913 75%, #03050a 100%)",
        "text_main": "#f1f5f9",
        "text_sub": "#94a3b8",
        "text_dim": "#64748b",
        "card_bg": "rgba(12, 20, 39, 0.65)",
        "card_border": "rgba(56, 189, 248, 0.18)",
        "nav_bg": "rgba(7, 11, 22, 0.88)",
        "nav_border": "rgba(56, 189, 248, 0.15)",
        "sidebar_bg": "#070b16",
        "sidebar_border": "rgba(56, 189, 248, 0.12)",
        "input_bg": "rgba(12, 20, 39, 0.85)",
        "input_border": "rgba(56, 189, 248, 0.22)",
        "accent": "#00f0ff",
        "accent_gradient": "linear-gradient(135deg, #0284c7 0%, #06b6d4 50%, #00f0ff 100%)",
        "btn_text": "#030712",
        "hero_gradient": "linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)",
        "hero_border": "rgba(56, 189, 248, 0.2)",
        "footer_bg": "rgba(7, 11, 22, 0.9)",
        "footer_border": "rgba(56, 189, 248, 0.15)",
        "divider_color": "rgba(56, 189, 248, 0.18)",
        "metric_bg": "rgba(15, 23, 42, 0.55)",
    },
    "light": {
        "bg_app": "radial-gradient(circle at 15% 15%, #f0f9ff 0%, #f8fafc 70%, #f1f5f9 100%)",
        "text_main": "#0f172a",
        "text_sub": "#475569",
        "text_dim": "#94a3b8",
        "card_bg": "#ffffff",
        "card_border": "rgba(2, 132, 199, 0.2)",
        "nav_bg": "rgba(255, 255, 255, 0.9)",
        "nav_border": "rgba(2, 132, 199, 0.18)",
        "sidebar_bg": "#f8fafc",
        "sidebar_border": "rgba(2, 132, 199, 0.15)",
        "input_bg": "#ffffff",
        "input_border": "rgba(2, 132, 199, 0.3)",
        "accent": "#0284c7",
        "accent_gradient": "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)",
        "btn_text": "#ffffff",
        "hero_gradient": "linear-gradient(135deg, rgba(224, 242, 254, 0.6) 0%, #ffffff 100%)",
        "hero_border": "rgba(2, 132, 199, 0.25)",
        "footer_bg": "rgba(248, 250, 252, 0.95)",
        "footer_border": "rgba(2, 132, 199, 0.18)",
        "divider_color": "rgba(2, 132, 199, 0.2)",
        "metric_bg": "#ffffff",
    }
}

active_theme = theme_vars["dark" if is_dark else "light"]

# --- Custom Styling via CSS Variables ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {{
        --bg-app: {active_theme['bg_app']};
        --text-main: {active_theme['text_main']};
        --text-sub: {active_theme['text_sub']};
        --text-dim: {active_theme['text_dim']};
        --card-bg: {active_theme['card_bg']};
        --card-border: {active_theme['card_border']};
        --nav-bg: {active_theme['nav_bg']};
        --nav-border: {active_theme['nav_border']};
        --sidebar-bg: {active_theme['sidebar_bg']};
        --sidebar-border: {active_theme['sidebar_border']};
        --input-bg: {active_theme['input_bg']};
        --input-border: {active_theme['input_border']};
        --accent: {active_theme['accent']};
        --accent-gradient: {active_theme['accent_gradient']};
        --btn-text: {active_theme['btn_text']};
        --hero-gradient: {active_theme['hero_gradient']};
        --hero-border: {active_theme['hero_border']};
        --footer-bg: {active_theme['footer_bg']};
        --footer-border: {active_theme['footer_border']};
        --divider-color: {active_theme['divider_color']};
        --metric-bg: {active_theme['metric_bg']};
    }}

    /* Global Base */
    html, body, [class*="css"] {{
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    
    .stApp {{
        background: var(--bg-app);
        color: var(--text-main);
    }}

    /* Container Max Width & Clean Centering */
    .main .block-container {{
        max-width: 1240px;
        padding-top: 1rem;
        padding-bottom: 3rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }}

    /* Sticky Top Navigation Bar */
    .top-nav-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--nav-bg);
        border: 1px solid var(--nav-border);
        border-radius: 14px;
        padding: 12px 20px;
        margin-bottom: 24px;
        backdrop-filter: blur(16px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, {'0.3' if is_dark else '0.06'});
        position: sticky;
        top: 12px;
        z-index: 100;
    }}

    .nav-brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        text-decoration: none;
        color: var(--text-main);
    }}
    .nav-brand-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        background: linear-gradient(135deg, var(--text-main) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .nav-badge {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        padding: 2px 7px;
        border-radius: 9999px;
        background: rgba(14, 165, 233, 0.12);
        color: var(--accent);
        border: 1px solid rgba(14, 165, 233, 0.3);
    }}

    .nav-links {{
        display: flex;
        align-items: center;
        gap: 18px;
    }}
    .nav-link-item {{
        color: var(--text-sub);
        text-decoration: none;
        font-size: 0.88rem;
        font-weight: 500;
        transition: color 0.15s ease;
    }}
    .nav-link-item:hover {{
        color: var(--accent);
    }}

    /* Sidebar Glassmorphic Treatment */
    [data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding-top: 2rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }}

    /* Headings */
    h1, h2, h3 {{
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: -0.02em;
        color: var(--text-main) !important;
    }}

    /* Hero Banner */
    .hero-banner {{
        background: var(--hero-gradient);
        border: 1px solid var(--hero-border);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(0, 0, 0, {'0.35' if is_dark else '0.06'});
    }}
    .hero-banner::before {{
        content: "";
        position: absolute;
        top: -60px;
        right: -60px;
        width: 220px;
        height: 220px;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.16) 0%, rgba(0,0,0,0) 70%);
        pointer-events: none;
    }}
    .hero-tag {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
        background: rgba(14, 165, 233, 0.1);
        border: 1px solid rgba(14, 165, 233, 0.3);
        padding: 4px 10px;
        border-radius: 9999px;
        margin-bottom: 12px;
    }}
    .hero-title {{
        font-size: 2.25rem;
        font-weight: 700;
        line-height: 1.15;
        margin: 0 0 10px 0;
        background: linear-gradient(135deg, var(--text-main) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero-desc {{
        color: var(--text-sub);
        font-size: 1.02rem;
        line-height: 1.5;
        max-width: 820px;
        margin: 0;
    }}

    /* Section Divider with Accent Glow */
    .section-divider {{
        display: flex;
        align-items: center;
        gap: 14px;
        margin: 36px 0 20px 0;
    }}
    .section-divider-line {{
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(14, 165, 233, 0.25) 0%, rgba(14, 165, 233, 0.05) 100%);
    }}
    .section-divider-line.right {{
        background: linear-gradient(270deg, rgba(14, 165, 233, 0.25) 0%, rgba(14, 165, 233, 0.05) 100%);
    }}
    .section-divider-badge {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.98rem;
        font-weight: 600;
        color: var(--text-main);
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    /* File Uploader Custom Aesthetics */
    [data-testid="stFileUploader"] section {{
        background: var(--card-bg) !important;
        border: 1px dashed var(--input-border) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        transition: all 0.2s ease-in-out !important;
    }}
    [data-testid="stFileUploader"] section:hover {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 18px rgba(14, 165, 233, 0.15) !important;
    }}
    [data-testid="stFileUploader"] button {{
        background: var(--input-bg) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}

    /* Input Field Styling */
    [data-testid="stTextInput"] input {{
        background: var(--input-bg) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 10px !important;
        color: var(--text-main) !important;
        font-size: 0.95rem !important;
        padding: 12px 14px !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 14px rgba(14, 165, 233, 0.22) !important;
    }}

    /* Preset Chips */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 9999px !important;
        color: var(--text-sub) !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        padding: 6px 14px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: rgba(14, 165, 233, 0.12) !important;
        border-color: var(--accent) !important;
        color: var(--text-main) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.18);
    }}

    /* Primary Action Button (Analyze Imagery) */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: var(--accent_gradient) !important;
        color: var(--btn-text) !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px 28px !important;
        box-shadow: 0 6px 24px rgba(14, 165, 233, 0.35) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        transform: translateY(-2px) scale(1.008);
        box-shadow: 0 8px 30px rgba(14, 165, 233, 0.5) !important;
        filter: brightness(1.06);
    }}
    div[data-testid="stButton"] > button[kind="primary"]:active {{
        transform: translateY(1px);
    }}

    /* Status Badges */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
    }}
    .status-badge-cyan {{
        background: rgba(6, 182, 212, 0.15);
        color: var(--accent);
        border: 1px solid rgba(6, 182, 212, 0.35);
    }}
    .status-badge-emerald {{
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }}
    .status-badge-amber {{
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }}
    .status-badge-rose {{
        background: rgba(244, 63, 94, 0.15);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.35);
    }}

    /* Pulsing Indicator Dot */
    .pulse-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }}
    .pulse-green {{
        background-color: #10b981;
        box-shadow: 0 0 8px #10b981;
    }}
    .pulse-red {{
        background-color: #f43f5e;
        box-shadow: 0 0 8px #f43f5e;
    }}

    /* KPI Metrics Boxes */
    [data-testid="stMetric"] {{
        background: var(--metric-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 14px 18px;
        backdrop-filter: blur(10px);
    }}
    [data-testid="stMetricLabel"] {{
        color: var(--text-sub) !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
    }}
    [data-testid="stMetricValue"] {{
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--accent) !important;
        font-size: 1.7rem !important;
        font-weight: 700 !important;
    }}

    /* Result Card Display */
    .result-box {{
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 14px;
        padding: 22px;
        margin: 18px 0;
        box-shadow: 0 8px 30px rgba(0, 0, 0, {'0.35' if is_dark else '0.06'});
    }}
    .result-text {{
        font-size: 1.05rem;
        line-height: 1.65;
        color: var(--text-main);
    }}

    /* Expanders & Accordions */
    div[data-testid="stExpander"] {{
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
    }}
    div[data-testid="stExpander"] > details > summary {{
        color: var(--text-main) !important;
        font-weight: 500 !important;
    }}

    /* Footer Container */
    .footer-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--footer-bg);
        border-top: 1px solid var(--footer-border);
        border-radius: 14px;
        padding: 20px 24px;
        margin-top: 48px;
        backdrop-filter: blur(12px);
    }}
    .footer-link {{
        color: var(--text-sub);
        text-decoration: none;
        font-size: 0.85rem;
        font-weight: 500;
        margin-left: 18px;
        transition: color 0.15s ease;
    }}
    .footer-link:hover {{
        color: var(--accent);
    }}
</style>
""", unsafe_allow_html=True)


# --- Sticky Top Navigation Bar ---
nav_left, nav_right = st.columns([3, 2])

with nav_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; padding: 6px 0;">
        <img src="https://img.icons8.com/isometric/100/satellite.png" width="30"/>
        <span class="nav-brand-title">SatQuery AI</span>
        <span class="nav-badge">v1.0 ORCHESTRATOR</span>
    </div>
    """, unsafe_allow_html=True)

with nav_right:
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1, 1, 1, 0.8])
    with btn_col1:
        st.markdown('<div style="padding-top: 8px; text-align: center;"><a href="#imagery-ingestion" class="nav-link-item">Studio</a></div>', unsafe_allow_html=True)
    with btn_col2:
        st.markdown('<div style="padding-top: 8px; text-align: center;"><a href="#audit-log" class="nav-link-item">Audit</a></div>', unsafe_allow_html=True)
    with btn_col3:
        st.markdown(f'<div style="padding-top: 8px; text-align: center;"><a href="{default_api_url}/docs" target="_blank" class="nav-link-item">Docs ↗</a></div>', unsafe_allow_html=True)
    with btn_col4:
        theme_icon = "☀️ Light" if is_dark else "🌙 Dark"
        if st.button(theme_icon, key="theme_toggle_btn", help="Switch between Dark and Light mode"):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)


# --- Sidebar: System Diagnostics & Health ---
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
        <img src="https://img.icons8.com/isometric/100/satellite.png" width="44"/>
        <div>
            <h2 style="font-size: 1.3rem; margin: 0;">SatQuery AI</h2>
            <div style="font-size: 0.72rem; color: var(--accent); letter-spacing: 0.08em; text-transform: uppercase; font-family: 'JetBrains Mono', monospace;">EO Orchestrator</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙️ Connection Settings", expanded=False):
        API_URL = st.text_input(
            "Backend API URL",
            value=default_api_url,
            help="Connect to local (http://localhost:8000) or remote Hugging Face Space / Render URL"
        ).rstrip("/")

    st.markdown("<div style='margin-top: 14px; margin-bottom: 8px; font-weight: 600; font-size: 0.85rem; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.05em;'>System Health</div>", unsafe_allow_html=True)
    
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=3)
        if health_resp.status_code == 200:
            health = health_resp.json()
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px;">
                <span class="pulse-dot pulse-green"></span>
                <span style="color: #10b981; font-size: 0.85rem; font-weight: 600;">API Connected & Ready</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"**Database:** `{health.get('database')}`")
            hw = health.get("hardware", {})
            st.markdown(f"**Compute:** `{hw.get('device_name', 'Unknown')}` (`{hw.get('configured_device', 'cpu')}`)")
            router_ready = health.get("router_llm_ready", False)
            if router_ready:
                st.markdown("**Router LLM:** <span class='status-badge status-badge-emerald'>Ready</span>", unsafe_allow_html=True)
            else:
                st.markdown("**Router LLM:** <span class='status-badge status-badge-amber'>Key Required</span>", unsafe_allow_html=True)

            with st.expander("Registered Tools"):
                for tool in health.get("registered_tools", []):
                    st.code(f"{tool['task']} -> {tool['model_wrapper']}", language="bash")
        else:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px;">
                <span class="pulse-dot pulse-red"></span>
                <span style="color: #f43f5e; font-size: 0.85rem; font-weight: 600;">HTTP {health_resp.status_code} Degraded</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; padding: 8px 12px; margin-bottom: 12px;">
            <span class="pulse-dot pulse-red"></span>
            <span style="color: #f43f5e; font-size: 0.85rem; font-weight: 600;">Backend Offline</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Waiting for backend at `{API_URL}`. Start it with:\n`uvicorn backend.main:app --port 8000`")

    st.divider()
    st.caption("Team Debuggers Den • SatQuery v1.0")


# --- Main Workspace: Hero Banner ---
st.markdown("""
<div class="hero-banner">
    <div class="hero-tag">🛰️ MISSION ORCHESTRATION PLATFORM</div>
    <h1 class="hero-title">SatQuery AI</h1>
    <p class="hero-desc">
        Next-generation multimodal Earth Observation intelligence. Natural language reasoning across high-resolution optical, SAR radar, and bi-temporal change imagery powered by <strong>GeoChat</strong>, <strong>GeoLLaVA</strong>, and <strong>EarthGPT</strong>.
    </p>
</div>
""", unsafe_allow_html=True)


# --- Section Divider 1: Imagery Ingestion ---
st.markdown("""
<div id="imagery-ingestion" class="section-divider">
    <div class="section-divider-badge">📥 1. Imagery Ingestion</div>
    <div class="section-divider-line right"></div>
</div>
""", unsafe_allow_html=True)

col_up1, col_up2 = st.columns(2, gap="large")

with col_up1:
    st.markdown("""
    <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">
        Tile A — Primary Observation
    </div>
    <div style="font-size: 0.8rem; color: var(--text-sub); margin-bottom: 10px;">
        High-res optical tile, multispectral band, or base SAR image
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
    st.markdown("""
    <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">
        Tile B — Comparison / Sensor Pair (Optional)
    </div>
    <div style="font-size: 0.8rem; color: var(--text-sub); margin-bottom: 10px;">
        Post-event tile for change analysis or co-registered SAR for optical-SAR fusion
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


# --- Section Divider 2: Mission Instruction & Query ---
st.markdown("""
<div class="section-divider">
    <div class="section-divider-badge">💬 2. Mission Instruction & Query</div>
    <div class="section-divider-line right"></div>
</div>
""", unsafe_allow_html=True)

# Preset Query Buttons
col_p1, col_p2, col_p3 = st.columns(3, gap="medium")
with col_p1:
    if st.button("✈️  Aircraft Detection", key="preset_air", help="VQA prompt for counting and localizing aircraft"):
        st.session_state.query_input_val = "Detect and count the aircraft parked at the airport terminals."
with col_p2:
    if st.button("🌲  Land Classification", key="preset_land", help="Captioning prompt for dominant vegetation and land cover"):
        st.session_state.query_input_val = "Identify the dominant land cover and vegetation types across this scene."
with col_p3:
    if st.button("🔄  Change Analysis", key="preset_change", help="Comparative prompt for bi-temporal structural changes"):
        st.session_state.query_input_val = "Compare both images and identify newly constructed buildings or infrastructure."

# Query Input Field
query_input = st.text_input(
    "Enter your analysis question or instruction:",
    value=st.session_state.query_input_val,
    placeholder="e.g., 'Detect and count airplanes on the runway', 'What is the land cover?', 'Identify changes between Image 1 and Image 2'",
    label_visibility="collapsed"
)

# Analyze Button
st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
analyze_clicked = st.button("🚀  Analyze Imagery & Orchestrate Pipeline", type="primary", use_container_width=True)

# --- Analysis Execution ---
if analyze_clicked:
    if not img1_file:
        st.warning("⚠️ Please upload at least one image (Tile A) to proceed.")
    elif not query_input.strip():
        st.warning("⚠️ Please enter a question or instruction about the imagery.")
    else:
        with st.spinner("🛰️ Routing query, evaluating guardrails, and invoking vision-language model..."):
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
                    st.error(f"API Error ({response.status_code}): {response.text}")
                else:
                    resp = response.json()
                    is_rejected = (
                        not resp.get("validation_ok", True)
                        or resp.get("selected_task") == "reject"
                        or resp.get("status") == "rejected"
                    )

                    if is_rejected:
                        st.markdown(f"""
                        <div style="background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.35); border-radius: 12px; padding: 16px 20px; margin: 18px 0;">
                            <div style="font-weight: 700; color: #f43f5e; font-size: 1.05rem; margin-bottom: 4px;">
                                🚫 Request Rejected by Guardrails
                            </div>
                            <div style="color: var(--text-main); font-size: 0.92rem;">
                                {resp.get('validation_msg', 'Query or imagery incompatible with registered task specifications.')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        if "trace" in resp and resp["trace"]:
                            with st.expander("🔍 Inspection & Validation Trace"):
                                st.json(resp["trace"])
                    else:
                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                        st.markdown("""
                        <div style="display: flex; align-items: center; gap: 8px; color: #10b981; font-weight: 600; font-size: 1.1rem;">
                            <span>✓</span> Analysis Orchestration Complete
                        </div>
                        """, unsafe_allow_html=True)

                        # KPI Header Cards
                        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                        with kpi1:
                            st.metric("Routed Task", resp.get("selected_task", "N/A"))
                        with kpi2:
                            st.metric("Model Deployed", resp.get("model_used", "N/A"))
                        with kpi3:
                            conf = resp.get("trace", {}).get("output_confidence")
                            conf_val = f"{conf:.0%}" if isinstance(conf, (int, float)) else "N/A"
                            st.metric("Confidence Score", conf_val)
                        with kpi4:
                            st.metric("Query Record", f"#{resp.get('query_id')}")

                        # Answer Section
                        result_data = resp.get("result", {})
                        answer_text = result_data.get("text") if isinstance(result_data, dict) else str(result_data)

                        st.markdown("""
                        <div class="result-box">
                            <div style="font-size: 0.8rem; color: var(--accent); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace;">
                                📝 SYNTHESIZED INTELLIGENCE RESULT
                            </div>
                            <div class="result-text">
                        """ + (answer_text or "No textual result returned.") + """
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
                                        label="📄  Download Official PDF Audit Report",
                                        data=report_resp.content,
                                        file_name=f"satquery_audit_report_{query_id}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                            except Exception as err:
                                st.caption(f"Report generation note: {err}")

                        # Auditable Execution Trace Details
                        with st.expander("🔍 Auditable Execution Trace & Telemetry"):
                            st.json(resp.get("trace", {}))

            except requests.exceptions.RequestException as req_err:
                st.error(f"Failed to communicate with API server: {req_err}")


# --- Section Divider 3: History & Audit Log ---
st.markdown("""
<div id="audit-log" class="section-divider">
    <div class="section-divider-badge">📜 3. Mission Audit History & Records</div>
    <div class="section-divider-line right"></div>
</div>
""", unsafe_allow_html=True)

try:
    hist_resp = requests.get(f"{API_URL}/history?limit=10", timeout=5)
    if hist_resp.status_code == 200:
        hist_data = hist_resp.json()
        entries = hist_data.get("history", [])
        if not entries:
            st.caption("No queries recorded in audit database yet.")
        else:
            for item in entries:
                task = item.get("selected_task", "unknown")
                model = item.get("model_used", "unknown")
                conf = item.get("output_confidence") or item.get("router_confidence") or 0.0
                qid = item.get("id")
                created = item.get("created_at", "")[:19].replace("T", " ")

                badge_class = "status-badge-cyan" if task == "vqa_caption_ground" else ("status-badge-amber" if task == "change_analysis" else "status-badge-emerald")

                header_label = f"Query #{qid} — {item.get('query_text')} [{task.upper()}] ({conf:.0%})"
                with st.expander(header_label):
                    col_h1, col_h2 = st.columns([3, 1])
                    with col_h1:
                        st.markdown(f"""
                        <div style="margin-bottom: 8px;">
                            <span class="status-badge {badge_class}">{task}</span>
                            <span style="color: var(--text-sub); font-size: 0.85rem; margin-left: 8px;">Model: <strong>{model}</strong></span>
                            <span style="color: var(--text-dim); font-size: 0.85rem; margin-left: 8px;">Validation: {item.get('validation_msg')}</span>
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-dim); margin-bottom: 8px;">Recorded timestamp: {created} UTC</div>
                        """, unsafe_allow_html=True)
                        if item.get("trace"):
                            st.json(item["trace"])
                    with col_h2:
                        if qid:
                            st.link_button("📄 Download PDF", f"{API_URL}/report/{qid}", use_container_width=True)
    else:
        st.caption(f"Could not load history (HTTP {hist_resp.status_code})")
except Exception as ex:
    st.caption(f"History unavailable: {ex}")


# --- Product Footer ---
st.markdown(f"""
<div class="footer-container">
    <div>
        <div style="display: flex; align-items: center; gap: 8px;">
            <img src="https://img.icons8.com/isometric/100/satellite.png" width="22"/>
            <span style="font-weight: 700; font-family: 'Space Grotesk', sans-serif; font-size: 0.95rem;">SatQuery AI</span>
            <span style="color: var(--text-dim); font-size: 0.82rem;">• © 2026 Team Debuggers Den</span>
        </div>
        <div style="color: var(--text-dim); font-size: 0.78rem; margin-top: 4px;">
            Autonomous Multi-Modal Earth Observation Orchestration & Audit Platform
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 18px;">
        <a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="footer-link">GitHub</a>
        <a href="{default_api_url}/docs" target="_blank" class="footer-link">API Docs</a>
        <a href="{default_api_url}/health" target="_blank" class="footer-link">Health API</a>
    </div>
</div>
""", unsafe_allow_html=True)
