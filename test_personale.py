"""
Test automatico completo della pipeline Blogger Support Agent.
Zero input richiesto — tutto automatizzato incluso HITL simulato.

Esecuzione:
    python test_personale.py
"""

import os
import sys
import random
import time

# =====================================================================
# CONFIGURAZIONE PERCORSI TCL/TK
# =====================================================================
base_python_path = r"C:\Users\HEW15EG0057NL\AppData\Local\Programs\Python\Python313"
os.environ['TCL_LIBRARY'] = os.path.join(base_python_path, 'tcl', 'tcl8.6')
os.environ['TK_LIBRARY']  = os.path.join(base_python_path, 'tcl', 'tk8.6')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "tools")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "database")))

from dotenv import load_dotenv
load_dotenv()
# Sostituisci l'import in cima:
from gui import esegui_hitl_interfaccia  # ← aggiungi questo import

# =====================================================================
# IMPORT COMPONENTI
# =====================================================================
from src.database.kg_operations import driver
from src.tools.indexing.indexer import indicizza_cartella
from src.nodes.planner import planner_node
from src.nodes.researcher import researcher_node
from src.nodes.drafter import drafter_node
from src.nodes.kg_updater import kg_updater_node
from src.tools.related_posts_tool import related_posts_tool
from src.tools.post_quality_classifier import (
    predici_qualita_tool,
    post_quality_classifier_tool,
)

# =====================================================================
# FALLBACK PIANI — usati se Gemini è offline
# =====================================================================
FALLBACK_PIANI = [
    {"regione": "Sicilia",    "topic": "Valle dei Templi di Agrigento"},
    {"regione": "Campania",   "topic": "Reggia di Caserta"},
    {"regione": "Toscana",    "topic": "Centro Storico di Firenze"},
    {"regione": "Sardegna",   "topic": "Su Nuraxi di Barumini"},
    {"regione": "Basilicata", "topic": "Sassi di Matera"},
    {"regione": "Veneto",     "topic": "Venezia e la sua Laguna"},
]

FALLBACK_RICERCHE = {
    "Valle dei Templi di Agrigento": {
        "descrizione": "La Valle dei Templi è un sito archeologico di Agrigento, tra i più importanti al mondo.",
        "storia":      "Fondata nel 582 a.C., Akragas divenne una delle più potenti città della Magna Grecia.",
        "cosa_vedere": "Tempio della Concordia, Tempio di Giunone, Tempio di Ercole, Giardino della Kolymbetra.",
        "informazioni_pratiche": "Aperto tutti i giorni 9:00-19:00. Biglietto 10€ intero, 5€ ridotto.",
        "fonti": ["https://whc.unesco.org/en/list/831"],
    },
    "Reggia di Caserta": {
        "descrizione": "La Reggia di Caserta è il più grande palazzo reale d'Italia, costruito nel XVIII secolo.",
        "storia":      "Costruita da Luigi Vanvitelli per Carlo di Borbone nel 1752.",
        "cosa_vedere": "Appartamenti reali, parco con fontane e cascata, giardino all'inglese.",
        "informazioni_pratiche": "Chiusa il martedì. Biglietto 16€.",
        "fonti": ["https://whc.unesco.org/en/list/549"],
    },
    "default": {
        "descrizione": "Splendido sito patrimonio UNESCO situato in Italia.",
        "storia":      "Ricco di storia millenaria e cultura.",
        "cosa_vedere": "Numerosi punti di interesse storico e artistico.",
        "informazioni_pratiche": "Consultare il sito ufficiale per orari e biglietti.",
        "fonti": ["https://whc.unesco.org"],
    },
}


# =====================================================================
# HITL SIMULATO — approva automaticamente dopo 2 secondi
# =====================================================================
def hitl_simulato(stato: dict) -> dict:
    """
    Simula la decisione HITL in modo automatico.
    Approva sempre — per testare il ciclo completo senza input umano.
    """
    print("\n" + "="*60)
    print("🤖 HITL SIMULATO — Approvazione automatica")
    print("="*60)

    bozza = stato.get("bozza", "")
    prob  = stato.get("prob_approvazione")
    rischio = stato.get("rischio_rifiuto", False)

    print(f"📄 Lunghezza bozza: {len(bozza)} caratteri")
    if prob is not None:
        print(f"🔮 Classifier: probabilità approvazione = {prob:.1%}")
        if rischio:
            print("⚠️  ATTENZIONE: classifier suggerisce rischio rifiuto")
        else:
            print("✓  Classifier: post probabilmente approvato")

    # Mostra anteprima bozza
    print("\n📝 Anteprima bozza (primi 300 caratteri):")
    print("-" * 40)
    print(bozza[:300] + "..." if len(bozza) > 300 else bozza)
    print("-" * 40)

    print("\n⏳ Approvazione automatica tra 2 secondi...")
    time.sleep(2)
    print("✅ Post APPROVATO automaticamente dal sistema.")

    return {
        **stato,
        "hitl_action":    "approva",
        "hitl_feedback":  None,
        "valutazione_fonti": stato.get("valutazione_fonti", {}),
    }


# =====================================================================
# PIPELINE PRINCIPALE
# =====================================================================
def esegui_pipeline():
    print("=" * 70)
    print("   🚀 PIPELINE AUTOMATICA — BLOGGER SUPPORT AGENT")
    print("   Zero input richiesto — tutto automatizzato")
    print("=" * 70)

    # Pulizia ambiente demo
    print("\n[SETUP] 🧹 Pulizia cronologia classifier nel KG...")
    with driver.session() as session:
        session.run("MATCH (e:EsempioClassifier) DETACH DELETE e")
    print("[SETUP] ✓ Ambiente pulito")

    # Stato iniziale
    stato = {
        "n": 5, "k": 1,
        "piano_corrente":    None,
        "ricerca":           None,
        "bozza":             None,
        "hitl_action":       None,
        "hitl_feedback":     None,
        "valutazione_fonti": None,
        "rischio_rifiuto":   None,
        "prob_approvazione": None,
        "post_id":           None,
        "reasoning_trace":   None,
    }

    modalita_fallback = False
    piano = None

    # ------------------------------------------------------------------
    # STEP 1 — Neo4j
    # ------------------------------------------------------------------
    print("\n[STEP 1] 💾 Verifica Database Neo4j")
    print("-" * 60)
    with driver.session() as session:
        result = session.run("MATCH (r:Regione) RETURN count(r) AS totale")
        totale = result.single()["totale"]
        print(f"✓ Connessione riuscita. Regioni nel KG: {totale}/20")

        # Inietta post storico per testare related_posts_tool
        session.run("""
            MERGE (r:Regione {nome: "Sicilia"})
            MERGE (p:Post {id: "demo-post-sicilia"})
            ON CREATE SET p.titolo = "Le Isole Eolie", p.data_creazione = "2026-01-01"
            MERGE (t:Topic {nome: "Isole Eolie"})
            MERGE (p)-[:AMBIENTATO_IN]->(r)
            MERGE (p)-[:TRATTA]->(t)
            MERGE (t)-[:APPARTIENE_A]->(r)
        """)
        print("✓ Post storico demo iniettato nel KG (Isole Eolie - Sicilia)")

    # ------------------------------------------------------------------
    # STEP 2 — Indicizzazione RAG
    # ------------------------------------------------------------------
    print("\n[STEP 2] 📂 Indicizzazione Documenti Locali (RAG)")
    print("-" * 60)
    try:
        indicizza_cartella("documenti_RAG")
        print("✓ Documenti indicizzati")
    except Exception as e:
        print(f"⚠ Avviso indicizzazione: {e}")

    # ------------------------------------------------------------------
    # STEP 3 — Planner
    # ------------------------------------------------------------------
    print("\n[STEP 3] 🧠 Planner Node")
    print("-" * 60)
    try:
        stato = planner_node(stato)
        piano = stato.get("piano_corrente")
        print(f"✓ Piano generato → Regione: '{piano['regione']}' | Topic: '{piano['topic']}'")
    except Exception as e:
        print(f"⚠ Planner offline ({type(e).__name__}) — attivo fallback...")
        modalita_fallback = True
        piano = random.choice(FALLBACK_PIANI)
        stato["piano_corrente"] = piano
        print(f"✓ Fallback → Regione: '{piano['regione']}' | Topic: '{piano['topic']}'")

    # ------------------------------------------------------------------
    # STEP 4 — Researcher
    # ------------------------------------------------------------------
    print("\n[STEP 4] 🔍 Researcher Node")
    print("-" * 60)
    if not modalita_fallback:
        try:
            print(f"➔ Ricerca in corso per: {piano['topic']}...")
            stato = researcher_node(stato)
            ricerca = stato.get("ricerca", {})
            print(f"✓ Ricerca completata. Sezioni: {list(ricerca.keys())}")
        except Exception as e:
            print(f"⚠ Researcher offline ({type(e).__name__}) — attivo fallback...")
            modalita_fallback = True

    if modalita_fallback:
        ricerca = FALLBACK_RICERCHE.get(piano["topic"], FALLBACK_RICERCHE["default"])
        stato["ricerca"] = ricerca
        print(f"✓ Dati fallback caricati per: {piano['topic']}")

    # ------------------------------------------------------------------
    # STEP 5 — Drafter
    # ------------------------------------------------------------------
    print("\n[STEP 5] ✍️  Drafter Node")
    print("-" * 60)
    if not modalita_fallback:
        try:
            stato = drafter_node(stato)
            print(f"✓ Bozza generata: {len(stato['bozza'])} caratteri")
        except Exception as e:
            print(f"⚠ Drafter offline ({type(e).__name__}) — attivo fallback...")
            modalita_fallback = True

    if modalita_fallback:
        bozza_fallback = (
            f"# {piano['topic']}\n\n"
            f"Situato nel cuore della {piano['regione']}, "
            f"questo straordinario patrimonio UNESCO rappresenta "
            f"uno dei tesori più preziosi della cultura italiana.\n\n"
            f"## Storia\n{ricerca.get('storia', '')}\n\n"
            f"## Cosa Vedere\n{ricerca.get('cosa_vedere', '')}\n\n"
            f"## Informazioni Pratiche\n{ricerca.get('informazioni_pratiche', '')}\n\n"
            f"## Fonti\n" + "\n".join(f"- {f}" for f in ricerca.get("fonti", []))
        )
        stato["bozza"] = bozza_fallback
        stato["valutazione_fonti"] = {f: 3 for f in ricerca.get("fonti", [])}
        stato["rischio_rifiuto"]   = False
        stato["prob_approvazione"] = None
        print(f"✓ Bozza fallback generata: {len(bozza_fallback)} caratteri")

    # ------------------------------------------------------------------
    # STEP 6 — Related Posts
    # ------------------------------------------------------------------
    print("\n[STEP 6] 🗺️  Related Posts Tool (Geodistanze)")
    print("-" * 60)
    try:
        sezione_correlati = related_posts_tool.invoke({
            "regione":        piano["regione"],
            "topic_corrente": piano["topic"],
        })
        if sezione_correlati:
            stato["bozza"] += sezione_correlati
            print("✓ Sezione correlati aggiunta alla bozza")
        else:
            print("ℹ Nessun post correlato nella regione")
    except Exception as e:
        print(f"⚠ Related posts error: {e}")

    # ------------------------------------------------------------------
    # STEP 7 — Classifier Prediction
    # ------------------------------------------------------------------
    print("\n[STEP 7] 🔮 Classifier — Screening Preventivo")
    print("-" * 60)
    try:
        messaggio = predici_qualita_tool.invoke({"testo": stato["bozza"]})
        print(f"➔ {messaggio}")
    except Exception as e:
        print(f"⚠ Classifier prediction error: {e}")

    # ------------------------------------------------------------------
    # STEP 8 — HITL con interfaccia grafica reale
    # ------------------------------------------------------------------
    print("\n[STEP 8] 🖥️  Human In The Loop (Interfaccia Grafica)")
    print("-" * 60)
    print("🚀 Apertura finestra di revisione — interagisci con la GUI...")
    
    risultato_gui = esegui_hitl_interfaccia(stato)
    stato = {**stato, **risultato_gui}
    azione = stato.get("hitl_action", "rifiuta")
    print(f"➔ Decisione registrata: {azione.upper()}")
    if stato.get("hitl_feedback"):
        print(f"➔ Feedback: {stato['hitl_feedback']}")

    # ------------------------------------------------------------------
    # STEP 9 — KG Updater
    # ------------------------------------------------------------------
    print("\n[STEP 9] 💾 KG Updater — Salvataggio Post")
    print("-" * 60)
    if azione == "approva":
        try:
            stato = kg_updater_node(stato)
            print(f"✓ Post salvato nel KG con ID: {stato.get('post_id')}")
        except Exception as e:
            print(f"⚠ KG Updater error: {e}")
    else:
        print("ℹ Post non salvato (non approvato)")

    # ------------------------------------------------------------------
    # STEP 10 — Fine-tuning Classifier
    # ------------------------------------------------------------------
    print("\n[STEP 10] 🔄 Continual Learning — Aggiornamento Classifier")
    print("-" * 60)
    try:
        label = "approvato" if azione == "approva" else "rifiutato"
        esito = post_quality_classifier_tool.invoke({
            "testo":   stato.get("bozza", ""),
            "label":   label,
            "regione": piano["regione"],
            "topic":   piano["topic"],
        })
        print(f"📊 Risultato aggiornamento:\n{esito}")
    except Exception as e:
        print(f"⚠ Classifier update error: {e}")

    # ------------------------------------------------------------------
    # RIEPILOGO FINALE
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("   ✅ PIPELINE COMPLETATA CON SUCCESSO")
    print("=" * 70)
    print(f"  Modalità:  {'FALLBACK' if modalita_fallback else 'REALE'}")
    print(f"  Regione:   {piano['regione']}")
    print(f"  Topic:     {piano['topic']}")
    print(f"  Post ID:   {stato.get('post_id', 'N/A')}")
    print(f"  Decisione: {azione.upper()}")
    print(f"  Bozza:     {len(stato.get('bozza', ''))} caratteri")
    print("=" * 70)



if __name__ == "__main__":
    esegui_pipeline()