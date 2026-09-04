# tests/test_crawler_and_features.py
"""
Comprehensive Integration & Web Feature Crawler Test Suite
Validates all backend and frontend HTTP routes, multi-modal pipelines, conversational
assistant, admin endpoints, and static asset crawler checks.
"""
import io
import json
import os
import uuid
import pytest
from PIL import Image
from starlette.testclient import TestClient
from backend.main import app
from orchestrator.db import SessionLocal, Query, Conversation, ChatMessage


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_optical_img(tmp_path):
    p = str(tmp_path / "opt.png")
    img = Image.new("RGB", (256, 256), color=(50, 150, 70))
    img.save(p, "PNG")
    return p


@pytest.fixture
def test_optical_img2(tmp_path):
    p = str(tmp_path / "opt2.png")
    img = Image.new("RGB", (256, 256), color=(150, 70, 50))
    img.save(p, "PNG")
    return p


@pytest.fixture
def test_sar_img(tmp_path):
    p = str(tmp_path / "sar.png")
    img = Image.new("L", (256, 256), color=128)
    img.save(p, "PNG")
    return p


# ==============================================================================
# 1. API ROOT & SYSTEM HEALTH CRAWLER
# ==============================================================================

def test_api_root_and_docs_crawler(client):
    """Crawl root and documentation endpoints."""
    r_root = client.get("/")
    assert r_root.status_code == 200
    root_data = r_root.json()
    assert root_data["status"] == "online"
    assert root_data["app"] == "SatQuery AI"

    r_docs = client.get("/docs")
    assert r_docs.status_code == 200
    assert "swagger" in r_docs.text.lower() or "html" in r_docs.text.lower()

    r_schema = client.get("/openapi.json")
    assert r_schema.status_code == 200
    schema = r_schema.json()
    assert "/query" in schema["paths"]
    assert "/chat" in schema["paths"]
    assert "/health" in schema["paths"]


def test_system_health_telemetry(client):
    """Verify detailed diagnostics on /health."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["database"] == "connected"
    assert "hardware" in data
    assert "registered_tools" in data
    assert len(data["registered_tools"]) >= 3


# ==============================================================================
# 2. MULTIMODAL PIPELINE DISPATCH & VISUALIZATION TESTS
# ==============================================================================

def test_task_a_optical_vqa_and_grounding(client, test_optical_img):
    """Test Task A single-image VQA and grounding with visual output."""
    with open(test_optical_img, "rb") as f:
        files = [("files", ("test_runway.png", io.BytesIO(f.read()), "image/png"))]

    resp = client.post("/query", data={"query": "Locate aircraft on the runway"}, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_task"] == "vqa_caption_ground"
    assert data["validation_ok"] is True
    assert "visual_output_url" in data
    if data["visual_output_url"]:
        img_res = client.get(data["visual_output_url"])
        assert img_res.status_code == 200
        assert "image" in img_res.headers.get("content-type", "")


def test_task_b_change_detection(client, test_optical_img, test_optical_img2):
    """Test Task B bi-temporal change detection with 3-panel heatmap visual."""
    with open(test_optical_img, "rb") as f1, open(test_optical_img2, "rb") as f2:
        files = [
            ("files", ("epoch1.png", io.BytesIO(f1.read()), "image/png")),
            ("files", ("epoch2.png", io.BytesIO(f2.read()), "image/png")),
        ]

    resp = client.post("/query", data={"query": "Identify urban construction delta between images"}, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_task"] == "change_analysis"
    assert data["validation_ok"] is True
    assert data["visual_output_url"] is not None
    vis_res = client.get(data["visual_output_url"])
    assert vis_res.status_code == 200


def test_task_c_optical_sar_fusion(client, test_optical_img, test_sar_img):
    """Test Task C cross-modality fusion with false-color composite visual."""
    with open(test_optical_img, "rb") as f1, open(test_sar_img, "rb") as f2:
        files = [
            ("files", ("optical.png", io.BytesIO(f1.read()), "image/png")),
            ("files", ("sar.png", io.BytesIO(f2.read()), "image/png")),
        ]

    resp = client.post("/query", data={"query": "Joint optical and SAR radar analysis"}, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_task"] == "optical_sar_fusion"
    assert data["validation_ok"] is True
    assert data["visual_output_url"] is not None


# ==============================================================================
# 3. CONVERSATIONAL ASSISTANT & QUERY CONTEXT TESTS
# ==============================================================================

def test_chat_multi_turn_with_session(client):
    """Test multi-turn conversational chat with session continuity."""
    # Turn 1
    r1 = client.post("/chat", json={"message": "What sensors can SatQuery fuse?"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert "session_id" in d1
    session_id = d1["session_id"]
    assert "response" in d1
    assert len(d1["response"]) > 10

    # Turn 2
    r2 = client.post("/chat", json={"message": "Tell me more about SAR backscatter.", "session_id": session_id})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["session_id"] == session_id

    # Retrieve history
    r_hist = client.get(f"/chat/{session_id}")
    assert r_hist.status_code == 200
    messages = r_hist.json()["messages"]
    assert len(messages) >= 4


def test_chat_with_referenced_query_id(client, test_optical_img):
    """Test chat assistant answering contextual questions based on past query."""
    with open(test_optical_img, "rb") as f:
        files = [("files", ("opt.png", io.BytesIO(f.read()), "image/png"))]
    q_resp = client.post("/query", data={"query": "Detect water channels"}, files=files)
    assert q_resp.status_code == 200
    qid = q_resp.json()["query_id"]

    c_resp = client.post("/chat", json={"message": "Can you explain the water detection trace?", "query_id": qid})
    assert c_resp.status_code == 200
    c_data = c_resp.json()
    assert c_data["query_id"] == qid
    assert "response" in c_data


# ==============================================================================
# 4. AUDIT REPORTS, HISTORY & MAINTENANCE PURGE
# ==============================================================================

def test_pdf_report_and_history_lifecycle(client, test_optical_img):
    """Test audit log persistence and PDF report generator."""
    with open(test_optical_img, "rb") as f:
        files = [("files", ("audit_target.png", io.BytesIO(f.read()), "image/png"))]
    q_resp = client.post("/query", data={"query": "Generate full audit trail"}, files=files)
    assert q_resp.status_code == 200
    qid = q_resp.json()["query_id"]

    # PDF Report Download
    pdf_resp = client.get(f"/report/{qid}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    # History list
    hist_resp = client.get("/history?limit=5")
    assert hist_resp.status_code == 200
    history = hist_resp.json()["history"]
    assert any(h["id"] == qid for h in history)

    # History detail
    detail_resp = client.get(f"/history/{qid}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == qid


def test_admin_cleanup_endpoint(client):
    """Test administrative purge endpoint."""
    resp = client.post("/admin/cleanup?max_age_hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "metrics" in data


# ==============================================================================
# 5. INPUT HARDENING & GUARDRAIL DEFENSE
# ==============================================================================

def test_empty_query_rejected(client, test_optical_img):
    """Ensure empty query returns HTTP 400."""
    with open(test_optical_img, "rb") as f:
        files = [("files", ("opt.png", io.BytesIO(f.read()), "image/png"))]
    resp = client.post("/query", data={"query": "   "}, files=files)
    assert resp.status_code == 400


def test_empty_file_rejected(client):
    """Ensure 0-byte file upload returns HTTP 400."""
    files = [("files", ("empty.png", io.BytesIO(b""), "image/png"))]
    resp = client.post("/query", data={"query": "Analyze empty file"}, files=files)
    assert resp.status_code == 400


def test_corrupted_file_rejected(client):
    """Ensure non-image garbage file returns HTTP 400."""
    files = [("files", ("corrupt.png", io.BytesIO(b"NOT_A_VALID_IMAGE_FILE_DATA"), "image/png"))]
    resp = client.post("/query", data={"query": "Analyze corrupt data"}, files=files)
    assert resp.status_code == 400


# ==============================================================================
# 6. STATIC ASSET INTEGRITY CRAWLER
# ==============================================================================

def test_frontend_static_assets_crawler():
    """Crawl local frontend asset files required by the UI."""
    assets_dir = os.path.join("frontend", "assets")
    required_assets = [
        "hero_orbital_satellite.mp4",
        "card_task_a_optical.jpg",
        "card_task_b_change.jpg",
        "card_task_c_sar.jpg",
        "card_task_d_lora.jpg"
    ]
    for asset in required_assets:
        p = os.path.join(assets_dir, asset)
        assert os.path.exists(p), f"Missing required UI asset: {p}"
        assert os.path.getsize(p) > 0, f"Asset file is empty: {p}"


def test_list_conversations_endpoint(client):
    """Ensure GET /conversations returns structured sessions with previews and message counts."""
    # Seed a chat message
    sess_id = f"test_conv_list_{uuid.uuid4().hex[:8]}"
    post_res = client.post("/chat", json={"message": "Testing conversation listing", "session_id": sess_id})
    assert post_res.status_code == 200

    resp = client.get("/conversations?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "conversations" in data
    assert "total" in data
    assert isinstance(data["conversations"], list)
    matching = [c for c in data["conversations"] if c.get("session_id") == sess_id]
    assert len(matching) == 1
    assert matching[0]["message_count"] == 2
    assert "Testing conversation listing" in matching[0]["preview"]

