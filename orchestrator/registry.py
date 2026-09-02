# orchestrator/registry.py
from typing import Dict, Any, List

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "vqa_caption_ground": {
        "model": "GeoChat",
        "description": "Single-image visual question answering, land-cover captioning, and referring object grounding.",
        "requires": {
            "num_images": 1,
            "modality": ["optical", "SAR"]
        },
        "params": ["query", "mode"],
        "valid_modes": ["vqa", "caption", "ground"],
        "output": ["text", "bbox"]
    },
    "change_analysis": {
        "model": "GeoLLaVA",
        "description": "Bi-temporal comparative analysis for topological and land-cover change detection.",
        "requires": {
            "num_images": 2,
            "same_location": True,
            "different_timestamp": True
        },
        "params": ["query"],
        "valid_modes": [None, "change"],
        "output": ["text", "change_mask"]
    },
    "optical_sar_fusion": {
        "model": "EarthGPT",
        "description": "Multi-sensor joint reasoning across co-registered optical spectrum and SAR backscatter.",
        "requires": {
            "num_images": 2,
            "modalities": ["optical", "SAR"],
            "co_registered": True
        },
        "params": ["query"],
        "valid_modes": [None, "fusion"],
        "output": ["text", "fused_map"]
    }
}


def get_tool(task_name: str) -> Dict[str, Any]:
    """Retrieve metadata and requirement schema for a registered tool."""
    return TOOL_REGISTRY.get(task_name)


def list_tools() -> List[str]:
    """List all registered tool identifiers."""
    return list(TOOL_REGISTRY.keys())
