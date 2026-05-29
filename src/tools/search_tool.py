"""
Search tool e Think tool per il Researcher del blog turistico italiano.

- search_tool: ricerca su internet tramite Tavily con summarizzazione
- think_tool: riflessione strategica per decidere se continuare a cercare

Dipendenze:
    pip install tavily-python langchain-google-genai
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from tavily import TavilyClient


# ==============================================================
# Configurazione
# ==============================================================

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

summarization_llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0,
)

SUMMARIZE_PROMPT = """Sei un assistente che sintetizza contenuti web per ricerche turistiche.
Dato il contenuto grezzo di una pagina web, estrai:
- Un riassunto conciso e informativo (max 200 parole)
- I passaggi chiave più rilevanti per il turismo italiano

Data odierna: {date}

Contenuto della pagina:
{content}

Rispondi in italiano con questo formato:
RIASSUNTO: ...
PASSAGGI CHIAVE: ...
"""


# ==============================================================
# Funzioni interne
# ==============================================================

def _summarize_content(content: str) -> str:
    """Sintetizza il contenuto grezzo di una pagina web."""
    from datetime import datetime
    try:
        risposta = summarization_llm.invoke([
            HumanMessage(content=SUMMARIZE_PROMPT.format(
                content=content[:4000],  # limita il contenuto per non eccedere il context
                date=datetime.now().strftime("%d/%m/%Y")
            ))
        ])
        return risposta.content
    except Exception:
        # Fallback: restituisce i primi 500 caratteri
        return content[:500] + "..."


def _format_results(results: list[dict]) -> str:
    """Formatta i risultati di ricerca in un testo strutturato."""
    if not results:
        return "Nessun risultato trovato. Prova con query diverse."

    output = "Risultati della ricerca:\n\n"
    for i, r in enumerate(results, 1):
        output += f"--- FONTE {i}: {r['title']} ---\n"
        output += f"URL: {r['url']}\n\n"
        output += f"{r['content']}\n\n"
        output += "-" * 60 + "\n"
    return output


# ==============================================================
# Search Tool
# ==============================================================

@tool
def search_tool(query: str) -> str:
    """
    Cerca informazioni su internet su luoghi turistici, monumenti,
    borghi, siti naturali e attrazioni italiane.
    Usare quando i documenti locali non contengono informazioni sufficienti.
    Limitare a max 5 chiamate per sessione di ricerca.

    Args:
        query: Query di ricerca specifica in italiano o inglese
               (es. "Valle dei Templi Agrigento storia orari visita")

    Returns:
        Risultati di ricerca sintetizzati con fonte e URL
    """
    risultati_grezzi = tavily_client.search(
        query=query,
        max_results=3,
        include_raw_content=True,
        topic="general",
    )

    risultati_processati = []
    seen_urls = set()

    for r in risultati_grezzi.get("results", []):
        url = r.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Sintetizza il contenuto grezzo se disponibile
        raw = r.get("raw_content", "")
        content = _summarize_content(raw) if raw else r.get("content", "")

        risultati_processati.append({
            "title": r.get("title", ""),
            "url": url,
            "content": content,
        })

    return _format_results(risultati_processati)


# ==============================================================
# Think Tool
# ==============================================================

@tool
def think_tool(riflessione: str) -> str:
    """
    Tool di riflessione strategica per valutare i progressi della ricerca.
    Usare dopo ogni ricerca per decidere se continuare o fermarsi.

    Quando usarlo:
    - Dopo ogni risultato di ricerca: ho trovato informazioni sufficienti?
    - Prima di una nuova ricerca: cosa manca ancora?
    - Prima di concludere: posso rispondere in modo completo a tutte le sezioni?

    La riflessione deve rispondere a:
    1. Cosa ho trovato finora per ciascuna sezione?
    2. Quali sezioni sono ancora incomplete?
    3. Devo cercare ancora o ho abbastanza informazioni?

    Args:
        riflessione: Analisi dettagliata dello stato della ricerca

    Returns:
        Conferma che la riflessione è stata registrata
    """
    return f"Riflessione registrata: {riflessione}"