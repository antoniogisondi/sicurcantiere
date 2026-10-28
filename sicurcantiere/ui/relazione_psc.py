"""Parti della pagina «Relazione del PSC» che non sono semplici testi: lavori a rischio particolare
(Allegato XI), rischio da ordigni bellici (art. 91, comma 2-bis), tavole e foto allegate (punto 2.1.4),
logo dello studio del coordinatore per la copertina."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sicurcantiere import relazione
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema
from sicurcantiere.ui.tabella import Colonna, TabellaCrud

TIPI_ALLEGATO = ("Foto o mappa del cantiere", "Planimetria di cantiere", "Tavola tecnica degli scavi",
                 "Profilo altimetrico", "Altro elaborato")
CHIAVE_LOGO = "logo_studio"


class RischiParticolari(QWidget):
    """Rischi da analizzare nelle lavorazioni (punto 2.2.3), Allegato XI con le misure per le voci presenti, e
    valutazione del rischio da ordigni bellici."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._carico = False
        self._timer = QTimer(self, singleShot=True, interval=600)
        self._timer.timeout.connect(self.salva)

        # rischi del punto 2.2.3: quelli trovati nelle schede delle fasi sono indicati accanto
        self.verificato_223 = QCheckBox("Ho analizzato i rischi del punto 2.2.3: sono spuntati quelli presenti nel "
                                        "cantiere, con le misure", self)
        griglia_223 = QGridLayout()
        griglia_223.setColumnStretch(1, 2)
        griglia_223.setColumnStretch(2, 2)
        self.voci_223: dict[str, tuple[QCheckBox, QLineEdit, QLabel]] = {}
        for riga, (lettera, testo, _) in enumerate(relazione.RISCHI_LAVORAZIONI):
            spunta = QCheckBox(f"{lettera})", self)
            etichetta = QLabel(testo, self)
            etichetta.setWordWrap(True)
            misure = QLineEdit(self)
            misure.setPlaceholderText("Misure generali (quelle delle fasi sono già nelle schede)")
            trovato = QLabel(self)
            trovato.setObjectName("hint")
            trovato.setWordWrap(True)
            griglia_223.addWidget(spunta, 2 * riga, 0)
            griglia_223.addWidget(etichetta, 2 * riga, 1)
            griglia_223.addWidget(misure, 2 * riga, 2)
            griglia_223.addWidget(trovato, 2 * riga + 1, 1, 1, 2)
            spunta.toggled.connect(self._modificato)
            misure.textChanged.connect(self._modificato)
            self.voci_223[lettera] = (spunta, misure, trovato)
        self.verificato_223.toggled.connect(self._modificato)
        corpo_223 = QVBoxLayout()
        corpo_223.addWidget(self.verificato_223)
        corpo_223.addLayout(griglia_223)
        riquadro_223 = tema.cornice("Rischi da analizzare nelle lavorazioni (Allegato XV punto 2.2.3)", corpo_223)

        self.verificato = QCheckBox("Ho verificato l'elenco dei lavori comportanti rischi particolari "
                                    "(Allegato XI): sono spuntati quelli presenti nel cantiere", self)
        griglia = QGridLayout()
        griglia.setColumnStretch(1, 2)
        griglia.setColumnStretch(2, 2)
        self.voci: dict[str, tuple[QCheckBox, QLineEdit]] = {}
        for riga, (numero, testo) in enumerate(relazione.ALLEGATO_XI):
            spunta = QCheckBox(f"{numero}.", self)
            etichetta = QLabel(testo, self)
            etichetta.setWordWrap(True)
            misure = QLineEdit(self)
            misure.setPlaceholderText("Misure specifiche previste (se il lavoro è presente)")
            griglia.addWidget(spunta, riga, 0)
            griglia.addWidget(etichetta, riga, 1)
            griglia.addWidget(misure, riga, 2)
            spunta.toggled.connect(self._modificato)
            misure.textChanged.connect(self._modificato)
            self.voci[numero] = (spunta, misure)
        self.verificato.toggled.connect(self._modificato)
        corpo_xi = QVBoxLayout()
        corpo_xi.addWidget(self.verificato)
        corpo_xi.addLayout(griglia)
        riquadro_xi = tema.cornice("Lavori comportanti rischi particolari (Allegato XI)", corpo_xi)

        self.scavi = QComboBox(self)
        for voce in relazione.SCAVI:
            self.scavi.addItem(voce or "Non indicato", voce)
        self.esito = QComboBox(self)
        for voce in relazione.ESITI_ORDIGNI:
            self.esito.addItem(voce or "Non ancora valutato", voce)
        self.motivazione = QPlainTextEdit(self)
        self.motivazione.setPlaceholderText(
            "Motivazione e fonti consultate: storia del sito, bombardamenti documentati, precedenti scavi, "
            "indagini o bonifiche già eseguite, profondità degli scavi previsti.")
        self.motivazione.setMinimumHeight(90)
        self.avviso_scavi = QLabel(self)
        self.avviso_scavi.setObjectName("hint")
        self.avviso_scavi.setWordWrap(True)
        modulo = QFormLayout()
        modulo.addRow("Sono previsti scavi?", self.scavi)
        modulo.addRow("Esito della valutazione", self.esito)
        modulo.addRow("Motivazione", self.motivazione)
        modulo.addRow(self.avviso_scavi)
        for segnale in (self.scavi.currentIndexChanged, self.esito.currentIndexChanged):
            segnale.connect(self._modificato)
        self.motivazione.textChanged.connect(self._modificato)
        riquadro_ordigni = tema.cornice("Rischio da ordigni bellici inesplosi (art. 91, comma 2-bis)", modulo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(riquadro_223)
        layout.addWidget(riquadro_xi)
        layout.addWidget(riquadro_ordigni)
        layout.addStretch()

    def _modificato(self, *_args) -> None:
        if not self._carico:
            self._timer.start()

    def salva(self) -> None:
        self._timer.stop()
        dati = {"verificato": self.verificato.isChecked(),
                "voci": {n: {"presente": s.isChecked(), "misure": m.text().strip()} for n, (s, m) in self.voci.items()}}
        nuovo = json.dumps(dati, ensure_ascii=False)
        if nuovo != self.repo.testo(relazione.CHIAVE_ALLEGATO_XI):
            self.repo.salva_testo(relazione.CHIAVE_ALLEGATO_XI, nuovo)
        dati_223 = {"verificato": self.verificato_223.isChecked(),
                    "voci": {l: {"presente": sp.isChecked(), "misure": m.text().strip()}
                             for l, (sp, m, _) in self.voci_223.items()}}
        nuovo_223 = json.dumps(dati_223, ensure_ascii=False)
        if nuovo_223 != self.repo.testo(relazione.CHIAVE_RISCHI_LAVORAZIONI):
            self.repo.salva_testo(relazione.CHIAVE_RISCHI_LAVORAZIONI, nuovo_223)
        ordigni = json.dumps({"scavi": self.scavi.currentData(), "esito": self.esito.currentData(),
                              "motivazione": self.motivazione.toPlainText().strip()}, ensure_ascii=False)
        if ordigni != self.repo.testo(relazione.CHIAVE_ORDIGNI):
            self.repo.salva_testo(relazione.CHIAVE_ORDIGNI, ordigni)

    def carica(self) -> None:
        self.salva()
        self._carico = True
        dati = relazione.leggi_allegato_xi(self.repo.testo(relazione.CHIAVE_ALLEGATO_XI))
        self.verificato.setChecked(dati["verificato"])
        for n, (spunta, misure) in self.voci.items():
            spunta.setChecked(dati["voci"][n]["presente"])
            misure.setText(dati["voci"][n]["misure"])
        dati_223 = relazione.leggi_rischi_lavorazioni(self.repo.testo(relazione.CHIAVE_RISCHI_LAVORAZIONI))
        trovati = relazione.fasi_per_rischio(self.repo.elenco("fasi"), self.repo.rischi())
        self.verificato_223.setChecked(dati_223["verificato"])
        for l, (spunta, misure, etichetta) in self.voci_223.items():
            spunta.setChecked(dati_223["voci"][l]["presente"])
            misure.setText(dati_223["voci"][l]["misure"])
            fasi = trovati.get(l, [])
            etichetta.setText(("Nelle fasi: " + ", ".join(f"{f['codice']} {f['descrizione']}".strip() for f in fasi[:4])
                               + ("..." if len(fasi) > 4 else "")) if fasi else "")
            etichetta.setVisible(bool(fasi))
        ordigni = relazione.leggi_ordigni(self.repo.testo(relazione.CHIAVE_ORDIGNI))
        self.scavi.setCurrentIndex(max(self.scavi.findData(ordigni["scavi"]), 0))
        self.esito.setCurrentIndex(max(self.esito.findData(ordigni["esito"]), 0))
        self.motivazione.setPlainText(ordigni["motivazione"])
        con_scavi = relazione.fasi_con_scavi(self.repo.elenco("fasi"))
        self.avviso_scavi.setText(
            "Nel cronoprogramma ci sono fasi di scavo (" + ", ".join(f"{f['codice']} {f['descrizione']}".strip()
                                                                    for f in con_scavi[:3])
            + ("..." if len(con_scavi) > 3 else "") + "): la valutazione va eseguita." if con_scavi else
            "La valutazione spetta al coordinatore per la progettazione; se decide la bonifica preventiva, il "
            "committente incarica un'impresa specializzata.")
        self._carico = False


class AllegatiPSC(QWidget):
    """Foto e mappe del cantiere, planimetria e tavole (immagini o PDF) da allegare al PSC."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.tabella = TabellaCrud(repo, "allegati_psc", [
            Colonna("tipo", "Tipo", "scelta", scelte=lambda: [(t, t) for t in TIPI_ALLEGATO], larghezza=210),
            Colonna("titolo", "Titolo", "testo_lungo"),
            Colonna("file", "File", larghezza=320),
        ], valori_nuovo=lambda: {"tipo": TIPI_ALLEGATO[1]}, genitore=self)
        self.tabella.imposta_titolo("Tavole e foto allegate")
        self.tabella.btn_aggiungi.hide()
        self.tabella.aggiungi_pulsante("Aggiungi file...", self._aggiungi)
        nota = QLabel("Il PSC deve avere almeno una planimetria del cantiere (Allegato XV punto 2.1.4). Le immagini "
                      "e le pagine dei PDF vengono inserite nel documento; i file restano nella loro cartella.", self)
        nota.setObjectName("hint")
        nota.setWordWrap(True)

        self.logo = QLineEdit(self)
        self.logo.setReadOnly(True)
        self.logo.setPlaceholderText("Nessun logo: in copertina compaiono i dati dello studio del CSP")
        scegli = QPushButton("Scegli il logo...", self)
        scegli.clicked.connect(self._scegli_logo)
        togli = QPushButton("Rimuovi", self)
        tema.imposta_variante(togli, "quiet")
        togli.clicked.connect(lambda: self._imposta_logo(""))
        riga_logo = QHBoxLayout()
        riga_logo.addWidget(self.logo, 1)
        riga_logo.addWidget(scegli)
        riga_logo.addWidget(togli)

        # cosa riporta la planimetria (layout di cantiere): le voci essenziali mancanti sono segnalate nei controlli
        griglia = QGridLayout()
        self.contenuti: dict[str, QCheckBox] = {}
        for n, (voce, essenziale) in enumerate(relazione.CONTENUTI_PLANIMETRIA):
            spunta = QCheckBox(voce + ("" if essenziale else " (se presente)"), self)
            spunta.toggled.connect(self._salva_contenuti)
            griglia.addWidget(spunta, n // 2, n % 2)
            self.contenuti[voce] = spunta

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabella, 1)
        layout.addWidget(nota)
        layout.addWidget(tema.cornice("Cosa riporta la planimetria di cantiere", griglia))
        layout.addWidget(tema.cornice("Logo dello studio del coordinatore (copertina del PSC)", riga_logo))

    def _aggiungi(self) -> None:
        file, _ = QFileDialog.getOpenFileNames(self, "Tavole e foto del PSC", "",
                                               "Immagini e PDF (*.png *.jpg *.jpeg *.bmp *.pdf)")
        for percorso in file:
            tipo = TIPI_ALLEGATO[0] if Path(percorso).suffix.lower() in (".jpg", ".jpeg") else TIPI_ALLEGATO[1]
            self.repo.inserisci("allegati_psc", tipo=tipo, titolo=Path(percorso).stem, file=percorso)
        if file:
            self.tabella.ricarica()

    def _scegli_logo(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(self, "Logo dello studio", "", "Immagini (*.png *.jpg *.jpeg)")
        if percorso:
            self._imposta_logo(percorso)

    def _imposta_logo(self, percorso: str) -> None:
        self.repo.salva_testo(CHIAVE_LOGO, percorso)
        self.logo.setText(percorso)

    def _salva_contenuti(self, *_args) -> None:
        if getattr(self, "_carico_contenuti", False):
            return
        testo = ";".join(v for v, spunta in self.contenuti.items() if spunta.isChecked())
        if testo != self.repo.testo(relazione.CHIAVE_CONTENUTI_PLANIMETRIA):
            self.repo.salva_testo(relazione.CHIAVE_CONTENUTI_PLANIMETRIA, testo)

    def carica(self) -> None:
        self.tabella.ricarica()
        self.logo.setText(self.repo.testo(CHIAVE_LOGO))
        presenti = relazione.leggi_contenuti_planimetria(self.repo.testo(relazione.CHIAVE_CONTENUTI_PLANIMETRIA))
        self._carico_contenuti = True
        for voce, spunta in self.contenuti.items():
            spunta.setChecked(voce in presenti)
        self._carico_contenuti = False
