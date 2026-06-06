import os
import sys

# Sostituisci con il percorso esatto della tua installazione globale di Python se differente
base_python_path = r"C:\Users\HEW15EG0057NL\AppData\Local\Programs\Python\Python313"

os.environ['TCL_LIBRARY'] = os.path.join(base_python_path, 'tcl', 'tcl8.6')
os.environ['TK_LIBRARY'] = os.path.join(base_python_path, 'tcl', 'tk8.6')

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

class HitlGui:
    def __init__(self, root, state: dict):
        self.root = root
        self.state = state
        self.root.title("HITL - Validazione Post & Fonti")
        self.root.geometry("800x700")
        
        # Risultato della decisione dell'utente
        self.action_result = "rifiuta"
        self.feedback_result = ""
        self.fonti_aggiornate = {}

        # Dati dallo stato del grafo
        self.piano = state.get("piano_corrente", {"regione": "Sconosciuta", "topic": "Sconosciuto"})
        self.bozza_iniziale = state.get("bozza", "")
        self.valutazione_fonti = state.get("valutazione_fonti", {})

        self._build_widgets()

    def _build_widgets(self):
        # Header Informativo
        header_frame = ttk.Frame(self.root, padding=10)
        header_frame.pack(fill="x")
        
        ttk.Label(header_frame, text=f"Topic: {self.piano.get('topic')}", font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(header_frame, text=f"Regione: {self.piano.get('regione')}", font=("Helvetica", 11, "italic")).pack(anchor="w")

        # Main Notebook (Tab per dividere Bozza e Fonti)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # TAB 1: Testo della Bozza
        self.tab_bozza = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_bozza, text="Bozza del Post")
        
        self.txt_bozza = scrolledtext.ScrolledText(self.tab_bozza, wrap=tk.WORD, font=("Courier New", 10))
        self.txt_bozza.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_bozza.insert(tk.END, self.bozza_iniziale)

        # TAB 2: Gestione Fonti e Punteggi Qualità
        self.tab_fonti = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_fonti, text="Valutazione Qualità Fonti")

        # Frame interno scrollabile per le fonti
        canvas = tk.Canvas(self.tab_fonti)
        scrollbar = ttk.Scrollbar(self.tab_fonti, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Genera slider dinamici per ciascuna fonte nello stato
        self.sliders = {}
        if not self.valutazione_fonti:
            ttk.Label(self.scrollable_frame, text="Nessuna fonte registrata dal Researcher.").pack(pady=10)
        else:
            for url, score in self.valutazione_fonti.items():
                fonti_frame = ttk.LabelFrame(self.scrollable_frame, text=url, padding=5)
                fonti_frame.pack(fill="x", expand=True, padx=5, pady=5)
                
                score_var = tk.IntVar(value=score)
                self.sliders[url] = score_var
                
                slider = tk.Scale(fonti_frame, from_=0, to=5, orient=tk.HORIZONTAL, variable=score_var, tickinterval=1)
                slider.pack(fill="x", side="left", expand=True)
                
                ttk.Label(fonti_frame, text="(0 = Evita, 1-5 = Punteggio Qualità)").pack(side="right", padx=5)

        # Sezione inferiore: Feedback di modifica e Pulsanti Azione
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill="x", side="bottom")

        ttk.Label(bottom_frame, text="Feedback per modifiche (obbligatorio se si preme 'Richiedi Modifiche'):").pack(anchor="w")
        self.txt_feedback = tk.Entry(bottom_frame, font=("Helvetica", 10))
        self.txt_feedback.pack(fill="x", pady=5)

        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(fill="x", pady=5)

        ttk.Button(btn_frame, text="Approva e Salva", command=self._approva).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Richiedi Modifiche", command=self._modifica).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Rifiuta Piano", command=self._rifiuta).pack(side="left", padx=5)

    def _approva(self):
        self.action_result = "approva"
        self._concludi()

    def _modifica(self):
        self.feedback_result = self.txt_feedback.get().strip()
        if not self.feedback_result:
            messagebox.showwarning("Feedback Mancante", "Inserisci una nota di feedback per spiegare cosa modificare.")
            return
        self.action_result = "modifica"
        self._concludi()

    def _rifiuta(self):
        if messagebox.askyesno("Conferma Rifiuto", "Sei sicuro di voler scartare questo post? Verrà salvato come esempio negativo nel Classificatore."):
            self.action_result = "rifiuta"
            self._concludi()

    def _concludi(self):
        # Raccoglie i valori degli slider modificati dall'utente
        for url, score_var in self.sliders.items():
            self.fonti_aggiornate[url] = score_var.get()
        
        # Aggiorna il testo del post qualora l'utente lo abbia ritoccato direttamente nella textbox
        self.bozza_finale = self.txt_bozza.get("1.0", tk.END).strip()
        
        self.root.destroy()

def esegui_hitl_interfaccia(state: dict) -> dict:
    """
    Funzione wrapper da inserire nel ciclo di esecuzione del grafo
    per intercettare lo stato ed applicare le decisioni umane.
    """
    root = tk.Tk()
    gui = HitlGui(root, state)
    root.mainloop()
    
    # Restituisce le modifiche pronte per aggiornare LangGraph
    return {
        "hitl_action": gui.action_result,
        "hitl_feedback": gui.feedback_result if gui.action_result == "modifica" else None,
        "bozza": gui.bozza_finale if gui.action_result == "approva" else state.get("bozza"),
        "valutazione_fonti": gui.fonti_aggiornate
    }