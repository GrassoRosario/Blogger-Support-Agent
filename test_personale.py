import os
import sys

# Impostazione percorsi grafici .venv
base_python_path = r"C:\Users\HEW15EG0057NL\AppData\Local\Programs\Python\Python313"
os.environ['TCL_LIBRARY'] = os.path.join(base_python_path, 'tcl', 'tcl8.6')
os.environ['TK_LIBRARY'] = os.path.join(base_python_path, 'tcl', 'tk8.6')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "tools")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "database")))

from dotenv import load_dotenv
load_dotenv()

from src.nodes.planner import planner_node
from src.tools.related_posts_tool import related_posts_tool
from gui import esegui_hitl_interfaccia
from src.tools.post_quality_classifier import post_quality_classifier_tool
from src.database.kg_operations import driver

def inserisci_post_fittizio_per_itinerario():
    """Inserisce un post nel passato per fare in modo che il modulo geodistanze calcoli i KM reali"""
    with driver.session() as session:
        # Creiamo un post precedente in Piemonte (es. Varallo) per fare il test con i Sacri Monti
        session.run("""
            MERGE (r:Regione {nome: "Piemonte"})
            MERGE (p:Post {id: "vecchio-post-1", titolo: "Guida al Sacro Monte di Varallo", data_creazione: "2026-01-01"})
            MERGE (t:Topic {nome: "Sacro Monte di Varallo"})
            MERGE (p)-[:AMBIENTATO_IN]->(r)
            MERGE (p)-[:TRATTA]->(t)
            MERGE (t)-[:APPARTIENE_A]->(r)
        """)

def esegui_test_flusso_comunicazione():
    print("=== CONFIGURAZIONE GRAPH DB PER ITINERARIO ===")
    inserisci_post_fittizio_per_itinerario()

    stato_condiviso = {
        "n": 5, "k": 3, "piano_corrente": None, "ricerca": {"fonti": ["https://whc.unesco.org"]},
        "bozza": None, "hitl_action": None, "hitl_feedback": None
    }

    print("\n[FASE 1] Pianificazione e passaggi al Search...")
    try:
        stato_dopo_planner = planner_node(stato_condiviso)
        piano = stato_dopo_planner.get("piano_corrente")
    except Exception:
        print("⚠️  Blocco Quota API rilevato. Genero Piano e Articolo dinamico di test...")
        # Simuliamo il passaggio dati esatto: il Planner decide Piemonte -> Sacro Monte di Crea
        stato_dopo_planner = stato_condiviso.copy()
        stato_dopo_planner["piano_corrente"] = {
            "regione": "Piemonte",
            "topic": "Sacro Monte di Crea"
        }
        piano = stato_dopo_planner["piano_corrente"]

    # Generazione dinamica del testo simulando l'output del Drafter
    bozza_generata = (
        f"# Il Fascino del {piano['topic']}\n\n"
        f"Situato nel cuore del {piano['regione']}, questo splendido complesso monumentale "
        f"fa parte dei Sacri Monti patrimonio dell'umanità UNESCO."
    )

    print(f"-> Dati trasmessi: Regione='{piano['regione']}', Topic='{piano['topic']}'")

    print("\n[FASE 2] Controllo Itinerari e distanze nel passato (Related Posts Tool)...")
    # Il tool cercherà se in Piemonte ci sono post vecchi (troverà Varallo inserito sopra)
    sezione_itinerario = related_posts_tool.invoke({
        "regione": piano["regione"],
        "topic_corrente": piano["topic"]
    })

    if sezione_itinerario:
        print("✅ Post precedenti trovati! Calcolo geodistanza effettuato.")
        bozza_finale = bozza_generata + "\n\n" + sezione_itinerario
    else:
        bozza_finale = bozza_generata

    stato_dopo_planner["bozza"] = bozza_finale
    stato_dopo_planner["valutazione_fonti"] = {"https://whc.unesco.org": 5}

    print("\n[FASE 3] Invio dello stato alla GUI dello Human-in-the-Loop...")
    risultato_gui = esegui_hitl_interfaccia(stato_dopo_planner)
    azione = risultato_gui.get("hitl_action")
    print(f"-> Decisione utente catturata dalla GUI: '{azione}'")

    print("\n[FASE 4] Passaggio dati al modulo di Fine-Tuning...")
    label_ft = "approvato" if azione == "approva" else "rifiutato"
    risultato_ft = post_quality_classifier_tool.invoke({
        "testo": risultato_gui.get("bozza", bozza_finale),
        "label": label_ft,
        "regione": piano["regione"],
        "topic": piano["topic"]
    })
    print(risultato_ft)

if __name__ == "__main__":
    esegui_test_flusso_comunicazione()