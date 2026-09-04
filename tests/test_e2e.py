# tests/test_e2e.py
import io
import json
import os
import pytest
from PIL import Image
from starlette.testclient import TestClient
from backend.main import app
from orchestrator.db import Base, Query, UploadedImage, ExecutionTrace, SessionLocal, engine

SAMPLE_IMG_PATH = os.path.join("data", "raw", "sample_test.png")


@pytest.fixture(scope="session", autouse=True)
def setup_sample_image():
    """Ensure a synthetic sample image exists for end-to-end verification."""
    os.makedirs(os.path.dirname(SAMPLE_IMG_PATH), exist_ok=True)
    if not os.path.exists(SAMPLE_IMG_PATH):
        img = Image.new("RGB", (256, 256), color=(60, 120, 180))
        img.save(SAMPLE_IMG_PATH)
    yield


@pytest.fixture
def client():
    """Create in-process test client for full lifecycle testing."""
    return TestClient(app)


def test_database_and_audit_trace_e2e(tmp_path):
    """Verify end-to-end database auditing and report generation flow."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_db_path = str(tmp_path / "e2e_test.db")
    engine_test = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine_test)
    Session = sessionmaker(bind=engine_test)
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


def test_in_process_e2e_lifecycle(client):
    """Verify in-process end-to-end request/response lifecycle: health -> query -> history -> report."""
    # 1. Health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health.get("status") in ["healthy", "degraded"]
    assert health.get("router_llm_ready") is True

    # 2. Query execution with optical imagery
    with open(SAMPLE_IMG_PATH, "rb") as f:
        file_bytes = f.read()

    files = [("files", ("sample_optical.png", io.BytesIO(file_bytes), "image/png"))]
    resp = client.post("/query", data={"query": "Locate buildings and tarmac in this satellite scene"}, files=files)
    assert resp.status_code == 200
    res_json = resp.json()

    assert "query_id" in res_json
    assert res_json["selected_task"] == "vqa_caption_ground"
    assert "visual_output_url" in res_json
    query_id = res_json["query_id"]

    # 3. Verify static visual output serving
    if res_json["visual_output_url"]:
        vis_resp = client.get(res_json["visual_output_url"])
        assert vis_resp.status_code == 200
        assert "image/png" in vis_resp.headers.get("content-type", "")

    # 4. History retrieval
    history_resp = client.get("/history?limit=10")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert "history" in history_data
    history_ids = [item["id"] for item in history_data["history"]]
    assert query_id in history_ids

    # Query detail
    detail_resp = client.get(f"/history/{query_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == query_id

    # 5. PDF report generation and download
    report_resp = client.get(f"/report/{query_id}")
    assert report_resp.status_code == 200
    assert report_resp.headers.get("content-type") == "application/pdf"
    assert report_resp.content.startswith(b"%PDF")


def test_in_process_e2e_change_detection(client, tmp_path):
    """Verify bi-temporal change detection end-to-end execution and 3-panel visualization."""
    p1 = str(tmp_path / "t1.png")
    p2 = str(tmp_path / "t2.png")
    im1 = Image.new("RGB", (256, 256), color=(50, 150, 50))
    im2 = Image.new("RGB", (256, 256), color=(200, 100, 50))
    im1.save(p1, format="PNG")
    im2.save(p2, format="PNG")

    with open(p1, "rb") as f1, open(p2, "rb") as f2:
        files = [
            ("files", ("t1.png", io.BytesIO(f1.read()), "image/png")),
            ("files", ("t2.png", io.BytesIO(f2.read()), "image/png"))
        ]
        resp = client.post("/query", data={"query": "Detect and quantify changes between T1 and T2"}, files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_task"] == "change_analysis"
    assert data["visual_output_url"] is not None


def test_in_process_e2e_optical_sar_fusion(client, tmp_path):
    """Verify multi-sensor optical+SAR fusion end-to-end execution and false-color composite."""
    p_opt = str(tmp_path / "optical.png")
    p_sar = str(tmp_path / "sample_sar.png")
    im_opt = Image.new("RGB", (256, 256), color=(40, 120, 70))
    im_sar = Image.new("L", (256, 256), color=130)
    im_opt.save(p_opt, format="PNG")
    im_sar.save(p_sar, format="PNG")

    with open(p_opt, "rb") as f1, open(p_sar, "rb") as f2:
        files = [
            ("files", ("optical.png", io.BytesIO(f1.read()), "image/png")),
            ("files", ("sample_sar.png", io.BytesIO(f2.read()), "image/png"))
        ]
        resp = client.post("/query", data={"query": "Perform joint optical and radar fusion"}, files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_task"] == "optical_sar_fusion"
    assert data["visual_output_url"] is not None


def test_in_process_e2e_chat_and_hardening(client):
    """Verify chat conversation and input validation gates end-to-end."""
    # Chat conversation
    c_resp = client.post("/chat", json={"message": "Can you summarize satellite observation modes?"})
    assert c_resp.status_code == 200
    c_data = c_resp.json()
    assert "session_id" in c_data

    # Input hardening
    files = [("files", ("zero.png", io.BytesIO(b""), "image/png"))]
    h_resp = client.post("/query", data={"query": "Test empty"}, files=files)
    assert h_resp.status_code == 400
    assert "0 bytes" in h_resp.json()["detail"]

