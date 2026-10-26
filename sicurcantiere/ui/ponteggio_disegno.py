"""Schede «Disegno» e «Calcoli e quantità» della pagina dei ponteggi.

A sinistra i dati della geometria (lati, campata, impalcati, ancoraggi, mantovana, piano di appoggio), a
destra lo schema che si aggiorna mentre si scrive: vista tridimensionale da ruotare con il mouse, pianta,
prospetto di ogni lato e sezione tipo.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QFrame)

from sicurcantiere import disegno_ponteggio as D
from sicurcantiere import pimus
from sicurcantiere import ponteggio as P
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema


class VistaPonteggio(QWidget):
    """Disegno del ponteggio: nella vista 3D si ruota trascinando, si ingrandisce con la rotellina e si
    torna alla vista iniziale con un doppio clic; nel prospetto un clic su un nodo aggiunge o toglie
    l'ancoraggio (segnale nodo: lato, stilata, livello)."""

    nodo = Signal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ponteggio: dict[str, Any] | None = None
        self.tipo = D.TRE_D
        self.indice = 0
        self.vista = D.Vista3D()
        self._partenza: QPointF | None = None
        self._destro = False
        self.setMinimumSize(320, 260)
        self.setMouseTracking(False)

    def imposta(self, ponteggio: dict[str, Any] | None) -> None:
        self.ponteggio = ponteggio
        self.update()

    def mostra(self, tipo: str, indice: int = 0) -> None:
        self.tipo, self.indice = tipo, indice
        self.setCursor(Qt.CursorShape.OpenHandCursor if tipo == D.TRE_D else
                       Qt.CursorShape.PointingHandCursor if tipo == D.PROSPETTO else Qt.CursorShape.ArrowCursor)
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - nome di Qt
        pittore = QPainter(self)
        pittore.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.ponteggio is not None:
            D.disegna(pittore, self._area(), self.tipo, self.ponteggio, self.indice, self.vista)
        else:
            pittore.setPen(QColor("#8A8F96"))
            pittore.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Seleziona un ponteggio")
        pittore.end()

    def _area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(4, 4, -4, -4)

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self.tipo == D.PROSPETTO and self.ponteggio is not None and evento.button() == Qt.MouseButton.LeftButton:
            punto = D.nodo_prospetto(self._area(), self.ponteggio, self.indice, evento.position().x(),
                                     evento.position().y())
            if punto is not None:
                self.nodo.emit(self.indice, *punto)
            return
        self._partenza = evento.position()
        self._destro = evento.button() != Qt.MouseButton.LeftButton
        if self.tipo == D.TRE_D:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self._partenza is None or self.tipo != D.TRE_D:
            return
        delta = evento.position() - self._partenza
        self._partenza = evento.position()
        if self._destro:  # tasto destro o centrale: sposta il disegno
            x, y = self.vista.spostamento
            self.vista.spostamento = (x + delta.x(), y + delta.y())
        else:
            self.vista.rotazione = (self.vista.rotazione - delta.x() * 0.5) % 360
            self.vista.inclinazione = min(89.0, max(0.0, self.vista.inclinazione + delta.y() * 0.4))
        self.update()

    def mouseReleaseEvent(self, _evento) -> None:  # noqa: N802 - nome di Qt
        self._partenza = None
        if self.tipo == D.TRE_D:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, _evento) -> None:  # noqa: N802 - nome di Qt
        self.vista = D.Vista3D(mostra_edificio=self.vista.mostra_edificio)
        self.update()

    def wheelEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self.tipo != D.TRE_D:
            return
        fattore = 1.15 if evento.angleDelta().y() > 0 else 1 / 1.15
        self.vista.zoom = min(8.0, max(0.3, self.vista.zoom * fattore))
        self.update()


def _decimale(minimo: float, massimo: float, passo: float, decimali: int = 2, suffisso: str = " m") -> QDoubleSpinBox:
    campo = QDoubleSpinBox()
    campo.setRange(minimo, massimo)
    campo.setSingleStep(passo)
    campo.setDecimals(decimali)
    campo.setSuffix(suffisso)
    campo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return campo


class EditorGeometria(QWidget):
    """Dati della geometria del ponteggio selezionato, salvati in ponteggi.geometria a ogni modifica."""

    modificata = Signal()

    COLONNE_LATI = ("Lato / facciata", "Lunghezza (m)", "Altezza (m)", "Mantovana")

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.id_: int | None = None
        self._caricamento = False

        self.tipo = QComboBox()
        for t in pimus.TIPI_PONTEGGIO:
            self.tipo.addItem(t, t)
        self.forma = QComboBox()
        self.forma.addItem("Lati in sequenza (facciata, a L, a U)", "aperta")
        self.forma.addItem("Perimetro chiuso (giro completo)", "chiusa")
        self.lati = QTableWidget(0, 4)
        self.lati.setHorizontalHeaderLabels(self.COLONNE_LATI)
        self.lati.verticalHeader().setVisible(False)
        self.lati.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for colonna, larghezza in ((1, 92), (2, 82), (3, 84)):
            self.lati.setColumnWidth(colonna, larghezza)
        self.lati.setHorizontalHeaderLabels(("Lato / facciata", "Lunghezza", "Altezza", "Mantovana"))
        self.lati.horizontalHeaderItem(1).setToolTip("Lunghezza della facciata in metri")
        self.lati.horizontalHeaderItem(2).setToolTip("Altezza in metri; vuota = quella del ponteggio")
        self.lati.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lati.setMinimumHeight(130)
        self.lati.setToolTip("Un lato per ogni facciata, nell'ordine in cui si gira attorno all'edificio (a ogni "
                             "spigolo si gira di 90°). Altezza vuota o 0: quella del ponteggio.")
        aggiungi = QPushButton("Aggiungi lato")
        togli = QPushButton("Togli lato")
        tema.imposta_variante(togli, "quiet")
        aggiungi.clicked.connect(self._aggiungi_lato)
        togli.clicked.connect(self._togli_lato)
        pulsanti_lati = QHBoxLayout()
        pulsanti_lati.addWidget(aggiungi)
        pulsanti_lati.addWidget(togli)
        pulsanti_lati.addStretch()

        self.campata = _decimale(0.5, 5, 0.05)
        self.campata.setToolTip("Lunghezza della campata secondo il libretto (valori tipici: "
                                + ", ".join(f"{c:.2f}".replace(".", ",") for c in P.CAMPATE) + " m)")
        self.larghezza = _decimale(0.3, 3, 0.05)
        self.larghezza.setToolTip("Larghezza dell'impalcato (tipiche: 0,75 e 1,05 m)")
        self.interpiano = _decimale(1, 4, 0.05)
        self.interpiano.setToolTip("Distanza tra due impalcati (di solito 2,00 m)")
        self.distanza = _decimale(0, 1.5, 0.05)
        self.distanza.setToolTip("Distanza tra il ponteggio e la facciata: oltre 0,20 m serve il parapetto "
                                 "anche sul lato interno")
        self.ancoraggi_campate = QSpinBox()
        self.ancoraggi_campate.setRange(1, 10)
        self.ancoraggi_campate.setSuffix(" campate")
        self.ancoraggi_livelli = QSpinBox()
        self.ancoraggi_livelli.setRange(1, 10)
        self.ancoraggi_livelli.setSuffix(" livelli")
        self.rombo = QCheckBox("File sfalsate (a rombo)")
        self.mantovana = QCheckBox("Mantovana parasassi")
        self.mantovana_livello = QSpinBox()
        self.mantovana_livello.setRange(1, 60)
        self.mantovana_livello.setPrefix("al livello ")
        self.teli = QCheckBox("Teli o reti sulla facciata")
        self.peso_proprio = _decimale(0.05, 2, 0.05, 2, " kN/m²")
        self.peso_proprio.setToolTip("Peso del ponteggio per metro quadrato di facciata, dal libretto "
                                     "(circa 0,25-0,35 kN/m² per i telai prefabbricati con impalcati metallici)")
        self.terreno = QComboBox()
        for nome, valore in P.TERRENI:
            self.terreno.addItem(f"{nome} ({valore:g} kPa)", valore)
        self.terreno.addItem("Altro valore (da indagine)", -1.0)
        self.portanza = _decimale(10, 5000, 10, 0, " kPa")
        self.area_appoggio = _decimale(0.01, 2, 0.01, 2, " m²")
        self.area_appoggio.setToolTip("Superficie della tavola o piastra di ripartizione sotto ogni basetta "
                                      "(una basetta da sola è circa 0,02 m²)")

        modulo = QFormLayout()
        modulo.addRow("Campata", self.campata)
        modulo.addRow("Larghezza impalcato", self.larghezza)
        modulo.addRow("Interpiano", self.interpiano)
        modulo.addRow("Distanza dalla facciata", self.distanza)
        ancoraggi = QHBoxLayout()
        ancoraggi.addWidget(self.ancoraggi_campate)
        ancoraggi.addWidget(self.ancoraggi_livelli)
        modulo.addRow("Un ancoraggio ogni", ancoraggi)
        modulo.addRow("", self.rombo)
        mantovana = QHBoxLayout()
        mantovana.addWidget(self.mantovana)
        mantovana.addWidget(self.mantovana_livello)
        modulo.addRow("", self._riga(mantovana))
        modulo.addRow("", self.teli)
        appoggio = QFormLayout()
        appoggio.addRow("Peso proprio", self.peso_proprio)
        appoggio.addRow("Piano di appoggio", self.terreno)
        appoggio.addRow("Portanza", self.portanza)
        appoggio.addRow("Ripartizione per basetta", self.area_appoggio)
        for m in (modulo, appoggio):
            tema.stile_modulo(m)

        colonna = QWidget()
        lc = QVBoxLayout(colonna)
        lc.setContentsMargins(0, 0, 6, 0)
        lc.addWidget(QLabel("Tipologia"))
        lc.addWidget(self.tipo)
        lc.addWidget(QLabel("Forma"))
        lc.addWidget(self.forma)
        lc.addWidget(self.lati)
        lc.addLayout(pulsanti_lati)
        lc.addWidget(tema.cornice("Elementi e ancoraggi", modulo))
        lc.addWidget(tema.cornice("Piano di appoggio", appoggio))
        lc.addStretch()
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setFrameShape(QFrame.Shape.NoFrame)
        scorrimento.setWidget(colonna)
        scorrimento.setMinimumWidth(400)

        self.vista = VistaPonteggio()
        self.scelta_vista = QHBoxLayout()
        self.gruppo = QButtonGroup(self)
        self.gruppo.setExclusive(True)
        for n, (tipo, nome) in enumerate(((D.TRE_D, "3D"), (D.PIANTA, "Pianta"), (D.PROSPETTO, "Prospetto"),
                                          (D.SEZIONE, "Sezione"))):
            b = QPushButton(nome)
            b.setCheckable(True)
            b.setObjectName("filterChip")
            b.setProperty("tipo", tipo)
            self.gruppo.addButton(b, n)
            self.scelta_vista.addWidget(b)
        self.gruppo.button(0).setChecked(True)
        self.gruppo.buttonClicked.connect(lambda _b: self._cambia_vista())
        self.lato_prospetto = QComboBox()
        self.lato_prospetto.currentIndexChanged.connect(lambda _i: self._cambia_vista())
        self.scelta_vista.addWidget(self.lato_prospetto)
        self.edificio = QCheckBox("Edificio")
        self.edificio.setChecked(True)
        self.edificio.toggled.connect(self._mostra_edificio)
        self.scelta_vista.addWidget(self.edificio)
        self.scelta_vista.addStretch()
        nota = QLabel("Trascina per ruotare, rotellina per ingrandire, tasto destro per spostare, doppio clic per "
                      "tornare alla vista iniziale.")
        nota.setObjectName("hint")
        nota.setWordWrap(True)
        destra = QWidget()
        ld = QVBoxLayout(destra)
        ld.setContentsMargins(6, 0, 0, 0)
        ld.addLayout(self.scelta_vista)
        ld.addWidget(self.vista, 1)
        ld.addWidget(nota)
        self.nota_vista = nota

        divisore = QSplitter(Qt.Orientation.Horizontal)
        divisore.addWidget(scorrimento)
        divisore.addWidget(destra)
        divisore.setStretchFactor(0, 2)
        divisore.setStretchFactor(1, 4)
        divisore.setSizes([420, 800])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(divisore)

        self.forma.currentIndexChanged.connect(self._salva)
        self.tipo.currentIndexChanged.connect(self._salva)
        self.vista.nodo.connect(self._cambia_ancoraggio)
        self.lati.itemChanged.connect(self._salva)
        for campo in (self.campata, self.larghezza, self.interpiano, self.distanza, self.peso_proprio,
                      self.portanza, self.area_appoggio, self.ancoraggi_campate, self.ancoraggi_livelli,
                      self.mantovana_livello):
            campo.valueChanged.connect(self._salva)
        for spunta in (self.rombo, self.mantovana, self.teli):
            spunta.toggled.connect(self._salva)
        self.terreno.currentIndexChanged.connect(self._terreno_scelto)
        self._cambia_vista()

    @staticmethod
    def _riga(layout) -> QWidget:
        w = QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    # --- caricamento e salvataggio ---

    def carica(self, id_: int | None) -> None:
        self.id_ = id_
        self.setEnabled(id_ is not None)
        p = self.repo.leggi("ponteggi", id_) if id_ is not None else None
        self._caricamento = True
        try:
            if p is None:
                self.lati.setRowCount(0)
                self.vista.imposta(None)
                return
            g = P.geometria(p)
            indice_tipo = self.tipo.findData(p["tipo"])
            if indice_tipo < 0 and p["tipo"]:
                self.tipo.addItem(p["tipo"], p["tipo"])
                indice_tipo = self.tipo.count() - 1
            self.tipo.setCurrentIndex(max(0, indice_tipo))
            self.forma.setCurrentIndex(max(0, self.forma.findData(g["forma"])))
            self.lati.setRowCount(0)
            self._lati_dati = g["lati"]
            for lato in g["lati"]:
                self._riga_lato(lato["nome"], lato["lunghezza"], lato["altezza"], lato["mantovana"])
            self.campata.setValue(g["campata"])
            self.larghezza.setValue(g["larghezza"])
            self.interpiano.setValue(g["interpiano"])
            self.distanza.setValue(g["distanza"])
            self.ancoraggi_campate.setValue(g["ancoraggi_campate"])
            self.ancoraggi_livelli.setValue(g["ancoraggi_livelli"])
            self.rombo.setChecked(g["ancoraggi_rombo"])
            self.mantovana.setChecked(g["mantovana"])
            self.mantovana_livello.setValue(g["mantovana_livello"])
            self.teli.setChecked(g["teli"])
            self.peso_proprio.setValue(g["peso_proprio"])
            indice = self.terreno.findData(g["terreno"])
            self.terreno.setCurrentIndex(indice if indice >= 0 else self.terreno.count() - 1)
            self.portanza.setValue(g["terreno"])
            self.portanza.setEnabled(indice < 0)
            self.area_appoggio.setValue(g["area_appoggio"])
            self._aggiorna_lati_prospetto(g)
            self.vista.imposta(p)
        finally:
            self._caricamento = False

    def _riga_lato(self, nome: str, lunghezza: float, altezza: float, mantovana: bool = True) -> None:
        r = self.lati.rowCount()
        self.lati.insertRow(r)
        self.lati.setItem(r, 0, QTableWidgetItem(nome))
        spunta = QTableWidgetItem()
        spunta.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        spunta.setCheckState(Qt.CheckState.Checked if mantovana else Qt.CheckState.Unchecked)
        self.lati.setItem(r, 3, spunta)
        for c, valore in ((1, lunghezza), (2, altezza)):
            item = QTableWidgetItem(f"{valore:g}".replace(".", ",") if valore else "")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lati.setItem(r, c, item)

    def _valori_lati(self) -> list[dict[str, Any]]:
        def numero(r: int, c: int) -> float:
            item = self.lati.item(r, c)
            try:
                return max(0.0, float((item.text() if item else "").replace(",", ".") or 0))
            except ValueError:
                return 0.0

        precedenti = getattr(self, "_lati_dati", [])
        risultato = []
        for r in range(self.lati.rowCount()):
            vecchio = precedenti[r] if r < len(precedenti) else {}
            risultato.append({
                "nome": (self.lati.item(r, 0).text() if self.lati.item(r, 0) else "").strip() or f"Lato {r + 1}",
                "lunghezza": numero(r, 1), "altezza": numero(r, 2),
                "mantovana": self.lati.item(r, 3) is None or self.lati.item(r, 3).checkState() == Qt.CheckState.Checked,
                # ancoraggi aggiunti o tolti a mano sul prospetto
                "aggiunti": vecchio.get("aggiunti", []), "tolti": vecchio.get("tolti", [])})
        return risultato

    def geometria(self) -> dict[str, Any]:
        return {"forma": self.forma.currentData(), "lati": self._valori_lati(),
                "campata": self.campata.value(), "larghezza": self.larghezza.value(),
                "interpiano": self.interpiano.value(), "distanza": self.distanza.value(),
                "ancoraggi_campate": self.ancoraggi_campate.value(),
                "ancoraggi_livelli": self.ancoraggi_livelli.value(), "ancoraggi_rombo": self.rombo.isChecked(),
                "mantovana": self.mantovana.isChecked(), "mantovana_livello": self.mantovana_livello.value(),
                "teli": self.teli.isChecked(), "peso_proprio": self.peso_proprio.value(),
                "terreno": self.portanza.value(), "area_appoggio": self.area_appoggio.value()}

    def _salva(self, *_args) -> None:
        if self._caricamento or self.id_ is None:
            return
        g = P.geometria({"geometria": P.testo_geometria(self.geometria())})
        self._registra(g)

    def _registra(self, g: dict[str, Any]) -> None:
        self._lati_dati = g["lati"]
        valori = {"geometria": P.testo_geometria(g), "lunghezza": P.sviluppo(g), "tipo": self.tipo.currentData()}
        self.repo.aggiorna("ponteggi", self.id_, **valori)
        p = self.repo.leggi("ponteggi", self.id_)
        self._aggiorna_lati_prospetto(g)
        self.vista.imposta(p)
        self.modificata.emit()

    def _cambia_ancoraggio(self, indice: int, stilata: int, livello: int) -> None:
        if self.id_ is None:
            return
        p = self.repo.leggi("ponteggi", self.id_)
        g = P.cambia_ancoraggio(P.geometria(p), p, indice, stilata, livello)
        self._registra(g)

    def _terreno_scelto(self, _indice: int) -> None:
        valore = self.terreno.currentData()
        self.portanza.setEnabled(valore is not None and valore < 0)
        if valore is not None and valore > 0:
            self.portanza.setValue(valore)  # salva tramite valueChanged
        else:
            self._salva()

    def _aggiungi_lato(self) -> None:
        nomi = ["Nord", "Est", "Sud", "Ovest"]
        r = self.lati.rowCount()
        self._caricamento = True
        self._riga_lato(nomi[r % 4] if r < 4 else f"Lato {r + 1}", 10.0, 0)
        self._caricamento = False
        self._salva()

    def _togli_lato(self) -> None:
        if self.lati.rowCount() <= 1:
            return
        r = self.lati.currentRow()
        r = r if r >= 0 else self.lati.rowCount() - 1
        self.lati.removeRow(r)
        self._lati_dati = [l for n, l in enumerate(getattr(self, "_lati_dati", [])) if n != r]
        self._salva()

    # --- vista ---

    def _aggiorna_lati_prospetto(self, g: dict[str, Any]) -> None:
        attuale = self.lato_prospetto.currentIndex()
        self.lato_prospetto.blockSignals(True)
        self.lato_prospetto.clear()
        for lato in g["lati"]:
            self.lato_prospetto.addItem(lato["nome"])
        self.lato_prospetto.setCurrentIndex(min(max(attuale, 0), self.lato_prospetto.count() - 1))
        self.lato_prospetto.blockSignals(False)
        self._cambia_vista()

    def _cambia_vista(self) -> None:
        tipo = self.gruppo.checkedButton().property("tipo") if self.gruppo.checkedButton() else D.TRE_D
        self.lato_prospetto.setVisible(tipo == D.PROSPETTO)
        self.edificio.setVisible(tipo == D.TRE_D)
        if hasattr(self, "nota_vista"):
            self.nota_vista.setText(
                "Trascina per ruotare, rotellina per ingrandire, tasto destro per spostare, doppio clic per tornare "
                "alla vista iniziale." if tipo == D.TRE_D else
                "Clic su un nodo per aggiungere o togliere un ancoraggio (i cerchi tratteggiati sono quelli dello "
                "schema tolti a mano)." if tipo == D.PROSPETTO else "")
            self.nota_vista.setVisible(tipo in (D.TRE_D, D.PROSPETTO))
        self.vista.mostra(tipo, max(0, self.lato_prospetto.currentIndex()))

    def _mostra_edificio(self, visibile: bool) -> None:
        self.vista.vista.mostra_edificio = visibile
        self.vista.update()


class PannelloCalcoli(QWidget):
    """Riepilogo calcolato dalla geometria: ancoraggi, verifica del piano di appoggio, elementi."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.id_: int | None = None
        self.ancoraggi = QLabel()
        self.appoggio = QLabel()
        for etichetta in (self.ancoraggi, self.appoggio):
            etichetta.setWordWrap(True)
            etichetta.setTextFormat(Qt.TextFormat.RichText)
        self.elementi = QTableWidget(0, 3)
        self.elementi.setHorizontalHeaderLabels(["Elemento", "Quantità", "Unità"])
        self.elementi.verticalHeader().setVisible(False)
        self.elementi.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.elementi.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        nota = QLabel("Stime per preparare il PiMUS e controllare i dati: il numero e la posizione degli ancoraggi, "
                      "gli elementi e i carichi ammessi sono quelli del libretto del fabbricante o del progetto.")
        nota.setObjectName("hint")
        nota.setWordWrap(True)
        alto = QHBoxLayout()
        alto.addWidget(tema.cornice("Ancoraggi", self.ancoraggi), 1)
        alto.addWidget(tema.cornice("Piano di appoggio", self.appoggio), 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addLayout(alto)
        layout.addWidget(tema.cornice("Elementi (quantità indicative)", self.elementi), 1)
        layout.addWidget(nota)

    def carica(self, id_: int | None) -> None:
        self.id_ = id_
        p = self.repo.leggi("ponteggi", id_) if id_ is not None else None
        if p is None:
            self.ancoraggi.clear()
            self.appoggio.clear()
            self.elementi.setRowCount(0)
            return
        g = P.geometria(p)
        a = P.ancoraggi(p, g)
        self.ancoraggi.setText(
            f"<b>{a.numero}</b> ancoraggi · {_n(a.area_facciata, 1)} m² di facciata · "
            f"<b>{_n(a.area_per_ancoraggio, 1)} m²</b> per ancoraggio (riferimento usuale "
            f"{P.AREA_PER_ANCORAGGIO:g} m²)<br>{a.maglia}.")
        s = P.appoggio(p, g)
        esito = ("<span style='color:#1E6B34'><b>pressione entro la portanza</b></span>" if s.verificato else
                 f"<span style='color:#B42318'><b>pressione oltre la portanza</b></span>: ripartizione di almeno "
                 f"{_n(s.area_minima, 2)} m² per basetta")
        self.appoggio.setText(
            f"Carico sul montante più caricato: <b>{_n(s.carico_montante, 2)} kN</b> (sovraccarico "
            f"{_n(s.sovraccarico, 2)} kN/m²{'' if P.sovraccarico(p['classe_carico']) else ', classe 3 in mancanza della classe'})"
            f"<br>Pressione sul terreno: <b>{_n(s.pressione, 0)} kPa</b> su {_n(g['area_appoggio'], 2)} m² · "
            f"portanza {_n(s.portanza, 0)} kPa<br>{esito}.")
        voci = P.elementi(p, g)
        self.elementi.setRowCount(len(voci))
        for r, (nome, quantita, unita) in enumerate(voci):
            self.elementi.setItem(r, 0, QTableWidgetItem(nome))
            q = QTableWidgetItem(_n(quantita, 1 if isinstance(quantita, float) else 0))
            q.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.elementi.setItem(r, 1, q)
            self.elementi.setItem(r, 2, QTableWidgetItem(unita))


def _n(valore: float, cifre: int = 0) -> str:
    return P._n(valore, cifre)
