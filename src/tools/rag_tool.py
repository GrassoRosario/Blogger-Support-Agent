"""
RAG tool: risposta grounded in italiano tramite Gemini Flash.

Dipendenze:
    pip install langchain langchain-google-genai
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from tools.retriever_tool import retriever_tool

# ==============================================================
# Configurazione
# ==============================================================

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


# ==============================================================
# Tool
# ==============================================================

@tool
def rag_tool(domanda: str) -> str:
    """
    Risponde a domande su monumenti, siti naturali, borghi e luoghi
    di interesse italiani usando i documenti turistici indicizzati localmente.
    Fornisce risposte elaborate e grounded nelle fonti disponibili.
    Usare quando si vuole una risposta in linguaggio naturale, non i documenti grezzi.

    Args:
        domanda: Domanda sul luogo o monumento da approfondire
                 (es. "Qual è il valore universale della Reggia di Caserta?")

    Returns:
        Risposta in italiano basata sui documenti indicizzati
    """
    contesto = retriever_tool.invoke({"query": domanda})

    if "Nessun documento rilevante" in contesto:
        return "Non ho trovato informazioni sufficienti nei documenti locali."

    chain = PROMPT | llm
    risposta = chain.invoke({"contesto": contesto, "domanda": domanda})
    return risposta.content