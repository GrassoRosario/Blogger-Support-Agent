"""
Nodo KG Updater del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Riceve la bozza approvata dal HITL
- Legge topic, claim e fonti direttamente dall'output del Researcher
- Salva il post approvato nel Knowledge Graph

Nessuna chiamata LLM: tutte le informazioni sono già nello state.

Dipendenze:
    pip install neo4j
"""

from database.kg_operations import inserisci_post


# ==============================================================
# Nodo KG Updater
# ==============================================================

def kg_updater_node(state: dict) -> dict:
    """
    Nodo KG Updater del grafo LangGraph.

    Legge dallo state:
        piano_corrente (dict): {"regione": "...", "topic": "..."}
        bozza (str):           testo del post approvato dal HITL
        ricerca (dict):        output strutturato del Researcher

    Scrive sullo state:
        post_id (str): ID del post inserito nel KG
    """
    piano = state.get("piano_corrente")
    bozza = state.get("bozza")
    ricerca = state.get("ricerca", {})

    if not piano:
        raise ValueError("piano_corrente non trovato nello state.")
    if not bozza:
        raise ValueError("bozza non trovata nello state.")

    # Titolo: prima riga non vuota del post, senza # markdown
    titolo = next(
        (riga.strip().lstrip("#").strip()
         for riga in bozza.splitlines() if riga.strip()),
        piano["topic"]
    )

    # Topic: il topic del piano come lista
    topic = [piano["topic"]]

    # Claim e fonti direttamente dal Researcher
    claim = ricerca.get("claim", [])
    fonti = [
        {
            "url": url,
            "titolo": url,
            "quality_score": 0.5
        }
        for url in ricerca.get("fonti", [])
    ]

    # Inserisce il post nel KG
    post_id = inserisci_post(
        titolo=titolo,
        testo=bozza,
        regione=piano["regione"],
        topic=topic,
        fonti=fonti,
        claim=claim,
    )

    print(f"Post salvato nel KG con ID: {post_id}")

    return {
        **state,
        "post_id": post_id,
    }