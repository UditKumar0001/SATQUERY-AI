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
        "chip_bg": "#121924",
        "chip_text": "#cbd5e1",
        "chip_border": "#243247",
        "chip_hover_bg": "#1c2638",
        "chip_hover_text": "#00e5ff",
        "nav_bg": "#080c13",
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
        "bg_app": "#d9e0e8",
        "bg_panel": "#eaeff5",
        "bg_panel_sub": "#e0e7ef",
        "bg_input": "#ffffff",
        "border_color": "#94a3b8",
        "border_subtle": "#cbd5e1",
        "border_focus": "#0284c7",
        "text_primary": "#090d16",
        "text_secondary": "#334155",
        "text_muted": "#64748b",
        "accent_primary": "#0284c7",
        "accent_hover": "#0369a1",
        "btn_primary_bg": "#0284c7",
        "btn_primary_text": "#ffffff",
        "btn_primary_hover": "#0369a1",
        "chip_bg": "#e2e8f0",
        "chip_text": "#0f172a",
        "chip_border": "#94a3b8",
        "chip_hover_bg": "#cbd5e1",
        "chip_hover_text": "#0284c7",
        "nav_bg": "#eaeff5",
        "nav_border": "#94a3b8",
        "sidebar_bg": "#e2e8f0",
        "sidebar_border": "#94a3b8",
        "footer_bg": "#eaeff5",
        "footer_border": "#94a3b8",
        "metric_bg": "#edf2f7",
        "metric_value": "#0284c7",
        "result_bg": "#edf2f7",
        "result_border": "#94a3b8",
        "status_tag_bg": "rgba(2, 132, 199, 0.1)",
        "status_tag_border": "rgba(2, 132, 199, 0.35)",
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

    /* Mission Control Header Bar */
    .mc-header-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--nav-bg);
        border: 1px solid var(--nav-border);
        border-radius: 2px;
        padding: 10px 18px;
        margin-bottom: 20px;
    }}

    .mc-brand-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-primary);
    }}
    .mc-brand-sub {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.70rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        color: var(--accent-primary);
        margin-left: 8px;
        border-left: 1px solid var(--border-color);
        padding-left: 8px;
    }}

    .mc-nav-link {{
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-secondary);
        text-decoration: none;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        padding: 4px 10px;
        border: 1px solid transparent;
        border-radius: 2px;
        transition: all 0.15s ease;
    }}
    .mc-nav-link:hover {{
        color: var(--accent-primary);
        border-color: var(--border-color);
        background: var(--bg-panel-sub);
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

    /* File Uploader Sharp Technical Frame */
    [data-testid="stFileUploader"] section {{
        background: var(--bg-panel-sub) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        padding: 14px !important;
        transition: border-color 0.15s ease !important;
    }}
    [data-testid="stFileUploader"] section:hover {{
        border-color: var(--border-focus) !important;
    }}
    [data-testid="stFileUploader"] button {{
        background: var(--bg-panel) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
    }}

    /* Technical Input Field */
    [data-testid="stTextInput"] input {{
        background: var(--bg-input) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.90rem !important;
        padding: 10px 14px !important;
        transition: border-color 0.15s ease !important;
    }}
    [data-testid="stTextInput"] input:focus {{
        border-color: var(--border-focus) !important;
        box-shadow: none !important;
    }}

    /* Preset Secondary Buttons (Chips) */
    div[data-testid="stButton"] > button[kind="secondary"] {{
        background: var(--chip-bg) !important;
        color: var(--chip-text) !important;
        border: 1px solid var(--chip-border) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        padding: 8px 12px !important;
        width: 100% !important;
        transition: all 0.15s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="secondary"]:hover {{
        background: var(--chip-hover-bg) !important;
        color: var(--chip-hover-text) !important;
        border-color: var(--border-focus) !important;
    }}

    /* Primary Dispatch Action Button */
    div[data-testid="stButton"] > button[kind="primary"] {{
        background: var(--btn-primary-bg) !important;
        color: var(--btn-primary-text) !important;
        border: 1px solid var(--border-focus) !important;
        border-radius: 2px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        padding: 12px 24px !important;
        box-shadow: none !important;
        transition: background 0.15s ease !important;
    }}
    div[data-testid="stButton"] > button[kind="primary"]:hover {{
        background: var(--btn-primary-hover) !important;
        filter: brightness(1.05);
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

    /* Expanders */
    div[data-testid="stExpander"] {{
        background: var(--bg-panel) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        margin-bottom: 10px !important;
    }}
    div[data-testid="stExpander"] > details > summary {{
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
    }}

    /* Action Links & Download Buttons */
    div[data-testid="stDownloadButton"] > button {{
        background: var(--bg-panel-sub) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
    }}
    div[data-testid="stDownloadButton"] > button:hover {{
        border-color: var(--border-focus) !important;
        color: var(--accent-primary) !important;
    }}

    a[data-testid="stLinkButton"] {{
        background: var(--bg-panel-sub) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
    }}
    a[data-testid="stLinkButton"]:hover {{
        border-color: var(--border-focus) !important;
        color: var(--accent-primary) !important;
    }}

    /* Footer Instrument */
    .mc-footer {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--footer-bg);
        border: 1px solid var(--footer-border);
        border-radius: 2px;
        padding: 16px 20px;
        margin-top: 40px;
    }}
    .mc-footer-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.88rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--text-primary);
    }}
    .mc-footer-meta {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: var(--text-muted);
        margin-top: 2px;
    }}
</style>
""", unsafe_allow_html=True)


# --- Mission Control Top Navigation Bar ---
nav_left, nav_right = st.columns([3, 2])

with nav_left:
    st.markdown("""
    <div style="display: flex; align-items: center; padding: 6px 0;">
        <span class="mc-brand-title">SatQuery AI</span>
        <span class="mc-brand-sub">ISRO EO ORCHESTRATION CONSOLE // v1.0</span>
    </div>
    """, unsafe_allow_html=True)

with nav_right:
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 1, 1, 1.1])
    with nav_c1:
        st.markdown('<div style="padding-top: 8px; text-align: center;"><a href="#section-ingestion" class="mc-nav-link">[STUDIO]</a></div>', unsafe_allow_html=True)
    with nav_c2:
        st.markdown('<div style="padding-top: 8px; text-align: center;"><a href="#section-audit" class="mc-nav-link">[AUDIT]</a></div>', unsafe_allow_html=True)
    with nav_c3:
        st.markdown(f'<div style="padding-top: 8px; text-align: center;"><a href="{default_api_url}/docs" target="_blank" class="mc-nav-link">[SPECS ↗]</a></div>', unsafe_allow_html=True)
    with nav_c4:
        theme_label = "[MODE: DAY]" if is_dark else "[MODE: NIGHT]"
        if st.button(theme_label, key="theme_toggle_btn", help="Toggle between Night Operations and Daylight Ground-Control palette"):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)


# --- Sidebar: System Diagnostics & Health ---
with st.sidebar:
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;">
            TELEMETRY MONITOR
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--accent-primary); letter-spacing: 0.12em;">
            SUBSYSTEM STATUS BUS
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("[CONFIG: ENDPOINT DISPATCH]", expanded=False):
        API_URL = st.text_input(
            "BACKEND URL",
            value=default_api_url,
            help="Target FastAPI orchestrator endpoint"
        ).rstrip("/")

    st.markdown("<div style='margin-top: 14px; margin-bottom: 6px; font-family: \"JetBrains Mono\", monospace; font-weight: 700; font-size: 0.72rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.10em;'>SYSTEM READY STATE</div>", unsafe_allow_html=True)
    
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=3)
        if health_resp.status_code == 200:
            health = health_resp.json()
            st.markdown("""
            <div style="display: flex; align-items: center; background: var(--bg-panel-sub); border: 1px solid var(--border-color); border-left: 3px solid #10b981; padding: 7px 10px; margin-bottom: 12px;">
                <span class="telemetry-led led-green"></span>
                <span style="font-family: 'JetBrains Mono', monospace; color: #10b981; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em;">BUS ONLINE // 200 OK</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"<span style='font-family: \"JetBrains Mono\", monospace; font-size: 0.76rem;'>DB LINK: <code>{health.get('database')}</code></span>", unsafe_allow_html=True)
            hw = health.get("hardware", {})
            st.markdown(f"<span style='font-family: \"JetBrains Mono\", monospace; font-size: 0.76rem;'>ACCELERATOR: <code>{hw.get('device_name', 'Unknown')}</code> (<code>{hw.get('configured_device', 'cpu')}</code>)</span>", unsafe_allow_html=True)
            router_ready = health.get("router_llm_ready", False)
            if router_ready:
                st.markdown("<span style='font-family: \"JetBrains Mono\", monospace; font-size: 0.76rem;'>ROUTER LLM: <strong style='color: #10b981;'>[ACTIVE]</strong></span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='font-family: \"JetBrains Mono\", monospace; font-size: 0.76rem;'>ROUTER LLM: <strong style='color: #f59e0b;'>[KEY PENDING]</strong></span>", unsafe_allow_html=True)

            with st.expander("[ACTIVE TOOL REGISTRY]"):
                for tool in health.get("registered_tools", []):
                    st.code(f"{tool['task']} -> {tool['model_wrapper']}", language="bash")
        else:
            st.markdown(f"""
            <div style="display: flex; align-items: center; background: var(--bg-panel-sub); border: 1px solid var(--border-color); border-left: 3px solid #f43f5e; padding: 7px 10px; margin-bottom: 12px;">
                <span class="telemetry-led led-red"></span>
                <span style="font-family: 'JetBrains Mono', monospace; color: #ef4444; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em;">HTTP {health_resp.status_code} DEGRADED</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.markdown(f"""
        <div style="display: flex; align-items: center; background: var(--bg-panel-sub); border: 1px solid var(--border-color); border-left: 3px solid #ef4444; padding: 7px 10px; margin-bottom: 12px;">
            <span class="telemetry-led led-red"></span>
            <span style="font-family: 'JetBrains Mono', monospace; color: #ef4444; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em;">LINK OFFLINE // NO CARRIER</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Host connection inactive at `{API_URL}`. Initialize with:\n`uvicorn backend.main:app --port 8000`")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family: \"JetBrains Mono\", monospace; font-size: 0.70rem; color: var(--text-muted);'>TEAM DEBUGGERS DEN // ISRO DEMO</div>", unsafe_allow_html=True)


# --- Telemetry Hero Banner ---
st.markdown("""
<div class="telemetry-banner">
    <div class="telemetry-tag">MISSION DISPATCH // EARTH OBSERVATION MULTI-MODAL PIPELINE</div>
    <div class="telemetry-title">SatQuery AI Ground Station</div>
    <p class="telemetry-desc">
        Deterministic multi-sensor routing and visual reasoning console for spaceborne observation payloads. Integrates LangGraph state machine with <strong>GeoChat</strong> (optical VQA / localization), <strong>GeoLLaVA</strong> (bi-temporal change analysis), and <strong>EarthGPT</strong> (optical-SAR cross-sensor fusion).
    </p>
</div>
""", unsafe_allow_html=True)


# --- Section 1: Ingestion ---
st.markdown("""
<div id="section-ingestion" class="section-header-tag">
    <span>01 // SENSOR INGESTION SUBSYSTEM</span>
    <span style="font-size: 0.72rem; color: var(--text-muted);">SUPPORTED: GTIFF / PNG / MULTI-BAND</span>
</div>
""", unsafe_allow_html=True)

col_up1, col_up2 = st.columns(2, gap="large")

with col_up1:
    st.markdown("""
    <div class="tile-sub-title">TILE A — PRIMARY OBSERVATION</div>
    <div class="tile-sub-desc">High-resolution optical raster tile, multispectral band, or reference SAR backscatter.</div>
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
            st.image(pil_img1, caption=f"TILE A: {img1_file.name} [{pil_img1.width}×{pil_img1.height}px]", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img1_file.name} (GeoTIFF/Multi-band Sensor Tile)")

with col_up2:
    st.markdown("""
    <div class="tile-sub-title">TILE B — SECONDARY / TEMPORAL PAIR (OPTIONAL)</div>
    <div class="tile-sub-desc">Post-event comparative tile for change analysis or co-registered SAR for cross-sensor fusion.</div>
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
            st.image(pil_img2, caption=f"TILE B: {img2_file.name} [{pil_img2.width}×{pil_img2.height}px]", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img2_file.name} (GeoTIFF/Multi-band Sensor Tile)")


# --- Section 2: Query Specification ---
st.markdown("""
<div class="section-header-tag">
    <span>02 // QUERY SPECIFICATION & TASK ROUTING</span>
    <span style="font-size: 0.72rem; color: var(--text-muted);">ORCHESTRATOR: GEMINI / HEURISTIC FALLBACK</span>
</div>
""", unsafe_allow_html=True)

# Preset Technical Buttons
col_p1, col_p2, col_p3 = st.columns(3, gap="small")
with col_p1:
    if st.button("[TASK: VQA // AIRCRAFT RECON]", key="preset_air", help="Target detection and runway inventory"):
        st.session_state.query_input_val = "Detect and count the aircraft parked at the airport terminals."
with col_p2:
    if st.button("[TASK: CAPTION // SURFACE BIOME]", key="preset_land", help="Macro land-cover and surface categorization"):
        st.session_state.query_input_val = "Identify the dominant land cover and vegetation types across this scene."
with col_p3:
    if st.button("[TASK: DELTA // BI-TEMPORAL CHANGE]", key="preset_change", help="Topological delta detection across epochs"):
        st.session_state.query_input_val = "Compare both images and identify newly constructed buildings or infrastructure."

# Query Input Field
query_input = st.text_input(
    "Query Specification Input",
    value=st.session_state.query_input_val,
    placeholder="ENTER NATURAL LANGUAGE DIRECTIVE OR MISSION QUERY (e.g. 'Assess shoreline erosion and detect infrastructure modifications')...",
    label_visibility="collapsed"
)

# Analyze Button
st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
analyze_clicked = st.button("[ INITIATE INFERENCE & DISPATCH ORCHESTRATOR ]", type="primary", use_container_width=True)

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
st.markdown("""
<div id="section-audit" class="section-header-tag">
    <span>03 // MISSION AUDIT TRAIL & HISTORICAL TELEMETRY</span>
    <span style="font-size: 0.72rem; color: var(--text-muted);">DATABASE: SQLITE / AUDITABLE</span>
</div>
""", unsafe_allow_html=True)

try:
    hist_resp = requests.get(f"{API_URL}/history?limit=10", timeout=5)
    if hist_resp.status_code == 200:
        hist_data = hist_resp.json()
        entries = hist_data.get("history", [])
        if not entries:
            st.caption("[NOTICE] Database state: No historical records detected.")
        else:
            for item in entries:
                task = item.get("selected_task", "unknown")
                model = item.get("model_used", "unknown")
                conf = item.get("output_confidence") or item.get("router_confidence") or 0.0
                qid = item.get("id")
                created = item.get("created_at", "")[:19].replace("T", " ")

                header_label = f"LOG #{qid:04d} // [{task.upper()}] // CONF: {conf:.0%} // {item.get('query_text')}"
                with st.expander(header_label):
                    col_h1, col_h2 = st.columns([3, 1])
                    with col_h1:
                        st.markdown(f"""
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.80rem; margin-bottom: 6px;">
                            <span>TASK: <strong>{task}</strong></span> |
                            <span>MODEL: <strong>{model}</strong></span> |
                            <span>STATUS: {item.get('validation_msg')}</span>
                        </div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; color: var(--text-muted); margin-bottom: 8px;">
                            TIMESTAMP: {created} UTC
                        </div>
                        """, unsafe_allow_html=True)
                        if item.get("trace"):
                            st.json(item["trace"])
                    with col_h2:
                        if qid:
                            st.link_button("[PDF REPORT]", f"{API_URL}/report/{qid}", use_container_width=True)
    else:
        st.caption(f"[NOTICE] Audit bus communication fault (HTTP {hist_resp.status_code})")
except Exception as ex:
    st.caption(f"[NOTICE] Telemetry bus unavailable: {ex}")


# --- Ground Control Footer ---
st.markdown(f"""
<div class="mc-footer">
    <div>
        <div class="mc-footer-title">SATQUERY AI // EARTH OBSERVATION GROUND STATION</div>
        <div class="mc-footer-meta">ISRO EO-AI DEMONSTRATOR // TEAM DEBUGGERS DEN • © 2026</div>
    </div>
    <div style="display: flex; align-items: center; gap: 14px;">
        <a href="https://github.com/UditKumar0001/SATQUERY-AI" target="_blank" class="mc-nav-link">[GITHUB]</a>
        <a href="{default_api_url}/docs" target="_blank" class="mc-nav-link">[API SPECS]</a>
        <a href="{default_api_url}/health" target="_blank" class="mc-nav-link">[HEALTH BUS]</a>
    </div>
</div>
""", unsafe_allow_html=True)
