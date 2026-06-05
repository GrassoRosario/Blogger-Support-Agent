"""
Definizione dello State e del grafo LangGraph per il blog turistico italiano.

Flusso:
    Planner → Researcher → Drafter → HITL → KG Updater

Dipendenze:
    pip install langgraph langchain-google-genai
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

# ==============================================================
# State
# ==============================================================

class BlogState(TypedDict):
    # Parametri del Planner
    n: int                          # finestra anti-ripetizione (default 5)
    k: int                          # post da pianificare per ciclo (default 3)

    # Piano corrente scelto dal Planner
    piano_corrente: Optional[dict]  # {"regione": "...", "topic": "..."}

    # Output del Researcher
    ricerca: Optional[dict]         # sezioni strutturate + claim + fonti
    reasoning_trace: Optional[List[Any]] # <-- Traccia dei ragionamenti (Thought/Action/Observation) dell'agente ReAct

    # Output del Drafter
    bozza: Optional[str]                            # testo completo del post

    # HITL
    hitl_action: Optional[str]                      # "approva" | "modifica" | "rifiuta"
    hitl_feedback: Optional[str]                    # feedback testuale in caso di modifica
    valutazione_fonti: Optional[dict[str, int]]

    # Output del KG Updater
    post_id: Optional[str]          # ID del post salvato nel KG


# ==============================================================
# Router HITL
# ==============================================================

def hitl_router(state: BlogState) -> str:
    """
    Legge hitl_action dallo state e instrada verso il nodo corretto.
    Viene chiamato da Agent Inbox dopo la decisione dell'utente.
    """
    action = state.get("hitl_action")
    if action == "approva":
        return "kg_updater"
    elif action == "modifica":
        return "drafter"
    elif action == "rifiuta":
        return "planner"
    else:
        raise ValueError(f"hitl_action non valida: {action}")


# ==============================================================
# Grafo
# ==============================================================

def build_graph() -> StateGraph:
    graph = StateGraph(BlogState)

    # Nodi
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("drafter", drafter_node)
    graph.add_node("kg_updater", kg_updater_node)

    # Archi fissi
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "drafter")
    graph.add_edge("kg_updater", END)

    # Arco condizionale dopo il HITL
    graph.add_conditional_edges(
        "drafter",
        hitl_router,
        {
            "kg_updater": "kg_updater",  # approva
            "drafter":    "drafter",     # modifica → riscrivi
            "planner":    "planner",     # rifiuta → nuovo piano
        }
    )

    # Punto di ingresso
    graph.set_entry_point("planner")

    # Checkpointer per persistenza stato tra esecuzioni (necessario per HITL)
    checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_after=["drafter"],  # il grafo si ferma dopo il Drafter
    )


# ==============================================================
# Entry point
# ==============================================================

graph = build_graph()


if __name__ == "__main__":
    # Esecuzione di esempio
    config = {"configurable": {"thread_id": "blog-thread-1"}}

    stato_iniziale: BlogState = {
        "n": 5,
        "k": 3,
        "piano_corrente": None,
        "ricerca": None,
        "bozza": None,
        "hitl_action": None,
        "hitl_feedback": None,
        "post_id": None,
    }

    print("Avvio del grafo...")
    for evento in graph.stream(stato_iniziale, config=config):
        print(evento)