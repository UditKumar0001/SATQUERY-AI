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


def test_same_location_compatibility_levir_samples_pass():
    """Verify genuine LEVIR-CD bi-temporal change pairs (test_2, test_55) pass validation at threshold 0.54."""
    import os
    from orchestrator.compatibility import same_location_score, SAME_LOCATION_THRESHOLD
    from orchestrator.nodes import validate_node
    from orchestrator.graph_state import create_initial_state
    from orchestrator.metadata import extract_metadata

    sample_dir = os.path.join("data", "raw", "levir_samples")
    p1 = os.path.join(sample_dir, "T1_before.png")
    p2 = os.path.join(sample_dir, "T2_after.png")
    p1_v2 = os.path.join(sample_dir, "T1_before_v2.png")
    p2_v2 = os.path.join(sample_dir, "T2_after_v2.png")

    if os.path.exists(p1) and os.path.exists(p2):
        s1 = same_location_score(p1, p2)
        assert s1 >= SAME_LOCATION_THRESHOLD, f"test_2 score {s1} < {SAME_LOCATION_THRESHOLD}"
        state1 = create_initial_state("Detect changes", [p1, p2], [extract_metadata(p1), extract_metadata(p2)])
        state1["task"] = "change_analysis"
        res1 = validate_node(state1)
        assert res1["validation_ok"] is True

    if os.path.exists(p1_v2) and os.path.exists(p2_v2):
        s2 = same_location_score(p1_v2, p2_v2)
        assert s2 >= SAME_LOCATION_THRESHOLD, f"test_55 score {s2} < {SAME_LOCATION_THRESHOLD}"
        state2 = create_initial_state("Detect changes", [p1_v2, p2_v2], [extract_metadata(p1_v2), extract_metadata(p2_v2)])
        state2["task"] = "change_analysis"
        res2 = validate_node(state2)
        assert res2["validation_ok"] is True


def test_same_location_compatibility_rejects_different_locations():
    """Verify mismatched image pairs from different locations are rejected by the compatibility check."""
    import os
    from orchestrator.compatibility import same_location_score, SAME_LOCATION_THRESHOLD
    from orchestrator.nodes import validate_node
    from orchestrator.graph_state import create_initial_state
    from orchestrator.metadata import extract_metadata

    sample_dir = os.path.join("data", "raw", "levir_samples")
    p1 = os.path.join(sample_dir, "T1_before.png")
    p1_v2 = os.path.join(sample_dir, "T1_before_v2.png")

    if os.path.exists(p1) and os.path.exists(p1_v2):
        score = same_location_score(p1, p1_v2)
        assert score < SAME_LOCATION_THRESHOLD, f"Mismatched pair scored {score} >= {SAME_LOCATION_THRESHOLD}"
        state = create_initial_state("Detect changes", [p1, p1_v2], [extract_metadata(p1), extract_metadata(p1_v2)])
        state["task"] = "change_analysis"
        res = validate_node(state)
        assert res["validation_ok"] is False
        assert "Images do not appear to be the same location" in res["validation_msg"]
