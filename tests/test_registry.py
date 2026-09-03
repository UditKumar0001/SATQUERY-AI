# tests/test_registry.py
import pytest
from orchestrator.registry import TOOL_REGISTRY, list_tools, get_tool


def test_registry_contains_core_tools():
    """Verify registry contains the three required multi-modal tools."""
    expected_tools = {"vqa_caption_ground", "change_analysis", "optical_sar_fusion"}
    assert expected_tools.issubset(set(TOOL_REGISTRY.keys()))


def test_registry_tool_schemas():
    """Verify every registered tool has model, description, and requirements."""
    for tool_name, config in TOOL_REGISTRY.items():
        assert "model" in config
        assert "description" in config
        assert "requires" in config
        assert "num_images" in config["requires"]


def test_list_tools_format():
    """Verify list_tools returns registered tool identifiers."""
    tools = list_tools()
    assert len(tools) == 3
    assert "vqa_caption_ground" in tools
    assert "change_analysis" in tools
    assert "optical_sar_fusion" in tools


def test_get_tool():
    """Verify tool lookup by task name."""
    vqa_info = get_tool("vqa_caption_ground")
    assert vqa_info is not None
    assert vqa_info["model"] == "GeoChat"

    unknown_info = get_tool("nonexistent_tool")
    assert unknown_info is None
