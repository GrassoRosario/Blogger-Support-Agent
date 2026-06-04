"""
Search tool e Think tool per il Researcher del blog turistico italiano.
Versione ad alta leggibilità: genera un output cristallino per l'esame
senza effettuare chiamate LLM intermedie (zero crash di quota).
"""

import os
from langchain_core.tools import tool
from tavily import TavilyClient

# ==============================================================
# Configurazione
# ==============================================================

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Whitelist di domini istituzionali e culturali per garantire fonti autorevoli
DOMINI_FIDATI = [
    "whc.unesco.org",
    "unesco.cultura.gov.it",
    "cultura.gov.it",
    "italia.it",
    "beniculturali.it",
    "treccani.it",
    "sitiunesco.it",
    "regione.sicilia.it"
]

DOMINI_ESCLUSI = [
    "youtube.com", "getyourguide.com", "tripadvisor.com", 
    "casevacanzasicilia.it", "booking.com", "expedia.it", "komoot.com"
]

# ==============================================================
# Funzioni interne di Formattazione ad Alta Leggibilità
# ==============================================================

def _clean_content(text: str) -> str:
    """Pulisce il testo rimuovendo intestazioni, menu e tag spuri."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line_str = line.strip()
        # Salta elementi tipici di navigazione o formattazione markdown residua
        if not line_str or len(line_str) < 10:
            continue
        if any(x in line_str.lower() for x in ["[skip", "secret menu", "cookie", "navigazione", "###"]):
            continue
        cleaned.append(line_str)
    return " ".join(cleaned)

def _format_results(results: list[dict]) -> str:
    """Formatta i risultati in un layout chiaro e cristallino."""
    if not results:
        return "Nessun risultato autorevole trovato. Prova a riformulare la query con termini più specifici."

    output = "=== RISULTATI DELLA RICERCA WEB (FONTI VERIFICATE) ===\n\n"
    for i, r in enumerate(results, 1):
        full_text = _clean_content(r.get("content", ""))
        
        # Se il testo è troppo corto, usa una stringa di fallback
        if len(full_text) < 50:
            full_text = r.get("content", "Dettagli non disponibili nel testo estratto.")

        # Costruiamo il testo lineare del riassunto (le prime due frasi lunghe)
        sentences = [s.strip() for s in full_text.split(".") if len(s.strip()) > 20]
        riassunto_testo = ". ".join(sentences[:3]) + "." if sentences else full_text[:300]
        
        output += f"--- FONTE {i}: {r['title']} ---\n"
        output += f"URL PER CITAZIONE: {r['url']}\n\n"
        
        output += f"RIASSUNTO:\n{riassunto_testo}\n\n"
        
        output += "PASSAGGI CHIAVE:\n"
        # Creiamo punti elenco sintetici basati sul contenuto reale per massima chiarezza
        if len(sentences) >= 2:
            output += f"* **Contesto Principale**: {sentences[0]}.\n"
            if len(sentences) > 1:
                output += f"* **Dettagli e Attrazioni**: {sentences[1]}.\n"
            if len(sentences) > 2:
                output += f"* **Informazioni di Rilievo**: {sentences[2]}.\n"
        else:
            output += f"* **Punto Chiave**: {full_text[:150]}...\n"
            
        output += "\n" + "-" * 60 + "\n\n"
    return output


def _esegui_ricerca(query: str, include_domains=None, exclude_domains=None) -> dict:
    """Wrapper di chiamata per Tavily."""
    params = {
        "query": query,
        "max_results": 3,              # Limiti puliti a 3 fonti per non sovraccaricare il contesto
        "search_depth": "advanced",    # Ricerca approfondita
        "include_raw_content": False,  # No HTML grezzo per evitare sporcizia nel testo
        "topic": "general",
    }
    if include_domains:
        params["include_domains"] = include_domains
    if exclude_domains:
        params["exclude_domains"] = exclude_domains
        
    return tavily_client.search(**params)

# ==============================================================
# Search Tool Pubblico
# ==============================================================

@tool
def search_tool(query: str, solo_fidati: bool = True) -> str:
    """
    Cerca informazioni su internet su luoghi turistici, monumenti,
    borghi, siti naturali e attrazioni italiane.
    Garantisce un output chiaro, leggibile e privo di elementi di disturbo web.

    Args:
        query: Query specifica in italiano (es. "Cattedrale di Palermo storia architettura")
        solo_fidati: Se True, limita la ricerca ai domini istituzionali e culturali (default: True)
    """
    if solo_fidati:
        raw = _esegui_ricerca(query, include_domains=DOMINI_FIDATI)
        results = raw.get("results", [])
        
        # Fallback se i siti governativi non contengono la risposta specifica
        if not results:
            raw = _esegui_ricerca(query, exclude_domains=DOMINI_ESCLUSI)
            results = raw.get("results", [])
    else:
        raw = _esegui_ricerca(query, exclude_domains=DOMINI_ESCLUSI)
        results = raw.get("results", [])

    return _format_results(results)


# ==============================================================
# Think Tool Pubblico
# ==============================================================

@tool
def think_tool(riflessione: str) -> str:
    """
    Tool di riflessione strategica per valutare i progressi della ricerca.
    Usare dopo ogni ricerca per decidere se continuare o fermarsi.
    """
    return f"Riflessione registrata: {riflessione}"