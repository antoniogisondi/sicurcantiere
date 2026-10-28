"""Schede «Disegno» e «Calcoli e quantità» della pagina dei ponteggi.

A sinistra il ponteggio come insieme di tratti (ognuno con tipologia, posizione, angolo, misure propri), i
valori comuni, il piano di appoggio e gli elementi inseriti; a destra lo schema che si aggiorna mentre si
scrive: vista tridimensionale da ruotare con il mouse, pianta (un clic sceglie il tratto, trascinando si
sposta un tratto staccato), prospetto di ogni tratto (un clic aggiunge o toglie l'ancoraggio o l'elemento
scelto) e sezione.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sicurcantiere import disegno_ponteggio as D
from sicurcantiere import elementi_ponteggio as E
from sicurcantiere import ponteggio as P
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema

ANCORAGGI = "ancoraggi"


class VistaPonteggio(QWidget):
    """Disegno del ponteggio.

    - 3D: si ruota trascinando, si ingrandisce con la rotellina, si sposta con il tasto destro, doppio clic
      per tornare alla vista iniziale;
    - pianta: un clic sceglie il tratto (segnale tratto_scelto); trascinando si sposta un tratto staccato
      (segnale tratto_spostato con la nuova posizione);
    - prospetto: un clic aggiunge o toglie l'ancoraggio (segnale nodo) o l'elemento scelto (segnale campata).
    """

    nodo = Signal(int, int, int)            # tratto, stilata, livello
    campata = Signal(int, int, int)         # tratto, campata, livello
    tratto_scelto = Signal(int)
    tratto_spostato = Signal(int, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ponteggio: dict[str, Any] | None = None
        self.tipo = D.TRE_D
        self.indice = 0
        self.evidenzia: int | None = None
        self.strumento = ANCORAGGI
        self.vista = D.Vista3D()
        self._partenza: QPointF | None = None
        self._destro = False
        self._trascina: tuple[int, float, float, float, float] | None = None  # tratto, x0, y0 in m, x, y
        self.setMinimumSize(300, 200)

    def imposta(self, ponteggio: dict[str, Any] | None) -> None:
        self.ponteggio = ponteggio
        self.update()

    def mostra(self, tipo: str, indice: int = 0) -> None:
        self.tipo, self.indice = tipo, indice
        self.setCursor(Qt.CursorShape.OpenHandCursor if tipo == D.TRE_D else
                       Qt.CursorShape.PointingHandCursor if tipo in (D.PROSPETTO, D.PIANTA) else
                       Qt.CursorShape.ArrowCursor)
        self.update()

    def _area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(4, 4, -4, -4)

    def paintEvent(self, _evento) -> None:  # noqa: N802 - nome di Qt
        pittore = QPainter(self)
        pittore.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.ponteggio is not None:
            D.disegna(pittore, self._area(), self.tipo, self.ponteggio, self.indice, self.vista,
                      evidenzia=self.evidenzia)
        else:
            pittore.setPen(QColor("#8A8F96"))
            pittore.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Seleziona un ponteggio")
        pittore.end()

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self.ponteggio is None:
            return
        x, y = evento.position().x(), evento.position().y()
        sinistro = evento.button() == Qt.MouseButton.LeftButton
        if self.tipo == D.PROSPETTO and sinistro:
            if self.strumento == ANCORAGGI:
                punto = D.nodo_prospetto(self._area(), self.ponteggio, self.indice, x, y)
                if punto is not None:
                    self.nodo.emit(self.indice, *punto)
            else:
                punto = D.campata_prospetto(self._area(), self.ponteggio, self.indice, x, y)
                if punto is not None:
                    self.campata.emit(self.indice, *punto)
            return
        if self.tipo == D.PIANTA and sinistro:
            indice = D.tratto_in_pianta(self._area(), self.ponteggio, x, y)
            if indice is not None:
                self.tratto_scelto.emit(indice)
                g = P.geometria(self.ponteggio)
                t = g["tratti"][indice]
                if not t["collegato"]:
                    mx, my = D.trasformazione_pianta(self._area(), self.ponteggio).metri(x, y)
                    self._trascina = (indice, t["x"], t["y"], mx, my)
            return
        self._partenza = evento.position()
        self._destro = not sinistro
        if self.tipo == D.TRE_D:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self._trascina is not None and self.ponteggio is not None:
            indice, x0, y0, mx0, my0 = self._trascina
            mx, my = D.trasformazione_pianta(self._area(), self.ponteggio).metri(evento.position().x(),
                                                                               evento.position().y())
            g = P.geometria(self.ponteggio)
            # passo di 5 cm, la scala della pianta resta quella di partenza durante il trascinamento
            g["tratti"][indice]["x"] = round((x0 + mx - mx0) * 20) / 20
            g["tratti"][indice]["y"] = round((y0 + my - my0) * 20) / 20
            self.ponteggio = {**self.ponteggio, "geometria": P.testo_geometria(g)}
            self._trascina = (indice, x0, y0, mx0, my0)
            self.update()
            return
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
        if self._trascina is not None and self.ponteggio is not None:
            indice = self._trascina[0]
            t = P.geometria(self.ponteggio)["tratti"][indice]
            self._trascina = None
            self.tratto_spostato.emit(indice, t["x"], t["y"])
            return
        self._partenza = None
        if self.tipo == D.TRE_D:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, _evento) -> None:  # noqa: N802 - nome di Qt
        if self.tipo == D.TRE_D:
            self.vista = D.Vista3D(mostra_edificio=self.vista.mostra_edificio)
            self.update()

    def wheelEvent(self, evento) -> None:  # noqa: N802 - nome di Qt
        if self.tipo != D.TRE_D:
            return
        fattore = 1.15 if evento.angleDelta().y() > 0 else 1 / 1.15
        self.vista.zoom = min(8.0, max(0.3, self.vista.zoom * fattore))
        self.update()


def _decimale(minimo: float, massimo: float, passo: float, decimali: int = 2, suffisso: str = " m",
              comune: bool = False) -> QDoubleSpinBox:
    """Campo numerico; con `comune` il valore minimo si legge «come il ponteggio»."""
    campo = QDoubleSpinBox()
    campo.setRange(minimo, massimo)
    campo.setSingleStep(passo)
    campo.setDecimals(decimali)
    campo.setSuffix(suffisso)
    campo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if comune:
        campo.setSpecialValueText("come il ponteggio")
    return campo


def _riga(*widget) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    for x in widget:
        layout.addWidget(x)
    return w


def _intervallo(testo: str, predefinito: tuple[int, int]) -> tuple[int, int]:
    """«3-5» → (3, 5); «4» → (4, 4)."""
    parti = [p for p in testo.replace("–", "-").replace(" ", "").split("-") if p]
    try:
        numeri = [int(p) for p in parti]
    except ValueError:
        return predefinito
    if not numeri:
        return predefinito
    return min(numeri), max(numeri)


class EditorGeometria(QWidget):
    """Geometria ed elementi del ponteggio selezionato, salvati in ponteggi.geometria a ogni modifica."""

    modificata = Signal()

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.id_: int | None = None
        self.g: dict[str, Any] = P.geometria({})
        self._caricamento = False

        # --- tratti ---
        self.tratti = QTableWidget(0, 4)
        self.tratti.setHorizontalHeaderLabels(["Tratto", "Lunghezza", "Altezza", "Tipologia"])
        self.tratti.verticalHeader().setVisible(False)
        self.tratti.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for colonna, larghezza in ((1, 84), (2, 72), (3, 120)):
            self.tratti.setColumnWidth(colonna, larghezza)
        self.tratti.horizontalHeaderItem(1).setToolTip("Lunghezza della facciata servita, in metri")
        self.tratti.horizontalHeaderItem(2).setToolTip("Altezza in metri dalla quota di partenza; vuota = quella "
                                                       "del ponteggio")
        self.tratti.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tratti.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tratti.setMinimumHeight(140)
        aggiungi = QPushButton("Aggiungi tratto")
        duplica = QPushButton("Duplica")
        togli = QPushButton("Togli")
        tema.imposta_variante(togli, "quiet")
        aggiungi.clicked.connect(self._aggiungi_tratto)
        duplica.clicked.connect(self._duplica_tratto)
        togli.clicked.connect(self._togli_tratto)

        # --- tratto selezionato ---
        self.t_tipo = QComboBox()
        self.t_tipo.addItem("Come il ponteggio", "")
        for t in P.TIPI_PONTEGGIO:
            self.t_tipo.addItem(t, t)
        self.t_posizione = QComboBox()
        self.t_posizione.addItem("Collegato alla fine del tratto precedente", True)
        self.t_posizione.addItem("Staccato, in una posizione libera", False)
        self.t_svolta = _decimale(-180, 180, 15, 1, "°")
        self.t_svolta.setToolTip("Rotazione rispetto al tratto precedente: 90° spigolo a sinistra, -90° a destra, "
                                 "0° prosegue sulla stessa facciata")
        self.t_x = _decimale(-1000, 1000, 0.5)
        self.t_y = _decimale(-1000, 1000, 0.5)
        self.t_angolo = _decimale(-360, 360, 15, 1, "°")
        self.t_quota = _decimale(-50, 200, 0.5)
        self.t_quota.setToolTip("Quota del piano di appoggio del tratto (terrazzo, copertura, terreno in pendenza)")
        self.t_spostamento = _decimale(-50, 50, 0.1)
        self.t_spostamento.setToolTip("Sposta le campate lungo la facciata (0: centrate sulla facciata)")
        self.t_campata = _decimale(0, 5, 0.05, comune=True)
        self.t_larghezza = _decimale(0, 3, 0.05, comune=True)
        self.t_distanza = _decimale(-0.05, 2, 0.05, comune=True)
        self.t_verso = QComboBox()
        self.t_verso.addItem("A destra della facciata (lato strada)", "esterno")
        self.t_verso.addItem("A sinistra della facciata (cortile, interno)", "interno")
        self.t_mantovana = QCheckBox("Mantovana su questo tratto")
        self.modulo_tratto = QFormLayout()
        self.modulo_tratto.addRow("Tipologia del tratto", self.t_tipo)
        self.modulo_tratto.addRow("Posizione", self.t_posizione)
        self.modulo_tratto.addRow("Svolta rispetto al precedente", self.t_svolta)
        self.riga_xy = _riga(self.t_x, self.t_y)
        self.modulo_tratto.addRow("Inizio della facciata (x, y)", self.riga_xy)
        self.modulo_tratto.addRow("Direzione della facciata", self.t_angolo)
        self.modulo_tratto.addRow("Quota di partenza", self.t_quota)
        self.modulo_tratto.addRow("Spostamento lungo la facciata", self.t_spostamento)
        self.modulo_tratto.addRow("Campata", self.t_campata)
        self.modulo_tratto.addRow("Larghezza impalcato", self.t_larghezza)
        self.modulo_tratto.addRow("Distanza dalla facciata", self.t_distanza)
        self.modulo_tratto.addRow("Lato del ponteggio", self.t_verso)
        self.modulo_tratto.addRow("", self.t_mantovana)
        tema.stile_modulo(self.modulo_tratto)
        self.scheda_tratto = tema.cornice("Tratto selezionato", self.modulo_tratto)

        # --- valori comuni ---
        self.campata = _decimale(0.5, 5, 0.05)
        self.campata.setToolTip("Lunghezza della campata secondo il libretto (valori tipici: "
                                + ", ".join(f"{c:.2f}".replace(".", ",") for c in P.CAMPATE) + " m)")
        self.larghezza = _decimale(0.3, 3, 0.05)
        self.larghezza.setToolTip("Larghezza dell'impalcato (tipiche: 0,75 e 1,05 m)")
        self.interpiano = _decimale(1, 4, 0.05)
        self.interpiano.setToolTip("Distanza tra due impalcati (di solito 2,00 m)")
        self.distanza = _decimale(0, 1.5, 0.05)
        self.distanza.setToolTip("Distanza tra il ponteggio e la facciata: oltre 0,20 m serve il parapetto anche "
                                 "sul lato interno (art. 138)")
        self.ancoraggi_campate = QSpinBox()
        self.ancoraggi_campate.setRange(1, 10)
        self.ancoraggi_campate.setSuffix(" campate")
        self.ancoraggi_livelli = QSpinBox()
        self.ancoraggi_livelli.setRange(1, 10)
        self.ancoraggi_livelli.setSuffix(" livelli")
        self.tipo_ancoraggio = QComboBox()
        self.tipo_ancoraggio.setEditable(True)
        self.tipo_ancoraggio.addItems(E.TIPI_ANCORAGGIO)
        self.rombo = QCheckBox("File sfalsate (a rombo)")
        self.mantovana = QCheckBox("Mantovana parasassi")
        self.mantovana_livello = QSpinBox()
        self.mantovana_livello.setRange(1, 60)
        self.mantovana_livello.setPrefix("al livello ")
        self.teli = QCheckBox("Teli o reti su tutta la facciata")
        modulo = QFormLayout()
        modulo.addRow("Campata", self.campata)
        modulo.addRow("Larghezza impalcato", self.larghezza)
        modulo.addRow("Interpiano", self.interpiano)
        modulo.addRow("Distanza dalla facciata", self.distanza)
        modulo.addRow("Un ancoraggio ogni", _riga(self.ancoraggi_campate, self.ancoraggi_livelli))
        modulo.addRow("", self.rombo)
        modulo.addRow("Tipo di ancoraggio", self.tipo_ancoraggio)
        modulo.addRow("", _riga(self.mantovana, self.mantovana_livello))
        modulo.addRow("", self.teli)
        tema.stile_modulo(modulo)

        # --- piano di appoggio ---
        self.peso_proprio = _decimale(0.05, 2, 0.05, 2, " kN/m²")
        self.peso_proprio.setToolTip("Peso del ponteggio per metro quadrato di facciata, dal libretto (circa "
                                     "0,25-0,35 kN/m² per i telai prefabbricati con impalcati metallici)")
        self.terreno = QComboBox()
        for nome, valore in P.TERRENI:
            self.terreno.addItem(f"{nome} ({valore:g} kPa)", valore)
        self.terreno.addItem("Altro valore (da indagine)", -1.0)
        self.portanza = _decimale(10, 5000, 10, 0, " kPa")
        self.area_appoggio = _decimale(0.01, 2, 0.01, 2, " m²")
        self.area_appoggio.setToolTip("Superficie della tavola o piastra di ripartizione sotto ogni basetta (una "
                                      "basetta da sola è circa 0,02 m²)")
        appoggio = QFormLayout()
        appoggio.addRow("Peso proprio", self.peso_proprio)
        appoggio.addRow("Piano di appoggio", self.terreno)
        appoggio.addRow("Portanza", self.portanza)
        appoggio.addRow("Ripartizione per basetta", self.area_appoggio)
        tema.stile_modulo(appoggio)

        # --- elementi inseriti ---
        self.elementi = QTableWidget(0, 6)
        self.elementi.setHorizontalHeaderLabels(["Elemento", "Tratto", "Campate", "Impalcati", "Quantità", "Note"])
        self.elementi.verticalHeader().setVisible(False)
        self.elementi.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for colonna, larghezza in ((1, 80), (2, 66), (3, 72), (4, 70), (5, 110)):
            self.elementi.setColumnWidth(colonna, larghezza)
        self.elementi.horizontalHeaderItem(2).setToolTip("Campate occupate, per esempio 3-5")
        self.elementi.horizontalHeaderItem(3).setToolTip("Impalcati occupati, per esempio 2-4 (0 = a terra)")
        self.elementi.horizontalHeaderItem(4).setToolTip("Vuota: calcolata dalle campate e dagli impalcati")
        self.elementi.setMinimumHeight(150)
        togli_elemento = QPushButton("Togli elemento")
        tema.imposta_variante(togli_elemento, "quiet")
        togli_elemento.clicked.connect(self._togli_elemento)

        colonna = QWidget()
        lc = QVBoxLayout(colonna)
        lc.setContentsMargins(0, 0, 6, 0)
        lc.addWidget(tema.cornice("Tratti del ponteggio", self._blocco(
            self.tratti, _riga(aggiungi, duplica, togli),
            "Un tratto per facciata o parte di facciata, anche di tipologia diversa (per esempio un raccordo in tubi "
            "e giunti in una strettoia) o ruotato: restano un unico ponteggio.")))
        lc.addWidget(self.scheda_tratto)
        lc.addWidget(tema.cornice("Valori comuni a tutti i tratti", modulo))
        lc.addWidget(tema.cornice("Elementi inseriti", self._blocco(
            self.elementi, _riga(togli_elemento),
            "Si inseriscono dal prospetto: scegli l'elemento in «Inserisci» e fai clic sulla campata.")))
        lc.addWidget(tema.cornice("Piano di appoggio", appoggio))
        lc.addStretch()
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setFrameShape(QFrame.Shape.NoFrame)
        scorrimento.setWidget(colonna)
        scorrimento.setMinimumWidth(360)

        # --- vista ---
        self.vista = VistaPonteggio()
        self.gruppo = QButtonGroup(self)
        self.gruppo.setExclusive(True)
        barra = QHBoxLayout()
        for n, (tipo, nome) in enumerate(((D.TRE_D, "3D"), (D.PIANTA, "Pianta"), (D.PROSPETTO, "Prospetto"),
                                          (D.SEZIONE, "Sezione"))):
            b = QPushButton(nome)
            b.setCheckable(True)
            b.setObjectName("filterChip")
            b.setProperty("tipo", tipo)
            self.gruppo.addButton(b, n)
            barra.addWidget(b)
        self.gruppo.button(0).setChecked(True)
        self.gruppo.buttonClicked.connect(lambda _b: self._cambia_vista())
        self.tratto_vista = QComboBox()
        self.tratto_vista.currentIndexChanged.connect(lambda i: self._scegli_tratto(i))
        barra.addWidget(self.tratto_vista)
        self.edificio = QCheckBox("Edificio")
        self.edificio.setChecked(True)
        self.edificio.toggled.connect(self._mostra_edificio)
        barra.addWidget(self.edificio)
        barra.addStretch()
        self.strumento = QComboBox()
        self.strumento.addItem("Ancoraggi", ANCORAGGI)
        for categoria in E.CATEGORIE:
            voci = [v for v in E.CATALOGO if v.categoria == categoria]
            if voci:
                self.strumento.insertSeparator(self.strumento.count())
                for v in voci:
                    self.strumento.addItem(f"{categoria} · {v.nome}", v.chiave)
                    self.strumento.setItemData(self.strumento.count() - 1, v.descrizione, Qt.ItemDataRole.ToolTipRole)
        self.strumento.currentIndexChanged.connect(self._cambia_strumento)
        for combo in (self.strumento, self.tratto_vista, self.tipo_ancoraggio, self.terreno, self.t_posizione,
                      self.t_verso):
            # i nomi lunghi non allargano la finestra: si leggono per intero nell'elenco che si apre
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(14)
        self.etichetta_strumento = QLabel("Inserisci")
        self.riga_strumento = _riga(self.etichetta_strumento, self.strumento)
        self.riga_strumento.layout().setStretch(1, 1)
        self.nota_vista = QLabel()
        self.nota_vista.setObjectName("hint")
        self.nota_vista.setWordWrap(True)
        destra = QWidget()
        ld = QVBoxLayout(destra)
        ld.setContentsMargins(6, 0, 0, 0)
        ld.addLayout(barra)
        ld.addWidget(self.riga_strumento)
        ld.addWidget(self.vista, 1)
        ld.addWidget(self.nota_vista)

        divisore = QSplitter(Qt.Orientation.Horizontal)
        divisore.addWidget(scorrimento)
        divisore.addWidget(destra)
        divisore.setStretchFactor(0, 2)
        divisore.setStretchFactor(1, 4)
        divisore.setSizes([440, 800])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(divisore)

        # --- collegamenti ---
        self.tratti.itemChanged.connect(self._tratti_modificati)
        self.tratti.itemSelectionChanged.connect(self._tratto_selezionato)
        self.elementi.itemChanged.connect(self._elementi_modificati)
        for campo in (self.t_svolta, self.t_x, self.t_y, self.t_angolo, self.t_quota, self.t_spostamento,
                      self.t_campata, self.t_larghezza, self.t_distanza):
            campo.valueChanged.connect(self._tratto_modificato)
        for combo in (self.t_tipo, self.t_posizione, self.t_verso):
            combo.currentIndexChanged.connect(self._tratto_modificato)
        self.t_mantovana.toggled.connect(self._tratto_modificato)
        for campo in (self.campata, self.larghezza, self.interpiano, self.distanza, self.peso_proprio,
                      self.portanza, self.area_appoggio, self.ancoraggi_campate, self.ancoraggi_livelli,
                      self.mantovana_livello):
            campo.valueChanged.connect(self._comuni_modificati)
        for spunta in (self.rombo, self.mantovana, self.teli):
            spunta.toggled.connect(self._comuni_modificati)
        self.tipo_ancoraggio.currentTextChanged.connect(self._comuni_modificati)
        self.terreno.currentIndexChanged.connect(self._terreno_scelto)
        self.vista.nodo.connect(self._cambia_ancoraggio)
        self.vista.campata.connect(self._cambia_elemento)
        self.vista.tratto_scelto.connect(self._seleziona_tratto)
        self.vista.tratto_spostato.connect(self._sposta_tratto)
        self._cambia_vista()

    @staticmethod
    def _blocco(tabella, pulsanti, nota: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabella)
        layout.addWidget(pulsanti)
        etichetta = QLabel(nota)
        etichetta.setObjectName("hint")
        etichetta.setWordWrap(True)
        layout.addWidget(etichetta)
        return w

    # --- caricamento ---

    def ponteggio(self) -> dict[str, Any] | None:
        return self.repo.leggi("ponteggi", self.id_) if self.id_ is not None else None

    def indice_tratto(self) -> int:
        r = self.tratti.currentRow()
        return r if 0 <= r < len(self.g["tratti"]) else 0

    def carica(self, id_: int | None) -> None:
        self.id_ = id_
        self.setEnabled(id_ is not None)
        p = self.ponteggio()
        self._caricamento = True
        try:
            if p is None:
                self.tratti.setRowCount(0)
                self.elementi.setRowCount(0)
                self.vista.imposta(None)
                return
            self.g = P.geometria(p)
            g = self.g
            self.campata.setValue(g["campata"])
            self.larghezza.setValue(g["larghezza"])
            self.interpiano.setValue(g["interpiano"])
            self.distanza.setValue(g["distanza"])
            self.ancoraggi_campate.setValue(g["ancoraggi_campate"])
            self.ancoraggi_livelli.setValue(g["ancoraggi_livelli"])
            self.rombo.setChecked(g["ancoraggi_rombo"])
            self.tipo_ancoraggio.setCurrentText(g["tipo_ancoraggio"])
            self.mantovana.setChecked(g["mantovana"])
            self.mantovana_livello.setValue(g["mantovana_livello"])
            self.teli.setChecked(g["teli"])
            self.peso_proprio.setValue(g["peso_proprio"])
            indice = self.terreno.findData(g["terreno"])
            self.terreno.setCurrentIndex(indice if indice >= 0 else self.terreno.count() - 1)
            self.portanza.setValue(g["terreno"])
            self.portanza.setEnabled(indice < 0)
            self.area_appoggio.setValue(g["area_appoggio"])
        finally:
            self._caricamento = False
        self._mostra(p, mantieni=False)

    def _mostra(self, p: dict[str, Any], mantieni: bool = True) -> None:
        """Riempie tratti ed elementi e ridisegna, mantenendo il tratto selezionato."""
        selezionato = self.indice_tratto() if mantieni else 0
        self._caricamento = True
        try:
            elenco = P.tratti(p, self.g)
            self.tratti.setRowCount(len(elenco))
            for r, (t, dati) in enumerate(zip(elenco, self.g["tratti"])):
                self.tratti.setItem(r, 0, QTableWidgetItem(dati["nome"]))
                for c, valore in ((1, dati["lunghezza"]), (2, dati["altezza"])):
                    item = QTableWidgetItem(f"{valore:g}".replace(".", ",") if valore else "")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.tratti.setItem(r, c, item)
                tipo = QTableWidgetItem(t.tipo)
                tipo.setFlags(tipo.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tratti.setItem(r, 3, tipo)
            selezionato = min(selezionato, len(elenco) - 1)
            self.tratti.selectRow(selezionato)
            self.tratto_vista.blockSignals(True)
            self.tratto_vista.clear()
            for t in elenco:
                self.tratto_vista.addItem(t.nome)
            self.tratto_vista.setCurrentIndex(selezionato)
            self.tratto_vista.blockSignals(False)
            self._mostra_elementi(elenco)
            self._carica_tratto(selezionato)
        finally:
            self._caricamento = False
        self.vista.evidenzia = selezionato
        self.vista.imposta(p)
        self._cambia_vista()

    def _mostra_elementi(self, elenco: list[P.Tratto]) -> None:
        self.elementi.setRowCount(len(self.g["elementi"]))
        for r, e in enumerate(self.g["elementi"]):
            v = E.voce(e["tipo"])
            t = elenco[e["tratto"]]
            valori = [v.nome if v else e["tipo"], t.nome,
                      f"{e['da'] + 1}" if e["da"] == e["a"] else f"{e['da'] + 1}-{e['a'] + 1}",
                      f"{e['livello']}" if e["livello"] == e["livello_a"] else f"{e['livello']}-{e['livello_a']}",
                      (f"{e['quantita']:g}".replace(".", ",") if e["quantita"] else ""), e["note"]]
            for c, valore in enumerate(valori):
                item = QTableWidgetItem(valore)
                if c in (0, 1):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 4 and not e["quantita"]:
                    q = E.quantita(e, t.campata, t.interpiano)
                    item.setToolTip(f"Calcolata: {q:g}")
                self.elementi.setItem(r, c, item)

    def _carica_tratto(self, indice: int) -> None:
        if not self.g["tratti"]:
            return
        t = self.g["tratti"][indice]
        self.scheda_tratto.findChild(QLabel, "cardTitle").setText(f"Tratto selezionato · {t['nome']}")
        self.t_tipo.setCurrentIndex(max(0, self.t_tipo.findData(t["tipo"])))
        self.t_posizione.setCurrentIndex(0 if t["collegato"] else 1)
        self.t_posizione.setEnabled(indice > 0)
        self.t_svolta.setValue(t["svolta"])
        self.t_x.setValue(t["x"])
        self.t_y.setValue(t["y"])
        self.t_angolo.setValue(t["angolo"])
        self.t_quota.setValue(t["quota"])
        self.t_spostamento.setValue(t["spostamento"])
        self.t_campata.setValue(t["campata"] or 0)
        self.t_larghezza.setValue(t["larghezza"] or 0)
        self.t_distanza.setValue(-0.05 if t["distanza"] is None else t["distanza"])
        self.t_verso.setCurrentIndex(max(0, self.t_verso.findData(t["verso"])))
        self.t_mantovana.setChecked(t["mantovana"])
        self._visibilita_posizione(t["collegato"])

    def _visibilita_posizione(self, collegato: bool) -> None:
        for campo, visibile in ((self.t_svolta, collegato), (self.riga_xy, not collegato),
                                (self.t_angolo, not collegato)):
            campo.setVisible(visibile)
            etichetta = self.modulo_tratto.labelForField(campo)
            if etichetta is not None:
                etichetta.setVisible(visibile)

    # --- salvataggio ---

    def _registra(self) -> None:
        if self.id_ is None:
            return
        self.g = P.geometria({"geometria": P.testo_geometria(self.g)})
        self.repo.aggiorna("ponteggi", self.id_, geometria=P.testo_geometria(self.g), lunghezza=P.sviluppo(self.g))
        self._mostra(self.ponteggio())
        self.modificata.emit()

    def _tratti_modificati(self, item: QTableWidgetItem) -> None:
        if self._caricamento:
            return
        r, c = item.row(), item.column()
        t = self.g["tratti"][r]
        if c == 0:
            t["nome"] = item.text().strip() or f"Tratto {r + 1}"
        elif c in (1, 2):
            try:
                valore = max(0.0, float(item.text().replace(",", ".") or 0))
            except ValueError:
                valore = t["lunghezza" if c == 1 else "altezza"]
            t["lunghezza" if c == 1 else "altezza"] = valore
        self._registra()

    def _tratto_modificato(self, *_args) -> None:
        if self._caricamento or not self.g["tratti"]:
            return
        i = self.indice_tratto()
        t = self.g["tratti"][i]
        collegato = bool(self.t_posizione.currentData()) and i > 0
        if collegato != t["collegato"] and self.id_ is not None:
            # passando da collegato a staccato il tratto resta dov'è
            calcolato = P.tratti(self.ponteggio(), self.g)[i]
            self.t_x.blockSignals(True)
            self.t_y.blockSignals(True)
            self.t_angolo.blockSignals(True)
            self.t_x.setValue(calcolato.origine[0])
            self.t_y.setValue(calcolato.origine[1])
            self.t_angolo.setValue(calcolato.angolo if calcolato.angolo <= 180 else calcolato.angolo - 360)
            for campo in (self.t_x, self.t_y, self.t_angolo):
                campo.blockSignals(False)
        t.update({
            "tipo": self.t_tipo.currentData() or "", "collegato": collegato, "svolta": self.t_svolta.value(),
            "x": self.t_x.value(), "y": self.t_y.value(), "angolo": self.t_angolo.value(),
            "quota": self.t_quota.value(), "spostamento": self.t_spostamento.value(),
            "campata": self.t_campata.value() or None, "larghezza": self.t_larghezza.value() or None,
            "distanza": None if self.t_distanza.value() < 0 else self.t_distanza.value(),
            "verso": self.t_verso.currentData(), "mantovana": self.t_mantovana.isChecked(),
        })
        self._visibilita_posizione(collegato)
        self._registra()

    def _comuni_modificati(self, *_args) -> None:
        if self._caricamento:
            return
        self.g.update({
            "campata": self.campata.value(), "larghezza": self.larghezza.value(),
            "interpiano": self.interpiano.value(), "distanza": self.distanza.value(),
            "ancoraggi_campate": self.ancoraggi_campate.value(), "ancoraggi_livelli": self.ancoraggi_livelli.value(),
            "ancoraggi_rombo": self.rombo.isChecked(), "tipo_ancoraggio": self.tipo_ancoraggio.currentText(),
            "mantovana": self.mantovana.isChecked(), "mantovana_livello": self.mantovana_livello.value(),
            "teli": self.teli.isChecked(), "peso_proprio": self.peso_proprio.value(),
            "terreno": self.portanza.value(), "area_appoggio": self.area_appoggio.value(),
        })
        self._registra()

    def _terreno_scelto(self, _indice: int) -> None:
        valore = self.terreno.currentData()
        self.portanza.setEnabled(valore is not None and valore < 0)
        if valore is not None and valore > 0:
            self.portanza.setValue(valore)  # salva tramite valueChanged
        else:
            self._comuni_modificati()

    def _elementi_modificati(self, item: QTableWidgetItem) -> None:
        if self._caricamento:
            return
        e = self.g["elementi"][item.row()]
        testo = item.text()
        if item.column() == 2:
            da, a = _intervallo(testo, (e["da"] + 1, e["a"] + 1))
            e["da"], e["a"] = max(0, da - 1), max(0, a - 1)
        elif item.column() == 3:
            e["livello"], e["livello_a"] = _intervallo(testo, (e["livello"], e["livello_a"]))
        elif item.column() == 4:
            try:
                e["quantita"] = max(0.0, float(testo.replace(",", ".") or 0))
            except ValueError:
                pass
        elif item.column() == 5:
            e["note"] = testo
        self._registra()

    # --- comandi ---

    def _aggiungi_tratto(self) -> None:
        nomi = ["Nord", "Est", "Sud", "Ovest"]
        n = len(self.g["tratti"])
        self.g["tratti"].append({**P.TRATTO, "nome": nomi[n % 4] if n < 4 else f"Tratto {n + 1}",
                                 "collegato": True, "svolta": 90.0})
        self._registra()
        self.tratti.selectRow(n)

    def _duplica_tratto(self) -> None:
        if not self.g["tratti"]:
            return
        i = self.indice_tratto()
        copia = {**self.g["tratti"][i], "nome": self.g["tratti"][i]["nome"] + " (copia)", "collegato": True,
                 "svolta": 0.0, "aggiunti": [], "tolti": []}
        self.g["tratti"].insert(i + 1, copia)
        for e in self.g["elementi"]:
            if e["tratto"] > i:
                e["tratto"] += 1
        self._registra()
        self.tratti.selectRow(i + 1)

    def _togli_tratto(self) -> None:
        if len(self.g["tratti"]) <= 1:
            return
        i = self.indice_tratto()
        del self.g["tratti"][i]
        self.g["elementi"] = [{**e, "tratto": e["tratto"] - (1 if e["tratto"] > i else 0)}
                              for e in self.g["elementi"] if e["tratto"] != i]
        if self.g["tratti"]:
            self.g["tratti"][0]["collegato"] = False
        self._registra()

    def _togli_elemento(self) -> None:
        r = self.elementi.currentRow()
        if 0 <= r < len(self.g["elementi"]):
            del self.g["elementi"][r]
            self._registra()

    def _cambia_ancoraggio(self, indice: int, stilata: int, livello: int) -> None:
        if self.id_ is None:
            return
        self.g = P.cambia_ancoraggio(self.g, self.ponteggio(), indice, stilata, livello)
        self._registra()

    def _cambia_elemento(self, indice: int, campata: int, livello: int) -> None:
        tipo = self.strumento.currentData()
        if self.id_ is None or not tipo or tipo == ANCORAGGI:
            return
        self.g = P.cambia_elemento(self.g, tipo, indice, campata, livello)
        self._registra()

    def _seleziona_tratto(self, indice: int) -> None:
        self.tratti.selectRow(indice)

    def _sposta_tratto(self, indice: int, x: float, y: float) -> None:
        if 0 <= indice < len(self.g["tratti"]):
            self.g["tratti"][indice]["x"], self.g["tratti"][indice]["y"] = x, y
            self._registra()

    # --- vista ---

    def _tratto_selezionato(self) -> None:
        if self._caricamento:
            return
        i = self.indice_tratto()
        self._caricamento = True
        try:
            self._carica_tratto(i)
            self.tratto_vista.setCurrentIndex(i)
        finally:
            self._caricamento = False
        self.vista.evidenzia = i
        self._cambia_vista()

    def _scegli_tratto(self, indice: int) -> None:
        if not self._caricamento and indice >= 0:
            self.tratti.selectRow(indice)
        self._cambia_vista()

    def _cambia_strumento(self, _indice: int) -> None:
        self.vista.strumento = self.strumento.currentData() or ANCORAGGI
        self._cambia_vista()

    def _cambia_vista(self) -> None:
        tipo = self.gruppo.checkedButton().property("tipo") if self.gruppo.checkedButton() else D.TRE_D
        self.tratto_vista.setVisible(tipo in (D.PROSPETTO, D.SEZIONE))
        self.edificio.setVisible(tipo == D.TRE_D)
        self.riga_strumento.setVisible(tipo == D.PROSPETTO)
        strumento = self.strumento.currentData()
        self.nota_vista.setText({
            D.TRE_D: "Trascina per ruotare, rotellina per ingrandire, tasto destro per spostare, doppio clic per "
                     "tornare alla vista iniziale. Il tratto selezionato è evidenziato.",
            D.PIANTA: "Clic su un tratto per sceglierlo; trascina un tratto staccato per spostarlo.",
            D.PROSPETTO: "Clic su un nodo per aggiungere o togliere un ancoraggio (tratteggiati quelli dello schema "
                         "tolti a mano)." if strumento == ANCORAGGI else
                         "Clic su una campata, all'altezza dell'impalcato, per inserire o togliere l'elemento.",
            D.SEZIONE: "",
        }[tipo])
        self.nota_vista.setVisible(bool(self.nota_vista.text()))
        self.vista.mostra(tipo, max(0, self.tratto_vista.currentIndex()))

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
            f"<b>{a.numero}</b> ancoraggi ({g['tipo_ancoraggio'].lower()}) · {_n(a.area_facciata, 1)} m² di "
            f"facciata · <b>{_n(a.area_per_ancoraggio, 1)} m²</b> per ancoraggio (riferimento usuale "
            f"{P.AREA_PER_ANCORAGGIO:g} m²)<br>{a.maglia}.")
        s = P.appoggio(p, g)
        esito = ("<span style='color:#1E6B34'><b>pressione entro la portanza</b></span>" if s.verificato else
                 f"<span style='color:#B42318'><b>pressione oltre la portanza</b></span>: ripartizione di almeno "
                 f"{_n(s.area_minima, 2)} m² per basetta")
        self.appoggio.setText(
            f"Carico sul montante più caricato ({s.tratto}): <b>{_n(s.carico_montante, 2)} kN</b> (sovraccarico "
            f"{_n(s.sovraccarico, 2)} kN/m²{'' if P.sovraccarico(p['classe_carico']) else ', classe 3 in mancanza della classe'})"
            f"<br>Pressione sul terreno: <b>{_n(s.pressione, 0)} kPa</b> su {_n(g['area_appoggio'], 2)} m² · "
            f"portanza {_n(s.portanza, 0)} kPa<br>{esito}.")
        voci = P.elementi(p, g)
        self.elementi.setRowCount(len(voci))
        for r, (nome, quantita, unita) in enumerate(voci):
            self.elementi.setItem(r, 0, QTableWidgetItem(nome))
            q = QTableWidgetItem(_n(quantita, 1 if isinstance(quantita, float) and not float(quantita).is_integer()
                                    else 0))
            q.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.elementi.setItem(r, 1, q)
            self.elementi.setItem(r, 2, QTableWidgetItem(unita))


def _n(valore: float, cifre: int = 0) -> str:
    return P._n(valore, cifre)


__all__ = ["EditorGeometria", "PannelloCalcoli", "VistaPonteggio", "json"]
