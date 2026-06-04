"""
RAG tool: risposte grounded su monumenti italiani usando documenti indicizzati localmente.
Orchestra dispatcher → retrieve_chunks → risposta LLM.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

from rag.retriever import retrieve_chunks, get_monumenti_disponibili
from rag.dispatcher import dispatch

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0.2,
)

PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Sei un assistente esperto di turismo italiano.
Rispondi alla domanda basandoti ESCLUSIVAMENTE sui documenti forniti.
Se le informazioni non sono sufficienti, dillo esplicitamente.
Rispondi sempre in italiano, anche se i documenti sono in inglese."""),
    ("human", """Documenti di riferimento:
{contesto}

Domanda: {domanda}"""),
])


@tool
def rag_tool(domanda: str) -> str:
    """
    Risponde a domande su monumenti, siti naturali, borghi e luoghi
    di interesse italiani usando i documenti turistici indicizzati localmente.
    Fornisce risposte elaborate e grounded nelle fonti disponibili.

    Args:
        domanda: Domanda sul luogo o monumento da approfondire
                 (es. "storia della Reggia di Caserta")

    Returns:
        Risposta in italiano basata sui documenti indicizzati,
        oppure "Nessun documento trovato per il monumento richiesto." se il monumento non è in archivio.
        oppure "Non ho trovato informazioni sufficienti nei documenti locali." se il monumento è presente ma non ci sono chunk rilevanti.
    """
    # Fase 1 — recupera la lista dei documenti disponibili
    mapping = get_monumenti_disponibili()

    # Fase 2 — dispatcher: identifica il documento e pulisce la query
    risultato_dispatch = dispatch(domanda, mapping)

    if not risultato_dispatch.get("trovato"):
        return "Nessun documento trovato per il monumento richiesto."

    source = risultato_dispatch["source"]
    query_pulita = risultato_dispatch["query_pulita"]

    # Fase 3 — retrieval filtrato per source
    contesto = retrieve_chunks(query=query_pulita, source=source)

    if "Nessun documento" in contesto:
        return "Non ho trovato informazioni sufficienti nei documenti locali."

    # Fase 4 — genera la risposta finale
    chain = PROMPT | llm
    risposta = chain.invoke({"contesto": contesto, "domanda": domanda})
    raw = risposta.content
    return raw[0]["text"]
   