"""
Post Quality Classifier — Fine-tuning dal feedback HITL.

Classifica se un post verrà approvato o rifiutato dall'utente,
addestrato sui post rifiutati/approvati dal HITL.

Flusso:
    1. HITL approva/rifiuta un post
    2. Il tool salva il post + label nel KG
    3. Quando accumula MIN_ESEMPI, esegue fine-tuning reale
       (TF-IDF + LogisticRegression via scikit-learn)
    4. Salva il modello su disco con joblib
    5. Prima del prossimo post, predice la probabilità di approvazione
    6. Se probabilità bassa, avvisa il drafter di riscrivere

Dipendenze:
    pip install scikit-learn joblib
"""

import os
import joblib
import numpy as np
from datetime import datetime
from pathlib import Path
from langchain_core.tools import tool
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
from src.database.kg_operations import driver


# ==============================================================
# Configurazione
# ==============================================================

MIN_ESEMPI     = 2          # fine-tuning scatta dopo 2 esempi per classe
SOGLIA_RISCHIO = 0.5        # sotto questa probabilità → drafter riscrive
MODEL_PATH     = Path("models/post_quality_classifier.joblib")
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


# ==============================================================
# Operazioni KG
# ==============================================================

def _salva_esempio(testo: str, label: str, regione: str, topic: str) -> None:
    """
    Salva un esempio di training nel KG.

    Args:
        testo:   Testo del post
        label:   "approvato" o "rifiutato"
        regione: Regione del post
        topic:   Topic del post
    """
    with driver.session() as session:
        session.run("""
            CREATE (e:EsempioClassifier {
                id:      randomUUID(),
                data:    $data,
                testo:   $testo,
                label:   $label,
                regione: $regione,
                topic:   $topic,
                usato:   false
            })
        """,
            data=datetime.now().isoformat(),
            testo=testo[:3000],
            label=label,
            regione=regione,
            topic=topic,
        )
    print(f"[CLASSIFIER] Esempio salvato: label='{label}', topic='{topic}'")


def _carica_tutti_esempi() -> tuple[list[str], list[str]]:
    """
    Carica tutti gli esempi dal KG.

    Returns:
        Tuple (testi, labels)
    """
    with driver.session() as session:
        result = session.run("""
            MATCH (e:EsempioClassifier)
            RETURN e.testo AS testo, e.label AS label
            ORDER BY e.data ASC
        """)
        records = list(result)
        testi  = [r["testo"] for r in records]
        labels = [r["label"] for r in records]
    return testi, labels


def _conta_esempi_per_label() -> dict[str, int]:
    """Conta esempi per ogni label nel KG."""
    with driver.session() as session:
        result = session.run("""
            MATCH (e:EsempioClassifier)
            RETURN e.label AS label, count(e) AS totale
        """)
        return {r["label"]: r["totale"] for r in result}


def _salva_metriche(metriche: str) -> None:
    """Salva le metriche del classificatore nel KG."""
    with driver.session() as session:
        session.run("""
            MERGE (m:MetricheClassifier {chiave: "latest"})
            SET m.metriche = $metriche,
                m.data_aggiornamento = $data
        """,
            metriche=metriche,
            data=datetime.now().isoformat(),
        )


def carica_metriche() -> str | None:
    """Legge le ultime metriche del classificatore dal KG."""
    with driver.session() as session:
        result = session.run("""
            MATCH (m:MetricheClassifier {chiave: "latest"})
            RETURN m.metriche AS metriche
        """)
        record = result.single()
        return record["metriche"] if record else None


# ==============================================================
# Fine-tuning reale
# ==============================================================

def _esegui_fine_tuning(testi: list[str], labels: list[str]) -> Pipeline:
    """
    Esegue il fine-tuning reale del classificatore.

    Pipeline:
        TF-IDF (estrazione features testuali)
        → LogisticRegression (classificatore)

    Args:
        testi:  Lista di testi dei post
        labels: Lista di label ("approvato" / "rifiutato")

    Returns:
        Pipeline sklearn addestrata
    """
    print(f"[CLASSIFIER] Avvio fine-tuning con {len(testi)} esempi...")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),     # unigrammi e bigrammi
            min_df=1,
            strip_accents="unicode",
            lowercase=True,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",  # gestisce sbilanciamento classi
        )),
    ])

    pipeline.fit(testi, labels)

    # Calcola metriche sul training set
    predictions = pipeline.predict(testi)
    metriche = classification_report(
        labels,
        predictions,
        target_names=["approvato", "rifiutato"],
        zero_division=0,
    )

    print(f"[CLASSIFIER] ✓ Fine-tuning completato")
    print(f"[CLASSIFIER] Metriche:\n{metriche}")

    # Salva metriche nel KG
    _salva_metriche(metriche)

    # Salva modello su disco
    joblib.dump(pipeline, MODEL_PATH)
    print(f"[CLASSIFIER] Modello salvato in: {MODEL_PATH}")

    return pipeline


def _carica_modello() -> Pipeline | None:
    """
    Carica il modello dal disco se esiste.

    Returns:
        Pipeline sklearn oppure None se non esiste ancora
    """
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return None


# ==============================================================
# Predizione
# ==============================================================

def predici_qualita(testo: str) -> dict:
    """
    Predice se un post verrà approvato o rifiutato.
    Usata dal drafter prima di mostrare il post al HITL.

    Args:
        testo: Testo del post da valutare

    Returns:
        Dict con:
            - label:       "approvato" o "rifiutato"
            - probabilita: float 0-1
            - rischio:     True se probabilità approvazione < SOGLIA
            - messaggio:   Messaggio human-readable
    """
    modello = _carica_modello()

    if modello is None:
        return {
            "label":       "sconosciuto",
            "probabilita": None,
            "rischio":     False,
            "messaggio":   "Modello non ancora addestrato — servono almeno 2 esempi per classe.",
        }

    proba = modello.predict_proba([testo])[0]
    classi = modello.classes_
    idx_approvato = list(classi).index("approvato")
    prob_approvazione = proba[idx_approvato]

    label = "approvato" if prob_approvazione >= SOGLIA_RISCHIO else "rifiutato"
    rischio = prob_approvazione < SOGLIA_RISCHIO

    messaggio = (
        f"Probabilità approvazione: {prob_approvazione:.1%}\n"
        f"Predizione: {label}\n"
        + ("⚠️ RISCHIO RIFIUTO — il drafter dovrebbe riscrivere il post." if rischio
           else "✓ Post probabilmente approvato.")
    )

    return {
        "label":       label,
        "probabilita": round(prob_approvazione, 3),
        "rischio":     rischio,
        "messaggio":   messaggio,
    }


# ==============================================================
# Tool principale
# ==============================================================

@tool
def post_quality_classifier_tool(
    testo: str,
    label: str,
    regione: str,
    topic: str,
) -> str:
    """
    Raccoglie esempi dal feedback HITL e addestra un classificatore
    che predice se un post verrà approvato o rifiutato dall'utente.

    Il fine-tuning scatta automaticamente quando accumula almeno
    MIN_ESEMPI esempi per ogni classe (approvato/rifiutato).

    Usare SEMPRE dopo ogni decisione HITL (approva o rifiuta).

    Args:
        testo:   Testo completo del post
        label:   "approvato" se l'utente ha approvato,
                 "rifiutato" se l'utente ha rifiutato o modificato
        regione: Regione del post (es. "Sicilia")
        topic:   Topic del post (es. "Valle dei Templi")

    Returns:
        Stato del classificatore e metriche se il fine-tuning è avvenuto
    """
    # 1. Salva esempio nel KG
    _salva_esempio(testo, label, regione, topic)

    # 2. Conta esempi per classe
    conteggio = _conta_esempi_per_label()
    n_approvati = conteggio.get("approvato", 0)
    n_rifiutati = conteggio.get("rifiutato", 0)

    print(f"[CLASSIFIER] Esempi: approvati={n_approvati}, rifiutati={n_rifiutati}")

    # 3. Controlla se ha raggiunto il minimo per entrambe le classi
    if n_approvati < MIN_ESEMPI or n_rifiutati < MIN_ESEMPI:
        mancano_approvati = max(0, MIN_ESEMPI - n_approvati)
        mancano_rifiutati = max(0, MIN_ESEMPI - n_rifiutati)
        return (
            f"Esempio '{label}' salvato nel KG.\n"
            f"Stato: approvati={n_approvati}/{MIN_ESEMPI}, "
            f"rifiutati={n_rifiutati}/{MIN_ESEMPI}\n"
            f"Mancano: {mancano_approvati} approvati, "
            f"{mancano_rifiutati} rifiutati per avviare il fine-tuning."
        )

    # 4. Raggiunto il minimo — avvia fine-tuning
    print(f"[CLASSIFIER] Soglia raggiunta — avvio fine-tuning...")
    testi, labels = _carica_tutti_esempi()

    try:
        _esegui_fine_tuning(testi, labels)
        metriche = carica_metriche()
        return (
            f"✓ Fine-tuning completato con {len(testi)} esempi.\n"
            f"Modello salvato in: {MODEL_PATH}\n\n"
            f"METRICHE:\n{metriche}"
        )
    except Exception as e:
        return f"Errore durante il fine-tuning: {e}"


# ==============================================================
# Tool di predizione
# ==============================================================

@tool
def predici_qualita_tool(testo: str) -> str:
    """
    Predice se un post verrà approvato o rifiutato dall'utente
    usando il classificatore addestrato dal feedback HITL.

    Usare PRIMA di mostrare il post al HITL per valutare il rischio.
    Se il rischio è alto, il drafter dovrebbe riscrivere il post.

    Args:
        testo: Testo completo del post da valutare

    Returns:
        Predizione con probabilità e suggerimento
    """
    risultato = predici_qualita(testo)
    return risultato["messaggio"]