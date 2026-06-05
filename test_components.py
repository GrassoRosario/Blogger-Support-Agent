"""
Test dei componenti del sistema BLOGGER_AGENT.

Esecuzione singolo test:
    python test_components.py neo4j
    python test_components.py indexer
    python test_components.py retriever
    python test_components.py rag
    python test_components.py search
    python test_components.py planner
    python test_components.py researcher
    python test_components.py drafter
    python test_components.py kg_updater

Esecuzione tutti i test in sequenza:
    python test_components.py all
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "tools")))

from dotenv import load_dotenv
load_dotenv()


# ==============================================================
# 1. Neo4j
# ==============================================================

def test_neo4j():
    print("\n=== TEST NEO4J ===")
    from src.database.kg_operations import driver

    with driver.session() as session:
        result = session.run("MATCH (r:Regione) RETURN count(r) AS totale")
        totale = result.single()["totale"]
        print(f"Regioni nel KG: {totale}")
        assert totale == 20, f"Attese 20 regioni, trovate {totale}"

        result = session.run("MATCH (n) RETURN labels(n) AS label, count(n) AS totale")
        for record in result:
            print(f"  {record['label']}: {record['totale']} nodi")

    print("✓ Neo4j OK")


# ==============================================================
# 2. Indexer
# ==============================================================

def test_indexer():
    print("\n=== TEST INDEXER ===")
    from src.tools.indexing.indexer import indicizza_cartella
    indicizza_cartella("documenti_RAG")
    print("✓ Indexer OK")

# ==============================================================
# 3. Retrieve Chunks
# ==============================================================

def test_retrieve_chunks():
    print("\n=== TEST RETRIEVE CHUNKS ===")
    from src.tools.rag.retriever import retrieve_chunks, get_monumenti_disponibili

    mapping = get_monumenti_disponibili()

    # Verifica che la Reggia di Caserta sia nel mapping e recupera il source
    source = mapping.get("18th-Century Royal Palace at Caserta with the")
    assert source is not None, \
        "Reggia di Caserta non trovata nel mapping — verifica i dati indicizzati"

    # Caso positivo: source presente
    print("\n=== CASO POSITIVO ===")
    risultato = retrieve_chunks(query="storia", source=source)
    print(risultato + "\n")
    assert "Nessun documento" not in risultato, \
        "\nNessun chunk trovato — verifica che l'indexer sia stato eseguito"

    # Caso negativo: source inesistente
    print("\n=== CASO NEGATIVO:  ===")
    risultato_vuoto = retrieve_chunks(query="storia", source="monumento_inesistente.pdf")
    print(f"Risultato source inesistente: {risultato_vuoto}")
    assert "Nessun documento" in risultato_vuoto, \
        "Atteso messaggio di fallback per source inesistente"

    print("✓ Retrieve Chunks OK")


# ==============================================================
# 4. Dispatcher
# ==============================================================

def test_dispatcher():
    print("\n=== TEST DISPATCHER ===")
    from src.tools.rag.dispatcher import dispatch
    from src.tools.rag.retriever import get_monumenti_disponibili

    mapping = get_monumenti_disponibili()
    print(f"Monumenti disponibili: {list(mapping.keys())}")

    # Caso positivo: monumento presente
    risultato = dispatch("storia della Reggia di Caserta", mapping)
    print(f"Risultato dispatch: {risultato}")
    assert risultato["trovato"] is True, "Il dispatcher non ha trovato il monumento"
    assert risultato["source"] is not None, "source è None"
    assert risultato["query_pulita"] is not None, "query_pulita è None"
    assert "caserta" not in risultato["query_pulita"].lower(), \
        "Il nome del monumento non è stato rimosso dalla query"
    print(f"  source: {risultato['source']}")
    print(f"  query_pulita: {risultato['query_pulita']}")

    # Caso negativo: monumento non presente
    print("\n=== TEST DISPATCHER: CASO NEGATIVO ===")
    risultato_assente = dispatch("storia del Taj Mahal", mapping)
    print(f"Risultato dispatch (assente): {risultato_assente}")
    assert risultato_assente["trovato"] is False, \
        "Il dispatcher ha trovato un monumento che non esiste"

    print("✓ Dispatcher OK")


# ==============================================================
# 5. RAG
# ==============================================================

def test_rag():
    print("\n=== TEST RAG ===")
    from src.tools.rag.rag_tool import rag_tool

    # Caso positivo: monumento presente
    risultato = rag_tool.invoke({"domanda": "storia della Reggia di Caserta"})
    print(risultato + "\n")
    assert len(risultato) > 50, "Risposta troppo corta"
    assert "Nessun documento trovato" not in risultato, \
        "Il rag_tool non ha trovato il documento"

    # Caso negativo: monumento non presente
    print("\n=== TEST RAG: CASO NEGATIVO ===")
    risultato_assente = rag_tool.invoke({"domanda": "storia del Taj Mahal"})
    print(f"Risultato assente: {risultato_assente}")
    assert risultato_assente == "Nessun documento trovato per il monumento richiesto.", \
        "Il rag_tool non ha gestito correttamente il caso di monumento assente"

    print("✓ RAG OK")

# ==============================================================
# 5. Search
# ==============================================================

def test_search():
    print("\n=== TEST SEARCH ===")
    from src.tools.search_tool import search_tool

    risultato = search_tool.invoke({"query": "cosa vedere in Sicilia monumenti storici"})
    print(risultato)
    assert "Nessun risultato" not in risultato, "Nessun risultato trovato — verifica TAVILY_API_KEY"
    print("✓ Search OK")


# ==============================================================
# 6. Planner
# ==============================================================

def test_planner():
    print("\n=== TEST PLANNER ===")
    from src.nodes.planner import planner_node

    state = {
        "n": 5, "k": 3,
        "piano_corrente": None, "ricerca": None,
        "bozza": None, "hitl_action": None, "hitl_feedback": None, "post_id": None
    }

    risultato = planner_node(state)
    piano = risultato.get("piano_corrente")
    print(f"Piano corrente: {piano}")
    assert piano is not None, "piano_corrente è None"
    assert "regione" in piano and "topic" in piano, "Piano malformato — mancano 'regione' o 'topic'"
    assert isinstance(piano["regione"], str) and len(piano["regione"]) > 0, "Regione vuota"
    assert isinstance(piano["topic"], str) and len(piano["topic"]) > 0, "Topic vuoto"
    print(f"  Regione: {piano['regione']}")
    print(f"  Topic:   {piano['topic']}")
    print("✓ Planner OK")


# ==============================================================
# 7. Researcher
# ==============================================================

def test_researcher():
    print("\n=== TEST RESEARCHER ===")
    from src.nodes.researcher import researcher_node

    state = {
        "n": 5, "k": 3,
        "piano_corrente": {"regione": "Campania", "topic": "Reggia di Caserta"},
        "ricerca": None, "bozza": None,
        "hitl_action": None, "hitl_feedback": None, "post_id": None
    }

    risultato = researcher_node(state)
    ricerca = risultato.get("ricerca") 
    print(f"Sezioni trovate: {list(ricerca.keys())}")

    sezioni_attese = ["descrizione", "storia", "cosa_vedere", "informazioni_pratiche", "claim", "fonti"]
    for sezione in sezioni_attese:
        assert sezione in ricerca, f"Sezione mancante: {sezione}"
        assert ricerca[sezione], f"Sezione vuota: {sezione}"

    print("✓ Researcher OK")


# ==============================================================
# 8. Drafter
# ==============================================================

def test_drafter():
    print("\n=== TEST DRAFTER ===")
    from src.nodes.drafter import drafter_node

    state = {
        "n": 5, "k": 3,
        "piano_corrente": {"regione": "Campania", "topic": "Reggia di Caserta"},
        "ricerca": {
            "descrizione": "La Reggia di Caserta è un palazzo reale del XVIII secolo.",
            "storia": "Costruita da Luigi Vanvitelli per Carlo di Borbone nel 1752.",
            "cosa_vedere": "Il parco, le fontane, gli appartamenti reali.",
            "informazioni_pratiche": "Aperta tutti i giorni tranne il martedì. Biglietto 16 euro.",
            "claim": ["Costruita nel 1752", "Patrimonio UNESCO dal 1997"],
            "fonti": ["https://reggiadicaserta.cultura.gov.it"]
        },
        "bozza": None, "hitl_action": None, "hitl_feedback": None, "post_id": None
    }

    risultato = drafter_node(state)
    bozza = risultato.get("bozza")
    print(bozza[:500])
    assert bozza and len(bozza) > 200, "Bozza troppo corta o assente"
    print("✓ Drafter OK")


# ==============================================================
# 9. KG Updater
# ==============================================================

def test_kg_updater():
    print("\n=== TEST KG UPDATER ===")
    from src.nodes.kg_updater import kg_updater_node

    state = {
        "n": 5, "k": 3,
        "piano_corrente": {"regione": "Campania", "topic": "Reggia di Caserta"},
        "ricerca": {
            "claim": ["Costruita nel 1752", "Patrimonio UNESCO dal 1997"],
            "fonti": ["https://reggiadicaserta.cultura.gov.it"]
        },
        "bozza": "# La Reggia di Caserta\n\nLa Reggia di Caserta è uno dei palazzi reali più grandi del mondo...",
        "hitl_action": None, "hitl_feedback": None, "post_id": None
    }

    risultato = kg_updater_node(state)
    post_id = risultato.get("post_id")
    print(f"Post ID: {post_id}")
    assert post_id is not None, "post_id è None"
    print("✓ KG Updater OK")


# ==============================================================
# Entry point
# ==============================================================

TESTS = {
    "neo4j":            test_neo4j,
    "indexer":          test_indexer,
    "dispatcher":       test_dispatcher,       
    "retrieve_chunks":  test_retrieve_chunks,  
    "rag":              test_rag,              
    "search":           test_search,
    "planner":          test_planner,
    "researcher":       test_researcher,
    "drafter":          test_drafter,
    "kg_updater":       test_kg_updater,
}

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python test_components.py <test> oppure 'all'")
        print(f"Test disponibili: {', '.join(TESTS.keys())}")
        sys.exit(1)

    comando = sys.argv[1]

    if comando == "all":
        errori = []
        for nome, test in TESTS.items():
            try:
                test()
            except Exception as e:
                print(f"✗ {nome} FALLITO: {e}")
                errori.append(nome)
        print(f"\n{'='*40}")
        if errori:
            print(f"Test falliti: {', '.join(errori)}")
        else:
            print("Tutti i test superati ✓")
    elif comando in TESTS:
        try:
            TESTS[comando]()
        except Exception as e:
            print(f"✗ Test fallito: {e}")
            sys.exit(1)
    else:
        print(f"Test sconosciuto: {comando}")
        print(f"Test disponibili: {', '.join(TESTS.keys())}")
        sys.exit(1)