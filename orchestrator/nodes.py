# orchestrator/nodes.py
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

from geo_engine import IncompatibleRastersError, run_change_detection_pipeline
from geo_engine.segmentation import SAM2Segmentor, refine_change_with_sam2
from models.earthgpt_wrapper import EarthGPTModel
from models.geochat_wrapper import GeoChatModel
from models.geollava_wrapper import GeoLLaVAModel
from .compatibility import SAME_LOCATION_THRESHOLD, same_location_score
from .graph_state import AgentState
from .registry import TOOL_REGISTRY

load_dotenv()

_ROUTER_MODEL_NAME = os.getenv("OPENAI_ROUTER_MODEL", "gpt-4o-mini")
_client = None


def _get_openai_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and not api_key.startswith("your-"):
            try:
                _client = OpenAI(api_key=api_key)
            except Exception as e:
                print(f"[ClassifyNode] Failed to initialize OpenAI client: {e}")
                _client = None
    return _client


ROUTER_SYSTEM_PROMPT = """You are a task router for a remote-sensing analysis system with these tools:
  - general_chat: zero images, general conversation or remote sensing concept explanation
  - vqa_caption_ground: single image, VQA/caption/grounding
  - change_analysis: two images, same location, bi-temporal change detection
  - optical_sar_fusion: two images, one optical one SAR, co-registered

CRITICAL RULES:
- If num_images is 0, ALWAYS select task "general_chat" and mode "chat".
- If num_images is 1, ALWAYS select task "vqa_caption_ground" and mode "caption", "ground", or "vqa". NEVER select "general_chat" when num_images is 1.
- If num_images is 2 and modalities are optical and SAR, select "optical_sar_fusion".
- If num_images is 2 and both are optical, select "change_analysis".

Output ONLY valid JSON matching this schema:
{"task": "<general_chat|vqa_caption_ground|change_analysis|optical_sar_fusion|reject>", "mode": "<vqa|caption|ground|chat|change|null>", "reason": "<short justification>", "confidence": 0.0-1.0}"""


def _clean_json_string(text: str) -> str:
    """Extract raw JSON string from potentially markdown-wrapped LLM text."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def classify_node(state: AgentState) -> AgentState:
    """Classify the incoming query and image metadata using router LLM or deterministic fallback."""
    num_imgs = len(state.get("images_meta", []))
    modalities = [m.get("modality", "unknown") for m in state.get("images_meta", [])]
    summary = {
        "num_images": num_imgs,
        "modalities": modalities
    }
    user_content = f"Query: {state.get('query', '')}\nMetadata: {json.dumps(summary)}"

    routed = None
    client = _get_openai_client()

    if client:
        try:
            response = client.chat.completions.create(
                model=_ROUTER_MODEL_NAME,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw_text = response.choices[0].message.content or "{}"
            clean_text = _clean_json_string(raw_text)
            routed = json.loads(clean_text)
        except Exception as e:
            print(f"[ClassifyNode] Router API error or parse failure: {e}")

    # Deterministic fallback router if LLM unavailable or invalid output
    if not routed or not isinstance(routed, dict) or "task" not in routed:
        q_lower = state.get("query", "").lower()
        num_imgs = summary["num_images"]
        modalities = summary["modalities"]

        if num_imgs == 0:
            routed = {
                "task": "general_chat",
                "mode": "chat",
                "reason": "Text-only query routed to conversational assistant",
                "confidence": 0.95
            }
        elif num_imgs == 1:
            mode = "caption" if "describe" in q_lower or "caption" in q_lower else ("ground" if "locate" in q_lower or "where" in q_lower else "vqa")
            routed = {"task": "vqa_caption_ground", "mode": mode, "reason": "Single image query routed to GeoChat", "confidence": 0.90}
        elif num_imgs == 2 and set(modalities) == {"optical", "SAR"}:
            routed = {"task": "optical_sar_fusion", "mode": None, "reason": "Dual sensor optical+SAR pair routed to EarthGPT", "confidence": 0.95}
        elif num_imgs == 2:
            routed = {"task": "change_analysis", "mode": "change", "reason": "Bi-temporal image pair routed to Geo Evidence Engine", "confidence": 0.92}
        else:
            routed = {"task": "reject", "mode": None, "reason": "Unsupported image configuration", "confidence": 0.0}

    # Ensure consistency between image count and routed task
    if routed and isinstance(routed, dict) and "task" in routed:
        task_name = routed["task"]
        if num_imgs == 0 and task_name != "general_chat":
            routed["task"] = "general_chat"
            routed["mode"] = "chat"
        elif num_imgs == 1 and task_name in ("general_chat", "change_analysis", "optical_sar_fusion"):
            routed["task"] = "vqa_caption_ground"
        elif num_imgs == 2 and task_name in ("general_chat", "vqa_caption_ground"):
            if set(modalities) == {"optical", "SAR"}:
                routed["task"] = "optical_sar_fusion"
            else:
                routed["task"] = "change_analysis"

    # Normalize mode for vqa_caption_ground
    if routed and isinstance(routed, dict) and routed.get("task") == "vqa_caption_ground":
        if routed.get("mode") not in ("caption", "ground", "vqa"):
            q_lower = state.get("query", "").lower()
            if any(k in q_lower for k in ("describe", "caption", "terrain", "land cover", "scene", "overview")):
                routed["mode"] = "caption"
            elif any(k in q_lower for k in ("locate", "where", "detect", "ground", "find", "coordinate")):
                routed["mode"] = "ground"
            else:
                routed["mode"] = "vqa"

    state["task"] = routed.get("task", "reject")
    state["mode"] = routed.get("mode")
    state["router_confidence"] = float(routed.get("confidence", 0.85))

    # Detect if user explicitly requests fine-grained segmentation / boundary delineation
    q_lower = state.get("query", "").lower()
    seg_keywords = ["segment", "segmentation", "precise", "boundary", "boundaries", "outline", "delineate", "delineation", "exact region", "exact building", "polygon"]
    state["requires_segmentation"] = any(k in q_lower for k in seg_keywords)

    return state


def validate_node(state: AgentState) -> AgentState:
    """Deterministic validation node checking image counts, modalities, and spatial compatibility."""
    task = state.get("task")
    meta = state.get("images_meta", [])

    # Special handling for general conversation
    if task == "general_chat":
        if len(meta) == 0:
            state["validation_ok"] = True
            state["validation_msg"] = "General conversation validated"
            return state
        else:
            state["validation_ok"] = False
            state["validation_msg"] = "General conversation does not support images"
            return state

    if not task or task not in TOOL_REGISTRY:
        state["validation_ok"] = False
        state["validation_msg"] = f"Unknown or rejected task '{task}'"
        return state

    req = TOOL_REGISTRY[task]["requires"]
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


def geo_evidence_node(state: AgentState) -> AgentState:
    """Execute deterministic Geo Evidence Engine for bi-temporal change detection."""
    imgs = state.get("images_raw", [])
    query = state.get("query", "").lower()

    if len(imgs) < 2:
        state["validation_ok"] = False
        state["validation_msg"] = "Change analysis requires at least 2 images."
        return state

    # Detect index preference from query keywords
    if any(k in query for k in ["water", "flood", "lake", "river", "ndwi"]):
        index = "ndwi"
    elif any(k in query for k in ["building", "built", "urban", "construction", "ndbi"]):
        index = "ndbi"
    else:
        index = "ndvi"

    # Direction preference
    direction = "auto"
    if any(k in query for k in ["decrease", "loss", "decline", "drop", "deforestation"]):
        direction = "decrease"
    elif any(k in query for k in ["increase", "gain", "expansion", "growth"]):
        direction = "increase"

    try:
        evidence = run_change_detection_pipeline(
            t1_path=imgs[0],
            t2_path=imgs[1],
            index=index,
            threshold=0.25,
            direction=direction,
        )
        state["geo_evidence"] = evidence
        state["change_mask"] = evidence.get("mask_path")
        state["geojson"] = evidence.get("geojson")
        state["overlay_path"] = evidence.get("overlay_path")
    except IncompatibleRastersError as e:
        state["validation_ok"] = False
        state["validation_msg"] = f"Incompatible satellite rasters: {e}"
        state["result"] = {
            "text": f"Change analysis failed due to incompatible rasters: {e}",
            "answer": f"Change analysis failed due to incompatible rasters: {e}",
            "error": str(e),
        }
    except Exception as e:
        state["validation_ok"] = False
        state["validation_msg"] = f"Geo Evidence Engine error: {e}"
        state["result"] = {
            "text": f"Geo Evidence Engine error: {e}",
            "answer": f"Geo Evidence Engine error: {e}",
            "error": str(e),
        }

    return state


def sam2_node(state: AgentState) -> AgentState:
    """Execute SAM 2 secondary visual boundary refinement on candidate change regions."""
    evidence = state.get("geo_evidence")
    imgs = state.get("images_raw", [])

    if not evidence or not evidence.get("change_detected") or len(imgs) < 2:
        return state

    try:
        seg_res = refine_change_with_sam2(
            change_result=evidence,
            t2_raster=imgs[1],
        )
        state["segmentation_evidence"] = seg_res

        # If SAM 2 refined segment polygons, enrich state geojson
        if seg_res.get("segmentation_detected") and seg_res.get("segments"):
            features = []
            for s in seg_res["segments"]:
                gj = s.get("geojson", {})
                if gj.get("features"):
                    features.extend(gj["features"])
            if features:
                state["geojson"] = {
                    "type": "FeatureCollection",
                    "features": features,
                }
    except Exception as e:
        state["segmentation_evidence"] = {
            "segmentation_detected": False,
            "status": "unavailable",
            "model": "SAM2",
            "source": "geo_evidence_candidate",
            "error": str(e),
        }

    return state


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
    """Execute appropriate vision-language model or synthesize evidence-grounded final response."""
    task = state.get("task")
    imgs = state.get("images_raw", [])
    query = state.get("query", "")
    mode = state.get("mode")

    geochat, geollava, earthgpt = _get_models()

    if task == "vqa_caption_ground":
        state["result"] = geochat.infer(imgs[0], query, mode=mode or "vqa")

    elif task == "change_analysis":
        evidence = state.get("geo_evidence")
        seg_evidence = state.get("segmentation_evidence")

        if evidence:
            change_detected = evidence.get("change_detected", False)
            if change_detected:
                change_type = evidence.get("change_type", "spectral change")
                area_ha = evidence.get("changed_area_ha", 0.0)
                pct = evidence.get("change_percent", 0.0)
                pixels = evidence.get("changed_pixels", 0)

                ans = (
                    f"Bi-temporal geospatial change analysis detected **{change_type}** across the monitored region.\n\n"
                    f"- **Measured Changed Area**: {area_ha:.2f} hectares ({area_ha * 10000:.0f} m²)\n"
                    f"- **Change Magnitude**: {pct:.1f}% of analyzed scene ({pixels} changed pixels)\n"
                    f"- **Evidence Basis**: {evidence.get('evidence_type', 'spectral_difference')}\n"
                )

                if seg_evidence:
                    if seg_evidence.get("segmentation_detected"):
                        segs = seg_evidence.get("segments", [])
                        tot_ha = seg_evidence.get("total_refined_area_ha", 0.0)
                        ans += (
                            f"\n**SAM 2 Visual Boundary Refinement**:\n"
                            f"- Identified {len(segs)} refined candidate object region(s) covering {tot_ha:.2f} hectares.\n"
                        )
                        if segs and "confidence" in segs[0]:
                            ans += f"- Refinement Quality / Confidence: {segs[0]['confidence']:.2f}\n"
                    elif seg_evidence.get("status") == "unavailable":
                        ans += "\n*Note: Change was verified by Geo Evidence Engine, but precise segmentation is currently unavailable in this environment.*\n"
            else:
                ans = (
                    "Bi-temporal comparative analysis detected no statistically significant land-cover or "
                    "spectral change between the earlier (T1) and subsequent (T2) acquisitions; "
                    "canopy reflectance and surface structures remain stable."
                )

            state["result"] = {
                "text": ans,
                "answer": ans,
                "geo_evidence": evidence,
                "segmentation_evidence": seg_evidence,
                "change_mask": state.get("change_mask"),
                "geojson": state.get("geojson"),
                "overlay_path": state.get("overlay_path"),
                "mode": "change",
            }
        elif len(imgs) >= 2:
            state["result"] = geollava.infer(imgs[0], imgs[1], query)
        else:
            state["result"] = {
                "text": "Change analysis requires 2 images.",
                "answer": "Change analysis requires 2 images.",
            }

    elif task == "optical_sar_fusion":
        state["result"] = earthgpt.infer(imgs[0], imgs[1], query)

    elif task == "general_chat":
        q_lower = query.lower()
        if "ndvi" in q_lower:
            reply = (
                "**NDVI (Normalized Difference Vegetation Index)** is a remote-sensing spectral index "
                "calculated as (NIR - Red) / (NIR + Red). It measures the presence and density of green vegetation "
                "by contrasting high chlorophyll reflectance in the near-infrared with absorption in the red band."
            )
        elif "remote sensing" in q_lower:
            reply = (
                "**Remote Sensing** is the science of acquiring information about the Earth's surface using satellite "
                "or airborne sensors across optical, multispectral, hyperspectral, and Synthetic Aperture Radar (SAR) wavelengths."
            )
        elif any(g in q_lower for g in ["hi", "hello", "hey", "greetings"]):
            reply = (
                "👋 **Hello! Welcome to SatQuery AI.**\n\n"
                "I am your Earth Observation and Satellite Imagery Intelligence Assistant. "
                "I can assist you with remote sensing analysis, bi-temporal change detection, and multi-sensor fusion."
            )
        else:
            client = _get_openai_client()
            if client:
                try:
                    resp = client.chat.completions.create(
                        model=_ROUTER_MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "You are SatQuery AI, an Earth Observation intelligence assistant."},
                            {"role": "user", "content": query}
                        ],
                        max_tokens=300,
                    )
                    reply = resp.choices[0].message.content or f"SatQuery AI: received query '{query}'."
                except Exception:
                    reply = f"SatQuery AI Earth Observation assistant: received query '{query}'."
            else:
                reply = f"SatQuery AI Earth Observation assistant: received query '{query}'."

        state["result"] = {"text": reply, "answer": reply}

    else:
        state["result"] = {"text": f"Unsupported execution task: {task}", "answer": f"Unsupported execution task: {task}"}

    return state


def reject_node(state: AgentState) -> AgentState:
    """Handle early-rejected or invalidated requests gracefully with audit trail."""
    msg = state.get("validation_msg") or "Request rejected by controller validation gate."
    state["result"] = {"text": f"Request rejected: {msg}", "answer": f"Request rejected: {msg}"}
    return state


def combine_node(state: AgentState) -> AgentState:
    """Compile execution diagnostics and produce auditable trace summary with calibrated confidence."""
    result = state.get("result") or {}
    text = result.get("text", "").lower()

    # Lexical hedging analysis to calibrate output confidence
    hedges = ["possibly", "unclear", "may", "might", "uncertain", "approximate", "inconclusive"]
    hedge_penalties = sum(0.1 for h in hedges if h in text)
    output_conf = max(0.40, min(0.95, 0.90 - hedge_penalties))

    task = state.get("task")
    geo_evidence = state.get("geo_evidence")
    seg_evidence = state.get("segmentation_evidence")

    # If deterministic change evidence without ML model uncertainty, keep confidence uninvented (Requirement 9)
    if task == "change_analysis" and geo_evidence:
        if seg_evidence and seg_evidence.get("segments") and "confidence" in seg_evidence["segments"][0]:
            final_conf = seg_evidence["segments"][0]["confidence"]
        else:
            final_conf = None
    else:
        final_conf = round(output_conf, 2)

    state["trace"] = {
        "query": state.get("query", ""),
        "selected_task": task,
        "model_used": "AI Assistant" if task == "general_chat" else (TOOL_REGISTRY.get(task, {}).get("model", "none") if task else "none"),
        "parameters": {"mode": state.get("mode"), "requires_segmentation": state.get("requires_segmentation")},
        "validation": state.get("validation_msg", "ok"),
        "router_confidence": state.get("router_confidence"),
        "output_confidence": final_conf,
        "output_summary": result.get("text", "")[:220],
        "has_geo_evidence": geo_evidence is not None,
        "has_segmentation": seg_evidence is not None and seg_evidence.get("segmentation_detected", False),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return state
