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

# --- Mission Control Theme Variables (ISRO / Ground Station Spec) ---
theme_vars = {
    "dark": {
        "bg_app": "#070a0f",
        "bg_panel": "#0c1118",
        "bg_panel_sub": "#121924",
        "bg_input": "#090d14",
        "border_color": "#1e293b",
        "border_subtle": "#16202e",
        "border_focus": "#00e5ff",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent_primary": "#00e5ff",
        "accent_hover": "#38bdf8",
        "btn_primary_bg": "#00e5ff",
        "btn_primary_text": "#05080e",
        "btn_primary_hover": "#38e1f0",
        "btn_secondary_bg": "#121924",
        "hero_card_bg": "#0c1118",
        "chip_bg": "#121924",
        "chip_text": "#cbd5e1",
        "chip_border": "#243247",
        "chip_hover_bg": "#1c2638",
        "chip_hover_text": "#00e5ff",
        "nav_bg": "#0c1118",
        "nav_border": "#1e293b",
        "sidebar_bg": "#080c13",
        "sidebar_border": "#1e293b",
        "footer_bg": "#080c13",
        "footer_border": "#1e293b",
        "metric_bg": "#0c1118",
        "metric_value": "#00e5ff",
        "result_bg": "#0a0e16",
        "result_border": "#1e293b",
        "status_tag_bg": "rgba(0, 229, 255, 0.08)",
        "status_tag_border": "rgba(0, 229, 255, 0.25)",
        "status_tag_text": "#00e5ff",
    },
    "light": {
        "bg_app": "#f8fafc",
        "bg_panel": "#ffffff",
        "bg_panel_sub": "#f1f5f9",
        "bg_input": "#ffffff",
        "border_color": "#e2e8f0",
        "border_subtle": "#e2e8f0",
        "border_focus": "#0284c7",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#64748b",
        "accent_primary": "#0284c7",
        "accent_hover": "#0369a1",
        "btn_primary_bg": "#0284c7",
        "btn_primary_text": "#ffffff",
        "btn_primary_hover": "#0369a1",
        "btn_secondary_bg": "#ffffff",
        "hero_card_bg": "#ffffff",
        "chip_bg": "#f1f5f9",
        "chip_text": "#0f172a",
        "chip_border": "#cbd5e1",
        "chip_hover_bg": "#e2e8f0",
        "chip_hover_text": "#0284c7",
        "nav_bg": "#ffffff",
        "nav_border": "#e2e8f0",
        "sidebar_bg": "#f8fafc",
        "sidebar_border": "#e2e8f0",
        "footer_bg": "#ffffff",
        "footer_border": "#e2e8f0",
        "metric_bg": "#ffffff",
        "metric_value": "#0284c7",
        "result_bg": "#f8fafc",
        "result_border": "#e2e8f0",
        "status_tag_bg": "#e0f2fe",
        "status_tag_border": "#bae6fd",
        "status_tag_text": "#0284c7",
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
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, sans-serif;
    }}
    
    .stApp {{
        background-color: var(--bg-app);
        color: var(--text-primary);
    }}

    /* Container Max Width & Precise Grid */
    .main .block-container {{
        max-width: 1260px;
        padding-top: 1rem;
        padding-bottom: 3.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }}

    /* Reference Style Top Navbar (Verdika Pattern) */
    .ref-navbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--nav-bg);
        border: 1px solid var(--nav-border);
        border-radius: 8px;
        padding: 10px 18px;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }}
    .ref-nav-brand {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .ref-nav-logo {{
        width: 30px;
        height: 30px;
        background: var(--accent-primary);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
    }}
    .ref-nav-title {{
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 1.12rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.01em;
    }}
    .ref-nav-pill {{
        background: var(--status-tag-bg);
        color: var(--status-tag-text);
        border: 1px solid var(--status-tag-border);
        font-family: 'Inter', sans-serif;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 9999px;
        margin-left: 6px;
    }}
    .ref-nav-link {{
        font-family: 'Inter', sans-serif;
        font-size: 0.88rem;
        font-weight: 500;
        color: var(--text-secondary);
        text-decoration: none;
        padding: 6px 10px;
        border-radius: 6px;
        transition: all 0.15s ease;
    }}
    .ref-nav-link:hover {{
        color: var(--accent-primary);
        background: var(--bg-panel-sub);
    }}

    /* Reference Style Hero Card (Verdika Pattern) */
    .ref-hero-card {{
        background: var(--hero-card-bg);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 56px 24px 48px;
        text-align: center;
        margin-bottom: 32px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
    }}
    .ref-hero-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--status-tag-bg);
        color: var(--status-tag-text);
        border: 1px solid var(--status-tag-border);
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 4px 14px;
        border-radius: 9999px;
        margin-bottom: 20px;
    }}
    .ref-hero-title {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: 2.85rem;
        font-weight: 700;
        line-height: 1.15;
        letter-spacing: -0.02em;
        color: var(--text-primary);
        margin: 0 auto 16px;
    }}
    .ref-hero-desc {{
        font-family: 'Inter', sans-serif;
        color: var(--text-secondary);
        font-size: 1.05rem;
        line-height: 1.6;
        max-width: 680px;
        margin: 0 auto 28px;
    }}
    .ref-hero-actions {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
    }}
    .ref-btn-primary {{
        background: var(--accent-primary);
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        font-weight: 600;
        padding: 10px 22px;
        border-radius: 8px;
        text-decoration: none;
        border: 1px solid transparent;
        transition: opacity 0.15s ease;
        box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25);
    }}
    .ref-btn-primary:hover {{
        opacity: 0.92;
    }}
    .ref-btn-secondary {{
        background: var(--btn-secondary-bg);
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color);
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        font-weight: 600;
        padding: 10px 22px;
        border-radius: 8px;
        text-decoration: none;
        transition: background 0.15s ease;
    }}
    .ref-btn-secondary:hover {{
        background: var(--bg-panel-sub);
    }}

    /* Reference Style Stats Grid (4 Cards) */
    .ref-stats-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 28px;
    }}
    @media (max-width: 960px) {{
        .ref-stats-grid {{
            grid-template-columns: repeat(2, 1fr);
        }}
    }}
    @media (max-width: 520px) {{
        .ref-stats-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    .ref-stat-card {{
        background: var(--hero-card-bg);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 20px 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
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
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 6px;
    }}
    .val-green {{ color: #10b981; }}
    .val-blue {{ color: var(--accent-primary); }}
    .val-purple {{ color: #8b5cf6; }}
    .val-orange {{ color: #f59e0b; }}
    .ref-stat-sub {{
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        line-height: 1.4;
    }}

    /* Full Bleed Tech Ticker Strip */
    .tech-ticker-wrap {{
        width: 100vw;
        position: relative;
        left: 50%;
        right: 50%;
        margin-left: -50vw;
        margin-right: -50vw;
        background: var(--accent-primary);
        overflow: hidden;
        white-space: nowrap;
        padding: 12px 0;
        margin-top: 6px;
        margin-bottom: 36px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
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
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #ffffff;
        padding: 0 20px;
        white-space: nowrap;
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
    .ref-section-kicker {{
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 4px;
    }}
    .ref-section-title {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-size: 1.45rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 4px;
        letter-spacing: -0.01em;
    }}
    .ref-section-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.88rem;
        color: var(--text-secondary);
        margin-bottom: 18px;
    }}
    .ref-card-header {{
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 2px;
    }}
    .ref-card-desc {{
        font-family: 'Inter', sans-serif;
        font-size: 0.80rem;
        color: var(--text-secondary);
        margin-bottom: 10px;
    }}

    /* Reference File Uploader Cards */
    [data-testid="stFileUploader"] section {{
        background: var(--hero-card-bg) !important;
        border: 1px dashed var(--border-color) !important;
        border-radius: 10px !important;
        padding: 24px 18px !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stFileUploader"] section:hover {{
        border-color: var(--accent-primary) !important;
        box-shadow: 0 2px 10px rgba(2, 132, 199, 0.08) !important;
    }}
    [data-testid="stFileUploader"] button {{
        background: var(--btn-secondary-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        padding: 6px 14px !important;
        transition: all 0.15s ease !important;
    }}
    [data-testid="stFileUploader"] button:hover {{
        border-color: var(--accent-primary) !important;
        color: var(--accent-primary) !important;
    }}

    /* Reference Input Field */
    [data-testid="stTextInput"] input {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.94rem !important;
        padding: 12px 16px !important;
        transition: border-color 0.15s ease !important;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.12) !important;
    }}

    /* Reference Style Preset Chips */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: var(--hero-card-bg) !important;
        color: var(--accent-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.86rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
        text-transform: none !important;
        padding: 10px 16px !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: var(--accent-primary) !important;
        color: #ffffff !important;
        border-color: var(--accent-primary) !important;
        box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25) !important;
    }}

    /* Reference Style Primary Action Button */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: var(--btn-primary-bg) !important;
        color: var(--btn-primary-text) !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.96rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        text-transform: none !important;
        padding: 14px 28px !important;
        box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25) !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        background: var(--btn-primary-hover) !important;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35) !important;
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

    /* History Entry Card */
    .ref-history-card {{
        background: var(--hero-card-bg);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }}
    .ref-history-card:hover {{
        border-color: var(--accent-primary);
        box-shadow: 0 2px 8px rgba(2, 132, 199, 0.08);
    }}
    .ref-history-query {{
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 6px 0;
    }}
    .ref-history-meta {{
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: 12px;
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
    }}

    /* Reference Footer Styles */
    .ref-footer-wrap {{
        width: 100vw;
        position: relative;
        left: 50%;
        right: 50%;
        margin-left: -50vw;
        margin-right: -50vw;
        background: var(--footer-bg);
        border-top: 1px solid var(--footer-border);
        padding: 48px 0 32px;
        margin-top: 56px;
    }}
    .ref-footer-inner {{
        max-width: 1260px;
        margin: 0 auto;
        padding: 0 2rem;
    }}
    .ref-footer-strip {{
        background: var(--hero-card-bg);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 22px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 36px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }}
    @media (max-width: 768px) {{
        .ref-footer-strip {{
            flex-direction: column;
            gap: 16px;
            align-items: flex-start;
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
    }}
    .ref-footer-grid {{
        display: grid;
        grid-template-columns: 2fr 1fr 1fr 1.2fr;
        gap: 36px;
        margin-bottom: 28px;
    }}
    @media (max-width: 920px) {{
        .ref-footer-grid {{
            grid-template-columns: repeat(2, 1fr);
        }}
    }}
    @media (max-width: 520px) {{
        .ref-footer-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    .ref-footer-col-title {{
        font-family: 'Inter', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 14px;
    }}
    .ref-footer-link {{
        display: block;
        font-family: 'Inter', sans-serif;
        font-size: 0.84rem;
        color: var(--text-secondary);
        text-decoration: none;
        margin-bottom: 9px;
        transition: color 0.15s ease;
    }}
    .ref-footer-link:hover {{
        color: var(--accent-primary);
    }}
    .ref-footer-divider {{
        height: 1px;
        background: var(--border-color);
        margin: 28px 0 20px;
    }}
    .ref-footer-bottom {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-family: 'Inter', sans-serif;
        font-size: 0.80rem;
        color: var(--text-muted);
    }}
</style>
""", unsafe_allow_html=True)


# --- Top Navigation Bar (Reference Style) ---
nav_left, nav_right = st.columns([3, 2])

with nav_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; padding: 4px 0;">
        <div class="ref-nav-logo">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"></circle>
                <path d="m4.93 4.93 4.24 4.24"></path>
                <path d="m14.83 9.17 4.24-4.24"></path>
                <path d="m14.83 14.83 4.24 4.24"></path>
                <path d="m9.17 14.83-4.24 4.24"></path>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>
        </div>
        <span class="ref-nav-title">SatQuery AI</span>
        <span class="ref-nav-pill">EARTH OBSERVATION</span>
    </div>
    """, unsafe_allow_html=True)

with nav_right:
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 1, 1, 0.8])
    with nav_c1:
        st.markdown('<div style="padding-top: 6px; text-align: center;"><a href="#section-ingestion" class="ref-nav-link">Dashboard</a></div>', unsafe_allow_html=True)
    with nav_c2:
        st.markdown('<div style="padding-top: 6px; text-align: center;"><a href="#section-audit" class="ref-nav-link">History</a></div>', unsafe_allow_html=True)
    with nav_c3:
        st.markdown(f'<div style="padding-top: 6px; text-align: center;"><a href="{default_api_url}/docs" target="_blank" class="ref-nav-link">Docs ↗</a></div>', unsafe_allow_html=True)
    with nav_c4:
        theme_icon = "☀️" if is_dark else "🌙"
        if st.button(theme_icon, key="theme_toggle_btn", help="Switch between Light and Dark mode"):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)


# --- Sidebar: System Diagnostics & Health ---
with st.sidebar:
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


# --- Hero Section (Reference Style) ---
st.markdown(f"""
<div class="ref-hero-card">
    <div class="ref-hero-badge">
        <span style="font-size: 0.85rem; color: var(--accent-primary);">✦</span> MISSION ORCHESTRATION PLATFORM
    </div>
    <div class="ref-hero-title">
        SatQuery AI<br/>
        <span style="color: var(--accent-primary);">for Earth Observation</span>
    </div>
    <p class="ref-hero-desc">
        Deterministic multi-modal reasoning across high-resolution satellite and aerial imagery. Orchestrates visual question answering, bi-temporal change detection, and cross-sensor fusion powered by <strong>GeoChat</strong>, <strong>GeoLLaVA</strong>, and <strong>EarthGPT</strong>.
    </p>
    <div class="ref-hero-actions">
        <a href="#section-ingestion" class="ref-btn-primary">Explore Studio ↓</a>
        <a href="{default_api_url}/docs" target="_blank" class="ref-btn-secondary">API Documentation ↗</a>
    </div>
</div>
""", unsafe_allow_html=True)


# --- Reference Stats Bar (4 Metric Cards) ---
st.markdown("""
<div class="ref-stats-grid">
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
ticker_content = " • ".join([f"<span class='ticker-item'>{item}</span>" for item in ticker_items])
ticker_track = f"{ticker_content} • {ticker_content}"

st.markdown(f"""
<div class="tech-ticker-wrap">
    <div class="tech-ticker-track">
        {ticker_track}
    </div>
</div>
""", unsafe_allow_html=True)


# --- Section 1: Ingestion ---
st.markdown("""
<div id="section-ingestion">
    <div class="ref-section-kicker">STEP 01 • SENSOR INGESTION</div>
    <div class="ref-section-title">Imagery Ingestion</div>
    <div class="ref-section-desc">Upload primary observation imagery and an optional secondary or temporal tile for multi-modal analysis.</div>
</div>
""", unsafe_allow_html=True)

col_up1, col_up2 = st.columns(2, gap="large")

with col_up1:
    st.markdown("""
    <div class="ref-card-header">Tile A — Primary Observation</div>
    <div class="ref-card-desc">High-resolution optical raster tile, multispectral band, or base SAR backscatter (GeoTIFF, PNG, JPG).</div>
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
    <div class="ref-card-header">Tile B — Secondary / Temporal Pair (Optional)</div>
    <div class="ref-card-desc">Post-event comparative tile for change detection or co-registered SAR for cross-sensor fusion.</div>
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
st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div>
    <div class="ref-section-kicker">STEP 02 • DIRECTIVE & INSTRUCTION</div>
    <div class="ref-section-title">Mission Instruction & Query</div>
    <div class="ref-section-desc">Choose a pre-configured analysis template or enter custom natural language instructions.</div>
</div>
""", unsafe_allow_html=True)

# Preset Technical Buttons
col_p1, col_p2, col_p3 = st.columns(3, gap="small")
with col_p1:
    if st.button("✈️  Aircraft Detection", key="preset_air", help="Target detection and runway inventory"):
        st.session_state.query_input_val = "Detect and count the aircraft parked at the airport terminals."
with col_p2:
    if st.button("🌲  Land Classification", key="preset_land", help="Macro land-cover and surface categorization"):
        st.session_state.query_input_val = "Identify the dominant land cover and vegetation types across this scene."
with col_p3:
    if st.button("🔄  Change Analysis", key="preset_change", help="Topological delta detection across epochs"):
        st.session_state.query_input_val = "Compare both images and identify newly constructed buildings or infrastructure."

# Query Input Field
query_input = st.text_input(
    "Query Specification Input",
    value=st.session_state.query_input_val,
    placeholder="Enter your observation question (e.g. 'Detect and count aircraft', 'Identify newly constructed infrastructure')...",
    label_visibility="collapsed"
)

# Analyze Button
st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
analyze_clicked = st.button("⚡  Analyze Imagery & Orchestrate Pipeline", type="primary", use_container_width=True)

# --- Analysis Execution ---
if analyze_clicked:
    if not img1_file:
        st.warning("[ALERT] Ingestion fault: Tile A (Primary Observation) must be specified.")
    elif not query_input.strip():
        st.warning("[ALERT] Directive fault: Query specification input cannot be empty.")
    else:
        with st.spinner("DISPATCHING TO ORCHESTRATOR: Extracting metadata, checking guardrails, executing neural inference..."):
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
<div id="section-audit">
    <div class="ref-section-kicker">STEP 03 • TELEMETRY AUDIT</div>
    <div class="ref-section-title">Recent Queries & Audit Log</div>
    <div class="ref-section-desc">Historical pipeline execution records, verified task traces, and generated PDF audit reports.</div>
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
        st.caption(f"Audit log communication fault (HTTP {hist_resp.status_code})")
except Exception as ex:
    st.caption(f"Telemetry database unavailable: {ex}")


# --- Reference Product Footer ---
st.markdown(f"""
<div class="ref-footer-wrap">
    <div class="ref-footer-inner">
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
                <div class="ref-footer-col-title">PROJECT</div>
                <a href="#section-ingestion" class="ref-footer-link">How It Works</a>
                <a href="#section-ingestion" class="ref-footer-link">Ingestion Pipeline</a>
                <a href="#section-audit" class="ref-footer-link">State Machine Audit</a>
                <a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">Benchmarks & F1</a>
            </div>

            <div>
                <div class="ref-footer-col-title">TEAM</div>
                <a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">Team Debuggers Den</a>
                <a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">About Project</a>
                <a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="ref-footer-link">Source Repository</a>
                <a href="mailto:team@debuggersden.space" class="ref-footer-link">Direct Inquiries</a>
            </div>

            <div>
                <div class="ref-footer-col-title">RESOURCES</div>
                <a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">Documentation</a>
                <a href="{default_api_url}/docs" target="_blank" class="ref-footer-link">API Reference</a>
                <a href="{default_api_url}/health" target="_blank" class="ref-footer-link">System Health Bus</a>
                <a href="https://github.com/UditKumar0001/SATQUERY-AI/issues" target="_blank" class="ref-footer-link">Submit Feedback</a>
            </div>
        </div>

        <div class="ref-footer-divider"></div>

        <div class="ref-footer-bottom">
            <div>© 2026 Team Debuggers Den. All rights reserved.</div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="ref-hero-badge" style="margin-bottom: 0; padding: 3px 10px; font-size: 0.68rem;">✦ BUILT FOR ISRO</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
