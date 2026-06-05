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

def _format_results(results: list[dict], fonti: dict = None) -> str:
    """Formatta i risultati in un layout chiaro e cristallino."""
    if not results:
        return "Nessun risultato autorevole trovato. Prova a riformulare la query con termini più specifici."

    if fonti:
        score_map = fonti.get("use", {})
        results = sorted(
            results,
            key=lambda r: score_map.get(r["url"], 0),
            reverse=True
        )

    output = "=== RISULTATI DELLA RICERCA WEB (FONTI VERIFICATE) ===\n\n"
    for i, r in enumerate(results, 1):
        full_text = _clean_content(r.get("content", ""))

        if len(full_text) < 50:
            full_text = r.get("content", "Dettagli non disponibili nel testo estratto.")

        sentences = [s.strip() for s in full_text.split(".") if len(s.strip()) > 20]
        riassunto_testo = ". ".join(sentences[:3]) + "." if sentences else full_text[:300]

        output += f"--- FONTE {i}: {r['title']} ---\n"
        output += f"URL PER CITAZIONE: {r['url']}\n\n"

        output += f"RIASSUNTO:\n{riassunto_testo}\n\n"

        output += "PASSAGGI CHIAVE:\n"
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
# Search Tool 
# ==============================================================
@tool
def search_tool(query: str, fonti: dict = None) -> str:
    """
    Cerca informazioni su internet su luoghi turistici, monumenti,
    borghi, siti naturali e attrazioni italiane.
    Garantisce un output chiaro, leggibile e privo di elementi di disturbo web.

    IMPORTANTE: la query deve essere SPECIFICA e includere:
    - Nome esatto del luogo (es. "Valle dei Templi", "Reggia di Caserta")
    - Regione o città (es. "Agrigento", "Campania")
    - Aspetto cercato (es. "storia", "orari visita", "patrimonio UNESCO")

    Esempi di query CORRETTE:
      "Valle dei Templi Agrigento storia patrimonio UNESCO"
      "Reggia di Caserta orari biglietti cosa vedere"

    Esempi di query SBAGLIATE (troppo vaghe):
      "cosa vedere in Sicilia"
      "monumenti storici Italia"

    Args:
        query:  Query specifica in italiano (es. "Cattedrale di Palermo storia architettura")
        fonti:  Dict con "use" (url: quality_score) e "avoid" (lista url) restituito da kg_fonti_tool.
                Se assente, la ricerca avviene senza filtri sui domini.
                Se presente, i risultati sono restituiti in ordine decrescente di quality_score:
                le fonti con score più alto appaiono per prime.
    """
    if fonti:
        include = list(fonti.get("use", {}).keys())
        exclude = fonti.get("avoid", [])
        raw = _esegui_ricerca(query, include_domains=include, exclude_domains=exclude)
    else:
        raw = _esegui_ricerca(query)

    results = raw.get("results", [])
    return _format_results(results, fonti=fonti)


# ==============================================================
# Think Tool 
# ==============================================================

@tool
def think_tool(riflessione: str) -> str:
    """
    Tool di riflessione strategica per valutare i progressi della ricerca.
    Usare dopo ogni ricerca per decidere se continuare o fermarsi.
    """
    return f"Riflessione registrata: {riflessione}"