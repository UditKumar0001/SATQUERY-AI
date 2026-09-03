# backend/main.py
import json
import os
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.db import ExecutionTrace, Query, UploadedImage, get_db, init_db
from orchestrator.graph import orchestrator_app
from orchestrator.graph_state import create_initial_state
from orchestrator.metadata import extract_metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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
    from orchestrator.registry import list_tools

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
    api_key_set = bool(os.getenv("GEMINI_API_KEY"))

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "hardware": device_info,
        "router_llm_ready": api_key_set,
        "registered_tools": list_tools(),
        "version": "1.0.0"
    }



@app.post("/query")
async def handle_query(
    query: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Primary execution endpoint: ingests imagery, extracts metadata, invokes orchestrator, persists audit logs."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one image file must be uploaded.")

    # 1. Save uploaded files to unique execution staging directory
    session_id = str(uuid.uuid4())[:8]
    upload_dir = os.path.join("data", "raw", "uploads", session_id)
    os.makedirs(upload_dir, exist_ok=True)

    saved_paths = []
    try:
        for file in files:
            safe_filename = os.path.basename(file.filename)
            dest_path = os.path.join(upload_dir, safe_filename)
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_paths.append(dest_path)
    finally:
        for file in files:
            file.file.close()

    # 2. Extract metadata for all uploaded imagery
    meta_list = [extract_metadata(p) for p in saved_paths]

    # 3. Construct state and invoke LangGraph orchestrator
    initial_state = create_initial_state(
        query=query,
        images_raw=saved_paths,
        images_meta=meta_list
    )
    final_state = orchestrator_app.invoke(initial_state)

    trace = final_state.get("trace") or {}
    result = final_state.get("result") or {}

    # 4. Persist execution and audit records into database
    query_record = Query(
        query_text=query,
        selected_task=final_state.get("task", "reject"),
        model_used=trace.get("model_used", "none"),
        mode=final_state.get("mode"),
        router_confidence=final_state.get("router_confidence"),
        output_confidence=trace.get("output_confidence"),
        validation_msg=final_state.get("validation_msg") or "ok"
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


