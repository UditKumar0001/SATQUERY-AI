# tests/test_frontend_phase4.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from backend.main import app
from orchestrator.db import Base, Query, ExecutionTrace, SessionLocal, engine
from frontend.streamlit_app import (
    format_chat_metadata,
    render_geo_evidence_card,
    render_sam2_card,
    render_interactive_map,
    load_session_into_chat
)


@pytest.fixture
def client():
    return TestClient(app)


# =====================================================================
# 1. Chat Metadata Formatting Tests
# =====================================================================

def test_format_chat_metadata_general_chat():
    """Ordinary chat returns clean timestamp and no technical telemetry dumps."""
    resp = {
        "is_chat": True,
        "selected_task": "Conversational Assistant",
        "model_used": "SatQuery AI",
        "confidence": "Verified"
    }
    res = format_chat_metadata(resp, "14:20:00 UTC")
    assert res == "🕒 14:20:00 UTC"
    assert "OpenAI LLM" not in res
    assert "RECORD:" not in res
    assert "null" not in res


def test_format_chat_metadata_multimodal_query():
    """Change analysis or VLM query shows clean, professional metadata."""
    resp = {
        "is_chat": False,
        "selected_task": "change_analysis",
        "model_used": "GeoLLaVA",
        "geo_evidence": {
            "evidence_type": "spectral_difference",
            "change_detected": True
        }
    }
    res = format_chat_metadata(resp, "14:22:15 UTC")
    assert "Model: **GeoLLaVA**" in res
    assert "Task: **Change Analysis**" in res
    assert "Evidence: **Spectral Difference**" in res
    assert "Time: 14:22:15 UTC" in res


def test_format_chat_metadata_filters_ugly_defaults():
    """Verifies that none/N/A/null/OpenAI LLM are filtered out."""
    resp = {
        "is_chat": False,
        "selected_task": "Conversational Assistant",
        "model_used": "OpenAI LLM",
        "geo_evidence": None
    }
    res = format_chat_metadata(resp, "14:25:00 UTC")
    assert "OpenAI LLM" not in res
    assert "Conversational Assistant" not in res
    assert "Time: 14:25:00 UTC" in res


# =====================================================================
# 2. Geo Evidence Card UI Tests
# =====================================================================

def test_render_geo_evidence_card_change_detected():
    """Verifies Geo Evidence Card HTML renders with detected metrics."""
    geo_ev = {
        "change_detected": True,
        "change_type": "vegetation_loss",
        "changed_area_ha": 18.75,
        "changed_pixels": 4500,
        "change_percent": 14.2,
        "evidence_type": "spectral_difference"
    }
    with patch("streamlit.markdown") as mock_markdown:
        render_geo_evidence_card(geo_ev, turn_id="turn_123")
        assert mock_markdown.called
        html_out = mock_markdown.call_args[0][0]
        assert "geo-evidence-card" in html_out
        assert "GEO EVIDENCE ENGINE" in html_out
        assert "✓ Change Detected" in html_out
        assert "Vegetation Loss" in html_out
        assert "18.75 ha" in html_out
        assert "4,500" in html_out
        assert "14.2%" in html_out
        assert "Spectral Difference" in html_out


def test_render_geo_evidence_card_no_change():
    """Verifies Geo Evidence Card HTML for stable landscape."""
    geo_ev = {
        "change_detected": False,
        "change_type": "no_significant_change",
        "changed_area_ha": 0.0,
        "changed_pixels": 0,
        "change_percent": 0.0,
        "evidence_type": "spectral_difference"
    }
    with patch("streamlit.markdown") as mock_markdown:
        render_geo_evidence_card(geo_ev, turn_id="turn_456")
        assert mock_markdown.called
        html_out = mock_markdown.call_args[0][0]
        assert "geo-evidence-card" in html_out
        assert "⚪ Landscape Stable" in html_out
        assert "0.00 ha" in html_out


# =====================================================================
# 3. SAM 2 Refinement Card Tests
# =====================================================================

def test_render_sam2_card():
    """Verifies SAM 2 secondary refinement card displays correct metrics."""
    seg_ev = {
        "status": "success",
        "total_segments": 3,
        "total_area_ha": 12.45,
        "segments": [
            {"id": 0, "area_ha": 5.2, "confidence": 0.95},
            {"id": 1, "area_ha": 4.1, "confidence": 0.91},
            {"id": 2, "area_ha": 3.15, "confidence": 0.88}
        ]
    }
    with patch("streamlit.markdown") as mock_markdown:
        render_sam2_card(seg_ev, turn_id="turn_789")
        assert mock_markdown.called
        html_out = mock_markdown.call_args[0][0]
        assert "sam2-evidence-card" in html_out
        assert "SAM 2 SECONDARY REFINEMENT" in html_out
        assert "✓ Refined Boundaries" in html_out
        assert "12.45 ha" in html_out
        assert "3" in html_out
        assert "91.3%" in html_out


# =====================================================================
# 4. Interactive Map Tests
# =====================================================================

def test_render_interactive_map_leaflet_html():
    """Verifies Leaflet map HTML structure, tile layers, and GeoJSON overlays."""
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[77.20, 28.61], [77.21, 28.61], [77.21, 28.62], [77.20, 28.62], [77.20, 28.61]]]
                },
                "properties": {"change_type": "Vegetation Loss", "index": "ndvi"}
            }
        ]
    }
    sample_sam2_geo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[77.202, 28.612], [77.208, 28.612], [77.208, 28.618], [77.202, 28.618], [77.202, 28.612]]]
                },
                "properties": {"confidence": 0.94}
            }
        ]
    }

    with patch("streamlit.components.v1.html") as mock_html:
        render_interactive_map(
            geojson=sample_geojson,
            sam2_geojson=sample_sam2_geo,
            overlay_url="/static/visualizations/change_test.png",
            height=460,
            unique_id="unit_test_map"
        )
        assert mock_html.called
        rendered_html = mock_html.call_args[0][0]
        # Check Leaflet CDN inclusion
        assert "leaflet.js" in rendered_html
        assert "leaflet.css" in rendered_html
        # Check Basemap: Esri World Imagery & Dark Matter
        assert "World_Imagery" in rendered_html
        assert "basemaps.cartocdn.com/dark_all" in rendered_html
        # Check Change Detection GeoJSON (Red)
        assert "#ef4444" in rendered_html
        assert "Change Areas (GeoJSON)" in rendered_html
        # Check SAM 2 Segmentation Layer (Cyan)
        assert "#06b6d4" in rendered_html
        assert "SAM 2 Segmentation" in rendered_html
        # Check fitBounds
        assert "map.fitBounds" in rendered_html


def test_render_interactive_map_null_safe():
    """Verifies map renders safely even when GeoJSON is None without JS exceptions."""
    with patch("streamlit.components.v1.html") as mock_html:
        render_interactive_map(
            geojson=None,
            sam2_geojson=None,
            overlay_url=None,
            height=400,
            unique_id="empty_map"
        )
        assert mock_html.called
        rendered_html = mock_html.call_args[0][0]
        assert "var changeData = null;" in rendered_html
        assert "var sam2Data = null;" in rendered_html
        assert "L.map('map_empty_map'" in rendered_html


# =====================================================================
# 5. History API & State Restoration Tests
# =====================================================================

def test_history_detail_endpoint_returns_geo_evidence(client):
    """Test GET /history/{id} returns geo_evidence, segmentation_evidence, and geojson."""
    db = SessionLocal()
    try:
        q = Query(
            query_text="Evaluate deforestation around protected sanctuary",
            selected_task="change_analysis",
            model_used="GeoLLaVA",
            mode="change",
            router_confidence=0.92,
            output_confidence=0.88,
            validation_msg="ok",
            visual_output_path="/tmp/test_change.png",
            visual_output_url="/static/visualizations/change_test.png"
        )
        db.add(q)
        db.flush()

        trace_payload = {
            "model_used": "GeoLLaVA",
            "output_confidence": 0.88,
            "geo_evidence": {
                "change_detected": True,
                "change_type": "vegetation_loss",
                "changed_area_ha": 34.5,
                "changed_pixels": 8200,
                "change_percent": 18.5
            },
            "segmentation_evidence": {
                "status": "success",
                "total_area_ha": 30.2,
                "total_segments": 1
            },
            "geojson": {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}]
            },
            "overlay_path": "/tmp/test_change.png"
        }
        trace = ExecutionTrace(query_id=q.id, trace_json=json.dumps(trace_payload))
        db.add(trace)
        db.commit()
        qid = q.id
    finally:
        db.close()

    resp = client.get(f"/history/{qid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == qid
    assert data["geo_evidence"] is not None
    assert data["geo_evidence"]["change_detected"] is True
    assert data["geo_evidence"]["changed_area_ha"] == 34.5
    assert data["segmentation_evidence"] is not None
    assert data["segmentation_evidence"]["total_area_ha"] == 30.2
    assert data["geojson"] is not None
    assert data["overlay_path"] == "/tmp/test_change.png"


def test_load_session_into_chat_restoration():
    """Test load_session_into_chat restores messages, evidence, and active map state."""
    session_id = "test_hist_session_001"
    mock_messages = [
        {"role": "user", "content": "Analyze delta", "query_id": 9999},
        {"role": "assistant", "content": "Analysis shows 15 ha loss.", "query_id": 9999}
    ]

    mock_history_detail = {
        "id": 9999,
        "selected_task": "change_analysis",
        "model_used": "GeoLLaVA",
        "geo_evidence": {
            "change_detected": True,
            "changed_area_ha": 15.0,
            "change_type": "vegetation_loss"
        },
        "segmentation_evidence": None,
        "geojson": {"type": "FeatureCollection", "features": []},
        "visual_output_url": "/static/visualizations/change_9999.png",
        "trace": {}
    }

    def mock_requests_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        if f"/chat/{session_id}" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"session_id": session_id, "messages": mock_messages}
        elif "/history/9999" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_history_detail
        else:
            mock_resp.status_code = 404
        return mock_resp

    with patch("requests.get", side_effect=mock_requests_get), patch("streamlit.rerun"):
        load_session_into_chat(session_id, "http://localhost:8000")

    import streamlit as st
    assert len(st.session_state.chat_history) >= 1
    restored_turn = st.session_state.chat_history[0]
    assert restored_turn["user"]["text"] == "Analyze delta"
    assert restored_turn["response"]["geo_evidence"] is not None
    assert restored_turn["response"]["geo_evidence"]["changed_area_ha"] == 15.0
    assert st.session_state.show_interactive_map is True
    assert st.session_state.active_map_turn_id == restored_turn["id"]
