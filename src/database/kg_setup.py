from neo4j import GraphDatabase

# --- Connessione ---
URI = "bolt://localhost:7687"
driver = GraphDatabase.driver(URI, auth=None)


# --- Dati seed ---

REGIONI = [
    "Valle d'Aosta", "Piemonte", "Liguria", "Lombardia",
    "Trentino-Alto Adige", "Veneto", "Friuli-Venezia Giulia",
    "Emilia-Romagna", "Toscana", "Umbria", "Marche", "Lazio",
    "Abruzzo", "Molise", "Campania", "Puglia",
    "Basilicata", "Calabria", "Sicilia", "Sardegna"
]

DOMINI_FIDATI = [
    "whc.unesco.org",
    "unesco.cultura.gov.it",
    "cultura.gov.it",
    "italia.it",
    "beniculturali.it",
    "treccani.it",
    "sitiunesco.it",
    "regione.sicilia.it"
]

DOMINI_ESCLUSI = [
    "youtube.com", "getyourguide.com", "tripadvisor.com",
    "casevacanzasicilia.it", "booking.com", "expedia.it", "komoot.com"
]


# --- Funzioni di setup ---

def crea_constraints(tx):
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Regione) REQUIRE r.nome IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Fonte) REQUIRE f.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (pp:PostPianificato) REQUIRE pp.id IS UNIQUE")


def carica_regioni(tx):
    for nome in REGIONI:
        tx.run(
            "MERGE (r:Regione {nome: $nome})",
            nome=nome
        )


def carica_fonti(tx):
    for dominio in DOMINI_FIDATI:
        tx.run("""
            MERGE (f:Fonte {id: $id})
            SET f.url = $url,
                f.trust_status = 'use',
                f.quality_score = 5
        """, id=dominio, url="https://" + dominio)

    for dominio in DOMINI_ESCLUSI:
        tx.run("""
            MERGE (f:Fonte {id: $id})
            SET f.url = $url,
                f.trust_status = 'avoid',
                f.quality_score = 0
        """, id=dominio, url="https://" + dominio)


# --- Esecuzione ---

def setup():
    with driver.session() as session:
        print("Creazione constraint e indici...")
        session.execute_write(crea_constraints)

        print("Caricamento regioni...")
        session.execute_write(carica_regioni)

        print("Caricamento fonti...")
        session.execute_write(carica_fonti)

        # Verifica
        result = session.run("MATCH (r:Regione) RETURN count(r) AS totale")
        print(f"Regioni caricate: {result.single()['totale']}")

        result = session.run("""
            MATCH (f:Fonte)
            RETURN f.trust_status AS status, count(f) AS totale
            ORDER BY status
        """)
        for row in result:
            print(f"Fonti '{row['status']}': {row['totale']}")

    driver.close()
    print("Setup completato.")


if __name__ == "__main__":
    setup()