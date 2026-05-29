"""
Tool di retrieval semantico sui documenti turistici indicizzati.

Dipendenze:
    pip install langchain langchain-community neo4j sentence-transformers
"""

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_core.tools import tool

# ==============================================================
# Configurazione
# ==============================================================

NEO4J_URI  = "bolt://localhost:7687"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

NEO4J_VECTOR_KWARGS = dict(
    url=NEO4J_URI,
    username="",
    password="",
    index_name="documenti_turistici",
    node_label="Documento",
    text_node_property="testo",
    embedding_node_property="embedding",
)

embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
vector_store = Neo4jVector.from_existing_index(
    embedding=embeddings,
    **NEO4J_VECTOR_KWARGS,
)


# ==============================================================
# Tool
# ==============================================================

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
    risultati = vector_store.similarity_search(query, k=4)

    if not risultati:
        return "Nessun documento rilevante trovato nell'indice locale."

    testi = []
    for i, doc in enumerate(risultati, 1):
        fonte = doc.metadata.get("source", "fonte sconosciuta")
        pagina = doc.metadata.get("page", "?")
        testi.append(f"[Documento {i} — {fonte}, pag. {pagina}]\n{doc.page_content}")

    return "\n\n".join(testi)