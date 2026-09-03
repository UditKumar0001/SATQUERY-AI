# tests/test_report.py
import os
import pytest

try:
    import reportlab
    REPORTLAB_INSTALLED = True
except ImportError:
    REPORTLAB_INSTALLED = False


@pytest.mark.skipif(not REPORTLAB_INSTALLED, reason="reportlab is not installed in this environment")
def test_generate_pdf_report(tmp_path):
    """Test generating a PDF audit report using ReportLab."""
    from backend.report import generate_pdf_report

    out_pdf = str(tmp_path / "test_report.pdf")
    query_data = {
        "query_id": 1,
        "query_text": "Detect airplanes in runway",
        "selected_task": "vqa_caption_ground",
        "model_used": "geochat",
        "mode": "vqa",
        "router_confidence": 0.95,
        "output_confidence": 0.90,
        "validation_msg": "ok",
        "created_at": "2026-09-03T12:00:00Z",
        "images": [],
        "result": {"text": "Detected 3 aircraft near terminal B."},
        "trace": {"test_metric": 0.90}
    }

    path = generate_pdf_report(1, query_data, out_pdf)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
