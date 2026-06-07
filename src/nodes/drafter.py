"""
Nodo Drafter del grafo LangGraph per il blog turistico italiano.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.database.kg_operations import get_quality_score_fonti
from src.tools.related_posts_tool import related_posts_tool
from src.tools.post_quality_classifier import predici_qualita


llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
    temperature=0.7,
)

PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Sei un blogger esperto di turismo italiano.
Scrivi post coinvolgenti, accurati e piacevoli da leggere per un pubblico generale.

Linee guida:
- Tono: caldo, appassionato, accessibile a tutti
- Lunghezza: 600-900 parole
- Struttura: introduzione coinvolgente, corpo con le informazioni, conclusione con invito alla visita
- Lingua: italiano
- Non inventare informazioni non presenti nel materiale fornito
- Cita le fonti in fondo al post"""),
    ("human", """Scrivi un post turistico su: {topic} ({regione})

DESCRIZIONE:
{descrizione}

STORIA:
{storia}

COSA VEDERE:
{cosa_vedere}

INFORMAZIONI PRATICHE:
{informazioni_pratiche}

FONTI:
{fonti}

{feedback_section}
"""),
])


def drafter_node(state: dict) -> dict:
    piano   = state.get("piano_corrente")
    ricerca = state.get("ricerca")
    bozza_precedente = state.get("bozza")
    feedback         = state.get("hitl_feedback")

    if not piano:
        raise ValueError("piano_corrente non trovato nello state.")
    if not ricerca:
        raise ValueError("ricerca non trovata nello state.")

    if bozza_precedente and feedback:
        feedback_section = (
            f"BOZZA PRECEDENTE:\n{bozza_precedente}\n\n"
            f"FEEDBACK DELL'UTENTE:\n{feedback}\n\n"
            f"Riscrivi il post tenendo conto del feedback ricevuto."
        )
    else:
        feedback_section = ""

    chain    = PROMPT | llm
    risposta = chain.invoke({
        "topic":                 piano["topic"],
        "regione":               piano["regione"],
        "descrizione":           ricerca.get("descrizione", ""),
        "storia":                ricerca.get("storia", ""),
        "cosa_vedere":           ricerca.get("cosa_vedere", ""),
        "informazioni_pratiche": ricerca.get("informazioni_pratiche", ""),
        "fonti":                 "\n".join(ricerca.get("fonti", [])),
        "feedback_section":      feedback_section,
    })

    # Estrai testo dalla risposta LangChain
    if isinstance(risposta.content, str):
        bozza = risposta.content
    elif isinstance(risposta.content, list):
        bozza = "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in risposta.content
        )
    else:
        bozza = str(risposta.content)

    # Aggiunge sezione post correlati
    sezione_correlati = related_posts_tool.invoke({
        "regione":        piano["regione"],
        "topic_corrente": piano["topic"],
    })
    bozza_finale = bozza + sezione_correlati

    # Predice qualità con il classificatore
    valutazione_qualita = predici_qualita(bozza_finale)
    print(f"[DRAFTER] {valutazione_qualita['messaggio']}")

    # Valutazione fonti
    fonti_trovate      = ricerca.get("fonti", [])
    valutazione_iniziale = get_quality_score_fonti(fonti_trovate)

    return {
        **state,
        "bozza":             bozza_finale,        # ← fix: bozza_finale non risposta.content
        "valutazione_fonti": valutazione_iniziale,
        "rischio_rifiuto":   valutazione_qualita["rischio"],
        "prob_approvazione": valutazione_qualita["probabilita"],
        "hitl_action":       None,
        "hitl_feedback":     None,
    }