# orchestrator/graph.py
from typing import List, Optional
from langgraph.graph import StateGraph, END
from .graph_state import AgentState, create_initial_state
from .metadata import extract_metadata
from .nodes import classify_node, validate_node, dispatch_node, combine_node, reject_node


def after_classify(state: AgentState) -> str:
    """Conditional branching after classify: route to validate unless rejected by router."""
    task = state.get("task")
    return "validate" if task and task != "reject" else "reject"


def after_validate(state: AgentState) -> str:
    """Conditional branching after validate: route to dispatch if validated, else reject."""
    return "dispatch" if state.get("validation_ok") else "reject"


# Build the StateGraph
graph = StateGraph(AgentState)

# Add nodes
graph.add_node("classify", classify_node)
graph.add_node("validate", validate_node)
graph.add_node("dispatch", dispatch_node)
graph.add_node("combine", combine_node)
graph.add_node("reject", reject_node)

# Set entry point
graph.set_entry_point("classify")

# Add conditional edges
graph.add_conditional_edges(
    "classify",
    after_classify,
    {"validate": "validate", "reject": "reject"}
)
graph.add_conditional_edges(
    "validate",
    after_validate,
    {"dispatch": "dispatch", "reject": "reject"}
)

# Connect downstream nodes
graph.add_edge("dispatch", "combine")
graph.add_edge("combine", END)
graph.add_edge("reject", END)

# Compile orchestrator workflow
orchestrator_app = graph.compile()


def run_orchestrator(query: str, image_paths: Optional[List[str]] = None) -> AgentState:
    """High-level execution entry point: extracts metadata and invokes the state graph."""
    paths = image_paths or []
    meta = [extract_metadata(p) for p in paths]
    initial_state = create_initial_state(query=query, images_raw=paths, images_meta=meta)
    return orchestrator_app.invoke(initial_state)
