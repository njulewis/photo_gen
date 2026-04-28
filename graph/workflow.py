import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from graph.state import ImageGenState
from graph.nodes import load_scene, extract_face, generate_scene_node, quality_check, output_result

load_dotenv()

_QUALITY_THRESHOLD = float(os.getenv("QUALITY_SCORE_THRESHOLD", "0.6"))
_MAX_RETRY = int(os.getenv("MAX_RETRY_COUNT", "3"))


def _route_after_load(state: ImageGenState) -> str:
    return "error_end" if state.get("error") else "extract_face"


def _route_after_extract(state: ImageGenState) -> str:
    return "error_end" if state.get("error") else "generate_scene"


def _route_after_generate(state: ImageGenState) -> str:
    return "error_end" if state.get("error") else "quality_check"


def _route_after_quality(state: ImageGenState) -> str:
    score = state.get("quality_score", 0.0)
    retry = state.get("retry_count", 0)
    if score >= _QUALITY_THRESHOLD or retry >= _MAX_RETRY:
        return "output"
    return "retry"


def _increment_retry(state: ImageGenState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1, "error": None}


def build_graph() -> StateGraph:
    builder = StateGraph(ImageGenState)

    builder.add_node("load_scene", load_scene)
    builder.add_node("extract_face", extract_face)
    builder.add_node("generate_scene", generate_scene_node)
    builder.add_node("quality_check", quality_check)
    builder.add_node("output_result", output_result)
    builder.add_node("increment_retry", _increment_retry)

    builder.set_entry_point("load_scene")
    builder.add_conditional_edges(
        "load_scene", _route_after_load,
        {"extract_face": "extract_face", "error_end": END},
    )

    builder.add_conditional_edges(
        "extract_face", _route_after_extract,
        {"generate_scene": "generate_scene", "error_end": END},
    )
    builder.add_conditional_edges(
        "generate_scene", _route_after_generate,
        {"quality_check": "quality_check", "error_end": END},
    )
    builder.add_conditional_edges(
        "quality_check", _route_after_quality,
        {"output": "output_result", "retry": "increment_retry"},
    )

    builder.add_edge("increment_retry", "generate_scene")
    builder.add_edge("output_result", END)

    return builder.compile()


graph = build_graph()
