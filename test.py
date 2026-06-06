import sys
import os

# Simulazione di uno stato del grafo tipico generato dopo il Drafter
stato_mock = {
    "n": 5,
    "k": 3,
    "piano_corrente": {
        "regione": "Sicilia",
        "topic": "Valle dei Templi di Agrigento"
    },
    "bozza": """# La Valle dei Templi: Un Viaggio nel Tempo ad Agrigento

La Valle dei Templi di Agrigento rappresenta una delle testimonianze più straordinarie della civiltà greca classica in Italia. Immaginate di passeggiare tra templi millenari al tramonto, immersi in un paesaggio unico al mondo.

## Cosa Vedere
- **Tempio della Concordia**: uno dei templi greci meglio conservati al mondo.
- **Tempio di Ercole**: il più antico tra i monumenti dell'area.

Visitate questo magnifico sito UNESCO per riscoprire il cuore della Magna Grecia!""",
    "valutazione_fonti": {
        "https://whc.unesco.org": 5,
        "https://cultura.gov.it": 4,
        "https://tripadvisor.com": 1
    },
    "hitl_action": None,
    "hitl_feedback": None
}

if __name__ == "__main__":
    # Importiamo la funzione dal modulo GUI appena creato
    from gui import esegui_hitl_interfaccia

    print("=== AVVIO TEST INTERFACCIA GRAFICA HITL ===")
    print("Apertura della finestra di validazione...")
    
    # Esecuzione del test grafico
    risultato_aggiornato = esegui_hitl_interfaccia(stato_mock)
    
    print("\n=== RISULTATI RICEVUTI DALL'INTERFACCIA ===")
    print(f"Azione Scelta:      {risultato_aggiornato['hitl_action']}")
    print(f"Feedback Inserito:  {risultato_aggiornato['hitl_feedback']}")
    print(f"Fonti Modificate:   {risultato_aggiornato['valutazione_fonti']}")
    print("\nTest completato con successo. Verifica che i dati corrispondano alle tue scelte.")