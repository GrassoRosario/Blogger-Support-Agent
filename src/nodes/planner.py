"""
Nodo Planner del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Controlla se esistono PostPianificati nel KG
- Se sì: prende il più vecchio e lo usa come piano_corrente
- Se no: genera K nuovi piani tramite regioni_disponibili() e Search,
         salva i K-1 piani rimanenti nel KG, usa il primo come piano_corrente

Non chiama direttamente l'LLM: delega la scelta del topic al tool Search.
"""

import random
from langchain_core.tools import tool
from kg_operations import (
    regioni_disponibili,
    topic_per_regione,
    prossimo_post_pianificato,
    inserisci_post_pianificati,
)
from search_tool import search_tool


# ==============================================================
# Tool Search per il Planner
# ==============================================================

def _cerca_topic(regione: str, topic_da_evitare: list[str]) -> str:
    """
    Costruisce una query e usa search_tool per trovare un topic
    turistico da trattare per la regione indicata.

    Args:
        regione:          Nome della regione italiana (es. "Sicilia")
        topic_da_evitare: Topic già trattati in post precedenti

    Returns:
        Nome del topic suggerito (es. "Valle dei Templi di Agrigento")
    """
    da_evitare = ", ".join(topic_da_evitare) if topic_da_evitare else "nessuno"
    query = (
        f"luoghi turistici da visitare in {regione} Italia "
        f"escludendo: {da_evitare}"
    )
    risultati = search_tool.invoke({"query": query})

    # Chiede a Gemini di estrarre il topic migliore dai risultati
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    import os

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0,
    )
    risposta = llm.invoke([HumanMessage(content=(
        f"Dai seguenti risultati di ricerca su luoghi turistici in {regione}, "
        f"scegli UN solo luogo o monumento specifico da visitare "
        f"(non già presente in questa lista: {da_evitare}). "
        f"Rispondi SOLO con il nome del luogo, niente altro.\n\n{risultati}"
    ))])
    return risposta.content.strip()


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
            topic = _cerca_topic(regione, da_evitare)
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