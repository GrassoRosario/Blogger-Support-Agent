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


# --- Funzioni di setup ---

def crea_constraints(tx):
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Regione) REQUIRE r.nome IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Fonte) REQUIRE f.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (pp:PostPianificato) REQUIRE pp.id IS UNIQUE")


def carica_regioni(tx):
    for nome in REGIONI:
        tx.run(
            "MERGE (r:Regione {nome: $nome})",
            nome=nome
        )


# --- Esecuzione ---

def setup():
    with driver.session() as session:
        print("Creazione constraint e indici...")
        session.execute_write(crea_constraints)

        print("Caricamento regioni...")
        session.execute_write(carica_regioni)

        # Verifica
        result = session.run("MATCH (r:Regione) RETURN count(r) AS totale")
        print(f"Regioni caricate: {result.single()['totale']}")

    driver.close()
    print("Setup completato.")


if __name__ == "__main__":
    setup()