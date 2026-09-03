# frontend/streamlit_app.py
import io
import os
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="SatQuery AI — Earth Observation Intelligence",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom modern styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgba(15, 23, 42, 0.95) 0%, rgba(3, 7, 18, 1) 90%);
        color: #f8fafc;
    }

    .glass-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 20px;
        backdrop-filter: blur(12px);
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }

    .badge-task {
        display: inline-block;
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.025em;
        text-transform: uppercase;
    }

    .badge-model {
        display: inline-block;
        background: linear-gradient(135deg, #059669, #10b981);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 6px;
    }

    .badge-rejected {
        display: inline-block;
        background: linear-gradient(135deg, #dc2626, #ef4444);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.6rem;
        font-weight: 700;
        color: #38bdf8;
    }

    div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# --- Sidebar: System Diagnostics & Health ---
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/satellite.png", width=64)
    st.title("SatQuery AI")
    st.caption("Multi-Modal Earth Observation Orchestrator")

    st.divider()
    st.subheader("System Health")
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=3)
        if health_resp.status_code == 200:
            health = health_resp.json()
            st.success("🟢 API Connected")
            st.write(f"**Database:** `{health.get('database')}`")
            hw = health.get("hardware", {})
            st.write(f"**Compute:** `{hw.get('device_name', 'Unknown')}` (`{hw.get('configured_device', 'cpu')}`)")
            router_ready = health.get("router_llm_ready", False)
            if router_ready:
                st.write("**Router LLM:** 🟢 Ready")
            else:
                st.warning("**Router LLM:** ⚠️ Key Missing")

            with st.expander("Registered Tools"):
                for tool in health.get("registered_tools", []):
                    st.code(f"{tool['task']} -> {tool['model_wrapper']}", language="bash")
        else:
            st.error(f"⚠️ Health check returned HTTP {health_resp.status_code}")
    except Exception as e:
        st.error(f"🔴 Cannot reach backend at `{API_URL}`")
        st.caption("Ensure backend is running: `uvicorn backend.main:app --port 8000`")

    st.divider()
    st.caption("Team Debuggers Den • SatQuery v1.0")


# --- Main Workspace ---
st.title("🛰️ SatQuery AI — Earth Observation Query Platform")
st.markdown(
    "Query satellite and aerial imagery with natural language. Powered by multimodal vision-language models (**GeoChat**, **GeoLLaVA**, **EarthGPT**) with LangGraph orchestration."
)

col_up1, col_up2 = st.columns(2)
with col_up1:
    st.subheader("Primary Image (Image 1)")
    img1_file = st.file_uploader(
        "Upload primary satellite/aerial tile",
        type=["tif", "tiff", "png", "jpg", "jpeg"],
        key="uploader_img1"
    )
    if img1_file:
        try:
            pil_img1 = Image.open(img1_file)
            st.image(pil_img1, caption=f"Image 1: {img1_file.name} ({pil_img1.width}x{pil_img1.height})", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img1_file.name} (GeoTIFF/Multi-band)")

with col_up2:
    st.subheader("Secondary Image (Optional / Change Detection)")
    img2_file = st.file_uploader(
        "Upload comparison image for bi-temporal tasks",
        type=["tif", "tiff", "png", "jpg", "jpeg"],
        key="uploader_img2"
    )
    if img2_file:
        try:
            pil_img2 = Image.open(img2_file)
            st.image(pil_img2, caption=f"Image 2: {img2_file.name} ({pil_img2.width}x{pil_img2.height})", use_container_width=True)
        except Exception:
            st.info(f"Loaded {img2_file.name} (GeoTIFF/Multi-band)")

# Prompt / Query Box
query_input = st.text_input(
    "Enter your analysis question or instruction:",
    placeholder="e.g., 'Detect and count airplanes on the runway', 'What is the land cover?', 'Identify changes between Image 1 and Image 2'"
)

# Quick sample buttons
cols_btn = st.columns([1, 1, 1, 3])
with cols_btn[0]:
    if st.button("✈️ Aircraft Detection"):
        query_input = "Detect and count the aircraft parked at the terminals."
with cols_btn[1]:
    if st.button("🌲 Land Classification"):
        query_input = "Identify the dominant land cover and vegetation types."
with cols_btn[2]:
    if st.button("🔄 Change Analysis"):
        query_input = "Compare both images and identify newly constructed buildings."

analyze_clicked = st.button("🚀 Analyze Imagery", type="primary", use_container_width=True)

if analyze_clicked:
    if not img1_file:
        st.warning("Please upload at least one image (Image 1) to proceed.")
    elif not query_input.strip():
        st.warning("Please enter a question or instruction about the imagery.")
    else:
        with st.spinner("Orchestrating multi-modal analysis across vision-language pipeline..."):
            try:
                # Prepare multipart payload
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
                        st.error(f"🚫 Request Rejected by Guardrails: {resp.get('validation_msg', 'Query or imagery incompatible.')}")
                        if "trace" in resp and resp["trace"]:
                            with st.expander("Inspection & Validation Trace"):
                                st.json(resp["trace"])
                    else:
                        st.success("Analysis Completed Successfully!")

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
                            st.metric("Query ID", f"#{resp.get('query_id')}")

                        # Answer Section
                        result_data = resp.get("result", {})
                        answer_text = result_data.get("text") if isinstance(result_data, dict) else str(result_data)

                        st.markdown("### 📝 Analysis Result")
                        st.info(answer_text or "No textual result returned.")

                        # Report Download
                        query_id = resp.get("query_id")
                        if query_id:
                            try:
                                report_resp = requests.get(f"{API_URL}/report/{query_id}", timeout=10)
                                if report_resp.status_code == 200:
                                    st.download_button(
                                        label="📄 Download PDF Audit Report",
                                        data=report_resp.content,
                                        file_name=f"satquery_report_{query_id}.pdf",
                                        mime="application/pdf"
                                    )
                            except Exception as err:
                                st.caption(f"Report generation note: {err}")

                        # Execution Trace Details
                        with st.expander("🔍 Auditable Execution Trace"):
                            st.json(resp.get("trace", {}))

            except requests.exceptions.RequestException as req_err:
                st.error(f"Failed to communicate with API server: {req_err}")


# --- History Section ---
st.divider()
st.subheader("📜 Recent Queries & Audit Log")

try:
    hist_resp = requests.get(f"{API_URL}/history?limit=10", timeout=5)
    if hist_resp.status_code == 200:
        hist_data = hist_resp.json()
        entries = hist_data.get("history", [])
        if not entries:
            st.caption("No queries recorded in database yet.")
        else:
            for item in entries:
                task = item.get("selected_task", "unknown")
                model = item.get("model_used", "unknown")
                conf = item.get("output_confidence") or item.get("router_confidence") or 0.0
                qid = item.get("id")
                created = item.get("created_at", "")[:19].replace("T", " ")

                with st.expander(f"Query #{qid}: {item.get('query_text')} — [{task.upper()}] ({conf:.0%})"):
                    col_h1, col_h2 = st.columns([3, 1])
                    with col_h1:
                        st.write(f"**Task:** `{task}` | **Model:** `{model}` | **Validation:** `{item.get('validation_msg')}`")
                        st.caption(f"Recorded at: {created}")
                        if item.get("trace"):
                            st.json(item["trace"])
                    with col_h2:
                        if qid:
                            st.link_button("Download PDF", f"{API_URL}/report/{qid}")
    else:
        st.caption(f"Could not load history (HTTP {hist_resp.status_code})")
except Exception as ex:
    st.caption(f"History unavailable: {ex}")
