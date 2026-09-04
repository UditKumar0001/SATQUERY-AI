# backend/main.py
import json
import os
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from pydantic import BaseModel

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.db import ExecutionTrace, Query, UploadedImage, Conversation, ChatMessage, get_db, init_db
from orchestrator.graph import orchestrator_app
import asyncio
from orchestrator.graph_state import create_initial_state
from orchestrator.metadata import extract_metadata
from orchestrator.visualization import render_grounding_box, render_change_heatmap, render_fused_composite
from orchestrator.cleanup import purge_old_uploads_and_visualizations


async def _background_cleanup_loop(interval_hours: int = 6, max_age_hours: int = 24):
    """Periodically purge temporary uploads and stale visualizations in background."""
    while True:
        try:
            purge_old_uploads_and_visualizations(max_age_hours=max_age_hours)
        except Exception as e:
            print(f"[Cleanup] Error in periodic cleanup loop: {e}")
        await asyncio.sleep(interval_hours * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        purge_old_uploads_and_visualizations(max_age_hours=24)
    except Exception as e:
        print(f"[Cleanup] Initial startup purge failed: {e}")

    cleanup_task = asyncio.create_task(_background_cleanup_loop(interval_hours=6, max_age_hours=24))
    try:
        yield
    finally:
        cleanup_task.cancel()


app = FastAPI(
    title="SatQuery AI",
    description="Intelligent Multi-Modal Earth Observation Orchestrator API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist and mount static file routes
_uploads_static_dir = os.path.join("data", "raw", "uploads")
_vis_static_dir = os.path.join("data", "processed", "visualizations")
os.makedirs(_uploads_static_dir, exist_ok=True)
os.makedirs(_vis_static_dir, exist_ok=True)

app.mount("/static/uploads", StaticFiles(directory=_uploads_static_dir), name="uploads")
app.mount("/static/visualizations", StaticFiles(directory=_vis_static_dir), name="visualizations")


@app.get("/")
def root():
    return {
        "app": "SatQuery AI",
        "status": "online",
        "docs_url": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Comprehensive health and readiness diagnostic endpoint."""
    import torch
    from sqlalchemy import text
    from orchestrator.registry import list_tools, TOOL_REGISTRY

    # 1. Database connectivity check
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # 2. Hardware acceleration diagnostics
    cuda_available = torch.cuda.is_available()
    device_info = {
        "cuda_available": cuda_available,
        "device_name": torch.cuda.get_device_name(0) if cuda_available else "CPU",
        "configured_device": os.getenv("MODEL_DEVICE", "cuda" if cuda_available else "cpu").lower()
    }

    # 3. Router configuration check
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_key_valid = bool(api_key and not api_key.startswith("your-") and not api_key.startswith("placeholder") and len(api_key) > 10)

    # 4. Registered tools with structured details
    tool_list = []
    for task_name, meta in TOOL_REGISTRY.items():
        tool_list.append({
            "task": task_name,
            "model": meta.get("model", "N/A"),
            "model_wrapper": meta.get("model", "N/A"),
            "description": meta.get("description", "")
        })

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "hardware": device_info,
        "router_llm_ready": api_key_valid,
        "registered_tools": tool_list,
        "version": "1.0.0"
    }



@app.post("/query")
async def handle_query(
    query: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Primary execution endpoint: ingests imagery, extracts metadata, invokes orchestrator, persists audit logs."""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not files:
        raise HTTPException(status_code=400, detail="At least one image file must be uploaded.")

    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB limit per file

    # 1. Save uploaded files to unique execution staging directory
    session_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join("data", "raw", "uploads", session_id)
    os.makedirs(upload_dir, exist_ok=True)

    saved_paths = []
    try:
        for file in files:
            filename = file.filename or "upload.bin"
            safe_filename = os.path.basename(filename)
            dest_path = os.path.join(upload_dir, safe_filename)
            file_size = 0
            with open(dest_path, "wb") as buffer:
                while True:
                    chunk = file.file.read(1024 * 1024)  # 1MB buffer
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > MAX_UPLOAD_SIZE:
                        buffer.close()
                        shutil.rmtree(upload_dir, ignore_errors=True)
                        raise HTTPException(
                            status_code=400,
                            detail=f"File '{filename}' exceeds maximum allowed upload size of 100MB."
                        )
                    buffer.write(chunk)

            if file_size == 0:
                shutil.rmtree(upload_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file '{filename}' is empty (0 bytes)."
                )
            saved_paths.append(dest_path)
    finally:
        for file in files:
            file.file.close()

    # 2. Extract metadata and validate image integrity
    meta_list = []
    for p in saved_paths:
        meta = extract_metadata(p)
        if meta.get("corrupted") or meta.get("error"):
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file '{os.path.basename(p)}' is corrupted or invalid: {meta.get('error')}"
            )
        meta_list.append(meta)

    # 3. Construct state and invoke LangGraph orchestrator
    initial_state = create_initial_state(
        query=query,
        images_raw=saved_paths,
        images_meta=meta_list
    )
    final_state = orchestrator_app.invoke(initial_state)

    # Ensure final_state is a valid dict (fallback if langgraph is mocked in test environment)
    if not isinstance(final_state, dict):
        from orchestrator.nodes import classify_node, validate_node, geo_evidence_node, sam2_node, dispatch_node, combine_node
        st = classify_node(initial_state)
        st = validate_node(st)
        if st.get("validation_ok"):
            if st.get("task") == "change_analysis":
                st = geo_evidence_node(st)
                if st.get("requires_segmentation") and st.get("geo_evidence", {}).get("change_detected"):
                    st = sam2_node(st)
            st = dispatch_node(st)
        st = combine_node(st)
        final_state = st

    trace = final_state.get("trace") if isinstance(final_state.get("trace"), dict) else {}
    result = final_state.get("result") if isinstance(final_state.get("result"), dict) else {}

    # 4. Generate high-quality visual outputs if validation succeeded
    vis_path = None
    vis_url = None
    if final_state.get("validation_ok"):
        task = final_state.get("task")
        try:
            if task == "vqa_caption_ground":
                mode = final_state.get("mode")
                bbox = result.get("bbox")
                label = f"{mode.upper() if mode else 'Grounding'}: {query[:30]}"
                vis_path = render_grounding_box(
                    saved_paths[0],
                    bbox=bbox if bbox else [0.2, 0.2, 0.7, 0.7],
                    label=label,
                    out_path=os.path.join(_vis_static_dir, f"grounding_{session_id}.png")
                )
            elif task == "change_analysis" and len(saved_paths) >= 2:
                # If deterministic Geo Evidence Engine generated an overlay, prefer it
                if final_state.get("overlay_path") and os.path.exists(final_state["overlay_path"]):
                    vis_path = os.path.join(_vis_static_dir, f"change_overlay_{session_id}.png")
                    try:
                        shutil.copyfile(final_state["overlay_path"], vis_path)
                    except Exception:
                        vis_path = final_state["overlay_path"]
                else:
                    vis_path = render_change_heatmap(
                        saved_paths[0],
                        saved_paths[1],
                        change_mask=result.get("change_mask"),
                        out_path=os.path.join(_vis_static_dir, f"change_{session_id}.png")
                    )
            elif task == "optical_sar_fusion" and len(saved_paths) >= 2:
                vis_path = render_fused_composite(
                    saved_paths[0],
                    saved_paths[1],
                    out_path=os.path.join(_vis_static_dir, f"fusion_{session_id}.png")
                )
            if vis_path and os.path.exists(vis_path):
                vis_filename = os.path.basename(vis_path)
                vis_url = f"/static/visualizations/{vis_filename}"
        except Exception as e:
            print(f"[Visualization] Rendering failed: {e}")
            vis_path = None
            vis_url = None

    # Persist structured evidence in execution trace for historical audit retrieval
    if final_state.get("geo_evidence"):
        trace["geo_evidence"] = final_state["geo_evidence"]
    if final_state.get("segmentation_evidence"):
        trace["segmentation_evidence"] = final_state["segmentation_evidence"]
    if final_state.get("geojson"):
        trace["geojson"] = final_state["geojson"]
    if final_state.get("overlay_path"):
        trace["overlay_path"] = final_state["overlay_path"]

    # 5. Persist execution and audit records into database
    query_record = Query(
        query_text=query,
        selected_task=final_state.get("task", "reject"),
        model_used=trace.get("model_used", "none"),
        mode=final_state.get("mode"),
        router_confidence=final_state.get("router_confidence"),
        output_confidence=trace.get("output_confidence"),
        validation_msg=final_state.get("validation_msg") or "ok",
        visual_output_path=vis_path,
        visual_output_url=vis_url
    )
    db.add(query_record)
    db.flush()

    for m in meta_list:
        img_record = UploadedImage(
            query_id=query_record.id,
            filepath=m["filepath"],
            modality=m.get("modality", "unknown"),
            format=m.get("format", "unknown"),
            timestamp_tag=m.get("timestamp")
        )
        db.add(img_record)

    trace_record = ExecutionTrace(
        query_id=query_record.id,
        trace_json=json.dumps(trace)
    )
    db.add(trace_record)

    db.commit()
    db.refresh(query_record)

    return {
        "query_id": query_record.id,
        "selected_task": query_record.selected_task,
        "model_used": query_record.model_used,
        "mode": query_record.mode,
        "validation_ok": final_state.get("validation_ok"),
        "validation_msg": query_record.validation_msg,
        "result": result,
        "answer": result.get("answer") or result.get("text"),
        "geo_evidence": final_state.get("geo_evidence"),
        "segmentation_evidence": final_state.get("segmentation_evidence"),
        "geojson": final_state.get("geojson"),
        "overlay_path": final_state.get("overlay_path"),
        "visual_output_path": vis_path,
        "visual_output_url": vis_url,
        "trace": trace,
        "created_at": query_record.created_at.isoformat()
    }


@app.get("/history")
def get_history(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """Retrieve historical queries, image metadata, and execution traces."""
    queries = (
        db.query(Query)
        .order_by(Query.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    history = []
    for q in queries:
        trace_data = None
        if q.trace and q.trace.trace_json:
            try:
                trace_data = json.loads(q.trace.trace_json)
            except Exception:
                trace_data = {"raw": q.trace.trace_json}

        history.append({
            "id": q.id,
            "query_text": q.query_text,
            "selected_task": q.selected_task,
            "model_used": q.model_used,
            "mode": q.mode,
            "router_confidence": q.router_confidence,
            "output_confidence": q.output_confidence,
            "validation_msg": q.validation_msg,
            "visual_output_path": q.visual_output_path,
            "visual_output_url": q.visual_output_url,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "images": [
                {
                    "id": img.id,
                    "filepath": img.filepath,
                    "modality": img.modality,
                    "format": img.format,
                    "timestamp_tag": img.timestamp_tag
                } for img in q.images
            ],
            "trace": trace_data
        })

    return {"total": len(history), "history": history}


@app.get("/history/{query_id}")
def get_query_detail(query_id: int, db: Session = Depends(get_db)):
    """Retrieve full detail for a single query audit record."""
    q = db.query(Query).filter(Query.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail=f"Query record {query_id} not found")

    trace_data = None
    if q.trace and q.trace.trace_json:
        try:
            trace_data = json.loads(q.trace.trace_json)
        except Exception:
            trace_data = {"raw": q.trace.trace_json}

    return {
        "id": q.id,
        "query_text": q.query_text,
        "selected_task": q.selected_task,
        "model_used": q.model_used,
        "mode": q.mode,
        "router_confidence": q.router_confidence,
        "output_confidence": q.output_confidence,
        "validation_msg": q.validation_msg,
        "visual_output_path": q.visual_output_path,
        "visual_output_url": q.visual_output_url,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "images": [
            {
                "id": img.id,
                "filepath": img.filepath,
                "modality": img.modality,
                "format": img.format,
                "timestamp_tag": img.timestamp_tag
            } for img in q.images
        ],
        "trace": trace_data,
        "geo_evidence": trace_data.get("geo_evidence") if isinstance(trace_data, dict) else None,
        "segmentation_evidence": trace_data.get("segmentation_evidence") if isinstance(trace_data, dict) else None,
        "geojson": trace_data.get("geojson") if isinstance(trace_data, dict) else None,
        "overlay_path": trace_data.get("overlay_path") if isinstance(trace_data, dict) else None,
    }


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    query_id: Optional[int] = None


@app.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    db: Session = Depends(get_db)
):
    """Multi-turn conversational assistant supporting Earth Observation query context and follow-up analysis."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 1. Resolve or initialize conversation session
    session_id = req.session_id
    conversation = None
    if session_id:
        conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()

    if not conversation:
        session_id = session_id or uuid.uuid4().hex[:12]
        conversation = Conversation(session_id=session_id)
        db.add(conversation)
        db.flush()

    # 2. Extract referenced query context if query_id is provided
    ref_context = ""
    if req.query_id:
        q = db.query(Query).filter(Query.id == req.query_id).first()
        if q:
            trace_data = {}
            if q.trace and q.trace.trace_json:
                try:
                    trace_data = json.loads(q.trace.trace_json)
                except Exception:
                    pass
            images_info = ", ".join([f"{img.modality} ({os.path.basename(img.filepath)})" for img in q.images])
            ref_context = (
                f"\n\nContext from Past Earth Observation Query #{q.id}:\n"
                f"- User Prompt: {q.query_text}\n"
                f"- Selected Task: {q.selected_task} (Mode: {q.mode})\n"
                f"- Model Used: {q.model_used}\n"
                f"- Confidence: {q.output_confidence or 'N/A'}\n"
                f"- Inferred Output: {trace_data.get('output_summary', 'N/A')}\n"
                f"- Visual Output: {q.visual_output_url or 'None'}\n"
                f"- Ingested Imagery: {images_info or 'None'}\n"
            )

    # 3. Fetch past messages for this session
    past_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(20)
        .all()
    )

    system_prompt = (
        "You are SatQuery AI, an expert Earth Observation and Satellite Imagery Intelligence Assistant. "
        "You assist analysts in understanding remote sensing, spatial grounding, bi-temporal change detection, "
        "and multi-sensor optical-SAR fusion. Provide precise, domain-grounded explanations."
        + ref_context
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    for m in past_messages:
        llm_messages.append({"role": m.role, "content": m.content})
    llm_messages.append({"role": "user", "content": req.message})

    # 4. Generate response via OpenAI or intelligent domain fallback
    api_key = os.getenv("OPENAI_API_KEY")
    router_model = os.getenv("OPENAI_ROUTER_MODEL", "gpt-4o-mini")
    assistant_reply = None

    if api_key and not api_key.startswith("your-"):
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=router_model,
                messages=llm_messages,
                temperature=0.7,
                max_tokens=500
            )
            raw_content = response.choices[0].message.content
            if isinstance(raw_content, str) and raw_content.strip():
                assistant_reply = raw_content.strip()
        except Exception as e:
            print(f"[ChatEndpoint] OpenAI generation error: {e}")

    if not isinstance(assistant_reply, str) or not assistant_reply.strip():
        msg_lower = req.message.strip().lower()
        if any(greet in msg_lower for greet in ["hello", "hi", "hey", "greetings", "good morning", "good evening"]):
            assistant_reply = (
                "👋 **Hello! Welcome to SatQuery AI.**\n\n"
                "I am your Earth Observation and Satellite Imagery Intelligence Assistant. "
                "I can assist you with:\n\n"
                "- ✈️ **Visual Question Answering & Object Grounding** (e.g. runway aircraft detection, port infrastructure)\n"
                "- 🗺️ **Bi-Temporal Change Detection** (e.g. urban expansion, deforestation, disaster assessment)\n"
                "- 🛰️ **Multi-Sensor Fusion** (combining Sentinel-2 Optical and Sentinel-1 SAR imagery)\n\n"
                "You can ask me questions about remote sensing analysis, or attach satellite image tiles to run full VLM inference pipelines!"
            )
        elif "help" in msg_lower:
            assistant_reply = (
                "### 🛰️ SatQuery AI Guidance\n\n"
                "Here is how you can interact with SatQuery AI:\n\n"
                "1. **Conversational Assistance**: Ask questions about remote sensing, satellite sensors (Sentinel, Landsat, SAR), or mission analysis.\n"
                "2. **Imagery Analysis**: Attach satellite tiles (optical `.png`/`.tif` or SAR backscatter) in the chat input and specify directives like *'Detect all aircraft parked at terminals'* or *'Identify new building constructions'*.\n"
                "3. **Audit Reports**: Every imagery analysis automatically produces downloadable PDF audit reports and verifiable telemetry traces."
            )
        elif req.query_id:
            assistant_reply = (
                f"Regarding telemetry record **#{req.query_id}** (`{req.message}`):\n\n"
                "The satellite imagery and processing metrics show consistent backscatter and reflectance signatures across "
                "the monitored region. What specific land-cover or feature details would you like to explore further?"
            )
        else:
            assistant_reply = (
                f"I received your inquiry regarding **\"{req.message}\"**.\n\n"
                "SatQuery AI specializes in multimodal satellite intelligence. To analyze specific regions, "
                "you can upload satellite imagery tiles (optical and/or SAR) using the attach option in the chat console, "
                "or ask me domain questions about remote sensing sensors, spectral bands, and change detection algorithms."
            )

    # 5. Persist user and assistant messages
    user_msg_record = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=req.message,
        query_id=req.query_id
    )
    assistant_msg_record = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_reply,
        query_id=req.query_id
    )
    db.add(user_msg_record)
    db.add(assistant_msg_record)
    db.commit()

    return {
        "session_id": conversation.session_id,
        "conversation_id": conversation.id,
        "query_id": req.query_id,
        "response": assistant_reply,
        "history_count": len(past_messages) + 2,
        "created_at": assistant_msg_record.created_at.isoformat()
    }


@app.get("/conversations")
def list_conversations(limit: int = 20, db: Session = Depends(get_db)):
    """List recent conversation sessions with preview and message counts."""
    convs = (
        db.query(Conversation)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for c in convs:
        msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == c.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        preview = ""
        first_user = next((m for m in msgs if m.role == "user"), None)
        if first_user:
            preview = first_user.content[:80] + ("..." if len(first_user.content) > 80 else "")
        elif msgs:
            preview = msgs[0].content[:80] + ("..." if len(msgs[0].content) > 80 else "")
        else:
            preview = "Empty conversation"

        result.append({
            "id": c.id,
            "session_id": c.session_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "message_count": len(msgs),
            "preview": preview,
            "last_active": msgs[-1].created_at.isoformat() if msgs and msgs[-1].created_at else (c.created_at.isoformat() if c.created_at else None)
        })
    return {"conversations": result, "total": len(result)}


@app.get("/chat/{session_id}")
def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    """Retrieve full message history for a given chat session."""
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail=f"Chat session '{session_id}' not found.")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session_id": conv.session_id,
        "conversation_id": conv.id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "query_id": m.query_id,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


@app.get("/report/{query_id}")
def download_pdf_report(query_id: int, db: Session = Depends(get_db)):
    """Generate and return a downloadable PDF audit report for a specific query."""
    from fastapi.responses import FileResponse
    from backend.report import generate_pdf_report

    q = db.query(Query).filter(Query.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")

    trace_data = {}
    if q.trace and q.trace.trace_json:
        try:
            trace_data = json.loads(q.trace.trace_json)
        except Exception:
            trace_data = {"raw": q.trace.trace_json}

    query_data = {
        "query_id": q.id,
        "query_text": q.query_text,
        "selected_task": q.selected_task,
        "model_used": q.model_used,
        "mode": q.mode,
        "router_confidence": q.router_confidence,
        "output_confidence": q.output_confidence,
        "validation_msg": q.validation_msg,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "images": [
            {
                "id": img.id,
                "filepath": img.filepath,
                "modality": img.modality,
                "format": img.format,
                "timestamp_tag": img.timestamp_tag
            } for img in q.images
        ],
        "result": {"text": trace_data.get("output_summary", "")},
        "trace": trace_data
    }

    report_path = os.path.join("data", "processed", "reports", f"satquery_report_{query_id}.pdf")
    generate_pdf_report(query_id, query_data, report_path)

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"satquery_audit_report_{query_id}.pdf"
    )


@app.post("/admin/cleanup")
def trigger_cleanup(max_age_hours: int = 24):
    """Trigger manual cleanup of uploads, visualizations, and reports older than max_age_hours."""
    stats = purge_old_uploads_and_visualizations(max_age_hours=max_age_hours)
    return {
        "status": "success",
        "max_age_hours": max_age_hours,
        "metrics": stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


