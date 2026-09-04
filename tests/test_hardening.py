# tests/test_hardening.py
import io
import os
import pytest
from PIL import Image
from starlette.testclient import TestClient
from backend.main import app
from orchestrator.metadata import extract_metadata


@pytest.fixture
def client():
    return TestClient(app)


def test_extract_metadata_empty_file(tmp_path):
    """Verify extract_metadata returns structured error for 0-byte files."""
    empty_file = str(tmp_path / "empty.tif")
    with open(empty_file, "wb") as f:
        pass

    meta = extract_metadata(empty_file)
    assert meta["corrupted"] is True
    assert meta["format"] == "EMPTY"
    assert "empty" in meta["error"].lower()


def test_extract_metadata_corrupted_file(tmp_path):
    """Verify extract_metadata returns structured error for corrupted image files."""
    corrupt_file = str(tmp_path / "corrupt.png")
    with open(corrupt_file, "wb") as f:
        f.write(b"NOT_A_VALID_IMAGE_DATA_CORRUPT_BYTES_XYZ_123")

    meta = extract_metadata(corrupt_file)
    assert meta["corrupted"] is True
    assert meta["format"] == "CORRUPTED"
    assert "Corrupted or unsupported" in meta["error"]


def test_extract_metadata_valid_image(tmp_path):
    """Verify extract_metadata correctly identifies valid image files."""
    valid_file = str(tmp_path / "sample_optical.png")
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    img.save(valid_file, format="PNG")

    meta = extract_metadata(valid_file)
    assert meta.get("corrupted") is not True
    assert meta["format"] == "PNG"
    assert meta["bands"] == 3
    assert meta["modality"] == "optical"


def test_api_rejects_empty_query(client):
    """Verify /query endpoint rejects empty or whitespace-only query string."""
    files = [("files", ("test.png", io.BytesIO(b"dummy"), "image/png"))]
    response = client.post("/query", data={"query": "   "}, files=files)
    assert response.status_code == 400
    assert "Query cannot be empty" in response.json()["detail"]


def test_api_rejects_zero_byte_upload(client):
    """Verify /query endpoint rejects 0-byte uploaded files with HTTP 400."""
    files = [("files", ("zero.png", io.BytesIO(b""), "image/png"))]
    response = client.post("/query", data={"query": "Detect changes"}, files=files)
    assert response.status_code == 400
    assert "0 bytes" in response.json()["detail"]


def test_api_rejects_corrupted_upload(client):
    """Verify /query endpoint rejects corrupted image files with HTTP 400."""
    files = [("files", ("corrupted.png", io.BytesIO(b"random_non_image_bytes"), "image/png"))]
    response = client.post("/query", data={"query": "Detect changes"}, files=files)
    assert response.status_code == 400
    assert "corrupted or invalid" in response.json()["detail"]
