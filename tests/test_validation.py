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
