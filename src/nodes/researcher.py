"""
Nodo Researcher del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Riceve il piano_corrente (regione + topic) dal Planner
- Usa un agente ReAct con tool per raccogliere informazioni
- Si ferma quando tutte le sezioni dell'output strutturato sono popolate
- Passa l'output strutturato al Drafter

Tool disponibili:
- rag_tool: risposta grounded dai documenti locali
- search_tool: ricerca su internet per informazioni non trovate localmente
- kg_fonti_tool: fonti già note dal KG per guidare la ricerca

Dipendenze:
    pip install langchain langchain-google-genai langgraph
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain.callbacks import StdOutCallbackHandler
from kg_operations import fonti_note
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
def kg_fonti_tool() -> dict:
    """
    Restituisce tutte le fonti del KG divise per affidabilità.

    Returns:
        Dict con "use" (url: quality_score) e "avoid" (lista url)
    """
    return fonti_note()


# ==============================================================
# Prompt del Researcher
# ==============================================================

SYSTEM_PROMPT = """Sei un ricercatore esperto di turismo italiano.
Il tuo compito è raccogliere informazioni su un luogo turistico italiano
per permettere la scrittura di un post di blog.

## FORMATO OBBLIGATORIO
Devi ragionare seguendo SEMPRE questo ciclo, senza eccezioni:

Thought: [spiega cosa sai finora e perché usi questo tool]
Action: [nome esatto del tool: rag_tool | search_tool | think_tool | kg_fonti_tool]
Action Input: [input del tool]
Observation: [risultato del tool — compilato automaticamente]

Ripeti il ciclo fino a quando tutte le sezioni sono popolate, poi:

Thought: Ho raccolto abbastanza informazioni per tutte le sezioni.
Final Answer: {"descrizione": "...", "storia": "...", ...}

## REGOLE
- Non saltare mai il Thought prima di ogni Action
- Nel Thought spiega PERCHÉ stai scegliendo quel tool specifico
- Non usare un tool senza aver scritto un Thought che lo giustifica
- Final Answer SOLO quando tutte le sezioni sono popolate


## SEZIONI DA POPOLARE
- descrizione: cos'è il luogo, dove si trova, aspetto generale
- storia: origini, eventi storici rilevanti, curiosità storiche
- cosa_vedere: elementi specifici da non perdere, dettagli notevoli
- informazioni_pratiche: come arrivare, orari, biglietti, consigli visita
- fonti: lista delle fonti usate con URL

## STRATEGIA
1. Cerca nei documenti locali con rag_tool
2. Chiama kg_fonti_tool per ottenere le fonti affidabili note, poi usa search_tool
   passando il risultato di kg_fonti_tool per limitare la ricerca ai domini fidati (max 3 chiamate)
3. Dopo ogni ricerca usa think_tool per valutare cosa hai trovato e cosa manca
4. Se le sezioni non sono ancora sufficientemente popolate, usa search_tool senza
   passare fonti per allargare la ricerca (max 2 chiamate aggiuntive)
5. Fermati quando tutte le sezioni sono sufficientemente popolate

Quando hai popolato tutte le sezioni, restituisci un JSON con questa struttura:
{
    "descrizione": "...",
    "storia": "...",
    "cosa_vedere": "...",
    "informazioni_pratiche": "...",
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
    agent = create_react_agent(llm, tools=[rag_tool, search_tool,
                                        think_tool, kg_fonti_tool], 
                           prompt=SYSTEM_PROMPT)

    executor = AgentExecutor(
        agent=agent,
        tools=[rag_tool, search_tool, think_tool, kg_fonti_tool],
        verbose=True,                    # stampa Thought/Action/Observation
        return_intermediate_steps=True,  # salva i passi nello state
        max_iterations=10,
    )

    # Lancia l'agente con il task specifico
    messaggio_utente = (
        f"Raccogli informazioni per un post turistico su: {topic} ({regione}).\n"
        f"Popola tutte le sezioni richieste e restituisci il JSON finale."
    )

    risultato = executor.invoke({"input": messaggio_utente})
    ultimo_messaggio = risultato["output"]

    # Parsing del JSON
    import json
    import re
    testo = re.sub(r"```json|```", "", ultimo_messaggio).strip()
    ricerca = json.loads(testo)

    return {
        **state,
        "ricerca": ricerca,
        "reasoning_trace": risultato["intermediate_steps"],  
}