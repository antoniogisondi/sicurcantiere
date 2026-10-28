"""Pagine della finestra principale."""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from PySide6.QtCore import QDate, QSettings, QStringListModel, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sicurcantiere import anagrafiche, analisi, controlli
from sicurcantiere.archivio import ATTREZZATURE, TIPOLOGIE, per_categoria
from sicurcantiere.archivio_utente import LAVORAZIONE, ArchivioAnagrafiche
from sicurcantiere.documenti.comune import euro
from sicurcantiere.documenti.fascicolo import genera_fascicolo
from sicurcantiere.documenti.maestranze import genera_schede_lavoratori, genera_tesserini
from sicurcantiere.documenti.moduli import genera_consegna_dpi
from sicurcantiere.documenti.sostanze import genera_elenco_sostanze
from sicurcantiere.documenti.notifica import genera_notifica
from sicurcantiere.documenti.pos import SEZIONI_POS, chiave_testo, genera_pos
from sicurcantiere.documenti.psc import genera_psc
from sicurcantiere.relazione import SEZIONI
from sicurcantiere.repository import Repository
from sicurcantiere.ui import archivio_anagrafiche, tema
from sicurcantiere.ui.composizioni import PannelloComposizioni
from sicurcantiere.ui.icone import icona
from sicurcantiere.ui.lavoro_ai import esegui_ai, registra_pulsante_ai
from sicurcantiere.ui.maestranze import PannelloLavoratori
from sicurcantiere.ui.modulo import ModuloRecord
from sicurcantiere.ui.struttura import StrutturaFase
from sicurcantiere.ui.gantt import ZOOM, ZOOM_PREDEFINITO, Gantt
from sicurcantiere.ui.riepilogo import Riepilogo
from sicurcantiere.ui.riepilogo import calcola as calcola_riepilogo
from sicurcantiere.ui.tabella import Colonna, TabellaCrud

RUOLI = anagrafiche.RUOLI_SOGGETTI
TIPI_IMPRESA = anagrafiche.TIPI_IMPRESA
TIPI_ATTREZZATURA = ["Macchina", "Attrezzo", "Opera provvisionale"]


def _titolo(testo: str) -> QLabel:
    etichetta = QLabel(testo)
    etichetta.setObjectName("pageTitle")
    etichetta.setWordWrap(True)
    return etichetta


def primario(pulsante: QPushButton) -> QPushButton:
    """Pulsante principale della pagina, nel colore del programma."""
    return tema.imposta_variante(pulsante, "primary")


def pulsante_ai(testo: str) -> QPushButton:
    """Pulsante che chiede qualcosa all'assistente AI (viola, come gli avvisi dell'assistente)."""
    pulsante = QPushButton(icona("ai", tema.correnti()["ai"]), testo)
    tema.imposta_variante(pulsante, "ai")
    registra_pulsante_ai(pulsante)  # nascosto finché l'assistente è spento
    return pulsante


def _riquadro(titolo: str, widget: QWidget) -> QGroupBox:
    g = QGroupBox(titolo)
    QVBoxLayout(g).addWidget(widget)
    return g


AVVISO_RESPONSABILITA = ("Il documento va riletto, completato dove necessario e firmato da chi ne ha la "
                         "responsabilità "
                         "(datore di lavoro per il POS, coordinatore per il PSC): il programma è uno strumento "
                         "di redazione e non sostituisce la valutazione dei rischi.")


def contesto_cantiere(repo: Repository) -> str:
    """Riepilogo del progetto da passare all'assistente AI.

    Senza dati personali: niente nomi di soggetti, imprese o lavoratori, niente indirizzo
    preciso; solo ruoli, tipologie, lavorazioni e il comune (vedi DialogoImpostazioniAI).
    """
    c = repo.cantiere()
    imprese = {i["id"]: i["tipo"] or "impresa" for i in repo.elenco("imprese")}
    righe = [
        f"Natura dell'opera: {c['natura_opera']}",
        f"Comune: {c['comune']} {c['provincia']}".strip(),
        f"Importo lavori: {c['importo_lavori']:.0f} euro",
        f"Descrizione: {c['descrizione']}",
        "Soggetti presenti: " + "; ".join(sorted({s["ruolo"] for s in anagrafiche.soggetti(repo)})),
        "Imprese: " + "; ".join(imprese.values()),
        "Fasi di lavoro:",
    ]
    for f in repo.elenco("fasi"):
        righe.append(f"- {f['codice']} {f['descrizione']}, {imprese.get(f['impresa_id'], 'impresa da definire')}, "
                     f"dal {f['data_inizio'] or '?'} al {f['data_fine'] or '?'}, zona {f['zona'] or '-'}")
    return "\n".join(righe)


class TestiLiberi(QWidget):
    """Editor di più sezioni di testo, salvate con un breve ritardo."""

    def __init__(self, repo: Repository, sezioni: list[tuple[str, str]],
                 chiave: Callable[[str], str] = lambda s: s, altezza: int = 120,
                 contesto_ai: Callable[[], str] | None = None, guide: dict[str, str] | None = None,
                 non_pertinente: bool = False):
        super().__init__()
        self.repo = repo
        self.compilati_cambiati: Callable[[], None] | None = None
        self.chiave = chiave
        self.contesto_ai = contesto_ai
        self.titoli = dict(sezioni)
        self.editor: dict[str, QPlainTextEdit] = {}
        self._in_sospeso: dict[str, str] = {}
        self._timer = QTimer(self, singleShot=True, interval=700)
        self._timer.timeout.connect(self.salva_in_sospeso)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for sezione, titolo in sezioni:
            from sicurcantiere.ui.tabella import _TestoCrescente

            editor = _TestoCrescente()  # si allunga mentre si scrive
            editor.setMinimumHeight(altezza)
            if guide and guide.get(sezione):
                editor.setPlaceholderText(guide[sezione])
            editor.textChanged.connect(lambda s=sezione: self._modificato(s))
            riquadro = _riquadro(titolo, editor)
            azioni = QHBoxLayout()
            azioni.addStretch()
            if non_pertinente:
                np = QPushButton("Non pertinente...")
                np.setToolTip("Il riquadro non serve per questo cantiere: indica il motivo, che resta scritto nel "
                              "PSC al posto del testo.")
                np.clicked.connect(lambda _=False, s=sezione: self._non_pertinente(s))
                azioni.addWidget(np)
            if contesto_ai is not None:
                bozza = pulsante_ai("Scrivi la bozza con l'assistente AI")
                bozza.setToolTip("Scrivi o migliora il testo della sezione partendo dai dati del cantiere")
                bozza.clicked.connect(lambda _=False, s=sezione: self._bozza_ai(s))
                azioni.addWidget(bozza)
            riquadro.layout().addLayout(azioni)
            layout.addWidget(riquadro)
            self.editor[sezione] = editor

    def _bozza_ai(self, sezione: str) -> None:
        assert self.contesto_ai is not None
        titolo = self.titoli[sezione]
        contesto = self.contesto_ai()
        attuale = self.editor[sezione].toPlainText()
        esegui_ai(self, f"L'assistente sta scrivendo «{titolo}»...",
                  lambda ai: ai.scrivi_sezione(titolo, contesto, attuale),
                  lambda testo: self.imposta_testo(sezione, testo))

    def imposta_testo(self, sezione: str, testo: str) -> None:
        """Sostituisce il testo di una sezione (annullabile con Ctrl+Z) e lo salva."""
        editor = self.editor[sezione]
        cursore = editor.textCursor()
        cursore.select(cursore.SelectionType.Document)
        cursore.insertText(testo)
        self.salva_in_sospeso()

    def _modificato(self, sezione: str) -> None:
        self._in_sospeso[self.chiave(sezione)] = self.editor[sezione].toPlainText()
        self._timer.start()
        if self.compilati_cambiati:
            self.compilati_cambiati()

    def compilati(self) -> int:
        return sum(1 for e in self.editor.values() if e.toPlainText().strip())

    def _non_pertinente(self, sezione: str) -> None:
        motivo, ok = QInputDialog.getText(
            self, "Non pertinente", f"Perché «{self.titoli[sezione].split('   ·')[0]}» non serve per questo "
                                    "cantiere?\n(per esempio «non sono previsti scavi»)")
        if ok and motivo.strip():
            motivo = motivo.strip().rstrip(".")
            self.imposta_testo(sezione, f"Non pertinente per questo cantiere: {motivo[:1].lower()}{motivo[1:]}.")

    def salva_in_sospeso(self) -> None:
        self._timer.stop()
        for chiave, testo in self._in_sospeso.items():
            self.repo.salva_testo(chiave, testo)
        self._in_sospeso.clear()

    def carica(self, chiave: Callable[[str], str] | None = None) -> None:
        self.salva_in_sospeso()
        if chiave is not None:
            self.chiave = chiave
        for sezione, editor in self.editor.items():
            editor.blockSignals(True)
            editor.setPlainText(self.repo.testo(self.chiave(sezione)))
            editor.blockSignals(False)


class Pagina(QWidget):
    titolo = ""
    voce = ""  # nome breve nella barra di navigazione
    icona = "cantiere"  # nome in ui/icone.py
    sottotitolo = ""  # una riga sotto il titolo
    # Sezioni dei controlli che riguardano la pagina: il loro numero compare nella barra
    # laterale; "*" raccoglie quelle che nessuna pagina dichiara.
    sezioni_controlli: tuple[str, ...] = ()

    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(24, 16, 24, 14)
        self.layout_.setSpacing(12)
        intestazione = QVBoxLayout()
        intestazione.setSpacing(2)
        intestazione.addWidget(_titolo(self.titolo))
        # con il genitore da subito: un widget senza genitore reso visibile diventa per un istante una
        # finestra a sé (su Windows compare e sparisce nella barra delle applicazioni)
        self.etichetta_sottotitolo = QLabel(self.sottotitolo, self)
        self.etichetta_sottotitolo.setObjectName("pageSubtitle")
        self.etichetta_sottotitolo.setWordWrap(True)
        self.etichetta_sottotitolo.setVisible(bool(self.sottotitolo))
        intestazione.addWidget(self.etichetta_sottotitolo)
        self.layout_.addLayout(intestazione)

    def aggiorna(self) -> None:
        """Ricarica i dati quando la pagina viene mostrata."""

    def salva_in_sospeso(self) -> None:
        """Salva le modifiche non ancora scritte (cambio pagina, chiusura)."""

    def genera_principale(self) -> None:
        """Genera il documento principale del programma (pulsante nella barra degli strumenti)."""
        raise NotImplementedError


class PaginaDatiGenerali(Pagina):
    titolo = "Dati generali del cantiere"
    voce = "Dati generali"
    icona = "cantiere"
    sezioni_controlli = ("Cantiere", "Dati generali")
    funzione_riepilogo = staticmethod(calcola_riepilogo)
    CAMPI = [
        ("nome", "Denominazione dell'opera"),
        ("natura_opera", "Natura dell'opera"),
        ("indirizzo", "Indirizzo"),
        ("cap", "CAP"),
        ("comune", "Comune"),
        ("provincia", "Provincia"),
        ("titolo_abilitativo", "Titolo abilitativo (permesso, SCIA, CILA...)"),
    ]

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self._caricata = False
        self.riepilogo = Riepilogo(self.funzione_riepilogo) if self.funzione_riepilogo else None
        if self.riepilogo is not None:
            self.layout_.addWidget(self.riepilogo)
        self.campi: dict[str, QLineEdit] = {}
        etichette = dict(self.CAMPI)
        for campo in etichette:
            e = QLineEdit()
            e.editingFinished.connect(lambda c=campo, w=e: self.repo.aggiorna_cantiere(**{c: w.text()}))
            self.campi[campo] = e
        self.campi["provincia"].setMaxLength(2)
        self.importo = self._numero(" €", "importo_lavori")
        self.costo_ug = self._numero(" €", "costo_uomo_giorno",
                                     f"{analisi.COSTO_UOMO_GIORNO:.0f} € (valore tipico)")
        self.costo_ug.setToolTip("Costo medio di un uomo-giorno, usato per stimare la durata delle fasi. Se non "
                                 f"lo indichi si usa il valore tipico di {analisi.COSTO_UOMO_GIORNO:.0f} €.")
        self.descrizione = QPlainTextEdit()
        self.descrizione.setPlaceholderText("Descrizione sintetica dell'opera")
        self._timer = QTimer(self, singleShot=True, interval=700)
        self._timer.timeout.connect(self._salva_descrizione)
        self.descrizione.textChanged.connect(self._timer.start)

        # Griglia a quattro colonne: (riga, colonna, ampiezza) di ogni campo.
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(14)
        griglia.setVerticalSpacing(10)
        for campo, (r, c, ampiezza) in {"nome": (0, 0, 4), "natura_opera": (1, 0, 2),
                                        "titolo_abilitativo": (1, 2, 2), "indirizzo": (2, 0, 1),
                                        "cap": (2, 1, 1), "comune": (2, 2, 1), "provincia": (2, 3, 1)}.items():
            griglia.addLayout(tema.campo_con_etichetta(etichette[campo], self.campi[campo]), r, c, 1, ampiezza)
        griglia.addLayout(tema.campo_con_etichetta("Importo presunto dei lavori", self.importo), 3, 0, 1, 2)
        griglia.addLayout(tema.campo_con_etichetta("Costo medio uomo-giorno", self.costo_ug), 3, 2, 1, 2)
        griglia.addLayout(tema.campo_con_etichetta("Descrizione sintetica", self.descrizione), 4, 0, 1, 4)
        for c, peso in enumerate((3, 1, 3, 1)):
            griglia.setColumnStretch(c, peso)
        griglia.setRowStretch(4, 1)
        self.riquadro_dati = tema.cornice("Dati dell'opera", griglia)
        self.corpo = QHBoxLayout()
        self.corpo.setSpacing(12)
        self.corpo.addWidget(self.riquadro_dati, 2)
        self.layout_.addLayout(self.corpo, 1)


    def _numero(self, suffisso: str, campo: str, suggerimento: str = "") -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0, 1e10)
        s.setDecimals(2)
        s.setGroupSeparatorShown(True)
        s.setSuffix(suffisso)
        tema.numero_vuoto(s, suggerimento)
        s.editingFinished.connect(lambda: self._salva_numero(campo, s.value()))
        return s

    def _salva_numero(self, campo: str, valore: float) -> None:
        self.repo.aggiorna_cantiere(**{campo: valore})
        if self.riepilogo is not None:
            self.riepilogo.aggiorna(self.repo)

    def _salva_descrizione(self) -> None:
        self.repo.aggiorna_cantiere(descrizione=self.descrizione.toPlainText())

    def salva_in_sospeso(self) -> None:
        # I campi salvano all'uscita dal campo: alla chiusura della finestra
        # potrebbe non accadere, quindi salviamo tutto qui.
        self._timer.stop()
        if not self._caricata:
            return
        self.repo.aggiorna_cantiere(
            **{campo: e.text() for campo, e in self.campi.items()},
            importo_lavori=self.importo.value(),
            costo_uomo_giorno=self.costo_ug.value(),
            descrizione=self.descrizione.toPlainText(),
        )

    def aggiorna(self) -> None:
        self._caricata = True
        c = self.repo.cantiere()
        for campo, e in self.campi.items():
            e.setText(c[campo])
        self.importo.setValue(c["importo_lavori"])
        self.costo_ug.setValue(c["costo_uomo_giorno"])
        self.descrizione.blockSignals(True)
        self.descrizione.setPlainText(c["descrizione"])
        self.descrizione.blockSignals(False)
        if self.riepilogo is not None:
            self.riepilogo.aggiorna(self.repo)


class PaginaSoggetti(Pagina):
    titolo = "Soggetti con compiti di sicurezza"
    voce = "Soggetti"
    icona = "soggetti"
    sezioni_controlli = ("Committente", "Soggetti")

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.committente_rl = QCheckBox("Il committente è anche responsabile dei lavori")
        self.committente_rl.setToolTip("Nei documenti il committente compare anche come responsabile dei lavori, "
                                       "senza dover inserire un responsabile dei lavori a parte.")
        self.committente_rl.toggled.connect(self._salva_committente_rl)
        self.layout_.addWidget(self.committente_rl)
        # ruoli che il programma sa necessari e che mancano, da aggiungere con un clic
        self.ruoli_mancanti = QHBoxLayout()
        self.ruoli_mancanti.setSpacing(6)
        self.nota_ruoli = QLabel()
        self.nota_ruoli.setObjectName("hint")
        self.nota_ruoli.setWordWrap(True)
        self.ruoli_mancanti.addWidget(self.nota_ruoli)
        self._pulsanti_ruoli: list[QPushButton] = []
        self.ruoli_mancanti.addStretch()
        self.layout_.addLayout(self.ruoli_mancanti)
        self.tabella = TabellaCrud(repo, "soggetti", [
            Colonna("ruolo", "Ruolo", "scelta", scelte=lambda: [(r, r) for r in RUOLI],
                    scelta_libera=True, larghezza=260),
            Colonna("nome", "Nominativo / ragione sociale", larghezza=210, vuota="da indicare"),
            Colonna("rappresentante", "Nella persona di", larghezza=170),
            Colonna("qualifica", "Qualifica", larghezza=140),
            Colonna("codice_fiscale", "Codice fiscale", larghezza=150),
            Colonna("partita_iva", "P. IVA", larghezza=110),
            Colonna("indirizzo", "Indirizzo", larghezza=200),
            Colonna("telefono", "Telefono", larghezza=110),
            Colonna("email", "Email", larghezza=170),
            Colonna("pec", "PEC", larghezza=170),
            Colonna("data_incarico", "Incarico dal", "data", larghezza=110,
                    suggerimento="Data di conferimento dell'incarico (coordinatori, responsabile dei lavori, "
                                 "progettista)"),
        ], elenco=["ruolo", "nome"], vuoto="Nessun soggetto inserito. Usa «Aggiungi» o «Prendi dall'archivio...».")
        self.tabella.imposta_titolo("Soggetti")
        self.tabella.modificata.connect(self._aggiorna_ruoli)
        self.tabella.aggiungi_pulsante("Prendi dall'archivio...", self._dall_archivio)
        self.tabella.aggiungi_pulsante("Salva in archivio", lambda: archivio_anagrafiche.salva_persona(
            self, self.repo, "soggetti", self.tabella.id_selezionato()))
        self.layout_.addWidget(self.tabella)

    def _dall_archivio(self) -> None:
        if (nuovo := archivio_anagrafiche.prendi_persona(self, self.repo, "soggetti")) is not None:
            self.tabella.ricarica()
            self.tabella.seleziona(nuovo)

    def _aggiorna_ruoli(self) -> None:
        for b in self._pulsanti_ruoli:
            b.deleteLater()
        self._pulsanti_ruoli.clear()
        presenti = {r["ruolo"] for r in self.tabella.righe() if r["nome"].strip() or r["ruolo"]}
        obblighi = analisi.obblighi(self.repo.elenco("imprese"), self.repo.elenco("fasi"))
        determinabile = bool(self.repo.elenco("imprese")) and bool(self.repo.elenco("fasi"))
        richiesti = [anagrafiche.COMMITTENTE, anagrafiche.CSP, anagrafiche.CSE]
        note = []
        if determinabile and not obblighi.psc:
            richiesti = [anagrafiche.COMMITTENTE]
            note.append("Coordinatori non necessari: una sola impresa esecutrice (art. 90, comma 3).")
        mancanti = [r for r in richiesti if r not in presenti]
        if mancanti:
            note.insert(0, "Da inserire:")
        self.nota_ruoli.setText(" ".join(note))
        tema.imposta_stato(self.nota_ruoli, "warning" if mancanti else None)
        self.nota_ruoli.setVisible(bool(note))
        for ruolo in mancanti:
            b = QPushButton(f"+ {ruolo.split(' (')[0]}")
            b.setToolTip(f"Aggiungi il {ruolo.lower()}")
            b.clicked.connect(lambda _=False, r=ruolo: self._aggiungi_ruolo(r))
            self.ruoli_mancanti.insertWidget(self.ruoli_mancanti.count() - 1, b)
            self._pulsanti_ruoli.append(b)

    def _aggiungi_ruolo(self, ruolo: str) -> None:
        nuovo = self.repo.inserisci("soggetti", ruolo=ruolo)
        self.tabella.ricarica()
        self.tabella.seleziona(nuovo)
        if self.tabella.dettaglio is not None:
            self.tabella.dettaglio.carica(nuovo)
            self.tabella.dettaglio.editori["nome"].setFocus()
        self._aggiorna_ruoli()

    def _salva_committente_rl(self, attivo: bool) -> None:
        self.repo.aggiorna_cantiere(committente_rl=int(attivo))

    def aggiorna(self) -> None:
        self.committente_rl.blockSignals(True)
        self.committente_rl.setChecked(bool(self.repo.cantiere()["committente_rl"]))
        self.committente_rl.blockSignals(False)
        self.tabella.ricarica()
        self._aggiorna_ruoli()


class PaginaImprese(Pagina):
    titolo = "Imprese, lavoratori e dati per il POS"
    voce = "Imprese e lavoratori"
    icona = "imprese"
    sezioni_controlli = ("Impresa", "Imprese", "Figure della sicurezza", "Lavoratori", "Testi del POS")
    # Schede di dettaglio mostrate dal programma: dati, figure, lavoratori, autonomi, idoneita, pos.
    schede_visibili: tuple[str, ...] = ("dati", "figure", "lavoratori", "autonomi", "idoneita", "pos")

    CAMPI_DATI = [
        (None, "Anagrafica"),
        ("forma_giuridica", "Forma giuridica", "scelta", anagrafiche.FORME_GIURIDICHE),
        ("codice_fiscale", "Codice fiscale"),
        ("cciaa", "Registro imprese / CCIAA (n. REA)"),
        ("ateco", "Codice ATECO / categoria ISTAT"),
        ("logo", "Logo dell'impresa (frontespizio del POS)", "immagine"),
        (None, "Dati dei lavori"),
        ("affidataria_id", "Impresa affidataria di riferimento", "impresa"),
        ("aut_subappalto", "Autorizzazione al subappalto (estremi)"),
        ("tipologia_lavori", "Tipologia dei lavori affidati"),
        ("importo_lavori", "Importo dei lavori da eseguire", "numero"),
        ("data_inizio", "Inizio dei lavori dell'impresa", "data"),
        ("data_fine", "Fine dei lavori dell'impresa", "data"),
        ("orario_lavoro", "Orario di lavoro in cantiere"),
        (None, "Consegna e verifica del POS (artt. 100 e 101 del D.Lgs. 81/2008)"),
        ("pos_rls_data", "Copia messa a disposizione del RLS il (almeno 10 giorni prima)", "data"),
        ("pos_affidataria_data", "Trasmesso all'impresa affidataria il", "data"),
        ("pos_cse_data", "Trasmesso al coordinatore per l'esecuzione il", "data"),
        ("pos_esito_data", "Esito positivo delle verifiche il", "data"),
        (None, "Soggetto incaricato dall'impresa affidataria (art. 97 del D.Lgs. 81/2008)"),
        ("incaricato_97", "Nominativo"),
        ("incaricato_97_mansione", "Mansione"),
        (None, "Sede legale e recapiti"),
        ("indirizzo", "Indirizzo"),
        ("cap", "CAP"),
        ("comune", "Comune"),
        ("provincia", "Provincia"),
        ("fax", "Fax"),
        ("email", "Email"),
        ("pec", "PEC"),
        ("recapito_cantiere", "Ufficio o recapito in cantiere"),
        (None, "Posizioni assicurative e contratto"),
        ("inail", "Posizione INAIL (codice ditta / PAT)"),
        ("inps", "Matricola INPS"),
        ("cassa_edile", "Cassa edile (cassa e codice impresa)"),
        ("ccnl", "Contratto collettivo applicato", "scelta", anagrafiche.CCNL),
        ("organico", "Organico medio annuo"),
        ("durc_scadenza", "DURC valido fino al", "data"),
        (None, "Qualificazione"),
        ("dvr_data", "Data del documento di valutazione dei rischi", "data"),
        ("soa", "Attestazione SOA (categorie e classifiche)"),
        ("certificazioni", "Certificazioni (ISO 9001, ISO 45001, ...)"),
    ]

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.tabella = TabellaCrud(repo, "imprese", [
            Colonna("ragione_sociale", "Ragione sociale", larghezza=240),
            Colonna("tipo", "Tipologia", "scelta", scelte=lambda: [(t, t) for t in TIPI_IMPRESA],
                    scelta_libera=True, larghezza=200),
            Colonna("partita_iva", "P. IVA", larghezza=120, vuota="da indicare"),
            Colonna("referente", "Referente", larghezza=150),
            Colonna("telefono", "Telefono"),
        ])
        self.tabella.imposta_titolo("Imprese")
        self.tabella.aggiungi_pulsante("Prendi dall'archivio...", self._impresa_dall_archivio)
        self.tabella.aggiungi_pulsante("Salva in archivio", lambda: archivio_anagrafiche.salva_impresa(
            self, self.repo, self.tabella.id_selezionato()))

        self.dati = ModuloRecord(repo, "imprese", self.CAMPI_DATI)
        self.dati.campi["provincia"].setMaxLength(2)
        scorrimento_dati = QScrollArea()
        scorrimento_dati.setWidgetResizable(True)
        scorrimento_dati.setWidget(self.dati)

        # Datore di lavoro e figure della sicurezza (Allegato XV 3.2.1 lett. a e b).
        self.figure = ModuloRecord(repo, "imprese", [
            ("datore_lavoro", "Datore di lavoro"),
            ("rspp_datore", "Il datore di lavoro svolge direttamente i compiti di RSPP (art. 34 del D.Lgs. 81/2008)", "spunta"),
            ("ruoli_datore", "Il datore di lavoro svolge anche il ruolo di", "spunte", anagrafiche.RUOLI_DATORE),
            ("figure_non_presenti", "Figure non presenti in questa impresa", "spunte",
             list(anagrafiche.FIGURE_FACOLTATIVE)),
            ("figure_motivazione", "Motivazione (se vuota, si usa una formula predefinita)", "testo_lungo"),
        ])
        self.elenco_figure = TabellaCrud(repo, "figure", [
            Colonna("ruolo", "Figura", "scelta", scelte=lambda: [(r, r) for r in anagrafiche.FIGURE_IMPRESA],
                    scelta_libera=True, larghezza=230),
            Colonna("nome", "Nominativo", larghezza=180),
            Colonna("qualifica", "Qualifica", larghezza=140),
            Colonna("codice_fiscale", "Codice fiscale", larghezza=150),
            Colonna("telefono", "Telefono", larghezza=110),
            Colonna("email", "Email", larghezza=160),
            Colonna("formazione", "Corso / attestato", larghezza=200),
            Colonna("formazione_scadenza", "Aggiornamento entro", "data"),
        ], valori_nuovo=lambda: {"ruolo": "Preposto"}, elenco=["ruolo", "nome"])
        self.elenco_figure.imposta_filtro(impresa_id=-1)
        self.elenco_figure.aggiungi_pulsante("Prendi dall'archivio...", self._figura_dall_archivio)
        self.elenco_figure.aggiungi_pulsante("Salva in archivio", lambda: archivio_anagrafiche.salva_persona(
            self, self.repo, "figure", self.elenco_figure.id_selezionato()))
        self.figure.campi["figure_motivazione"].setFixedHeight(46)
        contenuto_figure = QWidget()
        lf = QVBoxLayout(contenuto_figure)
        lf.addWidget(self.figure)
        aiuto = QLabel("Inserisci una riga per ogni persona e per ogni ruolo: RSPP, medico competente, RLS o RLST, "
                       "preposti, direttore tecnico, capocantiere, addetti al primo soccorso e antincendio. Se una "
                       "persona ricopre più ruoli (per esempio capocantiere e addetto al primo soccorso), inserisci "
                       "una riga per ciascun ruolo con lo stesso nominativo; i ruoli svolti dal datore di lavoro "
                       "si spuntano qui sopra.")
        aiuto.setObjectName("pageSubtitle")
        aiuto.setWordWrap(True)
        lf.addWidget(aiuto)
        self.elenco_figure.setMinimumHeight(260)
        lf.addWidget(self.elenco_figure, 1)
        # con la finestra bassa la scheda scorre invece di schiacciare caselle e tabella
        pannello_figure = QScrollArea()
        pannello_figure.setWidgetResizable(True)
        pannello_figure.setFrameShape(QFrame.Shape.NoFrame)
        pannello_figure.setWidget(contenuto_figure)

        self.lavoratori = PannelloLavoratori(repo)
        self.autonomi = PannelloLavoratori(repo, autonomi=True)
        self.testi_pos = TestiLiberi(repo, SEZIONI_POS, altezza=80, contesto_ai=self._contesto_ai)
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setWidget(self.testi_pos)

        from sicurcantiere.ui.idoneita import PannelloIdoneita

        self.idoneita = PannelloIdoneita(repo)
        self.schede = QTabWidget()
        for chiave, widget, titolo in (("dati", scorrimento_dati, "Dati dell'impresa"),
                                       ("figure", pannello_figure, "Figure della sicurezza"),
                                       ("lavoratori", self.lavoratori, "Maestranze"),
                                       ("autonomi", self.autonomi, "Lavoratori autonomi"),
                                       ("idoneita", self.idoneita, "Idoneità e patente"),
                                       ("pos", scorrimento, "Testi del POS")):
            if chiave in self.schede_visibili:
                self.schede.addTab(widget, titolo)
        self.schede.setEnabled(False)
        self.schede.setParent(self)
        self.schede.setVisible(bool(self.schede_visibili))
        self.schede.setTabBarAutoHide(True)  # una scheda sola: niente barra che sembra incompleta
        # Le schede non mostrate restano figlie della pagina: senza un genitore
        # Qt le distruggerebbe mentre la pagina le usa ancora.
        for w in (scorrimento_dati, pannello_figure, self.lavoratori, self.autonomi, self.idoneita, scorrimento):
            if w.parent() is None:
                w.setParent(self)
                w.hide()

        divisore = QSplitter(Qt.Orientation.Vertical)
        divisore.addWidget(self.tabella)
        divisore.addWidget(self.schede)
        divisore.setSizes([220, 480])
        self.layout_.addWidget(divisore)
        self.tabella.selezione_cambiata.connect(self._impresa_selezionata)

    def _impresa_dall_archivio(self) -> None:
        if (nuova := archivio_anagrafiche.prendi_impresa(self, self.repo)) is not None:
            self.tabella.ricarica()
            self.tabella.seleziona(nuova)

    def _figura_dall_archivio(self) -> None:
        impresa = self.tabella.id_selezionato()
        if impresa is not None and archivio_anagrafiche.prendi_persona(
                self, self.repo, "figure", impresa_id=impresa) is not None:
            self.elenco_figure.ricarica()

    def _contesto_ai(self) -> str:
        id_ = self.tabella.id_selezionato()
        impresa = self.repo.leggi("imprese", id_) if id_ is not None else None
        if impresa is None:
            return contesto_cantiere(self.repo)
        fasi = self.repo.elenco("fasi", impresa_id=id_)
        lavoratori = self.repo.elenco("lavoratori", impresa_id=id_)
        mansioni = Counter(l["mansione"] or "mansione non indicata" for l in lavoratori)
        righe = [
            f"Impresa che redige il POS: {impresa['tipo'] or 'impresa esecutrice'}",
            f"Orario di lavoro: {impresa['orario_lavoro'] or 'non indicato'}",
            f"Tipologia dei lavori: {impresa['tipologia_lavori'] or 'non indicata'}",
            "Lavorazioni dell'impresa: " + "; ".join(f"{f['codice']} {f['descrizione']}" for f in fasi),
            f"Lavoratori: {len(lavoratori)} (" + ", ".join(f"{n} {m}" for m, n in mansioni.items()) + ")",
        ]
        return contesto_cantiere(self.repo) + "\n\n" + "\n".join(righe)

    def _impresa_selezionata(self, id_: int | None) -> None:
        self.schede.setEnabled(id_ is not None)
        self.dati.carica(id_)
        self.figure.carica(id_)
        self.elenco_figure.imposta_filtro(impresa_id=id_ if id_ is not None else -1)
        self.lavoratori.imposta_impresa(id_)
        self.autonomi.imposta_impresa(id_)
        self.idoneita.imposta_impresa(id_)
        self.testi_pos.carica(lambda s, i=id_ if id_ is not None else -1: chiave_testo(i, s))

    def salva_in_sospeso(self) -> None:
        self.dati.salva_in_sospeso()
        self.figure.salva_in_sospeso()
        self.lavoratori.salva_in_sospeso()
        self.autonomi.salva_in_sospeso()
        self.idoneita.salva_in_sospeso()
        self.testi_pos.salva_in_sospeso()

    def aggiorna(self) -> None:
        self.tabella.ricarica()
        self.tabella.seleziona_prima()


def _valida_fase(fase: dict) -> str | None:
    inizio, fine = analisi.data(fase.get("data_inizio")), analisi.data(fase.get("data_fine"))
    if inizio and fine and fine < inizio:
        return "La data di fine non può precedere la data di inizio."
    return None


class DialogoArchivio(QDialog):
    """Archivio delle lavorazioni per tipologia di intervento e categoria, più quelle dell'utente."""

    TUTTE = "Tutte le tipologie"

    def __init__(self, genitore: QWidget | None = None):
        super().__init__(genitore)
        self.setWindowTitle("Importa lavorazioni dall'archivio")
        self.resize(700, 600)
        self.tipologia = QComboBox()
        self.tipologia.addItems([self.TUTTE] + TIPOLOGIE)
        self.tipologia.currentIndexChanged.connect(self._popola)
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Cerca una lavorazione...")
        self.filtro.textChanged.connect(self._filtra)
        self.albero = QTreeWidget()
        self.albero.setHeaderLabels(["Lavorazione", "Macchine e attrezzi"])
        self.albero.setColumnWidth(0, 380)
        self._spuntate: set[str] = set()
        self.albero.itemChanged.connect(self._ricorda)
        elimina = QPushButton("Elimina dalle lavorazioni personalizzate")
        elimina.clicked.connect(self._elimina_utente)
        pulsanti = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        pulsanti.accepted.connect(self.accept)
        pulsanti.rejected.connect(self.reject)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("Tipologia:"))
        riga.addWidget(self.tipologia, 1)
        basso = QHBoxLayout()
        basso.addWidget(elimina)
        basso.addStretch()
        basso.addWidget(pulsanti)
        layout = QVBoxLayout(self)
        layout.addLayout(riga)
        layout.addWidget(QLabel("Seleziona le lavorazioni da aggiungere al cantiere:"))
        layout.addWidget(self.filtro)
        layout.addWidget(self.albero)
        layout.addLayout(basso)
        self._popola()

    @staticmethod
    def _chiave(dati: dict) -> str:
        return ("utente:" + str(dati["id"])) if "dati" in dati else ("base:" + dati["codice"])

    def _popola(self) -> None:
        self.albero.blockSignals(True)
        self.albero.clear()
        tipologia = self.tipologia.currentText()
        for categoria, lavorazioni in per_categoria(None if tipologia == self.TUTTE else tipologia).items():
            nodo = QTreeWidgetItem(self.albero, [categoria])
            gruppi: dict[str, QTreeWidgetItem] = {}
            for lav in lavorazioni:
                padre = nodo
                if lav["gruppo"]:
                    if lav["gruppo"] not in gruppi:
                        gruppi[lav["gruppo"]] = QTreeWidgetItem(nodo, [lav["gruppo"]])
                    padre = gruppi[lav["gruppo"]]
                self._foglia(padre, f"{lav['codice']}  {lav['descrizione']}", ", ".join(lav["attrezzature"]), lav)
        archivio = ArchivioAnagrafiche()
        try:
            utente = archivio.elenco(LAVORAZIONE)
        finally:
            archivio.chiudi()
        nodo = QTreeWidgetItem(self.albero, ["Lavorazioni personalizzate"])
        font = nodo.font(0)
        font.setBold(True)
        nodo.setFont(0, font)
        if not utente:
            vuoto = QTreeWidgetItem(nodo, ["(nessuna: per aggiungerne, usa «Salva nell'archivio utente» nella tabella delle fasi)"])
            vuoto.setDisabled(True)
        for voce in utente:
            self._foglia(nodo, voce["nome"], ", ".join(a["nome"] for a in voce["dati"].get("attrezzature", [])), voce)
        self.albero.expandAll()
        self.albero.blockSignals(False)
        self._filtra(self.filtro.text())

    def _foglia(self, nodo: QTreeWidgetItem, testo: str, attrezzi: str, dati: dict) -> None:
        item = QTreeWidgetItem(nodo, [testo, attrezzi])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if self._chiave(dati) in self._spuntate
                           else Qt.CheckState.Unchecked)
        item.setData(0, Qt.ItemDataRole.UserRole, dati)

    def _ricorda(self, item: QTreeWidgetItem, _colonna: int) -> None:
        dati = item.data(0, Qt.ItemDataRole.UserRole)
        if dati:
            chiave = self._chiave(dati)
            if item.checkState(0) == Qt.CheckState.Checked:
                self._spuntate.add(chiave)
            else:
                self._spuntate.discard(chiave)

    def _foglie(self, nodo: QTreeWidgetItem | None = None):
        """Coppie (nodo padre, lavorazione) a qualsiasi livello dell'albero."""
        figli = ([self.albero.topLevelItem(i) for i in range(self.albero.topLevelItemCount())] if nodo is None
                 else [nodo.child(j) for j in range(nodo.childCount())])
        for figlio in figli:
            if figlio.data(0, Qt.ItemDataRole.UserRole):
                yield nodo, figlio
            else:
                yield from self._foglie(figlio)

    def _filtra(self, testo: str) -> None:
        testo = testo.lower().strip()

        def filtra(item: QTreeWidgetItem) -> bool:
            if item.data(0, Qt.ItemDataRole.UserRole):
                mostra = not testo or testo in item.text(0).lower() or testo in item.text(1).lower()
            else:
                risultati = [filtra(item.child(j)) for j in range(item.childCount())]
                mostra = not testo or any(risultati) or testo in item.text(0).lower()
            item.setHidden(not mostra)
            return mostra

        for i in range(self.albero.topLevelItemCount()):
            filtra(self.albero.topLevelItem(i))

    def _elimina_utente(self) -> None:
        item = self.albero.currentItem()
        dati = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not dati or "dati" not in dati:
            QMessageBox.information(self, "Archivio", "Seleziona una delle lavorazioni personalizzate.")
            return
        if QMessageBox.question(self, "Archivio", f"Vuoi eliminare «{dati['nome']}» dalle lavorazioni personalizzate?") \
                == QMessageBox.StandardButton.Yes:
            archivio = ArchivioAnagrafiche()
            try:
                archivio.elimina(dati["id"])
            finally:
                archivio.chiudi()
            self._spuntate.discard(self._chiave(dati))
            self._popola()

    def selezionate(self) -> list[dict]:
        return [item.data(0, Qt.ItemDataRole.UserRole) for _, item in self._foglie()
                if item.checkState(0) == Qt.CheckState.Checked]


class PannelloFaseGantt(QFrame):
    """Dettaglio della fase scelta nel cronoprogramma, con i collegamenti alle sue schede."""

    def __init__(self, pagina: PaginaFasi):
        super().__init__()
        self.pagina = pagina
        self.setObjectName("card")
        self.titolo = QLabel()
        self.titolo.setObjectName("sectionTitle")
        self.titolo.setWordWrap(True)
        self.dati = QLabel()
        self.dati.setWordWrap(True)
        self.dati.setObjectName("pageSubtitle")
        self.zona = QLabel()
        self.zona.setObjectName("hint")
        self.zona.setWordWrap(True)
        tema.imposta_stato(self.zona, "warning")
        self.collegamenti: list[QPushButton] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(self.titolo)
        layout.addWidget(self.dati)
        layout.addWidget(self.zona)
        regola = QFrame()
        regola.setObjectName("navRule")
        layout.addWidget(regola)
        for indice, nome in ((0, "Descrizione"), (2, "Rischi e misure"), (3, "Macchine e attrezzi"), (-1, "Interferenze")):
            b = QPushButton(nome)
            b.setObjectName("linkButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=indice: self._apri(i))
            layout.addWidget(b, alignment=Qt.AlignmentFlag.AlignLeft)
            self.collegamenti.append(b)
        layout.addStretch()
        aiuto = QLabel("Trascina una barra per spostare la fase; trascinane il bordo destro per cambiarne la durata.")
        aiuto.setObjectName("hint")
        aiuto.setWordWrap(True)
        layout.addWidget(aiuto)
        self.vuoto = QLabel("Fai clic su una fase del cronoprogramma per vederne i dati.")
        self.vuoto.setObjectName("hint")
        self.vuoto.setWordWrap(True)
        layout.insertWidget(0, self.vuoto)

    def _apri(self, indice: int) -> None:
        if indice < 0:
            vai = getattr(self.window(), "vai_a_sezione", None)
            if vai is not None:
                vai("Interferenze")
            return
        self.pagina.apri_scheda_fase(indice)

    def mostra(self, id_: int | None) -> None:
        fase = self.pagina.repo.leggi("fasi", id_) if id_ is not None else None
        for w in (self.titolo, self.dati, *self.collegamenti):
            w.setVisible(fase is not None)
        self.vuoto.setVisible(fase is None)
        self.zona.setVisible(fase is not None and not (fase["zona"] or "").strip())
        if fase is None:
            return
        repo = self.pagina.repo
        impresa = repo.leggi("imprese", fase["impresa_id"]) if fase["impresa_id"] else None
        inizio, fine = analisi.data(fase["data_inizio"]), analisi.data(fase["data_fine"])
        righe = [f"Impresa: {impresa['ragione_sociale'] if impresa else 'da definire'}"]
        righe.append(f"Dal {inizio:%d/%m/%Y} al {fine:%d/%m/%Y}" if inizio and fine else "Date da indicare")
        ug = analisi.uomini_giorno([fase])
        righe.append(f"Squadra: {fase['lavoratori'] or 0} · uomini-giorno: {ug or 0}")
        if fase["zona"]:
            righe.append(f"Zona: {fase['zona']}")
        self.titolo.setText(f"{fase['codice']} {fase['descrizione']}".strip())
        self.dati.setText("\n".join(righe))
        self.zona.setText("Zona non indicata: senza zona la fase interferisce con tutte quelle contemporanee. "
                          "Indicala nella vista «Elenco», scheda «Descrizione».")
        rischi = [r for r in repo.rischi(fase_id=fase["id"]) if not r["non_presente"]]
        attrezzature = repo.elenco("attrezzature", fase_id=fase["id"])
        interferenze = [i for i in self.pagina.gantt.interferenze if fase["id"] in (i.fase_a["id"], i.fase_b["id"])]
        for b, testo in zip(self.collegamenti, ("Descrizione ›", f"Rischi e misure ({len(rischi)}) ›",
                                                f"Macchine e attrezzi ({len(attrezzature)}) ›",
                                                f"Interferenze ({len(interferenze)}) ›")):
            b.setText(testo)


def scegli_da_elenco(genitore: QWidget, titolo: str, domanda: str, voci: list[str]) -> str | None:
    """Scelta di una voce da un elenco lungo, con la ricerca mentre si scrive."""
    dialogo = QDialog(genitore)
    dialogo.setWindowTitle(titolo)
    dialogo.resize(520, 520)
    cerca = QLineEdit()
    cerca.setPlaceholderText("Scrivi per cercare...")
    cerca.setClearButtonEnabled(True)
    elenco = QListWidget()
    elenco.addItems(voci)
    elenco.setCurrentRow(0)

    def filtra(testo: str) -> None:
        parole = testo.lower().split()
        primo = None
        for i in range(elenco.count()):
            voce = elenco.item(i)
            visibile = all(p in voce.text().lower() for p in parole)
            voce.setHidden(not visibile)
            if visibile and primo is None:
                primo = voce
        if primo is not None:
            elenco.setCurrentItem(primo)

    cerca.textChanged.connect(filtra)
    cerca.returnPressed.connect(dialogo.accept)
    elenco.itemDoubleClicked.connect(lambda _: dialogo.accept())
    pulsanti = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    pulsanti.button(QDialogButtonBox.StandardButton.Ok).setText("Aggiungi")
    pulsanti.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
    pulsanti.accepted.connect(dialogo.accept)
    pulsanti.rejected.connect(dialogo.reject)
    layout = QVBoxLayout(dialogo)
    etichetta = QLabel(domanda)
    etichetta.setWordWrap(True)
    layout.addWidget(etichetta)
    layout.addWidget(cerca)
    layout.addWidget(elenco, 1)
    layout.addWidget(pulsanti)
    if dialogo.exec() != QDialog.DialogCode.Accepted or elenco.currentItem() is None \
            or elenco.currentItem().isHidden():
        return None
    return elenco.currentItem().text()


def _rischio_da_valutare(r: dict) -> bool:
    """Rischio che richiede una valutazione specifica (rumore, vibrazioni, movimentazione...) ancora non collegata."""
    from sicurcantiere.valutazioni.automatiche import gruppo_rischio

    return not r["non_presente"] and not r["valutazione_id"] and gruppo_rischio(r["descrizione"]) is not None


class PaginaFasi(Pagina):
    titolo = "Fasi di lavoro e cronoprogramma (Gantt analitico)"
    voce = "Fasi e cronoprogramma"
    icona = "fasi"
    sezioni_controlli = ("Fasi", "Lavorazioni", "Rischi")
    # Nel PSC importi, squadre, date e Gantt delle fasi; nel POS non servono.
    cronoprogramma = True

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.fasi = TabellaCrud(repo, "fasi", [
            Colonna("lavorazione", "Lavorazione (gruppo di fasi)", "scelta", scelta_libera=True, larghezza=210,
                    scelte=lambda: [(g, g) for g in sorted({f["lavorazione"] for f in self.repo.elenco("fasi")
                                                             if f["lavorazione"]})],
                    suggerimento="La lavorazione più ampia di cui la fase fa parte, per esempio «Strutture in "
                                 "elevazione in c.a.»: raggruppa più fasi sotto un unico titolo nel POS. "
                                 "Facoltativa: per una fase isolata puoi lasciarla vuota."),
            Colonna("descrizione", "Fase di lavoro (attività svolta)", larghezza=280,
                    suggerimento="L'attività concreta, con i suoi rischi, macchine e lavoratori, per esempio "
                                 "«Getto del calcestruzzo di pilastri e travi con autopompa»."),
            Colonna("impresa_id", "Impresa", "scelta", scelte=self._imprese, larghezza=170, vuota="da assegnare"),
        ] + ([
            Colonna("zona", "Zona", larghezza=90),
            Colonna("importo", "Importo €", "decimale", larghezza=100),
            Colonna("incidenza_manodopera", "Manodopera %", "decimale", massimo=100, larghezza=115),
            Colonna("lavoratori", "Squadra", "intero", minimo=0, massimo=999, larghezza=65),
            Colonna("data_inizio", "Inizio", "data", larghezza=95),
            Colonna("data_fine", "Fine", "data", larghezza=95),
            Colonna("uomini_giorno", "Uomini-giorno", "calcolata",
                    calcola=lambda f: str(analisi.uomini_giorno([f]) or "")),
        ] if self.cronoprogramma else []), valida=_valida_fase,
            valori_nuovo=lambda: {"codice": self.repo.codice_automatico()})
        # il codice delle fasi lo assegna il programma: si aggiorna quando si indica la lavorazione
        self.fasi.modificata.connect(self._aggiorna_codici)
        self.fasi.imposta_titolo("Fasi di lavoro")
        archivio = primario(QPushButton("Importa dall'archivio..."))
        archivio.clicked.connect(self._importa)
        self.fasi.pulsanti.insertWidget(2, archivio)
        if self.cronoprogramma:
            calcola = QPushButton("Calcola la durata")
            calcola.setToolTip("Calcola la data di fine in base a importo, incidenza della manodopera, squadra e costo uomo-giorno.")
            calcola.clicked.connect(self._calcola_durata)
            self.fasi.pulsanti.insertWidget(3, calcola)
        self.fasi.aggiungi_pulsante("Salva nell'archivio utente", self._salva_in_archivio)

        self.rischi = TabellaCrud(repo, "rischi", [
            Colonna("descrizione", "Rischio", "testo_lungo", larghezza=220),
            Colonna("fonte", "Origine (lavorazione o attrezzatura)", larghezza=200),
            Colonna("probabilita", "P", "intero", minimo=1, massimo=4, larghezza=40),
            Colonna("danno", "D", "intero", minimo=1, massimo=4, larghezza=40),
            Colonna("livello", "Livello P×D", "calcolata", larghezza=130, disegno=tema.DelegatoLivello,
                    calcola=lambda r: "" if r["non_presente"]
                    else str(analisi.livello_rischio(r["probabilita"], r["danno"]))),
            Colonna("misure", "Misure di prevenzione e protezione", "testo_lungo"),
            Colonna("dpi", "DPI", "dpi", larghezza=200),
            Colonna("valutazione_id", "Valutazione specifica", "scelta", scelte=self._valutazioni, larghezza=200),
            Colonna("non_presente", "Non presente", "spunta", larghezza=95, suggerimento=(
                "Spunta se il rischio, pur valutato, non è presente nella fase (per esempio macchina "
                "silenziata o lavorazione che non lo comporta): resta escluso da valutazioni specifiche, "
                "segnaletica e DPI e nel POS compare con la motivazione.")),
            Colonna("motivazione", "Motivazione (se non presente)", "testo_lungo", larghezza=180),
        ], elenco=["descrizione", "livello"], vuoto="Nessun rischio per questa fase: importa la lavorazione "
                                                      "dall'archivio o usa «Suggerisci i rischi con l'AI».")
        self.rischi.aggiungi_filtri([
            ("Tutti", None),
            ("Alti e molto alti", lambda r: not r["non_presente"]
             and analisi.livello_rischio(r["probabilita"], r["danno"]) >= 6),
            ("Da valutare", _rischio_da_valutare),
        ])
        self.rischi.modificata.connect(self._aggiorna_gantt)
        suggerisci = pulsante_ai("Suggerisci i rischi con l'AI")
        suggerisci.clicked.connect(self._suggerisci_rischi)
        self.rischi.pulsanti.insertWidget(2, suggerisci)

        self.attrezzature = TabellaCrud(repo, "attrezzature", [
            Colonna("tipo", "Tipo", "scelta", scelte=lambda: [(t, t) for t in TIPI_ATTREZZATURA],
                    larghezza=160),
            Colonna("nome", "Nome", "scelta", scelta_libera=True, larghezza=200,
                    scelte=lambda: [(n, n) for n in sorted(ATTREZZATURE)]),
            Colonna("descrizione", "Descrizione", "testo_lungo"),
            Colonna("misure", "Misure prima, durante e dopo l'uso", "testo_lungo"),
            Colonna("dpi", "DPI dell'operatore", "testo_lungo"),
            Colonna("potenza_sonora", "Potenza sonora dB(A)", "decimale", larghezza=130, massimo=200,
                    suggerimento="Livello di potenza sonora LWA dichiarato dal fabbricante (art. 190 del D.Lgs. 81/2008): "
                                 "compare nella tabella del rumore del PSC"),
        ], elenco=["tipo", "nome"], vuoto="Nessuna macchina o attrezzatura per questa fase.")
        # un solo «Aggiungi dall'archivio...» con ricerca; le azioni dell'assistente in un menu
        self.scelta_archivio = QComboBox(self)  # attrezzatura scelta dall'archivio (non mostrata)
        self.scelta_archivio.addItems(sorted(ATTREZZATURE))
        self.scelta_archivio.hide()
        aggiungi_archivio = QPushButton("Aggiungi dall'archivio...")
        aggiungi_archivio.setToolTip("Cerca una macchina, un attrezzo o un'opera provvisionale nell'archivio e "
                                     "aggiungila alla fase con i suoi rischi.")
        aggiungi_archivio.clicked.connect(self._cerca_attrezzatura)
        self.attrezzature.pulsanti.insertWidget(2, aggiungi_archivio)
        self.attrezzature.modificata.connect(self._rischi_delle_attrezzature)
        assistente = pulsante_ai("Assistente AI")
        menu_ai = QMenu(assistente)
        suggerisci = menu_ai.addAction("Suggerisci macchine e attrezzi per la fase")
        suggerisci.setToolTip("Proponi macchine, attrezzi e opere provvisionali per la fase, con scheda d'uso e "
                              "rischi, compresi rumore, vibrazioni e movimentazione dei carichi.")
        suggerisci.triggered.connect(lambda: self._suggerisci_attrezzature())
        completa = menu_ai.addAction("Completa la scheda e i rischi dell'attrezzatura selezionata")
        completa.triggered.connect(lambda: self._completa_attrezzatura())
        menu_ai.setToolTipsVisible(True)
        assistente.setMenu(menu_ai)
        self.attrezzature.pulsanti.insertWidget(self.attrezzature.pulsanti.count() - 1, assistente)

        self.descrizione_fase = ModuloRecord(repo, "fasi", ([
            (None, "Dati per il cronoprogramma"),
            ("zona", "Zona di lavoro"),
            ("lavoratori", "Squadra (lavoratori)", "intero"),
            ("importo", "Importo dei lavori della fase", "numero"),
            ("incidenza_manodopera", "Incidenza della manodopera", "decimale", " %"),
            (None, "Descrizione e organizzazione"),
        ] if self.cronoprogramma else []) + [
            ("dettaglio", "Descrizione dell'attività", "testo_lungo"),
            ("addetto", "Lavoratori impegnati (addetto)"),
            ("modalita", "Modalità organizzative", "testo_lungo"),
            ("turni", "Turni di lavoro", "testo_lungo"),
            ("procedure_psc", "Procedure complementari richieste dal PSC", "testo_lungo"),
        ])
        self.descrizione_fase.salvato = self._dati_fase_salvati
        scorrimento_descrizione = QScrollArea()
        scorrimento_descrizione.setWidgetResizable(True)
        scorrimento_descrizione.setWidget(self.descrizione_fase)
        self.struttura = StrutturaFase(repo)

        self.dettaglio = QTabWidget()
        self.dettaglio.addTab(scorrimento_descrizione, "Descrizione e organizzazione")
        self.dettaglio.addTab(self.struttura, "Struttura")
        self.dettaglio.addTab(self.rischi, "Rischi e misure")
        self.dettaglio.addTab(self.attrezzature, "Macchine, attrezzi e opere provvisionali")
        self.dettaglio.setEnabled(False)
        self.dettaglio.currentChanged.connect(lambda _i: self._aggiorna_struttura())

        self.gantt = Gantt()
        self.gantt.fase_modificata.connect(self._fase_trascinata)
        self.gantt.fase_cliccata.connect(self._fase_dal_gantt)
        scorrimento = QScrollArea()
        scorrimento.setWidget(self.gantt)
        scorrimento.setWidgetResizable(False)
        self.zoom = QComboBox()
        self.zoom.addItems(list(ZOOM))
        self.zoom.setCurrentText(ZOOM_PREDEFINITO)
        self.zoom.currentTextChanged.connect(self.gantt.imposta_zoom)

        divisore = QSplitter(Qt.Orientation.Vertical)
        divisore.addWidget(self.fasi)
        divisore.addWidget(self.dettaglio)
        divisore.setSizes([260, 460])
        if not self.cronoprogramma:
            # Il cronoprogramma resta figlio della pagina (nascosto) per non essere distrutto.
            scorrimento.setParent(self)
            scorrimento.hide()
            self.layout_.addWidget(divisore)
        else:
            # nell'elenco solo lavorazione, fase, impresa, date e uomini-giorno: il resto nel dettaglio
            for n, col in enumerate(self.fasi.colonne):
                if col.campo in ("zona", "importo", "incidenza_manodopera", "lavoratori"):
                    self.fasi.vista.setColumnHidden(n, True)
            # due viste: elenco con il dettaglio della fase, cronoprogramma a tutta altezza
            self.vista_elenco = QPushButton("Elenco")
            self.vista_crono = QPushButton("Cronoprogramma")
            for b in (self.vista_elenco, self.vista_crono):
                b.setCheckable(True)
                b.setObjectName("segment")
            self.vista_elenco.clicked.connect(lambda: self._mostra_vista(0))
            self.vista_crono.clicked.connect(lambda: self._mostra_vista(1))
            barra = QHBoxLayout()
            barra.setSpacing(0)
            barra.addWidget(self.vista_elenco)
            barra.addWidget(self.vista_crono)
            barra.addStretch()
            self.etichetta_zoom = QLabel("Scala:")
            barra.addWidget(self.etichetta_zoom)
            barra.addSpacing(6)
            barra.addWidget(self.zoom)
            self.layout_.addLayout(barra)

            self.pannello_fase = PannelloFaseGantt(self)
            crono = QSplitter(Qt.Orientation.Horizontal)
            crono.setChildrenCollapsible(False)
            crono.addWidget(scorrimento)
            crono.addWidget(self.pannello_fase)
            crono.setStretchFactor(0, 1)
            self.pannello_fase.setFixedWidth(300)
            self.viste = QStackedWidget()
            self.viste.addWidget(divisore)
            self.viste.addWidget(crono)
            self.layout_.addWidget(self.viste, 1)
            self._mostra_vista(1 if QSettings().value("fasi/vista", 0, type=int) == 1 else 0)

        self.fasi.selezione_cambiata.connect(self._fase_selezionata)
        self.fasi.modificata.connect(self._aggiorna_gantt)

    def _imprese(self) -> list[tuple[int | None, str]]:
        return [(None, "(da definire)")] + [
            (i["id"], i["ragione_sociale"] or f"Impresa {i['id']}") for i in self.repo.elenco("imprese")
        ]

    def _valutazioni(self) -> list[tuple[int | None, str]]:
        from sicurcantiere.valutazioni import METODI

        return [(None, "—")] + [
            (v["id"], v["titolo"] or (METODI[v["metodo"]].nome if v["metodo"] in METODI else v["metodo"]))
            for v in self.repo.elenco("valutazioni")
        ]

    def _fase_selezionata(self, id_: int | None) -> None:
        self.dettaglio.setEnabled(id_ is not None)
        filtro = id_ if id_ is not None else -1
        self.descrizione_fase.carica(id_)
        self.rischi.imposta_filtro(fase_id=filtro)
        self.attrezzature.imposta_filtro(fase_id=filtro)
        fase = self.repo.leggi("fasi", id_) if id_ is not None else None
        nome = f"{fase['codice']} {fase['descrizione']}".strip() if fase else ""
        self.rischi.imposta_titolo(nome)
        self.attrezzature.imposta_titolo(nome)
        self._aggiorna_struttura()
        self.gantt.seleziona(id_)
        if self.cronoprogramma:
            self.pannello_fase.mostra(id_)

    def _mostra_vista(self, indice: int) -> None:
        self.viste.setCurrentIndex(indice)
        self.vista_elenco.setChecked(indice == 0)
        self.vista_crono.setChecked(indice == 1)
        self.zoom.setVisible(indice == 1)
        self.etichetta_zoom.setVisible(indice == 1)
        QSettings().setValue("fasi/vista", indice)
        if indice == 1:
            self.pannello_fase.mostra(self.fasi.id_selezionato())

    def apri_scheda_fase(self, indice: int) -> None:
        """Dal pannello del cronoprogramma alla scheda della fase (descrizione, rischi, macchine)."""
        if self.cronoprogramma:
            self._mostra_vista(0)
        self.dettaglio.setCurrentIndex(indice)

    def _fase_dal_gantt(self, id_: int) -> None:
        self.fasi.seleziona(id_)

    def _dati_fase_salvati(self, campo: str) -> None:
        if campo in ("zona", "lavoratori", "importo", "incidenza_manodopera"):
            self.fasi.ricarica()
            self._aggiorna_gantt()

    def _aggiorna_struttura(self) -> None:
        if self.dettaglio.currentWidget() is self.struttura:
            self.struttura.mostra(self.fasi.id_selezionato())

    def salva_in_sospeso(self) -> None:
        self.descrizione_fase.salva_in_sospeso()

    def _aggiorna_codici(self) -> None:
        """Le fasi create a mano (sigla «UT») prendono la sigla della lavorazione appena indicata."""
        from sicurcantiere.archivio import PREFISSO_UTENTE

        cambiati = False
        for f in self.repo.elenco("fasi"):
            if f["lavorazione"].strip() and (not f["codice"] or f["codice"].startswith(PREFISSO_UTENTE + ".")):
                nuovo = self.repo.codice_automatico(f["lavorazione"], escludi=f["id"])
                if not nuovo.startswith(PREFISSO_UTENTE + "."):
                    self.repo.aggiorna("fasi", f["id"], codice=nuovo)
                    cambiati = True
        if cambiati:
            selezionata = self.fasi.id_selezionato()
            self.fasi.ricarica()
            if selezionata is not None:
                self.fasi.seleziona(selezionata)

    def _aggiorna_gantt(self) -> None:
        imprese = {i["id"]: i["ragione_sociale"] or f"Impresa {i['id']}" for i in self.repo.elenco("imprese")}
        self.gantt.imposta_fasi(self.fasi.righe(), analisi.livelli_fasi(self.repo.rischi()), imprese)

    def _fase_trascinata(self, id_: int, inizio: str, fine: str) -> None:
        self.repo.aggiorna("fasi", id_, data_inizio=inizio, data_fine=fine)
        self.fasi.ricarica()
        self.fasi.seleziona(id_)
        self._aggiorna_gantt()

    def _importa(self) -> None:
        dialogo = DialogoArchivio(self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        ultima = None
        for lav in dialogo.selezionate():
            if "dati" in lav:  # lavorazione dell'archivio utente
                ultima = ArchivioAnagrafiche.inserisci_lavorazione(self.repo, lav)
            else:
                ultima = self.repo.importa_lavorazione(lav)
        self.fasi.ricarica()
        if ultima is not None:
            self.fasi.seleziona(ultima)
        self._aggiorna_gantt()

    def _salva_in_archivio(self) -> None:
        fase = self.fasi.id_selezionato()
        if fase is None:
            QMessageBox.information(self, "Archivio", "Seleziona prima la fase da salvare.")
            return
        archivio = ArchivioAnagrafiche()
        try:
            archivio.salva_lavorazione(self.repo, fase)
        except ValueError as e:
            QMessageBox.warning(self, "Archivio", str(e))
            return
        finally:
            archivio.chiudi()
        QMessageBox.information(self, "Archivio", "Lavorazione salvata tra le lavorazioni personalizzate "
                                                  "dell'archivio, con macchine, attrezzi e rischi: la trovi in "
                                                  "«Importa dall'archivio...».")

    def _cerca_attrezzatura(self) -> None:
        if self.fasi.id_selezionato() is None:
            return
        nome = scegli_da_elenco(self, "Aggiungi dall'archivio", "Cerca la macchina, l'attrezzo o l'opera "
                                "provvisionale:", sorted(ATTREZZATURE))
        if nome:
            self.scelta_archivio.setCurrentText(nome)
            self._aggiungi_attrezzatura()

    def _aggiungi_attrezzatura(self) -> None:
        fase = self.fasi.id_selezionato()
        if fase is None:
            return
        self.repo.aggiungi_attrezzatura(fase, self.scelta_archivio.currentText())
        self.attrezzature.ricarica()
        self.rischi.ricarica()
        self._aggiorna_gantt()

    def _rischi_delle_attrezzature(self) -> None:
        """Una macchina o un attrezzo scritto a mano porta nella fase i suoi rischi specifici."""
        from sicurcantiere.valutazioni.automatiche import completa_rischi_attrezzature

        if completa_rischi_attrezzature(self.repo):
            self.rischi.ricarica()

    def _suggerisci_rischi(self) -> None:
        fase_id = self.fasi.id_selezionato()
        if fase_id is None:
            return
        fase = self.repo.leggi("fasi", fase_id)
        lavorazione = f"{fase['codice']} {fase['descrizione']}".strip()
        if not lavorazione:
            QMessageBox.information(self, "Assistente AI", "Indica prima la descrizione della fase.")
            return
        attrezzature = [a["nome"] for a in self.repo.elenco("attrezzature", fase_id=fase_id)]
        esistenti = [f"{r['descrizione']} ({r['fonte']})" if r["fonte"] else r["descrizione"]
                     for r in self.repo.elenco("rischi", fase_id=fase_id)]
        esegui_ai(self, "L'assistente sta analizzando la lavorazione...",
                  lambda ai: ai.suggerisci_rischi(lavorazione, attrezzature, esistenti),
                  lambda proposte: self._scegli_rischi(fase_id, proposte))

    @staticmethod
    def _testo_rischio(r: dict) -> str:
        livello = analisi.livello_rischio(r["probabilita"], r["danno"])
        origine = f" ({r['fonte']})" if r.get("fonte") else ""
        return (f"{r['descrizione']}{origine}  -  P{r['probabilita']} × D{r['danno']} = {livello} "
                f"{analisi.classe_rischio(livello)}\n    Misure: {r['misure']}")

    def _scegli_proposte(self, titolo: str, nota: str, testi: list[str]) -> list[int] | None:
        """Elenco a spunta delle proposte dell'assistente; restituisce gli indici scelti."""
        dialogo = QDialog(self)
        dialogo.setWindowTitle(titolo)
        dialogo.resize(760, 460)
        elenco = QListWidget()
        for testo in testi:
            item = QListWidgetItem(testo)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            elenco.addItem(item)
        etichetta = QLabel(nota)
        etichetta.setWordWrap(True)
        pulsanti = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        pulsanti.accepted.connect(dialogo.accept)
        pulsanti.rejected.connect(dialogo.reject)
        layout = QVBoxLayout(dialogo)
        layout.addWidget(etichetta)
        layout.addWidget(elenco)
        layout.addWidget(pulsanti)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return [i for i in range(elenco.count()) if elenco.item(i).checkState() == Qt.CheckState.Checked]

    def _dopo_aggiunte(self) -> None:
        self._rischi_delle_attrezzature()
        self.attrezzature.ricarica()
        self.rischi.ricarica()
        self._aggiorna_gantt()

    def _scegli_rischi(self, fase_id: int, proposte: list[dict]) -> None:
        if not proposte:
            QMessageBox.information(self, "Assistente AI", "Nessun rischio aggiuntivo individuato.")
            return
        scelti = self._scegli_proposte(
            "Rischi suggeriti dall'assistente AI",
            "Seleziona i rischi da aggiungere alla fase. Valori e misure restano modificabili.",
            [self._testo_rischio(r) for r in proposte])
        if scelti is None or not self.repo.leggi("fasi", fase_id):
            return
        for i in scelti:
            self.repo.inserisci("rischi", fase_id=fase_id, **proposte[i])
        self._dopo_aggiunte()

    def _suggerisci_attrezzature(self) -> None:
        fase_id = self.fasi.id_selezionato()
        if fase_id is None:
            QMessageBox.information(self, "Assistente AI", "Seleziona una fase.")
            return
        fase = self.repo.leggi("fasi", fase_id)
        lavorazione = " - ".join(x for x in (fase["lavorazione"], f"{fase['codice']} {fase['descrizione']}".strip())
                                 if x)
        if not fase["descrizione"].strip():
            QMessageBox.information(self, "Assistente AI", "Indica prima la descrizione della fase.")
            return
        esistenti = [a["nome"] for a in self.repo.elenco("attrezzature", fase_id=fase_id)]
        esegui_ai(self, "L'assistente sta individuando macchine e attrezzature...",
                  lambda ai: ai.suggerisci_attrezzature(lavorazione, fase["dettaglio"], esistenti,
                                                        sorted(ATTREZZATURE)),
                  lambda proposte: self._scegli_attrezzature(fase_id, proposte))

    def _scegli_attrezzature(self, fase_id: int, proposte: list[dict]) -> None:
        if not proposte:
            QMessageBox.information(self, "Assistente AI", "Nessuna attrezzatura aggiuntiva individuata.")
            return
        testi = []
        for a in proposte:
            if a["nome"] in ATTREZZATURE:
                rischi = [r["descrizione"] for r in ATTREZZATURE[a["nome"]]["rischi"]]
                origine = "scheda dell'archivio"
            else:
                rischi = [r["descrizione"] for r in a["rischi"]]
                origine = "proposta dall'assistente"
            testi.append(f"{a['nome']} ({a['tipo'].lower()}, {origine})\n    Rischi: {', '.join(rischi) or '-'}")
        scelti = self._scegli_proposte(
            "Macchine e attrezzature suggerite dall'assistente AI",
            "Seleziona le attrezzature da aggiungere alla fase, con la relativa scheda d'uso e i relativi rischi. "
            "Per quelle presenti nell'archivio viene usata la scheda dell'archivio.", testi)
        if scelti is None or not self.repo.leggi("fasi", fase_id):
            return
        for i in scelti:
            self.repo.aggiungi_attrezzatura_proposta(fase_id, proposte[i])
        self._dopo_aggiunte()

    def _completa_attrezzatura(self) -> None:
        id_ = self.attrezzature.id_selezionato()
        if id_ is None:
            QMessageBox.information(self, "Assistente AI", "Seleziona una macchina o un attrezzo.")
            return
        a = self.repo.leggi("attrezzature", id_)
        if not a["nome"].strip():
            QMessageBox.information(self, "Assistente AI", "Indica prima il nome dell'attrezzatura.")
            return
        fase = self.repo.leggi("fasi", a["fase_id"])
        esistenti = [r["descrizione"] for r in self.repo.elenco("rischi", fase_id=a["fase_id"])
                     if r["fonte"] == a["nome"]]
        esegui_ai(self, "L'assistente sta compilando la scheda dell'attrezzatura...",
                  lambda ai: ai.completa_attrezzatura(a["nome"], a["tipo"], fase["descrizione"], esistenti),
                  lambda proposta: self._applica_attrezzatura(id_, proposta))

    def _applica_attrezzatura(self, id_: int, proposta: dict) -> None:
        from sicurcantiere.archivio_attrezzature import testo_misure

        a = self.repo.leggi("attrezzature", id_)
        if a is None:
            return
        rischi = [{**r, "fonte": a["nome"]} for r in proposta["rischi"]]
        scheda = []
        if not a["descrizione"].strip() and proposta["descrizione"]:
            scheda.append("Descrizione")
        if not a["misure"].strip() and any(proposta[k] for k in ("prima", "durante", "dopo")):
            scheda.append("Misure prima, durante e dopo l'uso")
        if not a["dpi"].strip() and proposta["dpi"]:
            scheda.append("DPI dell'operatore")
        testi = [f"Scheda d'uso: {', '.join(scheda)}"] if scheda else []
        testi += [self._testo_rischio(r) for r in rischi]
        if not testi:
            QMessageBox.information(self, "Assistente AI", "Scheda già completa e nessun rischio aggiuntivo.")
            return
        scelti = self._scegli_proposte(
            f"{a['nome']}: proposte dell'assistente AI",
            "Seleziona cosa aggiungere. I campi della scheda già compilati non vengono modificati.", testi)
        if scelti is None or not self.repo.leggi("attrezzature", id_):
            return
        if scheda and 0 in scelti:
            modifiche = {}
            if "Descrizione" in scheda:
                modifiche["descrizione"] = proposta["descrizione"]
            if "DPI dell'operatore" in scheda:
                modifiche["dpi"] = "; ".join(d.strip() for d in proposta["dpi"].split(",") if d.strip())
            if "Misure prima, durante e dopo l'uso" in scheda:
                modifiche["misure"] = testo_misure(proposta)
            self.repo.aggiorna("attrezzature", id_, **modifiche)
        primo = 1 if scheda else 0
        for i in scelti:
            if i >= primo:
                self.repo.inserisci("rischi", fase_id=a["fase_id"], **rischi[i - primo])
        self._dopo_aggiunte()

    def _calcola_durata(self) -> None:
        id_ = self.fasi.id_selezionato()
        if id_ is None:
            QMessageBox.information(self, "Calcola la durata", "Seleziona una fase.")
            return
        f = self.repo.leggi("fasi", id_)
        costo = self.repo.cantiere()["costo_uomo_giorno"] or analisi.COSTO_UOMO_GIORNO
        giorni = analisi.durata_stimata(f["importo"], f["incidenza_manodopera"], costo, f["lavoratori"])
        inizio = analisi.data(f["data_inizio"])
        if giorni is None or inizio is None:
            QMessageBox.information(
                self, "Calcola la durata",
                "Indica data di inizio, importo, incidenza della manodopera e squadra della fase, "
                "e il costo medio uomo-giorno nella pagina «Dati generali».")
            return
        fine = analisi.fine_dopo_giorni_lavorativi(inizio, giorni)
        self.repo.aggiorna("fasi", id_, data_fine=fine.isoformat())
        self.fasi.ricarica()
        self._aggiorna_gantt()

    def aggiorna(self) -> None:
        self.fasi.ricarica()
        self.fasi.seleziona_prima()
        self._aggiorna_gantt()


class PaginaInterferenze(Pagina):
    titolo = "Interferenze e prescrizioni di coordinamento"
    voce = "Interferenze"
    icona = "interferenze"
    sezioni_controlli = ("Interferenze",)
    sottotitolo = ("Fasi contemporanee di imprese diverse nella stessa zona (o con zona non indicata), calcolate dal "
                   "cronoprogramma e ordinate dalla più grave. Dove non scrivi una prescrizione, il PSC applica quella "
                   "generica di sfasamento.")

    def __init__(self, repo: Repository):
        super().__init__(repo)
        from sicurcantiere.documenti.psc import PRESCRIZIONE_GENERICA

        self.generica = PRESCRIZIONE_GENERICA
        self._elenco: list[analisi.Interferenza] = []
        self._prescrizioni: dict[tuple[int, int], str] = {}
        self._corrente: tuple[int, int] | None = None

        self.vista = QTableWidget(0, 2)
        self.vista.setHorizontalHeaderLabels(["Fasi in contemporanea", "Gravità"])
        self.vista.verticalHeader().setVisible(False)
        self.vista.setShowGrid(False)
        self.vista.setWordWrap(True)
        self.vista.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.vista.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vista.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.vista.setColumnWidth(1, 150)
        self.vista.setItemDelegateForColumn(1, tema.DelegatoGravita(self.vista))
        self.vista.verticalHeader().setDefaultSectionSize(52)
        self.vista.itemSelectionChanged.connect(self._selezionata)
        self.vuoto = QLabel("Nessuna interferenza: con le date e le zone delle fasi indicate non ci sono lavorazioni "
                            "contemporanee di imprese diverse nella stessa zona.")
        self.vuoto.setObjectName("hint")
        self.vuoto.setWordWrap(True)
        self.vuoto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sinistra = QFrame()
        sinistra.setObjectName("card")
        ls = QVBoxLayout(sinistra)
        ls.setContentsMargins(1, 1, 1, 1)
        ls.addWidget(self.vista)
        ls.addWidget(self.vuoto)

        # dettaglio: le due fasi, la zona e la prescrizione del coordinatore
        destra = QFrame()
        destra.setObjectName("card")
        ld = QVBoxLayout(destra)
        ld.setContentsMargins(16, 14, 16, 14)
        ld.setSpacing(8)
        self.titolo_dettaglio = QLabel()
        self.titolo_dettaglio.setObjectName("sectionTitle")
        self.titolo_dettaglio.setWordWrap(True)
        self.dati_dettaglio = QLabel()
        self.dati_dettaglio.setObjectName("pageSubtitle")
        self.dati_dettaglio.setWordWrap(True)
        self.zona = QPushButton("Zona non indicata: indicala in «Fasi» per ridurre le interferenze ›")
        self.zona.setObjectName("linkButton")
        self.zona.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zona.clicked.connect(lambda: getattr(self.window(), "vai_a_sezione", lambda _s: None)("Fasi"))
        etichetta = QLabel("Prescrizione del coordinatore")
        etichetta.setObjectName("fieldLabel")
        self.testo = QPlainTextEdit()
        self.testo.setPlaceholderText(f"Se lasci vuoto, nel PSC: «{PRESCRIZIONE_GENERICA}»")
        self._timer = QTimer(self, singleShot=True, interval=600)
        self._timer.timeout.connect(self._salva)
        self.testo.textChanged.connect(self._timer.start)
        ai = pulsante_ai("Scrivi con l'AI")
        ai.clicked.connect(self._scrivi_ai)
        generica = QPushButton("Usa la generica")
        generica.setToolTip("Inserisci la prescrizione generica di sfasamento, da adattare")
        generica.clicked.connect(lambda: self._imposta(PRESCRIZIONE_GENERICA))
        pulsanti = QHBoxLayout()
        pulsanti.addWidget(ai)
        pulsanti.addWidget(generica)
        pulsanti.addStretch()
        self.nessuna = QLabel("Seleziona un'interferenza nell'elenco.")
        self.nessuna.setObjectName("hint")
        for w in (self.nessuna, self.titolo_dettaglio, self.dati_dettaglio, self.zona, etichetta, self.testo):
            ld.addWidget(w)
        ld.addLayout(pulsanti)
        self._dettaglio = [self.titolo_dettaglio, self.dati_dettaglio, etichetta, self.testo, ai, generica]

        divisore = QSplitter(Qt.Orientation.Horizontal)
        divisore.setChildrenCollapsible(False)
        divisore.addWidget(sinistra)
        divisore.addWidget(destra)
        divisore.setSizes([520, 420])
        self.layout_.addWidget(divisore, 1)

    @staticmethod
    def stato(gravita: int, testo: str) -> str:
        if testo.strip():
            return "scritta"
        return "da scrivere" if gravita >= 6 else "generica"

    def aggiorna(self) -> None:
        self._salva()
        fasi = self.repo.elenco("fasi")
        self._elenco = analisi.interferenze(fasi, analisi.livelli_fasi(self.repo.rischi()))
        self._prescrizioni = self.repo.prescrizioni()
        corrente = self._corrente
        self.vista.blockSignals(True)
        self.vista.setRowCount(len(self._elenco))
        for r, i in enumerate(self._elenco):
            testo = (f"{i.fase_a['codice']} {i.fase_a['descrizione']}\n"
                     f"con {i.fase_b['codice']} {i.fase_b['descrizione']} · {i.inizio:%d/%m} - {i.fine:%d/%m}")
            primo = QTableWidgetItem(testo)
            primo.setToolTip(testo)
            self.vista.setItem(r, 0, primo)
            stato = self.stato(i.gravita, self._prescrizioni.get(i.chiave, ""))
            self.vista.setItem(r, 1, QTableWidgetItem(f"{i.gravita}|{stato}"))
        self.vista.blockSignals(False)
        self.vista.setVisible(bool(self._elenco))
        self.vuoto.setVisible(not self._elenco)
        chiavi = [i.chiave for i in self._elenco]
        self.vista.selectRow(chiavi.index(corrente) if corrente in chiavi else 0)
        if not self._elenco:
            self._mostra(None)

    def _selezionata(self) -> None:
        righe = self.vista.selectionModel().selectedRows()
        self._mostra(self._elenco[righe[0].row()] if righe and righe[0].row() < len(self._elenco) else None)

    def _mostra(self, i: analisi.Interferenza | None) -> None:
        self._salva()
        self._corrente = i.chiave if i else None
        for w in self._dettaglio:
            w.setVisible(i is not None)
        self.nessuna.setVisible(i is None)
        self.zona.setVisible(i is not None and not (i.fase_a["zona"] or i.fase_b["zona"]))
        if i is None:
            return
        imprese = {r["id"]: r["ragione_sociale"] for r in self.repo.elenco("imprese")}
        nomi = " e ".join(dict.fromkeys(imprese.get(f["impresa_id"], "impresa da definire")
                                        for f in (i.fase_a, i.fase_b)))
        self.titolo_dettaglio.setText(f"{i.fase_a['codice']} {i.fase_a['descrizione']}\n"
                                      f"e {i.fase_b['codice']} {i.fase_b['descrizione']}")
        zona = " / ".join(dict.fromkeys(z for z in (i.fase_a["zona"], i.fase_b["zona"]) if z))
        self.dati_dettaglio.setText(f"{i.inizio:%d/%m/%Y} - {i.fine:%d/%m/%Y} · {nomi}"
                                    + (f" · zona {zona}" if zona else ""))
        self.testo.blockSignals(True)
        self.testo.setPlainText(self._prescrizioni.get(i.chiave, ""))
        self.testo.blockSignals(False)

    def _imposta(self, testo: str) -> None:
        cursore = self.testo.textCursor()
        cursore.select(cursore.SelectionType.Document)
        cursore.insertText(testo)
        self._salva()

    def _salva(self) -> None:
        self._timer.stop()
        if self._corrente is None:
            return
        testo = self.testo.toPlainText()
        if self._prescrizioni.get(self._corrente, "") == testo:
            return
        self.repo.salva_prescrizione(*self._corrente, testo)
        self._prescrizioni[self._corrente] = testo
        for r, i in enumerate(self._elenco):
            if i.chiave == self._corrente:
                self.vista.item(r, 1).setText(f"{i.gravita}|{self.stato(i.gravita, testo)}")

    def salva_in_sospeso(self) -> None:
        self._salva()

    def _scrivi_ai(self) -> None:
        i = next((x for x in self._elenco if x.chiave == self._corrente), None)
        if i is None:
            return
        contesto = contesto_cantiere(self.repo) + (
            f"\nInterferenza tra «{i.fase_a['codice']} {i.fase_a['descrizione']}» e «{i.fase_b['codice']} "
            f"{i.fase_b['descrizione']}», dal {i.inizio:%d/%m/%Y} al {i.fine:%d/%m/%Y}, gravità {i.gravita}.")
        attuale = self.testo.toPlainText()
        esegui_ai(self, "L'assistente sta scrivendo la prescrizione...",
                  lambda ai: ai.scrivi_sezione("Prescrizione di coordinamento per l'interferenza", contesto, attuale),
                  self._imposta)


class PaginaCosti(Pagina):
    titolo = "Stima dei costi della sicurezza"
    voce = "Costi della sicurezza"
    icona = "costi"
    sezioni_controlli = ("Costi",)

    def __init__(self, repo: Repository):
        super().__init__(repo)
        from sicurcantiere.relazione import CATEGORIE_COSTI

        self.prezzario = QLineEdit()
        self.prezzario.setPlaceholderText("Per esempio: Prezzario regionale delle opere pubbliche 2025")
        self.prezzario.editingFinished.connect(self._salva_prezzario)
        # i prezzari usati di recente si propongono mentre si scrive (o con la freccia giù)
        self._prezzari = QStringListModel(self._prezzari_recenti(), self)
        completamento = QCompleter(self._prezzari, self)
        completamento.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completamento.setFilterMode(Qt.MatchFlag.MatchContains)
        self.prezzario.setCompleter(completamento)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("Prezzario di riferimento:"))
        riga.addWidget(self.prezzario, 1)
        self.layout_.addLayout(riga)
        self.tabella = TabellaCrud(repo, "costi", [
            Colonna("categoria", "Categoria (punto 4.1.1)", "scelta", larghezza=230,
                    scelte=lambda: [(k, f"{k}) {t}") for k, t in CATEGORIE_COSTI],
                    suggerimento="Voce dell'Allegato XV punto 4.1.1: il documento raggruppa i costi per categoria "
                                 "con i subtotali"),
            Colonna("codice", "Codice", larghezza=80),
            Colonna("descrizione", "Descrizione", "testo_lungo"),
            Colonna("unita", "U.M.", larghezza=60),
            Colonna("quantita", "Quantità", "decimale", larghezza=100),
            Colonna("prezzo_unitario", "Prezzo unitario", "decimale", larghezza=120),
            Colonna("importo", "Importo", "calcolata", larghezza=120,
                    calcola=lambda r: euro(r["quantita"] * r["prezzo_unitario"])),
        ], elenco=["categoria", "descrizione", "importo"],
            vuoto="Nessun costo inserito. La stima dei costi della sicurezza è un contenuto obbligatorio del PSC "
                  "(Allegato XV punto 4): usa «Aggiungi» per la prima voce.")
        self.tabella.imposta_titolo("Costi della sicurezza")
        # totale in alto, accanto al titolo: è il dato che il coordinatore cerca
        self.totale = QLabel()
        self.totale.setObjectName("cardTitle")
        self.tabella.pulsanti.addWidget(self.totale)
        self.subtotali = QLabel()
        self.subtotali.setObjectName("hint")
        self.subtotali.setWordWrap(True)
        self.tabella.modificata.connect(self._totale)
        self.layout_.addWidget(self.subtotali)
        self.layout_.addWidget(self.tabella)

    @staticmethod
    def _prezzari_recenti() -> list[str]:
        valore = QSettings().value("costi/prezzari", [])
        return [v for v in (valore if isinstance(valore, list) else [valore]) if v]

    def _salva_prezzario(self) -> None:
        testo = self.prezzario.text().strip()
        self.repo.aggiorna_cantiere(prezzario=testo)
        if testo:
            recenti = [testo] + [p for p in self._prezzari_recenti() if p != testo]
            QSettings().setValue("costi/prezzari", recenti[:10])
            self._prezzari.setStringList(recenti[:10])

    def _totale(self) -> None:
        from sicurcantiere.relazione import CATEGORIE_COSTI

        righe = self.tabella.righe()
        totale = analisi.totale_costi(righe)
        self.totale.setText(f"Totale {euro(totale)}")
        per_categoria: dict[str, float] = {}
        for r in righe:
            per_categoria[r["categoria"] or ""] = per_categoria.get(r["categoria"] or "", 0) + \
                r["quantita"] * r["prezzo_unitario"]
        parti = [f"{k}) {euro(per_categoria[k])}" for k, _ in CATEGORIE_COSTI if k in per_categoria]
        if "" in per_categoria:
            parti.append(f"senza categoria {euro(per_categoria[''])}")
        if not righe or totale <= 0:
            self.subtotali.setText("Il totale è 0,00 €: la stima dei costi della sicurezza è obbligatoria nel PSC "
                                   "(Allegato XV punto 4.1). Inserisci le voci, raggruppate per categoria.")
            tema.imposta_stato(self.subtotali, "warning")
        else:
            self.subtotali.setText("Subtotali per categoria (punto 4.1.1): " + " · ".join(parti))
            tema.imposta_stato(self.subtotali, None)

    def aggiorna(self) -> None:
        self.prezzario.setText(self.repo.cantiere()["prezzario"])
        self.tabella.ricarica()
        self._totale()

    def salva_in_sospeso(self) -> None:
        self.repo.aggiorna_cantiere(prezzario=self.prezzario.text())


class PaginaRelazione(Pagina):
    titolo = "Relazione del PSC"
    voce = "Relazione del PSC"
    icona = "relazione"
    sezioni_controlli = ("Relazione", "Rischi particolari", "Tavole")

    sottotitolo = ("I contenuti del PSC redatti dal coordinatore, ordinati secondo l'Allegato XV. Ogni riquadro "
                   "indica che cosa scrivere; l'assistente AI può preparare una bozza.")

    def __init__(self, repo: Repository):
        from sicurcantiere.relazione import GRUPPI
        from sicurcantiere.ui.relazione_psc import AllegatiPSC, RischiParticolari

        super().__init__(repo)
        self.schede = QTabWidget(self)
        self.gruppi: list[TestiLiberi] = []
        for nome, sezioni in GRUPPI:
            testi = TestiLiberi(repo, [(s.chiave, f"{s.titolo}   ·   {s.riferimento}") for s in sezioni],
                                contesto_ai=lambda: contesto_cantiere(repo),
                                guide={s.chiave: s.guida for s in sezioni}, altezza=90, non_pertinente=True)
            testi.compilati_cambiati = self._aggiorna_conteggi
            scorrimento = QScrollArea()
            scorrimento.setWidgetResizable(True)
            scorrimento.setWidget(testi)
            self.schede.addTab(scorrimento, nome)
            self.gruppi.append(testi)
            self._nomi_gruppi = getattr(self, "_nomi_gruppi", []) + [nome]
        self.rischi_particolari = RischiParticolari(repo)
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setWidget(self.rischi_particolari)
        self.schede.addTab(scorrimento, "Rischi particolari e ordigni bellici")
        self.allegati = AllegatiPSC(repo)
        self.schede.addTab(self.allegati, "Tavole, foto e logo")
        self.layout_.addWidget(self.schede)
        # compatibilità: il primo gruppo di testi
        self.testi = self.gruppi[0]

    def salva_in_sospeso(self) -> None:
        for testi in self.gruppi:
            testi.salva_in_sospeso()
        self.rischi_particolari.salva()

    def _aggiorna_conteggi(self) -> None:
        """Quanti riquadri sono compilati in ogni scheda, per esempio «Organizzazione  2 di 5»."""
        for n, (nome, testi) in enumerate(zip(self._nomi_gruppi, self.gruppi)):
            fatti, totale = testi.compilati(), len(testi.editor)
            self.schede.setTabText(n, f"{nome}  {fatti} di {totale}")
            self.schede.setTabToolTip(n, "Tutti i riquadri compilati" if fatti == totale else
                                      f"{totale - fatti} riquadri da compilare o da segnare come non pertinenti")

    def aggiorna(self) -> None:
        for testi in self.gruppi:
            testi.carica()
        self._aggiorna_conteggi()
        self.rischi_particolari.carica()
        self.allegati.carica()


class PaginaFascicolo(Pagina):
    titolo = "Fascicolo dell'opera"
    voce = "Fascicolo dell'opera"
    icona = "fascicolo"
    sezioni_controlli = ("Fascicolo",)

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.interventi = TabellaCrud(repo, "interventi", [
            Colonna("parte_opera", "Parte d'opera", larghezza=130),
            Colonna("intervento", "Intervento di manutenzione", "testo_lungo"),
            Colonna("periodicita", "Periodicità", larghezza=100),
            Colonna("rischi", "Rischi", "testo_lungo"),
            Colonna("misure_in_dotazione", "Misure in dotazione dell'opera", "testo_lungo"),
            Colonna("misure_ausiliarie", "Misure ausiliarie", "testo_lungo"),
        ], elenco=["parte_opera", "intervento", "periodicita"])
        self.interventi.imposta_titolo("Interventi di manutenzione")
        self.elaborati = TabellaCrud(repo, "elaborati", [
            Colonna("titolo", "Elaborato tecnico", larghezza=320),
            Colonna("autore", "Autore", larghezza=200),
            Colonna("data", "Data", "data", larghezza=100),
            Colonna("collocazione", "Collocazione"),
        ])
        self.elaborati.imposta_titolo("Elaborati tecnici")
        self.nessun_intervento = QCheckBox("L'opera non richiede interventi di manutenzione con misure di sicurezza "
                                           "(nessuna scheda II)")
        self.nessun_intervento.setToolTip("Dichiarazione esplicita: senza interventi né questa dichiarazione la "
                                          "pagina resta da completare.")
        self.nessun_intervento.toggled.connect(
            lambda attiva: self.repo.salva_testo(controlli.NESSUN_INTERVENTO, "1" if attiva else ""))
        self.layout_.addWidget(self.nessun_intervento)
        divisore = QSplitter(Qt.Orientation.Vertical)
        divisore.addWidget(_riquadro("Schede II: interventi di manutenzione e misure di sicurezza",
                                     self.interventi))
        divisore.addWidget(_riquadro("Schede III: documentazione di supporto", self.elaborati))
        divisore.setSizes([450, 250])
        self.layout_.addWidget(divisore)

    def aggiorna(self) -> None:
        self.interventi.ricarica()
        self.elaborati.ricarica()
        self.nessun_intervento.blockSignals(True)
        self.nessun_intervento.setChecked(self.repo.testo(controlli.NESSUN_INTERVENTO) == "1")
        self.nessun_intervento.blockSignals(False)
        self.nessun_intervento.setVisible(not self.interventi.righe())


class PaginaDocumenti(Pagina):
    """Generazione dei documenti, revisioni e controlli.

    Le sottoclassi dei singoli programmi scelgono quali documenti offrire
    (`documenti`) e quali controlli eseguire (`controlla`).
    """

    titolo = "Documenti, revisioni e controlli"
    voce = "Documenti e controlli"
    icona = "documenti"
    # psc, fascicolo, notifica: documenti del cantiere; pos, dpi: documenti per impresa
    documenti: tuple[str, ...] = ("psc", "fascicolo", "notifica", "pos")
    principale = "psc"
    controlla = staticmethod(controlli.controlla)

    PER_IMPRESA = ("pos", "dpi", "sostanze", "tesserini", "schede", "idoneita")
    # documenti principali: si compongono e restano salvati nel cantiere (bozza, emessa, consegnata)
    COMPONIBILI = {"pos": "POS", "psc": "PSC"}
    NOMI = {
        "psc": "Piano di sicurezza e coordinamento (PSC)",
        "fascicolo": "Fascicolo dell'opera",
        "notifica": "Notifica preliminare",
        "pos": "Piano operativo di sicurezza (POS)",
        "dpi": "Verbali di consegna dei DPI",
        "sostanze": "Elenco delle sostanze pericolose",
        "tesserini": "Tesserini di riconoscimento dei lavoratori",
        "schede": "Schede dei lavoratori (mansioni, rischi, DPI, formazione)",
        "idoneita": "Verifica dell'idoneità tecnico-professionale (Allegato XVII)",
    }
    NOMI_BREVI = {
        "psc": "PSC", "pos": "POS", "fascicolo": "Fascicolo dell'opera", "notifica": "Notifica preliminare",
        "dpi": "Verbali di consegna dei DPI", "sostanze": "Elenco delle sostanze", "tesserini": "Tesserini",
        "schede": "Schede dei lavoratori", "idoneita": "Verifica dell'idoneità...",
    }
    MOSTRATI = 5  # voci «da sistemare» visibili prima di «Mostra gli altri»

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.componibile = next((k for k in self.documenti if k in self.COMPONIBILI), None)
        nome_principale = self.COMPONIBILI.get(self.componibile, "documento")
        self.impresa = QComboBox()
        self.impresa.setMinimumWidth(260)
        # il selettore d'impresa serve solo ai documenti dell'impresa (POS): il PSC riguarda tutte le
        # imprese e i lavoratori autonomi del cantiere e non ha documenti da generare per una sola impresa
        self.con_impresa = self.componibile == "pos"
        if self.con_impresa:
            riga = QHBoxLayout()
            riga.addStretch()
            riga.addWidget(QLabel("Impresa:"))
            riga.addWidget(self.impresa)
            self.layout_.addLayout(riga)

        corpo = QWidget()
        lc = QVBoxLayout(corpo)
        lc.setContentsMargins(0, 0, 4, 0)
        lc.setSpacing(12)
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setFrameShape(QFrame.Shape.NoFrame)
        scorrimento.setWidget(corpo)
        self.layout_.addWidget(scorrimento, 1)

        # 1. posso consegnare? stato del documento e cose da sistemare
        self.stato = QLabel()
        self.stato.setObjectName("statusBanner")
        self.stato.setWordWrap(True)
        self.stato.setTextFormat(Qt.TextFormat.RichText)
        lc.addWidget(self.stato)
        self.controlli = QListWidget()
        self.controlli.setItemDelegate(tema.DelegatoControllo(self.controlli))
        self.controlli.setMouseTracking(True)
        self.controlli.itemClicked.connect(self._vai_al_controllo)
        self.controlli.itemActivated.connect(self._vai_al_controllo)
        self.controlli.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.altri = QPushButton()
        self.altri.setObjectName("linkButton")
        self.altri.clicked.connect(self._mostra_tutti)
        self._tutti = False
        corpo_controlli = QVBoxLayout()
        corpo_controlli.setSpacing(4)
        corpo_controlli.addWidget(self.controlli)
        corpo_controlli.addWidget(self.altri, alignment=Qt.AlignmentFlag.AlignLeft)
        self.riquadro_controlli = tema.cornice("Da sistemare", corpo_controlli)
        lc.addWidget(self.riquadro_controlli)

        # 2. un solo pulsante per comporre il documento principale
        self.revisioni = TabellaCrud(repo, "revisioni", [
            Colonna("documento", "Documento", "scelta", scelte=self._documenti, larghezza=200),
            Colonna("numero", "Rev.", "intero", larghezza=60),
            Colonna("data", "Data", "data", larghezza=100),
            Colonna("descrizione", "Descrizione delle modifiche", "testo_lungo"),
        ])
        self.revisioni.imposta_titolo("Revisioni degli altri documenti")
        self.composizioni = None
        self.schede = QTabWidget(self)
        if self.componibile:
            componi = primario(QPushButton(f"Componi la bozza del {nome_principale}"))
            componi.clicked.connect(lambda: self.genera(self.componibile))
            self.pulsante_componi = componi
            nota = QLabel("Con errori nei dati obbligatori il programma chiede conferma; la bozza resta salvata nel "
                          "cantiere e si emette quando è completa.")
            nota.setObjectName("hint")
            nota.setWordWrap(True)
            riga = QHBoxLayout()
            riga.addWidget(componi)
            riga.addSpacing(10)
            riga.addWidget(nota, 1)
            lc.addLayout(riga)
            self.composizioni = PannelloComposizioni(repo, self._documento_composto, nome_principale, self)
            self.composizioni.p_componi.hide()  # il pulsante della pagina è uno solo
            self.composizioni.setMinimumHeight(170)
            self.impresa.currentIndexChanged.connect(lambda _: (self.composizioni.ricarica(), self._controlla()))
            lc.addWidget(self.composizioni)
            self.schede.addTab(self.composizioni.mancanti, "Dati da completare nella bozza")
        self.schede.addTab(self.revisioni, "Revisioni degli altri documenti")
        self.schede.setMinimumHeight(170)
        lc.addWidget(self.schede)

        # 3. stampe secondarie
        self._pulsanti_documenti: list[tuple[str, QPushButton]] = []
        riga_altri = QHBoxLayout()
        riga_altri.setSpacing(6)
        titolo_altri = QLabel("Altri documenti")
        titolo_altri.setObjectName("sectionTitle")
        riga_altri.addWidget(titolo_altri)
        riga_altri.addSpacing(8)
        for chiave in self.documenti:
            if chiave in self.COMPONIBILI:
                continue
            b = QPushButton(self.NOMI_BREVI.get(chiave, self.NOMI[chiave]))
            b.setToolTip(self.NOMI[chiave])
            b.clicked.connect(lambda _=False, k=chiave: self.genera(k))
            riga_altri.addWidget(b)
            self._pulsanti_documenti.append((chiave, b))
        riga_altri.addStretch()
        lc.addLayout(riga_altri)
        lc.addStretch()

    def _mostra_tutti(self) -> None:
        self._tutti = not self._tutti
        self._controlla()

    def _documento_composto(self) -> str | None:
        if self.componibile == "psc":
            return "PSC"
        impresa = self.impresa.currentData()
        dati = self.repo.leggi("imprese", impresa) if impresa is not None else None
        return f"POS:{impresa}" if dati is not None and not anagrafiche.autonomo(dati) else None

    def _documenti(self) -> list[tuple[str, str]]:
        voci = []
        if "psc" in self.documenti:
            voci.append(("PSC", "PSC"))
        if "fascicolo" in self.documenti:
            voci.append(("FASCICOLO", "Fascicolo dell'opera"))
        if "pos" in self.documenti:
            voci += [(f"POS:{i['id']}", f"POS - {i['ragione_sociale']}") for i in self.repo.elenco("imprese")]
        return voci

    def _controlla(self) -> list[controlli.Segnalazione]:
        """Stato del documento principale e cose da sistemare, prima gli errori, ognuna con la sua pagina."""
        self.controlli.clear()
        elenco = self.controlla(self.repo)
        if self.con_impresa and self.impresa.currentData() is not None:
            # nel POS gli avvisi delle altre imprese non riguardano questo documento
            nome = self.impresa.currentText()
            altre = [self.impresa.itemText(i) for i in range(self.impresa.count()) if self.impresa.itemText(i) != nome]
            elenco = [s for s in elenco if not any(s.messaggio.startswith(f"{a}:") for a in altre if a)]
        elenco = sorted(elenco, key=lambda s: s.livello != controlli.ERRORE)
        errori = sum(1 for s in elenco if s.livello == controlli.ERRORE)
        avvisi = len(elenco) - errori
        pagine = getattr(self.window(), "pagine", [])
        for n, s in enumerate(elenco):
            pagina = next((p.voce or p.titolo for p in pagine if s.sezione in p.sezioni_controlli), s.sezione)
            item = QListWidgetItem(f"{s.livello} · {s.sezione}\n{s.messaggio}")
            item.setData(Qt.ItemDataRole.UserRole, s.sezione)
            item.setData(Qt.ItemDataRole.UserRole + 1, (s.livello, pagina, s.messaggio))
            item.setToolTip(f"{s.messaggio}\nFai clic per aprire la pagina «{pagina}».")
            self.controlli.addItem(item)
            item.setHidden(not self._tutti and n >= self.MOSTRATI)
        nascoste = max(0, len(elenco) - self.MOSTRATI)
        self.altri.setVisible(nascoste > 0)
        self.altri.setText("Mostra solo i primi" if self._tutti else f"Mostra gli altri {nascoste}")
        righe = len(elenco) if self._tutti else min(len(elenco), self.MOSTRATI)
        self.controlli.setFixedHeight(max(righe, 1) * 36 + 6)
        self.riquadro_controlli.setVisible(bool(elenco))
        nome = self.COMPONIBILI.get(self.componibile, "documento")
        if errori:
            titolo = (f"Il {nome} non è ancora pronto: "
                      + ("1 errore da risolvere" if errori == 1 else f"{errori} errori da risolvere"))
            dettaglio = (f"{avvisi} avvis{'o' if avvisi == 1 else 'i'}: vanno ricontrollati prima della consegna."
                         if avvisi else "Correggi gli errori nelle pagine indicate qui sotto.")
            stato = "error"
        elif avvisi:
            titolo = f"Il {nome} si può comporre"
            dettaglio = (f"{avvisi} avvis{'o' if avvisi == 1 else 'i'}: la bozza si può comporre, ma vanno "
                         "ricontrollati prima della consegna.")
            stato = "warning"
        else:
            titolo = f"Il {nome} è pronto"
            dettaglio = "Nessun errore e nessun avviso: puoi comporre la bozza ed emetterla."
            stato = "ok"
        self.stato.setText(f"<b>{titolo}</b><br>{dettaglio}")
        tema.imposta_stato(self.stato, stato)
        return elenco

    def _vai_al_controllo(self, item: QListWidgetItem) -> None:
        vai = getattr(self.window(), "vai_a_sezione", None)
        if vai is not None and item.data(Qt.ItemDataRole.UserRole):
            vai(item.data(Qt.ItemDataRole.UserRole))

    def _salva_docx(self, nome: str, funzione: Callable[[str], Any]) -> None:
        errori = [s for s in self._controlla() if s.livello == controlli.ERRORE]
        if errori:
            risposta = QMessageBox.question(
                self, "Controlli",
                ("I controlli segnalano 1 errore" if len(errori) == 1 else
                 f"I controlli segnalano {len(errori)} errori") + " nei dati (vedi l'elenco).\n"
                "Vuoi generare comunque il documento?")
            if risposta != QMessageBox.StandardButton.Yes:
                return
        predefinito = self.repo.progetto.percorso.with_name(f"{nome}.docx".replace("/", "-"))
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva il documento", str(predefinito),
                                                  "Documento Word (*.docx)")
        if not percorso:
            return
        try:
            file = funzione(percorso)
        except PermissionError:
            QMessageBox.warning(self, "Salvataggio non riuscito",
                                "Impossibile scrivere il file. Se è aperto in Word, chiudilo e riprova.")
            return
        from sicurcantiere.ui.anteprima import documento_creato

        documento_creato(self, file, avviso=AVVISO_RESPONSABILITA)

    def genera(self, chiave: str | None = None) -> None:
        chiave = chiave or self.principale
        if chiave in self.COMPONIBILI and self.composizioni is not None:
            if self.composizioni.componi():
                self.schede.setCurrentWidget(self.composizioni.mancanti)
                self.revisioni.ricarica()
            return
        cantiere = self.repo.cantiere()["nome"] or "Cantiere"
        if chiave in self.PER_IMPRESA:
            impresa, nome = self.impresa.currentData(), self.impresa.currentText()
            if impresa is None:
                if not self.repo.elenco("imprese"):
                    QMessageBox.information(self, "Documenti", "Inserisci prima l'impresa nella pagina «Imprese».")
                return
            dati_impresa = self.repo.leggi("imprese", impresa) or {}
            if anagrafiche.autonomo(dati_impresa) and chiave != "idoneita":
                QMessageBox.information(self, "Documenti", "Per i lavoratori autonomi si genera solo la verifica "
                                                           "dell'idoneità tecnico-professionale; gli altri documenti "
                                                           "riguardano le imprese con lavoratori.")
                return
            if chiave == "pos":
                self._salva_docx(f"POS - {nome} - {cantiere}", lambda p: genera_pos(self.repo, impresa, p))
            elif chiave == "tesserini":
                self._salva_docx(f"Tesserini - {nome}", lambda p: genera_tesserini(self.repo, impresa, p))
            elif chiave == "idoneita":
                from sicurcantiere.documenti.idoneita import genera_verifica_idoneita

                self._salva_docx(f"Verifica idoneità - {nome}", lambda p: genera_verifica_idoneita(self.repo, impresa, p))
            elif chiave == "schede":
                self._salva_docx(f"Schede lavoratori - {nome}",
                                 lambda p: genera_schede_lavoratori(self.repo, impresa, p))
            elif chiave == "sostanze":
                self._salva_docx(f"Sostanze pericolose - {nome}",
                                 lambda p: genera_elenco_sostanze(self.repo, impresa, p))
            else:
                self._salva_docx(f"Consegna DPI - {nome}", lambda p: genera_consegna_dpi(self.repo, impresa, p))
            return
        funzioni = {"psc": genera_psc, "fascicolo": genera_fascicolo, "notifica": genera_notifica}
        nomi = {"psc": "PSC", "fascicolo": "Fascicolo", "notifica": "Notifica preliminare"}
        self._salva_docx(f"{nomi[chiave]} - {cantiere}", lambda p: funzioni[chiave](self.repo, p))

    def genera_principale(self) -> None:
        self.genera()

    def aggiorna(self) -> None:
        corrente = self.impresa.currentData()
        self.impresa.clear()
        for i in self.repo.elenco("imprese"):
            nome = i["ragione_sociale"] or f"Impresa {i['id']}"
            if anagrafiche.autonomo(i):
                if "idoneita" in self.documenti:  # per gli autonomi c'è solo la verifica dell'idoneità
                    self.impresa.addItem(f"{nome} (lavoratore autonomo)", i["id"])
            else:
                self.impresa.addItem(nome, i["id"])
        self.impresa.setCurrentIndex(max(self.impresa.findData(corrente), 0))
        self.revisioni.ricarica()
        if self.composizioni is not None:
            self.composizioni.ricarica()
        obblighi = analisi.obblighi(self.repo.elenco("imprese"), self.repo.elenco("fasi"))
        for chiave, b in self._pulsanti_documenti:
            if chiave == "notifica":
                b.setText("Notifica preliminare" + ("" if obblighi.notifica else " (non obbligatoria)"))
                b.setToolTip("Notifica preliminare (art. 99): " + (
                    "obbligatoria per questo cantiere." if obblighi.notifica else
                    "per questo cantiere non è obbligatoria (una sola impresa e meno di "
                    f"{analisi.SOGLIA_UOMINI_GIORNO} uomini-giorno); la puoi comunque preparare."))
        self._controlla()
