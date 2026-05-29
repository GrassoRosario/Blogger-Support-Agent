import random
from langchain_core.tools import tool
from database.kg_operations import (
    regioni_disponibili,
    topic_per_regione,
    prossimo_post_pianificato,
    inserisci_post_pianificati,
)


# ==============================================================
# Tool Search (placeholder — sarà implementato separatamente)
# ==============================================================

@tool
def search_tool(regione: str, topic_da_evitare: list[str]) -> str:
    """
    Cerca su internet un topic di interesse turistico per la regione indicata,
    escludendo i topic già trattati.

    Args:
        regione:          Nome della regione italiana (es. "Sicilia")
        topic_da_evitare: Topic già trattati in post precedenti per questa regione

    Returns:
        Nome del topic suggerito (es. "Valle dei Templi di Agrigento")
    """
    raise NotImplementedError("Il tool Search non è ancora implementato.")


# ==============================================================
# Nodo Planner
# ==============================================================

def planner_node(state: dict) -> dict:
    """
    Nodo Planner del grafo LangGraph.

    Legge dallo state:
        n (int): finestra anti-ripetizione (default 5)
        k (int): numero di post da pianificare quando la lista è esaurita (default 3)

    Scrive sullo state:
        piano_corrente (dict): piano da eseguire nel ciclo corrente
            {
                "regione": "Sicilia",
                "topic": "Valle dei Templi di Agrigento"
            }
    """
    n = state.get("n", 5)
    k = state.get("k", 3)

    # 1. Controlla se esistono PostPianificati nel KG
    piano = prossimo_post_pianificato()

    if piano:
        # Esiste già un piano: lo usa direttamente
        print(f"Piano trovato nel KG: {piano}")
    else:
        # Nessun piano disponibile: ne genera K nuovi
        print("Nessun piano nel KG. Generazione di nuovi piani...")

        disponibili = regioni_disponibili(n)
        k_effettivo = min(k, len(disponibili))
        regioni_scelte = random.sample(disponibili, k_effettivo)

        piani_generati = []
        for regione in regioni_scelte:
            da_evitare = topic_per_regione(regione)
            topic = search_tool.invoke({
                "regione": regione,
                "topic_da_evitare": da_evitare
            })
            piani_generati.append({"regione": regione, "topic": topic})

        # Il primo piano diventa piano_corrente,
        # i rimanenti vengono salvati nel KG
        piano = piani_generati[0]
        if len(piani_generati) > 1:
            inserisci_post_pianificati(piani_generati[1:])
            print(f"{len(piani_generati) - 1} piani salvati nel KG.")

    return {
        **state,
        "piano_corrente": piano
    }