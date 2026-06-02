"""
Indicizzazione di documenti PDF nel Neo4j Vector Index.

Uso:
    python indexer.py <percorso_pdf_o_cartella>
    python indexer.py <percorso_pdf_o_cartella> --unesco
"""

import os
import sys
import pypdf

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_neo4j import Neo4jVector

from config import driver, NEO4J_VECTOR_KWARGS, carica_embeddings
from indexer_unesco import indicizza_pdf_unesco


# ============================================================
# EMBEDDINGS SINGLETON (IMPORTANTE PER PERFORMANCE)
# ============================================================

_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        print("Inizializzazione embeddings...")
        _embeddings = carica_embeddings()
    return _embeddings


# ============================================================
# CHECK GIA INDICIZZATO
# ============================================================

def gia_indicizzato(percorso: str) -> bool:
    with driver.session() as session:
        result = session.run(
            "MATCH (d:Documento) WHERE d.source = $source RETURN count(d) AS n",
            source=percorso,
        )
        return result.single()["n"] > 0


# ============================================================
# PDF STANDARD INDEXER
# ============================================================

def indicizza_pdf(percorso: str, embeddings=None):
    print(f"Caricamento: {percorso}")

    reader = pypdf.PdfReader(percorso)

    pagine = [
        Document(
            page_content=p.extract_text() or "",
            metadata={"source": percorso, "page": i},
        )
        for i, p in enumerate(reader.pages)
    ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    chunks = [
        c for c in splitter.split_documents(pagine)
        if len(c.page_content.strip()) >= 100
    ]

    if not chunks:
        print(" Nessun testo estratto.")
        return

    Neo4jVector.from_documents(
        documents=chunks,
        embedding=embeddings or get_embeddings(),
        **NEO4J_VECTOR_KWARGS,
    )

    print(f"  → {len(chunks)} chunk indicizzati.")


# ============================================================
# SINGLE FILE PIPELINE
# ============================================================

def indicizza_file(percorso: str, use_unesco: bool = False):
    if gia_indicizzato(percorso):
        print(f"  → Già indicizzato, salto: {percorso}")
        return

    embeddings = get_embeddings()

    if use_unesco:
        indicizza_pdf_unesco(percorso, embeddings)
    else:
        indicizza_pdf(percorso, embeddings)


# ============================================================
# CARTELLA PIPELINE
# ============================================================

def indicizza_cartella(cartella: str, use_unesco: bool = False):
    files = [
        os.path.join(cartella, f)
        for f in os.listdir(cartella)
        if f.lower().endswith(".pdf")
    ]

    if not files:
        print(f"Nessun PDF trovato in: {cartella}")
        return

    file_da_elaborare = [
        f for f in files if not gia_indicizzato(f)
    ]

    if not file_da_elaborare:
        print("\nTutti i documenti sono già stati processati.")
        return

    embeddings = get_embeddings()

    for f in file_da_elaborare:
        if use_unesco:
            indicizza_pdf_unesco(f, embeddings)
        else:
            indicizza_pdf(f, embeddings)

    print(f"\nCompletato: {len(file_da_elaborare)} documenti processati.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python indexer.py <percorso_pdf_o_cartella> [--unesco]")
        sys.exit(1)

    percorso = sys.argv[1]
    use_unesco = "--unesco" in sys.argv

    if os.path.isfile(percorso):
        indicizza_file(percorso, use_unesco)

    elif os.path.isdir(percorso):
        indicizza_cartella(percorso, use_unesco)

    else:
        print("Errore: specificare un file PDF o una cartella valida.")
        sys.exit(1)