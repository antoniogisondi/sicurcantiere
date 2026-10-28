"""Riquadri di riepilogo del cantiere (pagina Dati generali)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from sicurcantiere import anagrafiche, analisi, controlli
from sicurcantiere.documenti.comune import data_it, euro
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema

# Stati dei riquadri: errori e avvisi colorano la tessera (vedi risorse/tema/sicurcantiere.qss).
OK, ATTENZIONE, ERRORE, NEUTRO = "ok", "attenzione", "errore", "neutro"
STATI_TEMA = {ERRORE: "error", ATTENZIONE: "warning"}


@dataclass(frozen=True)
class Voce:
    chiave: str
    titolo: str
    valore: str
    nota: str = ""
    stato: str = NEUTRO
    pagina: str = ""  # sezione dei controlli della pagina che si apre con un clic («controlli»: i controlli)


def calcola(repo: Repository) -> list[Voce]:
    c = repo.cantiere()
    fasi = repo.elenco("fasi")
    imprese = repo.elenco("imprese")
    rischi = repo.rischi()
    costi = analisi.totale_costi(repo.elenco("costi"))
    periodo = analisi.periodo_lavori(fasi)
    ug = analisi.uomini_giorno(fasi)
    obblighi = analisi.obblighi(imprese, fasi)
    deroga = analisi.deroga_art_90_c11(c)
    interferenze = analisi.interferenze(fasi, analisi.livelli_fasi(rischi))
    prescrizioni = repo.prescrizioni()
    gravi = [i for i in interferenze if i.gravita >= 6]
    scoperte = [i for i in gravi if not prescrizioni.get(i.chiave, "").strip()]
    segnalazioni = controlli.controlla(repo)
    errori = sum(1 for s in segnalazioni if s.livello == controlli.ERRORE)
    avvisi = len(segnalazioni) - errori

    incidenza = f" ({costi / c['importo_lavori'] * 100:.1f}%)".replace(".", ",") if c["importo_lavori"] else ""
    # finché mancano imprese e fasi gli obblighi non si possono stabilire: si dice «da determinare»
    determinabile = bool(imprese) and bool(fasi)
    da_determinare = "Inserisci le imprese e assegna loro le fasi"
    return [
        Voce("importo", "Importo dei lavori", euro(c["importo_lavori"]) if c["importo_lavori"] else "Da indicare",
             f"Costi della sicurezza: {euro(costi)}{incidenza}" if costi else "Costi della sicurezza da stimare",
             NEUTRO if c["importo_lavori"] else ATTENZIONE, "Costi"),
        Voce("durata", "Durata dei lavori",
             f"{analisi.giorni_lavorativi(*periodo)} gg lavorativi" if periodo else "-",
             f"{data_it(periodo[0])} - {data_it(periodo[1])}" if periodo else "Date delle fasi mancanti",
             NEUTRO if periodo else ATTENZIONE, "Fasi"),
        Voce("uomini_giorno", "Entità del cantiere", f"{ug} uomini-giorno",
             f"Soglia per la notifica: {analisi.SOGLIA_UOMINI_GIORNO}",
             ATTENZIONE if ug >= analisi.SOGLIA_UOMINI_GIORNO else NEUTRO),
        Voce("picco", "Picco di lavoratori", str(analisi.picco_lavoratori(fasi)), "presenti contemporaneamente"),
        Voce("imprese", "Imprese esecutrici", str(obblighi.imprese) if determinabile else "Da determinare",
             ("con fasi assegnate" if determinabile else da_determinare),
             NEUTRO if determinabile else ATTENZIONE, "Imprese"),
        Voce("interferenze", "Interferenze", str(len(interferenze)) if periodo else "Da determinare",
             (f"{len(gravi)} gravi, {len(scoperte)} senza prescrizioni" if interferenze else "Nessuna contemporaneità")
             if periodo else "Servono le date delle fasi",
             (ERRORE if scoperte else ATTENZIONE if interferenze else OK) if periodo else NEUTRO, "Interferenze"),
        Voce("psc", "PSC e coordinatori",
             ("Obbligatori" if obblighi.psc else "Non obbligatori") if determinabile else "Da determinare",
             (("art. 90, c. 11: CSP non necessario, il PSC lo redige il CSE" if deroga else
               "art. 90, commi 3 e 4 (più imprese)") if obblighi.psc else "Una sola impresa esecutrice")
             if determinabile else da_determinare,
             (ATTENZIONE if obblighi.psc else OK) if determinabile else NEUTRO, "Soggetti"),
        Voce("notifica", "Notifica preliminare",
             ("Obbligatoria" if obblighi.notifica else "Non obbligatoria") if determinabile else "Da determinare",
             "art. 99 del D.Lgs. 81/2008" if determinabile else da_determinare,
             (ATTENZIONE if obblighi.notifica else OK) if determinabile else NEUTRO),
        Voce("controlli", "Controlli", "Nessun problema" if not segnalazioni else
             (f"{errori} errori" if errori != 1 else "1 errore") if errori else
             (f"{avvisi} avvisi" if avvisi != 1 else "1 avviso"),
             f"{avvisi} avvisi" if errori else "Pagina «Documenti e controlli»",
             ERRORE if errori else ATTENZIONE if avvisi else OK, "controlli"),
    ]


def calcola_pos(repo: Repository) -> list[Voce]:
    """Riquadri dal punto di vista dell'impresa che redige il POS."""
    from datetime import date

    from sicurcantiere.valutazioni import METODI
    from sicurcantiere.valutazioni.base import GIALLO as V_GIALLO
    from sicurcantiere.valutazioni.base import VERDE as V_VERDE

    imprese = [i for i in repo.elenco("imprese") if not anagrafiche.autonomo(i)]
    lavoratori = repo.elenco("lavoratori")
    fasi = repo.elenco("fasi")
    rischi = repo.rischi()
    oggi = date.today().isoformat()
    scadute = [l for l in lavoratori if l["idoneita_scadenza"] and l["idoneita_scadenza"] < oggi]
    alti = [r for r in rischi if analisi.livello_rischio(r["probabilita"], r["danno"]) >= 9]
    esiti = []
    for v in repo.elenco("valutazioni"):
        if v["metodo"] in METODI:
            esiti.append(METODI[v["metodo"]].esegui(repo.dati_valutazione(v["id"])))
    critiche = [e for e in esiti if e.colore not in (V_VERDE, V_GIALLO)]
    # Periodo dalle date dei lavori indicate per le imprese; in mancanza, dalle fasi (file del PSC).
    date_imprese = [(analisi.data(i["data_inizio"]), analisi.data(i["data_fine"])) for i in imprese]
    date_imprese = [(a, b) for a, b in date_imprese if a and b]
    periodo = ((min(a for a, _ in date_imprese), max(b for _, b in date_imprese)) if date_imprese
               else analisi.periodo_lavori(fasi))
    segnalazioni = controlli.controlla_pos(repo)
    errori = sum(1 for s in segnalazioni if s.livello == controlli.ERRORE)
    avvisi = len(segnalazioni) - errori
    return [
        Voce("imprese", "Imprese", str(len(imprese)),
             ", ".join(i["ragione_sociale"] for i in imprese)[:80] or "Inserisci l'impresa",
             NEUTRO if imprese else ERRORE),
        Voce("lavoratori", "Lavoratori", str(len(lavoratori)),
             f"{len(scadute)} con idoneità scaduta" if scadute else "Idoneità in corso di validità",
             ERRORE if scadute else OK if lavoratori else ATTENZIONE),
        Voce("durata", "Periodo dei lavori",
             f"{analisi.giorni_lavorativi(*periodo)} gg lavorativi" if periodo else "-",
             f"{data_it(periodo[0])} - {data_it(periodo[1])}" if periodo else "Date dei lavori dell'impresa mancanti"),
        Voce("fasi", "Lavorazioni", str(len(fasi)), f"{len(rischi)} rischi valutati"),
        Voce("rischi", "Rischi alti e molto alti", str(len(alti)), "livello P × D da 9 a 16",
             ATTENZIONE if alti else OK),
        # è un conteggio, non un problema da risolvere: il colore resta neutro
        Voce("valutazioni", "Valutazioni specifiche", str(len(esiti)),
             f"{len(critiche)} con rischio presente" if critiche else "Nessun rischio oltre la soglia",
             NEUTRO, "Valutazioni"),
        Voce("controlli", "Controlli", "Nessun problema" if not segnalazioni else
             (f"{errori} errori" if errori != 1 else "1 errore") if errori else
             (f"{avvisi} avvisi" if avvisi != 1 else "1 avviso"),
             f"{avvisi} avvisi" if errori else "Pagina «POS e controlli»",
             ERRORE if errori else ATTENZIONE if avvisi else OK, "controlli"),
    ]


class Tessera(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.pagina = ""
        self.setObjectName("tile")
        self.titolo = QLabel()
        self.titolo.setObjectName("tileTitle")
        self.titolo.setWordWrap(True)
        self.valore = QLabel()
        self.valore.setObjectName("tileValue")
        self.valore.setWordWrap(True)
        self.nota = QLabel()
        self.nota.setObjectName("tileNote")
        self.nota.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        layout.addWidget(self.titolo)
        layout.addWidget(self.valore)
        layout.addWidget(self.nota)

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        super().mousePressEvent(evento)
        finestra = self.window()
        if self.pagina == "controlli":
            getattr(finestra, "_vai_ai_controlli", lambda: None)()
        elif self.pagina:
            getattr(finestra, "vai_a_sezione", lambda _s: None)(self.pagina)

    def imposta(self, voce: Voce) -> None:
        self.pagina = voce.pagina
        self.setCursor(Qt.CursorShape.PointingHandCursor if voce.pagina else Qt.CursorShape.ArrowCursor)
        self.setToolTip("Fai clic per aprire la pagina" if voce.pagina else "")
        self.titolo.setText(voce.titolo)
        self.valore.setText(voce.valore)
        self.nota.setText(voce.nota)
        tema.imposta_stato(self, STATI_TEMA.get(voce.stato))


class Riepilogo(QWidget):
    MAX_COLONNE = 7

    def __init__(self, funzione=calcola) -> None:
        super().__init__()
        self.funzione = funzione
        self.griglia = QGridLayout(self)
        self.griglia.setContentsMargins(0, 0, 0, 0)
        self.griglia.setSpacing(10)
        self.tessere: dict[str, Tessera] = {}

    def aggiorna(self, repo: Repository) -> None:
        voci = self.funzione(repo)
        righe = -(-len(voci) // self.MAX_COLONNE)
        colonne = -(-len(voci) // max(righe, 1))
        for n, voce in enumerate(voci):
            tessera = self.tessere.get(voce.chiave)
            if tessera is None:
                tessera = self.tessere[voce.chiave] = Tessera()
                self.griglia.addWidget(tessera, n // colonne, n % colonne)
            tessera.imposta(voce)
