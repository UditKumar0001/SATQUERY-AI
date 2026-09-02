# orchestrator/nodes.py
import json
import os
import re
from dotenv import load_dotenv
import google.generativeai as genai
from .graph_state import AgentState

load_dotenv()

# Configure Google Generative AI
_api_key = os.getenv("GEMINI_API_KEY")
if _api_key and not _api_key.startswith("your-key"):
    genai.configure(api_key=_api_key)

_ROUTER_MODEL_NAME = os.getenv("GEMINI_ROUTER_MODEL", "gemini-3.6-flash")
_router = None


def _get_router_model():
    global _router
    if _router is None:
        try:
            _router = genai.GenerativeModel(_ROUTER_MODEL_NAME)
        except Exception:
            try:
                _router = genai.GenerativeModel("gemini-1.5-flash")
            except Exception:
                _router = None
    return _router


ROUTER_SYSTEM_PROMPT = """You are a task router for a remote-sensing analysis system with exactly three tools:
  - vqa_caption_ground: single image, VQA/caption/grounding
  - change_analysis: two images, same location, different timestamps
  - optical_sar_fusion: two images, one optical one SAR, co-registered

Output ONLY valid JSON matching this schema:
{"task": "<vqa_caption_ground|change_analysis|optical_sar_fusion|reject>", "mode": "<vqa|caption|ground|null>", "reason": "<short justification>", "confidence": 0.0-1.0}"""


def _clean_json_string(text: str) -> str:
    """Extract raw JSON string from potentially markdown-wrapped LLM text."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def classify_node(state: AgentState) -> AgentState:
    """Classify the incoming query and image metadata using Gemini router LLM."""
    summary = {
        "num_images": len(state.get("images_meta", [])),
        "modalities": [m.get("modality", "unknown") for m in state.get("images_meta", [])]
    }
    prompt = f"{ROUTER_SYSTEM_PROMPT}\n\nQuery: {state.get('query', '')}\nMetadata: {json.dumps(summary)}"

    routed = None
    router_model = _get_router_model()

    if router_model:
        try:
            response = router_model.generate_content(prompt)
            clean_text = _clean_json_string(response.text)
            routed = json.loads(clean_text)
        except Exception as e:
            print(f"[ClassifyNode] Router API error or parse failure: {e}")

    # Deterministic fallback router if LLM unavailable or invalid output
    if not routed or not isinstance(routed, dict) or "task" not in routed:
        q_lower = state.get("query", "").lower()
        num_imgs = summary["num_images"]
        modalities = summary["modalities"]

        if num_imgs == 1:
            mode = "caption" if "describe" in q_lower or "caption" in q_lower else ("ground" if "locate" in q_lower or "where" in q_lower else "vqa")
            routed = {"task": "vqa_caption_ground", "mode": mode, "reason": "Single image query routed to GeoChat", "confidence": 0.90}
        elif num_imgs == 2 and set(modalities) == {"optical", "SAR"}:
            routed = {"task": "optical_sar_fusion", "mode": None, "reason": "Dual sensor optical+SAR pair routed to EarthGPT", "confidence": 0.95}
        elif num_imgs == 2:
            routed = {"task": "change_analysis", "mode": None, "reason": "Bi-temporal image pair routed to GeoLLaVA", "confidence": 0.92}
        else:
            routed = {"task": "reject", "mode": None, "reason": "Unsupported image configuration", "confidence": 0.0}

    state["task"] = routed.get("task", "reject")
    state["mode"] = routed.get("mode")
    state["router_confidence"] = float(routed.get("confidence", 0.85))
    return state


# orchestrator/nodes.py (part 2 of 4) - Validate Node
from .registry import TOOL_REGISTRY
from .compatibility import same_location_score, SAME_LOCATION_THRESHOLD


def validate_node(state: AgentState) -> AgentState:
    """Deterministic validation node checking count, modality, and spatial compatibility."""
    task = state.get("task")
    if not task or task not in TOOL_REGISTRY:
        state["validation_ok"] = False
        state["validation_msg"] = f"Unknown or rejected task '{task}'"
        return state

    req = TOOL_REGISTRY[task]["requires"]
    meta = state.get("images_meta", [])
    raw = state.get("images_raw", [])

    # 1. Number of images check
    if req.get("num_images") != len(meta):
        state["validation_ok"] = False
        state["validation_msg"] = f"{task} requires {req['num_images']} image(s), got {len(meta)}"
        return state

    # 2. Modality check for single-image tool
    if "modality" in req and any(m.get("modality") not in req["modality"] for m in meta):
        state["validation_ok"] = False
        state["validation_msg"] = f"Unsupported modality for {task}"
        return state

    # 3. Modality check for multisensor dual-image tool
    if "modalities" in req:
        actual_modalities = sorted(m.get("modality", "unknown") for m in meta)
        required_modalities = sorted(req["modalities"])
        if actual_modalities != required_modalities:
            state["validation_ok"] = False
            state["validation_msg"] = f"{task} requires one optical and one SAR image, got {actual_modalities}"
            return state

    # 4. Spatial / co-location compatibility check
    if req.get("same_location") or req.get("co_registered"):
        if len(raw) >= 2:
            score = same_location_score(raw[0], raw[1])
            if score < SAME_LOCATION_THRESHOLD:
                state["validation_ok"] = False
                state["validation_msg"] = f"Images do not appear to be the same location (score={score:.2f} < {SAME_LOCATION_THRESHOLD})"
                return state
        else:
            state["validation_ok"] = False
            state["validation_msg"] = f"{task} requires 2 raw images for spatial verification"
            return state

    state["validation_ok"] = True
    state["validation_msg"] = "ok"
    return state


# orchestrator/nodes.py (part 3 of 4) - Dispatch & Reject Nodes
from models.geochat_wrapper import GeoChatModel
from models.geollava_wrapper import GeoLLaVAModel
from models.earthgpt_wrapper import EarthGPTModel

_geochat = None
_geollava = None
_earthgpt = None


def _get_models():
    global _geochat, _geollava, _earthgpt
    if _geochat is None:
        _geochat = GeoChatModel()
    if _geollava is None:
        _geollava = GeoLLaVAModel()
    if _earthgpt is None:
        _earthgpt = EarthGPTModel()
    return _geochat, _geollava, _earthgpt


def dispatch_node(state: AgentState) -> AgentState:
    """Execute the appropriate vision-language model based on validated task routing."""
    task = state.get("task")
    imgs = state.get("images_raw", [])
    query = state.get("query", "")
    mode = state.get("mode")

    geochat, geollava, earthgpt = _get_models()

    if task == "vqa_caption_ground":
        state["result"] = geochat.infer(imgs[0], query, mode=mode or "vqa")
    elif task == "change_analysis":
        state["result"] = geollava.infer(imgs[0], imgs[1], query)
    elif task == "optical_sar_fusion":
        state["result"] = earthgpt.infer(imgs[0], imgs[1], query)
    else:
        state["result"] = {"text": f"Unsupported execution task: {task}"}

    return state


def reject_node(state: AgentState) -> AgentState:
    """Handle early-rejected or invalidated requests gracefully with audit trail."""
    msg = state.get("validation_msg") or "Request rejected by controller validation gate."
    state["result"] = {"text": f"Request rejected: {msg}"}
    return state


# orchestrator/nodes.py (part 4 of 4) - Combine Node & Trace Builder
from datetime import datetime, timezone


def combine_node(state: AgentState) -> AgentState:
    """Compile execution diagnostics and produce auditable trace summary with calibrated confidence."""
    result = state.get("result") or {}
    text = result.get("text", "").lower()

    # Lexical hedging analysis to calibrate output confidence
    hedges = ["possibly", "unclear", "may", "might", "uncertain", "approximate", "inconclusive"]
    hedge_penalties = sum(0.1 for h in hedges if h in text)
    output_conf = max(0.40, min(0.95, 0.90 - hedge_penalties))

    task = state.get("task")
    state["trace"] = {
        "query": state.get("query", ""),
        "selected_task": task,
        "model_used": TOOL_REGISTRY.get(task, {}).get("model", "none") if task else "none",
        "parameters": {"mode": state.get("mode")},
        "validation": state.get("validation_msg", "ok"),
        "router_confidence": state.get("router_confidence"),
        "output_confidence": round(output_conf, 2),
        "output_summary": result.get("text", "")[:220],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return state



