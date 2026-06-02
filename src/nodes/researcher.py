"""
Nodo Researcher del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Riceve il piano_corrente (regione + topic) dal Planner
- Usa un agente ReAct con tool per raccogliere informazioni
- Si ferma quando tutte le sezioni dell'output strutturato sono popolate
- Passa l'output strutturato al Drafter

Tool disponibili:
- retriever_tool: chunk grezzi dai documenti locali
- rag_tool: risposta grounded dai documenti locali
- search_tool: ricerca su internet (placeholder)
- kg_claim_tool: claim già presenti nel KG per un topic
- kg_fonti_tool: fonti già usate per una regione

Dipendenze:
    pip install langchain langchain-google-genai langgraph
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from kg_operations import claim_esistenti_per_topic, fonti_per_regione
from retriever_tool import retriever_tool
from rag_tool import rag_tool
from search_tool import search_tool, think_tool


# ==============================================================
# Configurazione
# ==============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0.3,
)


# ==============================================================
# Tool KG
# ==============================================================

@tool
def kg_claim_tool(nome_topic: str) -> str:
    """
    Restituisce i claim (affermazioni fattuali) già presenti nel Knowledge Graph
    per un topic specifico. Usare per evitare di ripetere informazioni già
    pubblicate in post precedenti.

    Args:
        nome_topic: Nome del topic (es. "Reggia di Caserta")

    Returns:
        Lista di claim già pubblicati sul topic
    """
    claim = claim_esistenti_per_topic(nome_topic)
    if not claim:
        return f"Nessun claim trovato nel KG per il topic: {nome_topic}"
    return "\n".join(f"- {c}" for c in claim)


@tool
def kg_fonti_tool(nome_regione: str) -> str:
    """
    Restituisce le fonti già usate in post precedenti per una regione,
    ordinate per qualità. Usare per riutilizzare fonti affidabili già note.

    Args:
        nome_regione: Nome della regione (es. "Campania")

    Returns:
        Lista di fonti con URL e quality score
    """
    fonti = fonti_per_regione(nome_regione)
    if not fonti:
        return f"Nessuna fonte trovata nel KG per la regione: {nome_regione}"
    return "\n".join(
        f"- {f['titolo']} ({f['url']}) — score: {f['quality_score']}"
        for f in fonti
    )


# ==============================================================
# Prompt del Researcher
# ==============================================================

SYSTEM_PROMPT = """Sei un ricercatore esperto di turismo italiano.
Il tuo compito è raccogliere informazioni su un luogo turistico italiano
per permettere la scrittura di un post di blog.

Devi popolare TUTTE le seguenti sezioni:
- descrizione: cos'è il luogo, dove si trova, aspetto generale
- storia: origini, eventi storici rilevanti, curiosità storiche
- cosa_vedere: elementi specifici da non perdere, dettagli notevoli
- informazioni_pratiche: come arrivare, orari, biglietti, consigli visita
- claim: lista di affermazioni fattuali verificabili (date, misure, fatti storici)
- fonti: lista delle fonti usate con URL

Strategia:
1. Controlla prima i claim già pubblicati nel KG (kg_claim_tool) per evitare ripetizioni
2. Cerca nei documenti locali con rag_tool o retriever_tool
3. Usa search_tool per informazioni non trovate localmente (max 5 chiamate)
4. Dopo ogni ricerca usa think_tool per valutare cosa hai trovato e cosa manca
5. Fermati quando tutte le sezioni sono sufficientemente popolate

Quando hai popolato tutte le sezioni, restituisci un JSON con questa struttura:
{
    "descrizione": "...",
    "storia": "...",
    "cosa_vedere": "...",
    "informazioni_pratiche": "...",
    "claim": ["affermazione 1", "affermazione 2", ...],
    "fonti": ["url1", "url2", ...]
}

Rispondi SOLO con il JSON, senza testo aggiuntivo.
"""


# ==============================================================
# Nodo Researcher
# ==============================================================

def researcher_node(state: dict) -> dict:
    """
    Nodo Researcher del grafo LangGraph.

    Legge dallo state:
        piano_corrente (dict): {"regione": "...", "topic": "..."}

    Scrive sullo state:
        ricerca (dict): output strutturato con le sezioni popolate
    """
    piano = state.get("piano_corrente")
    if not piano:
        raise ValueError("piano_corrente non trovato nello state.")

    regione = piano["regione"]
    topic = piano["topic"]

    # Crea l'agente ReAct con i tool disponibili
    agent = create_react_agent(
        model=llm,
        tools=[rag_tool, retriever_tool, search_tool, think_tool, kg_claim_tool, kg_fonti_tool],
        prompt=SYSTEM_PROMPT,
    )

    # Lancia l'agente con il task specifico
    messaggio_utente = (
        f"Raccogli informazioni per un post turistico su: {topic} ({regione}).\n"
        f"Popola tutte le sezioni richieste e restituisci il JSON finale."
    )

    risultato = agent.invoke({
        "messages": [("user", messaggio_utente)]
    })

    # Estrae il contenuto dell'ultimo messaggio (il JSON finale)
    ultimo_messaggio = risultato["messages"][-1].content

    # Parsing del JSON
    import json
    import re
    # Rimuove eventuali backtick markdown se presenti
    testo = re.sub(r"```json|```", "", ultimo_messaggio).strip()
    ricerca = json.loads(testo)

    return {
        **state,
        "ricerca": ricerca,
    }