"""
Dispatcher LLM: estrae il monumento dalla query e lo risolve
contro la lista dei documenti disponibili.
"""

import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0.0,  # output deterministico — qui non serve creatività
)

PROMPT_DISPATCHER = ChatPromptTemplate.from_messages([
    ("system", """Sei un sistema di routing per un RAG su documenti turistici italiani.
Il tuo compito è:
1. Identificare il monumento o luogo a cui si riferisce la query
2. Trovare il documento più pertinente nella lista fornita

IMPORTANTE: i nomi nella lista possono essere in inglese, in italiano, o in formato esteso ufficiale UNESCO.
Devi ragionare sul significato, non sul testo letterale.
Esempi di corrispondenze valide:
- "Reggia di Caserta" → "18th-Century Royal Palace at Caserta with the Park, the Aqueduct of Vanvitelli, and the San Leucio Complex"
- "Colosseo" → "Rome's Historic Centre" oppure "Colosseum"
- "Pompei" → "Archaeological Areas of Pompei, Herculaneum and Torre Annunziata"

3. Restituire SOLO un oggetto JSON valido, senza markdown, senza backtick, senza spiegazioni

Formato di risposta se il documento è trovato:
{{"trovato": true, "source": "<valore esatto dalla lista>", "query_pulita": "<query senza il nome del monumento>"}}

Formato di risposta se nessun documento è pertinente:
{{"trovato": false, "source": null, "query_pulita": null}}"""),
    ("human", """Documenti disponibili:
{lista_monumenti}

Query: {query}"""),
])

def dispatch(query: str, mapping: dict[str, str]) -> dict:
    """
    Determina quale documento è pertinente alla query e riscrive la query
    rimuovendo il riferimento al monumento.

    Args:
        query:   Query originale dell'utente (es. "storia della reggia di caserta")
        mapping: Dizionario {nome_leggibile: source_originale} prodotto da
                 get_monumenti_disponibili()

    Returns:
        Dizionario con:
          - trovato (bool)
          - source (str|None): valore esatto del metadato da usare come filtro
          - query_pulita (str|None): query senza il nome del monumento
    """
    lista_monumenti = "\n".join(
        f"- {nome} (source: {source})"
        for nome, source in mapping.items()
    )

    chain = PROMPT_DISPATCHER | llm
    risposta = chain.invoke({
        "lista_monumenti": lista_monumenti,
        "query": query,
    })

    try:
        # Gemini restituisce una lista con un singolo elemento, un dizionario, che contiene nella chiave "text" la stringa JSON desiderata
        raw = risposta.content
        testo = raw[0]["text"]
        return json.loads(testo)
    except json.JSONDecodeError:
        # fallback sicuro: nessun documento trovato
        return {"trovato": False, "source": None, "query_pulita": None}