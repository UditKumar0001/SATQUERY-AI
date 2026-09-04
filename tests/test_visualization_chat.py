# tests/test_visualization_chat.py
import io
import os
import pytest
from PIL import Image
from starlette.testclient import TestClient
from backend.main import app
from orchestrator.db import Base, Conversation, ChatMessage, Query, engine, SessionLocal
from orchestrator.visualization import (
    render_grounding_box,
    render_change_heatmap,
    render_fused_composite
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_optical_image(tmp_path):
    path = str(tmp_path / "opt_test.png")
    img = Image.new("RGB", (256, 256), color=(60, 140, 80))
    img.save(path, format="PNG")
    return path


@pytest.fixture
def sample_sar_image(tmp_path):
    path = str(tmp_path / "sar_test.png")
    img = Image.new("L", (256, 256), color=120)
    img.save(path, format="PNG")
    return path


def test_render_grounding_box(sample_optical_image, tmp_path):
    """Test render_grounding_box generates valid annotated PNG."""
    out_path = str(tmp_path / "test_ground.png")
    bbox = [0.15, 0.20, 0.65, 0.70]
    res_path = render_grounding_box(sample_optical_image, bbox, label="Airport Terminal", out_path=out_path)

    assert os.path.exists(res_path)
    with Image.open(res_path) as out_img:
        assert out_img.format == "PNG"
        assert out_img.size == (256, 256)


def test_render_change_heatmap(sample_optical_image, tmp_path):
    """Test render_change_heatmap generates 3-panel comparative PNG."""
    # Create second image with slight difference
    img2_path = str(tmp_path / "opt_t2.png")
    img2 = Image.new("RGB", (256, 256), color=(180, 140, 80))
    img2.save(img2_path, format="PNG")

    out_path = str(tmp_path / "test_change.png")
    res_path = render_change_heatmap(sample_optical_image, img2_path, out_path=out_path)

    assert os.path.exists(res_path)
    with Image.open(res_path) as out_img:
        assert out_img.format == "PNG"
        # 3 panels side by side -> width must be > 2x height
        assert out_img.size[0] > out_img.size[1] * 2


def test_render_fused_composite(sample_optical_image, sample_sar_image, tmp_path):
    """Test render_fused_composite generates 3-panel false-color composite PNG."""
    out_path = str(tmp_path / "test_fusion.png")
    res_path = render_fused_composite(sample_optical_image, sample_sar_image, out_path=out_path)

    assert os.path.exists(res_path)
    with Image.open(res_path) as out_img:
        assert out_img.format == "PNG"
        assert out_img.size[0] > out_img.size[1] * 2


def test_db_conversations_and_chat_messages():
    """Test Conversation and ChatMessage models in SQLite."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    test_session_id = f"test_sess_{uid}"
    db = SessionLocal()
    try:
        conv = Conversation(session_id=test_session_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)

        msg1 = ChatMessage(conversation_id=conv.id, role="user", content="Hello SatQuery")
        msg2 = ChatMessage(conversation_id=conv.id, role="assistant", content="Hello Analyst")
        db.add_all([msg1, msg2])
        db.commit()

        fetched = db.query(Conversation).filter(Conversation.session_id == test_session_id).first()
        assert fetched is not None
        assert len(fetched.messages) == 2
        assert fetched.messages[0].role == "user"
        assert fetched.messages[1].role == "assistant"
    finally:
        db.close()


def test_chat_endpoint_lifecycle(client):
    """Test multi-turn conversation via /chat and /chat/{session_id} endpoints."""
    # 1. First turn: user initiates chat
    resp1 = client.post("/chat", json={"message": "Can you explain urban change detection?"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "session_id" in data1
    assert "response" in data1
    session_id = data1["session_id"]
    assert data1["history_count"] == 2

    # 2. Second turn: user follows up using same session_id
    resp2 = client.post("/chat", json={"session_id": session_id, "message": "What about SAR radar backscatter?"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["session_id"] == session_id
    assert data2["history_count"] == 4

    # 3. Retrieve chat history
    resp_hist = client.get(f"/chat/{session_id}")
    assert resp_hist.status_code == 200
    hist_data = resp_hist.json()
    assert hist_data["session_id"] == session_id
    assert len(hist_data["messages"]) == 4
    assert hist_data["messages"][0]["role"] == "user"
    assert hist_data["messages"][1]["role"] == "assistant"


def test_chat_endpoint_with_query_reference(client):
    """Test /chat with query_id context reference."""
    # Create an in-memory or dummy query in DB
    db = SessionLocal()
    try:
        q = Query(
            query_text="Find water bodies",
            selected_task="vqa_caption_ground",
            model_used="geochat",
            mode="ground",
            router_confidence=0.95,
            output_confidence=0.90,
            validation_msg="ok"
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        query_id = q.id
    finally:
        db.close()

    resp = client.post("/chat", json={"message": "Where was the river found?", "query_id": query_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_id"] == query_id
    assert "response" in data


def test_query_endpoint_returns_visual_output(client, sample_optical_image):
    """Test /query returns visual_output_url and static serving works."""
    with open(sample_optical_image, "rb") as f:
        file_bytes = f.read()

    files = [("files", ("optical.png", io.BytesIO(file_bytes), "image/png"))]
    resp = client.post("/query", data={"query": "Locate buildings in this sector"}, files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert "visual_output_path" in data
    assert "visual_output_url" in data
    if data["visual_output_url"]:
        assert data["visual_output_url"].startswith("/static/visualizations/")
        # Test static file serving
        static_resp = client.get(data["visual_output_url"])
        assert static_resp.status_code == 200
        assert "image/png" in static_resp.headers.get("content-type", "")
