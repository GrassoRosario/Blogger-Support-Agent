"""
Definizione dello State e del grafo LangGraph per il blog turistico italiano.
"""

from typing import Any, List, TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.nodes.planner import planner_node
from src.nodes.researcher import researcher_node
from src.nodes.drafter import drafter_node
from src.nodes.kg_updater import kg_updater_node

load_dotenv()

class BlogState(TypedDict):
    n:                 int
    k:                 int
    piano_corrente:    Optional[dict]
    ricerca:           Optional[dict]
    reasoning_trace:   Optional[List[Any]]
    bozza:             Optional[str]
    hitl_action:       Optional[str]
    hitl_feedback:     Optional[str]
    valutazione_fonti: Optional[dict]
    post_id:           Optional[str]
    rischio_rifiuto:   Optional[bool]
    prob_approvazione: Optional[float]


def hitl_router(state: BlogState) -> str:
    action = state.get("hitl_action")
    if action == "approva":
        return "kg_updater"
    elif action == "modifica":
        return "drafter"
    elif action == "rifiuta":
        return "planner"
    else:
        raise ValueError(f"hitl_action non valida: {action}")


def build_graph() -> StateGraph:
    graph = StateGraph(BlogState)
    graph.add_node("planner",    planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("drafter",    drafter_node)
    graph.add_node("kg_updater", kg_updater_node)
    graph.add_edge("planner",    "researcher")
    graph.add_edge("researcher", "drafter")
    graph.add_edge("kg_updater", END)
    graph.add_conditional_edges(
        "drafter",
        hitl_router,
        {
            "kg_updater": "kg_updater",
            "drafter":    "drafter",
            "planner":    "planner",
        }
    )
    graph.set_entry_point("planner")
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_after=["drafter"],
    )

graph = build_graph()