"""
Funzione interna di retrieval semantico sui documenti turistici indicizzati.
Non esposta all'agente — usata solo da rag_tool.
"""

from langchain_neo4j import Neo4jVector
from config import NEO4J_VECTOR_KWARGS, carica_embeddings

embeddings = carica_embeddings()

vector_store = Neo4jVector.from_existing_index(
    embedding=embeddings,
    search_type="vector",
    **NEO4J_VECTOR_KWARGS,
)

SOGLIA_SCORE = 0.6


def get_monumenti_disponibili() -> dict[str, str]:
    """
    Recupera tutti i valori distinti del metadato 'site_name' dal grafo Neo4j
    tramite query Cypher diretta.

    Returns:
        Dizionario {site_name: source_originale}
        Es. {"Reggia di Caserta": "reggia_di_caserta.pdf"}
    """
    query = "MATCH (d:Documento) RETURN DISTINCT d.site_name AS site_name, d.source AS source"
    risultati = vector_store.query(query)

    mapping = {}
    for record in risultati:
        site_name = record.get("site_name")
        source = record.get("source")
        if site_name and source:
            mapping[site_name] = source

    return mapping


def retrieve_chunks(query: str, source: str) -> str:
    """
    Cerca i chunk più rilevanti filtrati per un singolo documento (source).

    Args:
        query:  Query pulita, senza il nome del monumento
                (es. "storia", "orari di visita")
        source: Valore esatto del metadato source
                (es. "reggia_di_caserta.pdf")

    Returns:
        Testo grezzo dei chunk rilevanti con riferimento a fonte e sezione,
        oppure messaggio di fallback se nessun chunk supera la soglia.
    """
    risultati = vector_store.similarity_search_with_score(
        query,
        k=8,
        filter={"source": source},
    )

    if not risultati:
        return "Nessun documento rilevante trovato nell'indice locale."

    risultati_filtrati = [
        (doc, score) for doc, score in risultati if score >= SOGLIA_SCORE
    ]

    if not risultati_filtrati:
        return (
            f"Nessun documento sufficientemente rilevante trovato "
            f"(score massimo: {risultati[0][1]:.4f}, soglia: {SOGLIA_SCORE})."
        )

    testi = []
    for i, (doc, score) in enumerate(risultati_filtrati, 1):
        fonte = doc.metadata.get("source", "fonte sconosciuta")
        section = doc.metadata.get("section", "sezione sconosciuta")
        testi.append(
            f"[Documento {i} — {fonte}, section. {section} | Score: {score:.4f}]\n"
            f"{doc.page_content}"
        )

    return "\n\n".join(testi)