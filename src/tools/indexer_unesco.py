"""
Parser strutturato per documenti PDF UNESCO World Heritage Centre.
Focalizzato sull'estrazione di sezioni descrittive e informative.
"""

import pypdf
from langchain_core.documents import Document

# Sezioni del documento destinate all'estrazione e all'indicizzazione
SEZIONI_TARGET = {
    "Brief synthesis",
    "Integrity",
    "Authenticity",
    "Protection and management requirements",
    "Criterion (i)", "Criterion (ii)", "Criterion (iii)", "Criterion (iv)", 
    "Criterion (v)", "Criterion (vi)", "Criterion (vii)"
}

def indicizza_pdf_unesco(percorso: str, embeddings=None) -> list[Document]:
    """
    Carica un PDF UNESCO, ne estrae le sezioni descrittive principali,
    suddivide i testi lunghi preservando l'integrità delle frasi
    e carica i chunk risultanti nel database vettoriale Neo4j.
    """
    print(f"[UNESCO] Avvio elaborazione documento: {percorso}")
    
    try:
        reader = pypdf.PdfReader(percorso)
    except Exception as e:
        print(f"  ⚠ Errore durante la lettura del file PDF: {e}")
        return []

    righe = []
    for pagina in reader.pages:
        testo_pag = pagina.extract_text() or ""
        righe.extend([riga.strip() for riga in testo_pag.splitlines() if riga.strip()])

    # Rimozione di eventuali righe di rumore specifiche dei PDF UNESCO
    stringa_rumore = "Description Maps Documents Gallery Video Indicators"
    righe = [riga for riga in righe if riga != stringa_rumore]

    if not righe:
        print("  ⚠ Nessun testo estratto dal documento.")
        return []

    # 1. Suddivisione del testo in base alla struttura delle sezioni
    dati_sezioni = {}
    sezione_corrente = None

    for riga in righe:

        if riga == "Links":
            sezione_corrente = None
            continue

        sezione_trovata = None

        if riga in SEZIONI_TARGET:
            sezione_trovata = riga

        # I criteri di selezione sono numerati e racchiusi tra parentesi, ad esempio "Criterion (i)"
        elif "Criterion (" in riga:
            inizio = riga.find("Criterion (")
            fine = riga.find(")", inizio)
            if fine != -1:
                sezione_trovata = riga[inizio:fine+1]

        if sezione_trovata:
            sezione_corrente = sezione_trovata
            dati_sezioni[sezione_corrente] = []
            
            # Se la riga del criterio conteneva già del testo successivo, 
            # salviamo la parte restante all'interno della sezione stessa
            if "Criterion (" in riga and len(riga) > len(sezione_corrente):
                testo_residuo = riga[fine+1:].strip(" :,-")
                if testo_residuo:
                    dati_sezioni[sezione_corrente].append(testo_residuo)
        
        elif sezione_corrente:
            dati_sezioni[sezione_corrente].append(riga)

    # 2. Definizione dei metadati comuni per l'identificazione del sito
    # Il nome del sito corrisponde alla prima riga non vuota del documento
    nome_sito = righe[0] if righe else "Unknown"
    
    meta_base = {
        "source": percorso,
        "doc_type": "UNESCO_WHC",
        "site_name": nome_sito
    }

    # 3. Generazione dei chunk semantici
    chunks = []
    for nome_sezione, righe_sezione in dati_sezioni.items():
        testo_sezione = " ".join(righe_sezione).strip()
        
        # Ignora blocchi di testo troppo brevi o privi di contenuto informativo
        if len(testo_sezione) < 50:
            continue

        metadata = {**meta_base, "section": nome_sezione}

        # Per sezioni di lunghezza standard, il blocco viene mantenuto unito
        if len(testo_sezione) <= 1000:
            chunks.append(Document(page_content=testo_sezione, metadata=metadata))
        else:
            # Per sezioni estese, si procede alla scomposizione per frasi compiute
            frasi = [f.strip() for f in testo_sezione.split(". ") if f.strip()]
            buffer_frasi = []
            
            for frase in frasi:
                buffer_frasi.append(frase)
                testo_accumulato = ". ".join(buffer_frasi)
                if not testo_accumulato.endswith("."):
                    testo_accumulato += "."

                # Limite di circa 600 caratteri per garantire la granularità del RAG
                if len(testo_accumulato) > 600:
                    chunks.append(Document(page_content=testo_accumulato, metadata=metadata))
                    buffer_frasi = []
            
            # Inserimento delle frasi rimanenti nel buffer
            if buffer_frasi:
                testo_rimanente = ". ".join(buffer_frasi)
                if not testo_rimanente.endswith("."):
                    testo_rimanente += "."
                chunks.append(Document(page_content=testo_rimanente, metadata=metadata))

    print(f"  → Generati {len(chunks)} chunk strutturati da {len(dati_sezioni)} sezioni individuate.")
    
    # 4. Trasferimento e indicizzazione all'interno di Neo4j
    if chunks and embeddings:
        from langchain_neo4j import Neo4jVector
        from config import NEO4J_VECTOR_KWARGS
        
        try:
            Neo4jVector.from_documents(
                documents=chunks,
                embedding=embeddings,
                **NEO4J_VECTOR_KWARGS,
            )
            print("  → Caricamento e indicizzazione su Neo4j completati con successo.")
        except Exception as e:
            print(f"  ⚠ Errore durante la fase di caricamento su Neo4j: {e}")

    return chunks