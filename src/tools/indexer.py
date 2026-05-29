"""
Indicizzazione di documenti PDF nel Neo4j Vector Index.

Uso:
    python indexer.py <percorso_pdf_o_cartella> [--forza]

Dipendenze:
    pip install langchain langchain-community neo4j pypdf sentence-transformers
"""

import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Neo4jVector
from neo4j import GraphDatabase

# ==============================================================
# Configurazione
# ==============================================================

NEO4J_URI  = "bolt://localhost:7687"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

INDEX_NAME     = "documenti_turistici"
NODE_LABEL     = "Documento"
TEXT_PROPERTY  = "testo"
EMBEDDING_PROP = "embedding"

NEO4J_VECTOR_KWARGS = dict(
    url=NEO4J_URI,
    username="",
    password="",
    index_name=INDEX_NAME,
    node_label=NODE_LABEL,
    text_node_property=TEXT_PROPERTY,
    embedding_node_property=EMBEDDING_PROP,
)

driver = GraphDatabase.driver(NEO4J_URI, auth=None)
embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)


# ==============================================================
# Controllo duplicati
# ==============================================================

def _pdf_gia_indicizzato(percorso_pdf: str) -> bool:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Documento)
            WHERE d.source = $source
            RETURN count(d) AS totale
        """, source=percorso_pdf)
        return result.single()["totale"] > 0


# ==============================================================
# Indicizzazione
# ==============================================================

def indicizza_pdf(percorso_pdf: str, forza: bool = False):
    """
    Carica un PDF, lo divide in chunk e lo indicizza nel Neo4j Vector Index.
    Salta l'indicizzazione se il PDF è già presente, a meno che forza=True.

    Args:
        percorso_pdf: Percorso al file PDF (es. "documenti/colosseo.pdf")
        forza:        Se True, reindicizza anche se già presente (default False)
    """
    if not forza and _pdf_gia_indicizzato(percorso_pdf):
        print(f"  → Già indicizzato, salto: {percorso_pdf}")
        return

    print(f"Caricamento: {percorso_pdf}")

    # Carica ogni pagina come un documento separato e inserisce i metadati source e page
    loader = PyPDFLoader(percorso_pdf)
    pagine = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "]
    )
    chunks = splitter.split_documents(pagine)
    print(f"  → {len(chunks)} chunk generati")

    Neo4jVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        **NEO4J_VECTOR_KWARGS,
    )
    print(f"  → Indicizzazione completata.")


def indicizza_cartella(cartella: str, forza: bool = False):
    """
    Indicizza tutti i PDF presenti in una cartella.

    Args:
        cartella: Percorso alla cartella (es. "documenti/")
        forza:    Se True, reindicizza tutto (default False)
    """
    pdf_files = [
        os.path.join(cartella, f)
        for f in os.listdir(cartella)
        if f.endswith(".pdf")
    ]

    if not pdf_files:
        print(f"Nessun PDF trovato in: {cartella}")
        return

    for percorso in pdf_files:
        indicizza_pdf(percorso, forza=forza)

    print(f"\nIndicizzazione completata: {len(pdf_files)} documenti processati.")


# ==============================================================
# Entry point
# ==============================================================

if __name__ == "__main__":
    import sys
    forza = "--forza" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--forza"]

    if not args:
        print("Uso: python indexer.py <percorso_pdf_o_cartella> [--forza]")
        sys.exit(1)

    percorso = args[0]
    if os.path.isdir(percorso):
        indicizza_cartella(percorso, forza=forza)
    elif percorso.endswith(".pdf"):
        indicizza_pdf(percorso, forza=forza)
    else:
        print("Errore: specificare un file PDF o una cartella.")