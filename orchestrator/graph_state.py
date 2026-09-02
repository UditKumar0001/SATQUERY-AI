# orchestrator/graph_state.py
from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict, total=False):
    """Execution state passed between LangGraph nodes in the SatQuery orchestrator."""
    query: str
    images_meta: List[Dict[str, Any]]
    images_raw: List[str]
    task: Optional[str]
    mode: Optional[str]
    router_confidence: Optional[float]
    validation_ok: Optional[bool]
    validation_msg: Optional[str]
    result: Optional[Dict[str, Any]]
    trace: Optional[Dict[str, Any]]


def create_initial_state(
    query: str,
    images_raw: List[str],
    images_meta: Optional[List[Dict[str, Any]]] = None
) -> AgentState:
    """Convenience initializer for a clean AgentState."""
    return {
        "query": query,
        "images_raw": images_raw,
        "images_meta": images_meta if images_meta is not None else [],
        "task": None,
        "mode": None,
        "router_confidence": None,
        "validation_ok": None,
        "validation_msg": None,
        "result": None,
        "trace": None,
    }
