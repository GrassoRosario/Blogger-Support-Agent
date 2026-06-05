import uuid
from datetime import datetime
from neo4j import GraphDatabase

# --- Connessione ---
URI = "bolt://localhost:7687"
driver = GraphDatabase.driver(URI, auth=None)


# ==============================================================
# WRITE — Inserimento post approvato
# ==============================================================

def inserisci_post(titolo: str, testo: str, regione: str,
                   topic: list[str], fonti: list[dict], claim: list[str]):
    """
    Inserisce un post approvato nel KG con tutte le sue relazioni.

    Args:
        titolo:  Titolo del post
        testo:   Testo completo del post
        regione: Nome della regione (es. "Sicilia")
        topic:   Lista di nomi topic (es. ["Valle dei Templi", "Agrigento"])
        fonti:   Lista di dict con chiavi: url, titolo, quality_score
        claim:   Lista di stringhe (affermazioni estratte dal post)

    Example:
        inserisci_post(
            titolo="I Sassi di Matera",
            testo="I Sassi di Matera sono...",
            regione="Basilicata",
            topic=["Sassi di Matera"],
            fonti=[{"url": "https://...", "titolo": "UNESCO", "quality_score": 0.9}],
            claim=["Patrimonio UNESCO dal 1993", "Abitati da 9.000 anni"]
        )
    """
    
    post_id = str(uuid.uuid4())
    data = datetime.now().isoformat()

    with driver.session() as session:
        session.execute_write(
            _inserisci_post_tx,
            post_id, titolo, testo, data, regione, topic, fonti, claim
        )
    print(f"Post inserito: {post_id}")
    return post_id


def _inserisci_post_tx(tx, post_id, titolo, testo, data,
                       regione, topic, fonti, claim):
    # Crea il nodo Post e collega alla Regione
    tx.run("""
        CREATE (p:Post {id: $id, titolo: $titolo, testo: $testo, data_creazione: $data})
        WITH p
        MATCH (r:Regione {nome: $regione})
        MERGE (p)-[:AMBIENTATO_IN]->(r)
    """, id=post_id, titolo=titolo, testo=testo, data=data, regione=regione)

    # Crea i Topic, li collega al Post e alla Regione
    for nome_topic in topic:
        tx.run("""
            MERGE (t:Topic {nome: $nome})
            ON CREATE SET t.id = $topic_id
            WITH t
            MATCH (p:Post {id: $post_id})
            MERGE (p)-[:TRATTA]->(t)
            WITH t
            MATCH (r:Regione {nome: $regione})
            MERGE (t)-[:APPARTIENE_A]->(r)
        """, nome=nome_topic, topic_id=str(uuid.uuid4()),
             post_id=post_id, regione=regione)

    # Crea le Fonti e le collega al Post
    for f in fonti:
        tx.run("""
            MERGE (f:Fonte {url: $url})
            ON CREATE SET f.id = $id, f.titolo = $titolo, f.quality_score = $score
            WITH f
            MATCH (p:Post {id: $post_id})
            MERGE (p)-[:CITA]->(f)
        """, url=f["url"], id=str(uuid.uuid4()), titolo=f["titolo"],
             score=f["quality_score"], post_id=post_id)

    # Crea i Claim e li collega al Post
    for testo_claim in claim:
        tx.run("""
            CREATE (c:Claim {id: $id, testo: $testo})
            WITH c
            MATCH (p:Post {id: $post_id})
            MERGE (p)-[:CONTIENE]->(c)
        """, id=str(uuid.uuid4()), testo=testo_claim, post_id=post_id)


# ==============================================================
# WRITE/READ — Gestione PostPianificati
# ==============================================================

def inserisci_post_pianificati(piani: list[dict]):
    """
    Salva una lista di piani nel KG come nodi PostPianificato.
    Chiamata dal Planner quando genera K nuovi piani.

    Args:
        piani: Lista di dict con chiavi: regione, topic

    Example:
        inserisci_post_pianificati([
            {"regione": "Sicilia", "topic": "Valle dei Templi"},
            {"regione": "Toscana", "topic": "Cinque Terre"},
        ])
    """
    with driver.session() as session:
        for piano in piani:
            session.execute_write(_inserisci_post_pianificato_tx, piano)
    print(f"{len(piani)} PostPianificati inseriti.")


def _inserisci_post_pianificato_tx(tx, piano: dict):
    tx.run("""
        CREATE (pp:PostPianificato {id: $id, data_creazione: $data})
        WITH pp
        MATCH (r:Regione {nome: $regione})
        MERGE (pp)-[:RIGUARDA]->(r)
        WITH pp
        MERGE (t:Topic {nome: $topic})
        ON CREATE SET t.id = $topic_id
        MERGE (pp)-[:PROPONE]->(t)
    """, id=str(uuid.uuid4()), data=datetime.now().isoformat(),
         regione=piano["regione"], topic=piano["topic"],
         topic_id=str(uuid.uuid4()))


def prossimo_post_pianificato() -> dict | None:
    """
    Legge il PostPianificato più vecchio dal KG, lo elimina e lo restituisce.
    Chiamata dal Planner all'inizio di ogni esecuzione.

    Returns:
        Dict con regione e topic, oppure None se non ci sono piani.

    Example:
        piano = prossimo_post_pianificato()
        # {"regione": "Sicilia", "topic": "Valle dei Templi"}
    """
    with driver.session() as session:
        result = session.execute_write(_prossimo_post_pianificato_tx)
    return result


def _prossimo_post_pianificato_tx(tx) -> dict | None:
    # Legge il piano più vecchio
    result = tx.run("""
        MATCH (pp:PostPianificato)-[:RIGUARDA]->(r:Regione)
        MATCH (pp)-[:PROPONE]->(t:Topic)
        RETURN pp.id AS id, r.nome AS regione, t.nome AS topic
        ORDER BY pp.data_creazione ASC
        LIMIT 1
    """)
    record = result.single()

    if not record:
        return None

    # Elimina il piano dal KG
    tx.run("""
        MATCH (pp:PostPianificato {id: $id})
        DETACH DELETE pp
    """, id=record["id"])

    return {"regione": record["regione"], "topic": record["topic"]}


# ==============================================================
# READ — Query del Planner
# ==============================================================

def regioni_recenti(n: int) -> list[str]:
    """
    Restituisce le regioni degli ultimi N post.
    Usata dal Planner per evitare ripetizioni.

    Args:
        n: Finestra anti-ripetizione (es. 5)
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Post)-[:AMBIENTATO_IN]->(r:Regione)
            WITH r, p ORDER BY p.data_creazione DESC
            WITH r LIMIT $n
            RETURN DISTINCT r.nome AS regione
        """, n=n)
        return [record["regione"] for record in result]


def regioni_disponibili(n: int) -> list[str]:
    """
    Restituisce le regioni NON presenti negli ultimi N post.
    Fallback: restituisce tutte le 20 regioni se non ce ne sono di disponibili.

    Args:
        n: Finestra anti-ripetizione (es. 5)
    """
    recenti = set(regioni_recenti(n))

    with driver.session() as session:
        result = session.run("MATCH (r:Regione) RETURN r.nome AS regione")
        tutte = [record["regione"] for record in result]

    disponibili = [r for r in tutte if r not in recenti]

    if not disponibili:
        print("Fallback: tutte le regioni sono recenti, selezione casuale dalla lista completa.")
        return tutte

    return disponibili


def topic_per_regione(nome_regione: str) -> list[str]:
    """
    Restituisce i topic già trattati per una regione.
    Usata dal Planner per evitare ripetizioni di topic specifici.

    Args:
        nome_regione: Nome della regione (es. "Toscana")
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (t:Topic)-[:APPARTIENE_A]->(r:Regione {nome: $nome})
            RETURN t.nome AS topic
        """, nome=nome_regione)
        return [record["topic"] for record in result]


# ==============================================================
# READ — Query del Drafter
# ==============================================================

def claim_esistenti_per_topic(nome_topic: str) -> list[str]:
    """
    Restituisce i claim già presenti nel KG per un topic.
    Usata dal Drafter per garantire consistenza con i post precedenti.

    Args:
        nome_topic: Nome del topic (es. "Colosseo")
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Post)-[:TRATTA]->(t:Topic {nome: $nome})
            MATCH (p)-[:CONTIENE]->(c:Claim)
            RETURN c.testo AS claim
        """, nome=nome_topic)
        return [record["claim"] for record in result]


def fonti_per_regione(nome_regione: str) -> list[dict]:
    """
    Restituisce le fonti già usate per post nella regione,
    ordinate per quality_score decrescente.
    Usata dal Drafter per riutilizzare fonti di qualità già note.

    Args:
        nome_regione: Nome della regione (es. "Campania")
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Post)-[:AMBIENTATO_IN]->(r:Regione {nome: $nome})
            MATCH (p)-[:CITA]->(f:Fonte)
            RETURN DISTINCT f.url AS url, f.titolo AS titolo,
                            f.quality_score AS quality_score
            ORDER BY f.quality_score DESC
        """, nome=nome_regione)
        return [dict(record) for record in result]


# ==============================================================
# Chiusura connessione
# ==============================================================

def chiudi():
    driver.close()