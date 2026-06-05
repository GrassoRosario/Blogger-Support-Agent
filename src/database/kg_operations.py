import uuid
from datetime import datetime
from neo4j import GraphDatabase

# --- Connessione ---
URI = "bolt://localhost:7687"
driver = GraphDatabase.driver(URI, auth=None)


# ==============================================================
# WRITE — Inserimento post approvato
# ==============================================================

def inserisci_post(titolo: str, testo: str, regione: str, topic: list[str], fonti: list[dict]):
    """
    Inserisce un post approvato nel KG con tutte le sue relazioni.

    Args:
        titolo:  Titolo del post
        testo:   Testo completo del post
        regione: Nome della regione (es. "Sicilia")
        topic:   Lista di nomi topic (es. ["Valle dei Templi", "Agrigento"])
        fonti:   Lista di dict con chiavi: url, quality_score, trust_status

    Example:
        inserisci_post(
            titolo="I Sassi di Matera",
            testo="I Sassi di Matera sono...",
            regione="Basilicata",
            topic=["Sassi di Matera"],
            fonti=[{"url": "https://...", "quality_score": 5, "trust_status": "use"}]
        )
    """
    post_id = str(uuid.uuid4())
    data = datetime.now().isoformat()

    with driver.session() as session:
        session.execute_write(
            _inserisci_post_tx,
            post_id, titolo, testo, data, regione, topic, fonti
        )
    print(f"Post inserito: {post_id}")
    return post_id


def _inserisci_post_tx(tx, post_id, titolo, testo, data,
                       regione, topic, fonti):
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
            ON CREATE SET f.id = $id, f.quality_score = $score,
                          f.trust_status = $trust_status
            WITH f
            MATCH (p:Post {id: $post_id})
            MERGE (p)-[:CITA]->(f)
        """, url=f["url"], id=str(uuid.uuid4()),
             score=f["quality_score"], trust_status=f["trust_status"],
             post_id=post_id)


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
# READ — Query del Researcher
# ==============================================================
def fonti_note() -> dict:
    """
    Restituisce tutte le fonti del KG divise per trust_status.

    Returns:
        Dict con due chiavi:
          - "use":   dict {url: quality_score} per le fonti affidabili, ordinate per score desc
          - "avoid": lista di url per le fonti da non usare
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (f:Fonte)
            RETURN f.url AS url, f.quality_score AS quality_score,
                   f.trust_status AS trust_status
            ORDER BY f.quality_score DESC
        """)

        use = {}
        avoid = []
        for record in result:
            if record["trust_status"] == "use":
                use[record["url"]] = record["quality_score"]
            else:
                avoid.append(record["url"])

    return {"use": use, "avoid": avoid}


# ==============================================================
# READ — Ottieni score per una lista di fonti (per Drafter/HITL)
# ==============================================================

def get_quality_score_fonti(urls: list[str]) -> dict[str, int]:
    """
    Dato un elenco di URL, restituisce {url: quality_score} per ciascuno.
    Le fonti non presenti nel KG avranno quality_score 1 come valore di default.
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (f:Fonte)
            WHERE f.url IN $urls
            RETURN f.url AS url, f.quality_score AS quality_score
        """, urls=urls)
        known = {record["url"]: record["quality_score"] for record in result}

    return {url: known.get(url, 1) for url in urls}

# ==============================================================
# Chiusura connessione
# ==============================================================

def chiudi():
    driver.close()