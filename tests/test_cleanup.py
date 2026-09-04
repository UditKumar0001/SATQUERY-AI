# tests/test_cleanup.py
import os
import time
import pytest
from starlette.testclient import TestClient
from backend.main import app
from orchestrator.cleanup import purge_old_uploads_and_visualizations


@pytest.fixture
def client():
    return TestClient(app)


def test_purge_old_uploads(tmp_path):
    """Verify purge_old_uploads_and_visualizations deletes stale files and preserves fresh files."""
    up_dir = tmp_path / "uploads"
    vis_dir = tmp_path / "visualizations"
    rep_dir = tmp_path / "reports"
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(vis_dir, exist_ok=True)
    os.makedirs(rep_dir, exist_ok=True)

    now = time.time()
    old_time = now - (30 * 3600)  # 30 hours ago (stale)
    fresh_time = now - (2 * 3600)  # 2 hours ago (fresh)

    # 1. Create stale upload session directory
    old_session = up_dir / "sess_old"
    os.makedirs(old_session, exist_ok=True)
    old_file = old_session / "image_old.png"
    with open(old_file, "wb") as f:
        f.write(b"old image bytes" * 10)
    os.utime(old_file, (old_time, old_time))
    os.utime(old_session, (old_time, old_time))

    # 2. Create fresh upload session directory
    fresh_session = up_dir / "sess_fresh"
    os.makedirs(fresh_session, exist_ok=True)
    fresh_file = fresh_session / "image_fresh.png"
    with open(fresh_file, "wb") as f:
        f.write(b"fresh image bytes" * 10)
    os.utime(fresh_file, (fresh_time, fresh_time))
    os.utime(fresh_session, (fresh_time, fresh_time))

    # 3. Create stale visualization
    old_vis = vis_dir / "vis_old.png"
    with open(old_vis, "wb") as f:
        f.write(b"old vis bytes")
    os.utime(old_vis, (old_time, old_time))

    # 4. Create fresh visualization
    fresh_vis = vis_dir / "vis_fresh.png"
    with open(fresh_vis, "wb") as f:
        f.write(b"fresh vis bytes")
    os.utime(fresh_vis, (fresh_time, fresh_time))

    # Run purge with 24 hours threshold
    stats = purge_old_uploads_and_visualizations(
        max_age_hours=24,
        upload_dir=str(up_dir),
        vis_dir=str(vis_dir),
        report_dir=str(rep_dir)
    )

    # Assert old items purged
    assert not os.path.exists(old_session)
    assert not os.path.exists(old_vis)
    assert stats["purged_uploads"] >= 1
    assert stats["purged_visualizations"] >= 1

    # Assert fresh items preserved
    assert os.path.exists(fresh_session)
    assert os.path.exists(fresh_file)
    assert os.path.exists(fresh_vis)


def test_admin_cleanup_endpoint(client):
    """Verify /admin/cleanup endpoint executes successfully."""
    response = client.post("/admin/cleanup?max_age_hours=48")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["max_age_hours"] == 48
    assert "metrics" in data
    assert "total_purged" in data["metrics"]


def test_static_directories_mounted(client):
    """Verify static routes /static/uploads and /static/visualizations are mounted and accessible."""
    # Write a small test file in data/processed/visualizations
    vis_dir = os.path.join("data", "processed", "visualizations")
    test_file = os.path.join(vis_dir, "mount_test.txt")
    with open(test_file, "w") as f:
        f.write("static_mount_ok")

    try:
        resp = client.get("/static/visualizations/mount_test.txt")
        assert resp.status_code == 200
        assert resp.text == "static_mount_ok"
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
