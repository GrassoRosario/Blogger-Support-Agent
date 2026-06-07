"""
Nodo Planner del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Controlla se esistono PostPianificati nel KG
- Se sì: prende il più vecchio e lo usa come piano_corrente
- Se no: genera K nuovi piani tramite regioni_disponibili() e Search,
         salva i K-1 piani rimanenti nel KG, usa il primo come piano_corrente
- Salva esempio "rifiutato" nel classifier se arriviamo da un rifiuto HITL
"""

import os
import random
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from src.database.kg_operations import (
    regioni_disponibili,
    topic_per_regione,
    prossimo_post_pianificato,
    inserisci_post_pianificati,
)
from src.tools.search_tool import search_tool
from src.tools.post_quality_classifier import post_quality_classifier_tool


# ==============================================================
# LLM (istanziato una sola volta)
# ==============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0,
)


# ==============================================================
# Funzioni interne
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

    risposta = llm.invoke([HumanMessage(content=(
        f"Dai seguenti risultati di ricerca su luoghi turistici in {regione}, "
        f"scegli UN solo luogo o monumento specifico da visitare "
        f"(non già presente in questa lista: {da_evitare}). "
        f"Rispondi SOLO con il nome del luogo, niente altro.\n\n{risultati}"
    ))])
    if isinstance(risposta.content, str):
        testo_topic = risposta.content
    elif isinstance(risposta.content, list):
        testo_topic = "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in risposta.content
        )
    else:
        testo_topic = str(risposta.content)

    return testo_topic.strip()


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
        piano_corrente (dict):
            {
                "regione": "Sicilia",
                "topic":   "Valle dei Templi di Agrigento"
            }
    """
    n = state.get("n", 5)
    k = state.get("k", 3)

    # Salva esempio "rifiutato" nel classifier se arriviamo da un rifiuto HITL
    if state.get("hitl_action") == "rifiuta" and state.get("bozza") and state.get("piano_corrente"):
        print("[Planner] Post rifiutato — salvo esempio nel classifier...")
        risultato = post_quality_classifier_tool.invoke({
            "testo":   state["bozza"],
            "label":   "rifiutato",
            "regione": state["piano_corrente"]["regione"],
            "topic":   state["piano_corrente"]["topic"],
        })
        print(f"[Planner] Classifier: {risultato}")

    # 1. Controlla se esistono PostPianificati nel KG
    piano = prossimo_post_pianificato()

    if piano:
        print(f"[Planner] Piano trovato nel KG: {piano}")
    else:
        # 2. Nessun piano: genera K nuovi piani
        print("[Planner] Nessun piano nel KG. Generazione di nuovi piani...")

        disponibili = regioni_disponibili(n)
        k_effettivo = min(k, len(disponibili))
        regioni_scelte = random.sample(disponibili, k_effettivo)

        piani_generati = []
        for regione in regioni_scelte:
            da_evitare = topic_per_regione(regione)
            topic = _cerca_topic(regione, da_evitare)
            piani_generati.append({"regione": regione, "topic": topic})

        # Il primo diventa piano_corrente, i rimanenti vanno nel KG
        piano = piani_generati[0]
        if len(piani_generati) > 1:
            inserisci_post_pianificati(piani_generati[1:])
            print(f"[Planner] {len(piani_generati) - 1} piani salvati nel KG.")

    return {
        **state,
        "piano_corrente": piano,
    }