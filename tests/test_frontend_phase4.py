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
    render_spatial_evidence_side_panel,
    render_t1_t2_comparison,
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
        assert "var groundingData = null;" in rendered_html
        assert "L.map('map_empty_map'" in rendered_html


def test_render_interactive_map_with_grounding_geojson():
    """Verifies map renders grounding box vector overlay with distinct green styling."""
    sample_grounding = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[12.4, 41.8], [12.5, 41.8], [12.5, 41.9], [12.4, 41.9], [12.4, 41.8]]]
                },
                "properties": {
                    "label": "military airstrip",
                    "source": "GeoChat Grounding",
                    "area_ha": 42.5
                }
            }
        ]
    }
    with patch("streamlit.components.v1.html") as mock_html:
        render_interactive_map(
            geojson=None,
            sam2_geojson=None,
            grounding_geojson=sample_grounding,
            overlay_url=None,
            height=450,
            unique_id="grounding_test_map"
        )
        assert mock_html.called
        rendered_html = mock_html.call_args[0][0]
        # Check green stroke style
        assert "#22c55e" in rendered_html
        assert "Grounding Boxes" in rendered_html
        assert "military airstrip" in rendered_html
        assert "GeoChat Grounding" in rendered_html
        assert "props.area_ha.toFixed(2)" in rendered_html
        assert "42.5" in rendered_html
        assert "map.fitBounds" in rendered_html


def test_render_interactive_map_layer_opacity_controls():
    """Verifies Step 9 layer opacity controls, range sliders, and interactive toggles."""
    sample_change = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, "properties": {}}]
    }
    sample_sam2 = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.2]]]}, "properties": {}}]
    }
    sample_ground = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.1]]]}, "properties": {}}]
    }

    with patch("streamlit.components.v1.html") as mock_html:
        render_interactive_map(
            geojson=sample_change,
            sam2_geojson=sample_sam2,
            grounding_geojson=sample_ground,
            height=500,
            unique_id="opacity_test_map"
        )
        assert mock_html.called
        rendered_html = mock_html.call_args[0][0]

        # 1. Header & Panel
        assert "LAYERS & OPACITY" in rendered_html
        assert "lcp-collapse-btn" in rendered_html

        # 2. Basemap Controls
        assert "rdo-sat_opacity_test_map" in rendered_html
        assert "rdo-dark_opacity_test_map" in rendered_html
        assert "slide-basemap_opacity_test_map" in rendered_html

        # 3. Change Areas Toggle & Opacity Slider
        assert "chk-change_opacity_test_map" in rendered_html
        assert "slide-change_opacity_test_map" in rendered_html
        assert "changeLayer.setStyle" in rendered_html

        # 4. SAM 2 Toggle & Opacity Slider
        assert "chk-sam2_opacity_test_map" in rendered_html
        assert "slide-sam2_opacity_test_map" in rendered_html
        assert "sam2Layer.setStyle" in rendered_html

        # 5. Grounding Toggle & Opacity Slider
        assert "chk-grounding_opacity_test_map" in rendered_html
        assert "slide-grounding_opacity_test_map" in rendered_html
        assert "groundingLayer.setStyle" in rendered_html


def test_render_spatial_evidence_side_panel_change_analysis():
    """Verifies Step 10 Spatial Evidence Side Panel renders with real backend metrics."""
    resp_data = {
        "model_used": "GeoLLaVA",
        "output_confidence": 0.91,
        "geo_evidence": {
            "change_detected": True,
            "changed_area_ha": 18.42,
            "change_percent": 12.8,
            "evidence_type": "spectral_difference",
            "crs": "EPSG:32633"
        },
        "segmentation_evidence": {
            "status": "success",
            "total_area_ha": 17.85,
            "total_segments": 1
        }
    }
    with patch("streamlit.markdown") as mock_md:
        render_spatial_evidence_side_panel(resp_data)
        assert mock_md.called
        html = mock_md.call_args[0][0]

        # Check required fields from Step 10 spec
        assert "SPATIAL EVIDENCE" in html
        assert "Change Detected:" in html
        assert "YES" in html
        assert "18.42 ha" in html
        assert "+12.8%" in html
        assert "HIGH" in html
        assert "91 / 100" in html
        assert "GeoLLaVA" in html
        assert "Spectral Difference" in html
        assert "17.85 ha" in html
        assert "EPSG:32633" in html


def test_render_spatial_evidence_side_panel_grounding():
    """Verifies Step 10 Spatial Evidence Side Panel handles grounding detection results."""
    resp_data = {
        "model_used": "GeoChat",
        "output_confidence": 0.88,
        "grounding_geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "label": "military airstrip",
                    "area_ha": 36.00
                }
            }]
        }
    }
    with patch("streamlit.markdown") as mock_md:
        render_spatial_evidence_side_panel(resp_data)
        assert mock_md.called
        html = mock_md.call_args[0][0]

        assert "SPATIAL EVIDENCE" in html
        assert "DETECTED" in html
        assert "36.00 ha" in html
        assert "88 / 100" in html
        assert "GeoChat Grounding" in html
        assert "military airstrip" in html


def test_render_spatial_evidence_side_panel_null_safe():
    """Verifies side panel handles empty/None payloads without throwing errors."""
    with patch("streamlit.markdown") as mock_md:
        render_spatial_evidence_side_panel(None)
        assert not mock_md.called

    with patch("streamlit.markdown") as mock_md:
        render_spatial_evidence_side_panel({})
        assert not mock_md.called


# =====================================================================
# 4b. Step 7: T1 / T2 / CHANGE Comparison Tests
# =====================================================================

def test_render_t1_t2_comparison_with_dual_imagery():
    """Verifies Step 7 T1 / T2 / CHANGE comparison renders swipe slider and multi-view tabs."""
    sample_turn = {
        "id": "turn_test_comp",
        "user": {
            "text": "Detect deforestation between T1 and T2",
            "images": [
                {"name": "t1_2022.tif", "thumb_b64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="},
                {"name": "t2_2024.tif", "thumb_b64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="}
            ]
        },
        "response": {
            "visual_output_bytes": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            "visual_output_url": "/static/visualizations/change_test.png"
        }
    }

    with patch("streamlit.tabs") as mock_tabs, patch("streamlit.components.v1.html") as mock_html, patch("streamlit.image") as mock_img:
        tab_mock_list = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        mock_tabs.return_value = tab_mock_list

        render_t1_t2_comparison(sample_turn, unique_id="unit_comp")

        assert mock_tabs.called
        tab_names = mock_tabs.call_args[0][0]
        assert "↔ Swipe Comparison" in tab_names
        assert "T1 (Pre-Event)" in tab_names
        assert "T2 (Post-Event)" in tab_names
        assert "CHANGE (Evidence Mask)" in tab_names

        # Verify swipe component HTML
        assert mock_html.called
        swipe_html = mock_html.call_args[0][0]
        assert "swipe-wrapper" in swipe_html
        assert "swipe-clip" in swipe_html
        assert "T1 (Pre-Event)" in swipe_html
        assert "T2 (Post-Event)" in swipe_html
        assert "swipe-slider" in swipe_html


def test_render_t1_t2_comparison_change_mask_only():
    """Verifies graceful fallback to CHANGE mask tab when only 1 image or mask is available."""
    sample_turn = {
        "id": "turn_single",
        "user": {"images": []},
        "response": {
            "visual_output_bytes": b"fake_png_bytes",
            "visual_output_url": "/static/visualizations/single.png"
        }
    }
    with patch("streamlit.tabs") as mock_tabs, patch("streamlit.image") as mock_img:
        mock_tabs.return_value = [MagicMock(), MagicMock()]
        render_t1_t2_comparison(sample_turn, unique_id="unit_single")

        assert mock_tabs.called
        tab_names = mock_tabs.call_args[0][0]
        assert "CHANGE (Evidence Mask)" in tab_names


def test_render_t1_t2_comparison_null_safe():
    """Verifies render_t1_t2_comparison handles None / empty turns without crashing."""
    with patch("streamlit.tabs") as mock_tabs:
        render_t1_t2_comparison(None)
        assert not mock_tabs.called
        render_t1_t2_comparison({})
        assert not mock_tabs.called




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
            "grounding_geojson": {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[10, 20], [11, 20], [11, 21], [10, 20]]]}}]
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
    assert data["grounding_geojson"] is not None
    assert data["grounding_geojson"]["type"] == "FeatureCollection"
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
