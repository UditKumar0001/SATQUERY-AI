# tests/test_validation.py
import pytest
from orchestrator.nodes import validate_node


def test_change_analysis_rejects_single_image():
    """Verify change analysis task rejects requests with only one image."""
    state = {
        "task": "change_analysis",
        "images_meta": [{"modality": "optical", "format": "GTiff"}]
    }
    state = validate_node(state)
    assert state["validation_ok"] is False
    assert "requires 2 image(s)" in state["validation_msg"]


def test_fusion_requires_optical_and_sar():
    """Verify optical-SAR fusion rejects requests with two optical images."""
    state = {
        "task": "optical_sar_fusion",
        "images_meta": [
            {"modality": "optical", "format": "GTiff"},
            {"modality": "optical", "format": "GTiff"}
        ]
    }
    state = validate_node(state)
    assert state["validation_ok"] is False
    assert "requires one optical and one SAR" in state["validation_msg"]


def test_vqa_single_image_valid():
    """Verify VQA / caption / grounding accepts single optical or multispectral image."""
    state = {
        "task": "vqa_caption_ground",
        "images_meta": [{"modality": "optical", "format": "GTiff"}]
    }
    state = validate_node(state)
    assert state["validation_ok"] is True
    assert state["validation_msg"] == "ok"


def test_vqa_rejects_multiple_images():
    """Verify single-image VQA task rejects multiple uploaded images."""
    state = {
        "task": "vqa_caption_ground",
        "images_meta": [
            {"modality": "optical", "format": "GTiff"},
            {"modality": "optical", "format": "GTiff"}
        ]
    }
    state = validate_node(state)
    assert state["validation_ok"] is False


def test_unknown_task_rejected():
    """Verify unrecognized or arbitrary task names are rejected by validation gate."""
    state = {
        "task": "unknown_random_task",
        "images_meta": [{"modality": "optical", "format": "GTiff"}]
    }
    state = validate_node(state)
    assert state["validation_ok"] is False
    assert "Unknown or rejected task" in state["validation_msg"]


def test_missing_task_rejected():
    """Verify requests with no assigned task are rejected."""
    state = {
        "task": None,
        "images_meta": []
    }
    state = validate_node(state)
    assert state["validation_ok"] is False


def test_classify_node_fallback_routing():
    """Verify classify_node routes correctly via fallback when LLM is unavailable."""
    from orchestrator.nodes import classify_node

    # Single image caption
    state = {
        "query": "Describe the terrain and land cover",
        "images_meta": [{"modality": "optical"}]
    }
    res = classify_node(state)
    assert res["task"] == "vqa_caption_ground"
    assert res["mode"] == "caption"

    # Dual image optical + SAR fusion
    state_fusion = {
        "query": "Perform joint multi-sensor fusion",
        "images_meta": [{"modality": "optical"}, {"modality": "SAR"}]
    }
    res_fusion = classify_node(state_fusion)
    assert res_fusion["task"] == "optical_sar_fusion"

    # Dual image bi-temporal change
    state_change = {
        "query": "Detect changes between before and after images",
        "images_meta": [{"modality": "optical"}, {"modality": "optical"}]
    }
    res_change = classify_node(state_change)
    assert res_change["task"] == "change_analysis"
