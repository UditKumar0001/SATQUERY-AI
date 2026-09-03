# tests/test_e2e.py
import json
import os
import pytest
import requests
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
SAMPLE_IMG_PATH = os.path.join("data", "raw", "sample_test.png")


@pytest.fixture(scope="session", autouse=True)
def setup_sample_image():
    """Ensure a synthetic sample image exists for end-to-end verification."""
    os.makedirs(os.path.dirname(SAMPLE_IMG_PATH), exist_ok=True)
    if not os.path.exists(SAMPLE_IMG_PATH):
        img = Image.new("RGB", (256, 256), color=(60, 120, 180))
        img.save(SAMPLE_IMG_PATH)
    yield
    # Keep the sample for future manual CLI/GUI testing


def is_backend_running() -> bool:
    """Check if the backend FastAPI service is currently reachable."""
    try:
        r = requests.get(f"{BACKEND_API_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def test_database_and_audit_trace_e2e(tmp_path):
    """Verify end-to-end database auditing and report generation flow."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from orchestrator.db import Base, Query, UploadedImage, ExecutionTrace

    test_db_path = str(tmp_path / "e2e_test.db")
    engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Ingest query record
    q = Query(
        query_text="Assess coastal erosion and shoreline changes",
        selected_task="vqa_caption_ground",
        model_used="GeoChat",
        mode="vqa",
        router_confidence=0.96,
        output_confidence=0.91,
        validation_msg="ok"
    )
    session.add(q)
    session.commit()
    session.refresh(q)

    # 2. Attach image
    img = UploadedImage(
        query_id=q.id,
        filepath=SAMPLE_IMG_PATH,
        modality="optical",
        format="PNG"
    )
    session.add(img)

    # 3. Attach full execution trace
    trace_payload = {
        "query": q.query_text,
        "selected_task": q.selected_task,
        "model_used": q.model_used,
        "output_confidence": q.output_confidence,
        "output_summary": "Minimal coastal erosion detected along the northern shoreline."
    }
    trace = ExecutionTrace(query_id=q.id, trace_json=json.dumps(trace_payload))
    session.add(trace)
    session.commit()

    # 4. Assert integrity
    fetched = session.query(Query).filter(Query.id == q.id).first()
    assert fetched is not None
    assert fetched.selected_task == "vqa_caption_ground"
    assert len(fetched.images) == 1
    assert fetched.trace is not None

    session.close()


@pytest.mark.skipif(not is_backend_running(), reason="Backend server is not running on BACKEND_API_URL")
def test_live_api_end_to_end():
    """Verify live API end-to-end request/response cycle (Step 34)."""
    # 1. Health check
    health = requests.get(f"{BACKEND_API_URL}/health", timeout=5).json()
    assert health.get("status") in ["healthy", "degraded"]

    # 2. Query execution
    with open(SAMPLE_IMG_PATH, "rb") as f:
        files = [("files", ("sample_test.png", f, "image/png"))]
        data = {"query": "Describe this satellite tile."}
        resp = requests.post(f"{BACKEND_API_URL}/query", data=data, files=files, timeout=60)

    assert resp.status_code == 200
    res_json = resp.json()
    assert "query_id" in res_json
    assert "selected_task" in res_json
    assert "trace" in res_json

    query_id = res_json["query_id"]

    # 3. History retrieval
    history = requests.get(f"{BACKEND_API_URL}/history?limit=5", timeout=5).json()
    assert "history" in history
    query_ids = [item["id"] for item in history["history"]]
    assert query_id in query_ids

    # 4. PDF report generation and download
    report_resp = requests.get(f"{BACKEND_API_URL}/report/{query_id}", timeout=10)
    assert report_resp.status_code == 200
    assert report_resp.headers.get("content-type") == "application/pdf"
    assert report_resp.content.startswith(b"%PDF")
