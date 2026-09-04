"""Comprehensive integration tests for Geo Evidence Engine + SAM 2 inside LangGraph.

Covers all 10 required test scenarios:
TEST 1: General conversation -> Existing AI path (no Geo Evidence Engine or SAM 2)
TEST 2: Single image question -> Existing image-analysis path (GeoChat)
TEST 3: T1 + T2 change query -> Geo Evidence Engine
TEST 4: Change query + segmentation request -> Geo Evidence Engine -> SAM 2
TEST 5: Change detected -> Evidence passed to AI -> AI response contains correct measured values
TEST 6: No change detected -> AI correctly reports no detected change
TEST 7: Invalid/incompatible images -> Clear error without crash
TEST 8: SAM 2 unavailable -> Evidence pipeline continues without fabricated segmentation
TEST 9: Normal chat after a geo query -> Existing chat continues correctly
TEST 10: Conversation history -> Evidence-backed response remains correctly represented in DB trace
"""

import json
import os
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin

from orchestrator.graph import orchestrator_app, run_orchestrator
from orchestrator.graph_state import create_initial_state
from orchestrator.metadata import extract_metadata


@pytest.fixture
def synthetic_t1_t2(tmp_path):
    """Fixture creating synthetic bi-temporal 5-band GeoTIFF pair with known vegetation decrease."""
    p1 = str(tmp_path / "t1_veg.tif")
    p2 = str(tmp_path / "t2_veg.tif")

    height, width = 20, 20
    crs = CRS.from_epsg(32633)
    res = 20.0  # 20m pixels -> 400 m2 per pixel
    transform = from_origin(500000.0, 3000000.0, res, res)

    # 5 bands: 1=Red, 2=Green, 3=Blue, 4=NIR, 5=SWIR
    t1_data = np.full((5, height, width), 0.2, dtype=np.float32)
    # 4x4 region of high vegetation in T1 (16 pixels)
    t1_data[3, 5:9, 5:9] = 0.8  # NIR high
    t1_data[0, 5:9, 5:9] = 0.2  # Red low

    t2_data = t1_data.copy()
    t2_data[3, 5:9, 5:9] = 0.2  # NIR dropped (vegetation decrease)
    t2_data[0, 5:9, 5:9] = 0.6  # Red rose

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 5,
        "dtype": rasterio.float32,
        "crs": crs,
        "transform": transform,
    }

    with rasterio.open(p1, "w", **profile) as d1:
        d1.write(t1_data)
    with rasterio.open(p2, "w", **profile) as d2:
        d2.write(t2_data)

    return p1, p2, transform, crs


# =====================================================================
# TEST 1: General conversation -> Existing AI path
# =====================================================================

def test_1_general_conversation_existing_ai_path():
    """Verify general conversational query ('What is NDVI?') routes to general_chat without triggering Geo Evidence Engine or SAM 2."""
    state = run_orchestrator("What is NDVI?", image_paths=[])

    assert state["task"] == "general_chat"
    assert state["validation_ok"] is True
    # Geo Evidence Engine and SAM 2 MUST NOT be triggered
    assert state.get("geo_evidence") is None
    assert state.get("segmentation_evidence") is None
    assert "NDVI" in state["result"]["answer"] or "Normalized Difference Vegetation Index" in state["result"]["answer"]


# =====================================================================
# TEST 2: Single image question -> Existing image-analysis path
# =====================================================================

def test_2_single_image_question_existing_path(tmp_path):
    """Verify single-image question routes to vqa_caption_ground (GeoChat) without triggering Geo Evidence Engine."""
    single_img = str(tmp_path / "single_opt.png")
    from PIL import Image
    im = Image.new("RGB", (10, 10), color=(100, 150, 50))
    im.save(single_img)

    state = run_orchestrator("Describe the terrain in this satellite scene", image_paths=[single_img])

    assert state["task"] == "vqa_caption_ground"
    assert state["validation_ok"] is True
    assert state.get("geo_evidence") is None
    assert state.get("segmentation_evidence") is None
    assert state["trace"]["model_used"] == "GeoChat"


# =====================================================================
# TEST 3: T1 + T2 change query -> Geo Evidence Engine
# =====================================================================

def test_3_temporal_change_query_triggers_geo_evidence(synthetic_t1_t2):
    """Verify bi-temporal change query routes to Geo Evidence Engine and does NOT invoke SAM 2 when segmentation was not requested."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    state = run_orchestrator("Compare 2022 and 2025 satellite images and detect what changed", image_paths=[t1_path, t2_path])

    assert state["task"] == "change_analysis"
    assert state["validation_ok"] is True
    assert state.get("requires_segmentation") is False

    # Geo Evidence Engine WAS invoked
    geo_evidence = state.get("geo_evidence")
    assert geo_evidence is not None
    assert geo_evidence["change_detected"] is True
    assert geo_evidence["change_type"] == "vegetation decrease"
    assert geo_evidence["changed_pixels"] == 16

    # SAM 2 was NOT invoked because user did not ask for segmentation
    assert state.get("segmentation_evidence") is None


# =====================================================================
# TEST 4: Change query + segmentation request -> Geo Evidence Engine -> SAM 2
# =====================================================================

def test_4_change_query_with_segmentation_triggers_sam2(synthetic_t1_t2):
    """Verify change query explicitly requesting segmentation invokes both Geo Evidence Engine and SAM 2."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    state = run_orchestrator("Compare these two images and segment the exact changed region boundaries", image_paths=[t1_path, t2_path])

    assert state["task"] == "change_analysis"
    assert state["validation_ok"] is True
    assert state.get("requires_segmentation") is True

    # Both Geo Evidence and SAM 2 were invoked
    assert state.get("geo_evidence") is not None
    assert state.get("geo_evidence")["change_detected"] is True

    seg_evidence = state.get("segmentation_evidence")
    assert seg_evidence is not None
    assert seg_evidence["model"] == "SAM2"
    assert seg_evidence["source"] == "geo_evidence_candidate"
    assert state.get("geojson") is not None
    assert state.get("overlay_path") is not None


# =====================================================================
# TEST 5: Change detected -> Evidence passed to AI -> AI response contains correct measured values
# =====================================================================

def test_5_ai_response_uses_exact_deterministic_evidence(synthetic_t1_t2):
    """Verify AI response strictly incorporates measured hectares, pixel counts, and change type without inventing values."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    state = run_orchestrator("Detect vegetation changes between earlier and later acquisitions", image_paths=[t1_path, t2_path])

    geo_ev = state["geo_evidence"]
    area_ha = geo_ev["changed_area_ha"]
    pct = geo_ev["change_percent"]
    pixels = geo_ev["changed_pixels"]
    change_type = geo_ev["change_type"]

    answer = state["result"]["answer"]

    # Must contain exact measured metrics
    assert f"{area_ha:.2f}" in answer
    assert f"{pct:.1f}%" in answer
    assert str(pixels) in answer
    assert change_type in answer
    assert state["result"]["geo_evidence"] == geo_ev


# =====================================================================
# TEST 6: No change detected -> AI correctly reports no detected change
# =====================================================================

def test_6_no_change_detected_reports_stable(synthetic_t1_t2):
    """Verify that when T1 and T2 have no spectral change, AI reports no change and skips SAM 2."""
    t1_path, _, _, _ = synthetic_t1_t2

    # Pass identical images T1 and T1
    state = run_orchestrator("Compare these images and detect changes", image_paths=[t1_path, t1_path])

    assert state["task"] == "change_analysis"
    assert state.get("geo_evidence") is not None
    assert state["geo_evidence"]["change_detected"] is False
    assert state["geo_evidence"]["changed_pixels"] == 0

    # SAM 2 skipped
    assert state.get("segmentation_evidence") is None

    # AI response mentions no significant change / stable
    answer = state["result"]["answer"]
    assert "no statistically significant" in answer.lower() or "stable" in answer.lower()


# =====================================================================
# TEST 7: Invalid/incompatible images -> Clear error
# =====================================================================

def test_7_incompatible_images_reports_clear_error(tmp_path):
    """Verify that rasters with incompatible CRS raise clear error without crashing."""
    p1 = str(tmp_path / "t1_utm.tif")
    p2 = str(tmp_path / "t2_wgs84.tif")

    profile1 = {
        "driver": "GTiff",
        "height": 10,
        "width": 10,
        "count": 5,
        "dtype": rasterio.float32,
        "crs": CRS.from_epsg(32633),
        "transform": from_origin(500000, 3000000, 10, 10),
    }
    profile2 = dict(profile1, crs=CRS.from_epsg(4326))

    with rasterio.open(p1, "w", **profile1) as d1:
        d1.write(np.zeros((5, 10, 10), dtype=np.float32))
    with rasterio.open(p2, "w", **profile2) as d2:
        d2.write(np.zeros((5, 10, 10), dtype=np.float32))

    state = run_orchestrator("Compare these images", image_paths=[p1, p2])

    assert state["validation_ok"] is False
    assert "incompatible" in state["validation_msg"].lower() or "crs" in state["validation_msg"].lower()
    assert "error" in state["result"]["answer"].lower() or "incompatible" in state["result"]["answer"].lower()


# =====================================================================
# TEST 8: SAM 2 unavailable -> Evidence pipeline continues without fabricated segmentation
# =====================================================================

def test_8_sam2_unavailable_graceful_continuation(synthetic_t1_t2, monkeypatch):
    """Verify that if SAM 2 fails/unavailable, deterministic change evidence is preserved and AI does not fabricate segmentation."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    # Simulate SAM 2 being unavailable in the environment
    def mock_refine_fail(*args, **kwargs):
        return {
            "segmentation_detected": False,
            "segments": [],
            "model": "SAM2",
            "source": "geo_evidence_candidate",
            "status": "unavailable",
            "error": "Checkpoint weights missing for SAM 2.",
        }

    monkeypatch.setattr("orchestrator.nodes.refine_change_with_sam2", mock_refine_fail)

    state = run_orchestrator("Compare these images and segment the change", image_paths=[t1_path, t2_path])

    # 1. Change detection succeeded
    assert state["geo_evidence"]["change_detected"] is True

    # 2. SAM 2 reported unavailable
    assert state["segmentation_evidence"]["status"] == "unavailable"

    # 3. AI response notes segmentation is unavailable without fabricating false segments
    ans = state["result"]["answer"]
    assert "segmentation is currently unavailable" in ans
    assert "16" in ans  # Still has the real measured 16 changed pixels


# =====================================================================
# TEST 9: Normal chat after a geo query -> Existing chat continues correctly
# =====================================================================

def test_9_normal_chat_after_geo_query(synthetic_t1_t2):
    """Verify normal chat queries work seamlessly before and after geo change queries."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    # 1. Run geo change query
    geo_state = run_orchestrator("Compare 2022 and 2025 images", image_paths=[t1_path, t2_path])
    assert geo_state["task"] == "change_analysis"

    # 2. Run standard conversational question
    chat_state = run_orchestrator("What is remote sensing?", image_paths=[])
    assert chat_state["task"] == "general_chat"
    assert chat_state.get("geo_evidence") is None
    assert "remote sensing" in chat_state["result"]["answer"].lower()


# =====================================================================
# TEST 10: Conversation history -> Evidence-backed response remains correctly represented
# =====================================================================

def test_10_conversation_history_trace_preservation(synthetic_t1_t2):
    """Verify execution trace captures all evidence metadata for auditable historical storage."""
    t1_path, t2_path, _, _ = synthetic_t1_t2

    state = run_orchestrator("Compare and segment changes", image_paths=[t1_path, t2_path])
    trace = state.get("trace")

    assert trace is not None
    assert trace["selected_task"] == "change_analysis"
    assert trace["has_geo_evidence"] is True
    assert "output_summary" in trace
    assert "timestamp" in trace
