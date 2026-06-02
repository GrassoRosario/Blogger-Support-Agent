"""
Tool di retrieval semantico sui documenti turistici indicizzati.

Dipendenze:
    pip install langchain langchain-community neo4j sentence-transformers
"""

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector
from langchain_core.tools import tool

from config import NEO4J_VECTOR_KWARGS, carica_embeddings

embeddings = carica_embeddings()

vector_store = Neo4jVector.from_existing_index(
    embedding=embeddings,
    search_type="vector",
    **NEO4J_VECTOR_KWARGS,
)

@tool
def retriever_tool(query: str) -> str:
    """
    Cerca e restituisce i chunk di testo più rilevanti dai documenti
    turistici italiani indicizzati localmente.
    Usare quando si vogliono i documenti grezzi da elaborare autonomamente.

    Args:
        query: Argomento o domanda da cercare
               (es. "storia della Reggia di Caserta")

    Returns:
        Testo grezzo estratto dai documenti più rilevanti con riferimento a fonte e pagina
    """
    risultati = vector_store.similarity_search(query, k=8)

    if not risultati:
        return "Nessun documento rilevante trovato nell'indice locale."

    testi = []
    for i, doc in enumerate(risultati, 1):
        fonte = doc.metadata.get("source", "fonte sconosciuta")
        section = doc.metadata.get("section", "sezione sconosciuta")
        testi.append(f"[Documento {i} — {fonte}, section. {section}]\n{doc.page_content}")

    return "\n\n".join(testi)