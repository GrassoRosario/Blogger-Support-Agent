"""
Nodo KG Updater del grafo LangGraph per il blog turistico italiano.

Responsabilità:
- Riceve la bozza approvata dal HITL
- Legge topic e fonti direttamente dall'output del Researcher
- Salva il post approvato nel Knowledge Graph
- Salva esempio "approvato" nel classifier per il fine-tuning

Nessuna chiamata LLM: tutte le informazioni sono già nello state.

Dipendenze:
    pip install neo4j
"""

from src.database.kg_operations import inserisci_post
from src.tools.post_quality_classifier import post_quality_classifier_tool


# ==============================================================
# Nodo KG Updater
# ==============================================================

def kg_updater_node(state: dict) -> dict:
    """
    Nodo KG Updater del grafo LangGraph.

    Legge dallo state:
        piano_corrente (dict):      {"regione": "...", "topic": "..."}
        bozza (str):                testo del post approvato dal HITL
        ricerca (dict):             output strutturato del Researcher
        valutazione_fonti (dict):   coppie {url: voto_utente} modificate via HITL

    Scrive sullo state:
        post_id (str): ID del post inserito nel KG
    """
    piano = state.get("piano_corrente")
    bozza = state.get("bozza")
    ricerca = state.get("ricerca", {})
    valutazione_fonti = state.get("valutazione_fonti", {})

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

    # Fonti: costruisce la lista con punteggi e status di affidabilità
    fonti = []
    for url in ricerca.get("fonti", []):
        score = valutazione_fonti.get(url)
        trust_status = "avoid" if score == 0 else "use"
        fonti.append({
            "url":           url,
            "quality_score": score,
            "trust_status":  trust_status,
        })

    # Inserisce il post nel KG
    post_id = inserisci_post(
        titolo=titolo,
        testo=bozza,
        regione=piano["regione"],
        topic=topic,
        fonti=fonti,
    )
    print(f"[KG UPDATER] Post salvato nel KG con ID: {post_id}")

    # Salva esempio "approvato" nel classifier per il fine-tuning
    # Il post è stato approvato dall'utente → esempio positivo
    risultato_classifier = post_quality_classifier_tool.invoke({
        "testo":   bozza,
        "label":   "approvato",
        "regione": piano["regione"],
        "topic":   piano["topic"],
    })
    print(f"[KG UPDATER] Classifier: {risultato_classifier}")

    return {
        **state,
        "post_id": post_id,
    }