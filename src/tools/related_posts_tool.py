"""
Tool per i post correlati nella stessa regione.

Flusso:
    1. Interroga il KG per trovare post pubblicati nella stessa regione
    2. Geocodifica ogni luogo con geopy (Nominatim)
    3. Calcola la distanza in km tra il post corrente e i post correlati
    4. Genera una sezione markdown "Esplora anche..." da aggiungere al post

Dipendenze:
    pip install geopy
"""

import time
from langchain_core.tools import tool
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from src.database.kg_operations import driver


# ==============================================================
# Configurazione
# ==============================================================

geolocator = Nominatim(user_agent="blogger_support_agent")
MAX_CORRELATI = 3       # max post correlati da mostrare
GEOCODE_DELAY = 1.0     # secondi tra chiamate Nominatim (rate limit)


# ==============================================================
# Funzioni interne
# ==============================================================

def _get_post_correlati(regione: str, topic_corrente: str) -> list[dict]:
    """
    Recupera dal KG i post pubblicati nella stessa regione,
    escludendo il post corrente.

    Returns:
        Lista di dict: [{"titolo": str, "topic": str}, ...]
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Post)-[:AMBIENTATO_IN]->(r:Regione {nome: $regione})
            MATCH (p)-[:TRATTA]->(t:Topic)
            WHERE t.nome <> $topic_corrente
            RETURN p.titolo AS titolo, t.nome AS topic
            ORDER BY p.data_creazione DESC
            LIMIT $limit
        """, regione=regione, topic_corrente=topic_corrente, limit=MAX_CORRELATI)
        return [dict(r) for r in result]


def _geocodifica(luogo: str, regione: str) -> tuple[float, float] | None:
    """
    Geocodifica un luogo restituendo (lat, lon).
    Aggiunge la regione per disambiguare.

    Returns:
        Tupla (lat, lon) oppure None se non trovato
    """
    try:
        time.sleep(GEOCODE_DELAY)
        location = geolocator.geocode(f"{luogo}, {regione}, Italia")
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"[GEO] Errore geocodifica '{luogo}': {e}")
    return None


def _calcola_distanza(coord1: tuple, coord2: tuple) -> float | None:
    """
    Calcola la distanza in km tra due coordinate (lat, lon).

    Returns:
        Distanza in km arrotondata, oppure None
    """
    try:
        return round(geodesic(coord1, coord2).km, 1)
    except Exception:
        return None


def _genera_sezione_markdown(
    topic_corrente: str,
    correlati: list[dict],
) -> str:
    """
    Genera la sezione markdown "Esplora anche..." da appendere al post.

    Args:
        topic_corrente: Nome del luogo del post corrente
        correlati: Lista di dict con topic, titolo, distanza_km

    Returns:
        Stringa markdown della sezione correlati
    """
    if not correlati:
        return ""

    sezione = "\n\n---\n\n"
    sezione += "## 📍 Esplora anche nella stessa regione\n\n"
    sezione += (
        f"Se stai pianificando una visita a **{topic_corrente}**, "
        f"potresti combinare il tuo viaggio con queste altre mete:\n\n"
    )

    for c in correlati:
        distanza = c.get("distanza_km")
        dist_str = f" — a circa **{distanza} km**" if distanza else ""
        sezione += f"- **{c['topic']}**{dist_str}: {c['titolo']}\n"

    sezione += (
        "\n> 💡 *Consiglio:* Pianifica un itinerario combinando più siti "
        "per ottimizzare i tuoi spostamenti e scoprire al meglio la regione.\n"
    )
    return sezione


# ==============================================================
# Related Posts Tool
# ==============================================================

@tool
def related_posts_tool(regione: str, topic_corrente: str) -> str:
    """
    Trova post correlati nella stessa regione e genera una sezione
    markdown con distanze da aggiungere in fondo al post corrente.

    Usare dopo che il Drafter ha completato la bozza, prima di
    restituire il testo finale.

    Args:
        regione:         Nome della regione del post corrente (es. "Sicilia")
        topic_corrente:  Nome del luogo trattato nel post (es. "Valle dei Templi")

    Returns:
        Sezione markdown "Esplora anche..." oppure stringa vuota
        se non ci sono post correlati nella regione.
    """
    # 1. Recupera post correlati dal KG
    correlati = _get_post_correlati(regione, topic_corrente)

    if not correlati:
        print(f"[RELATED] Nessun post correlato trovato per regione: {regione}")
        return ""

    print(f"[RELATED] {len(correlati)} post correlati trovati in {regione}")

    # 2. Geocodifica il luogo corrente
    coord_corrente = _geocodifica(topic_corrente, regione)
    if coord_corrente:
        print(f"[RELATED] Coordinate '{topic_corrente}': {coord_corrente}")
    else:
        print(f"[RELATED] Geocodifica fallita per '{topic_corrente}', distanze non disponibili")

    # 3. Per ogni correlato: geocodifica + calcola distanza
    correlati_arricchiti = []
    for post in correlati:
        coord_post = _geocodifica(post["topic"], regione)
        distanza = None

        if coord_corrente and coord_post:
            distanza = _calcola_distanza(coord_corrente, coord_post)
            print(f"[RELATED] Distanza '{topic_corrente}' → '{post['topic']}': {distanza} km")

        correlati_arricchiti.append({
            "titolo":      post["titolo"],
            "topic":       post["topic"],
            "distanza_km": distanza,
        })

    # Ordina per distanza (i più vicini prima), i None in fondo
    correlati_arricchiti.sort(
        key=lambda x: x["distanza_km"] if x["distanza_km"] is not None else float("inf")
    )

    # 4. Genera sezione markdown
    return _genera_sezione_markdown(topic_corrente, correlati_arricchiti)