"""Pagina dei ponteggi e del PiMUS."""

from __future__ import annotations


from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QFrame,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sicurcantiere import pimus
from sicurcantiere import ponteggio as P
from sicurcantiere.documenti.pimus import genera_pimus
from sicurcantiere.repository import Repository
from sicurcantiere.ui.pagine import ModuloRecord, Pagina, TestiLiberi, contesto_cantiere, primario
from sicurcantiere.ui.ponteggio_disegno import EditorGeometria, PannelloCalcoli
from sicurcantiere.ui.tabella import Colonna, TabellaCrud


def _scadenza(riga) -> str:
    scadenza = P.scadenza_formazione(riga)
    stato = P.stato_formazione(riga)
    return f"{scadenza.strftime('%d/%m/%Y')} · {stato}" if scadenza else stato


class PaginaPonteggi(Pagina):
    titolo = "Ponteggi e PiMUS"
    voce = "Ponteggi e PiMUS"
    icona = "ponteggi"
    sezioni_controlli = ("Ponteggi", "*")

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.id_: int | None = None
        self.tabella = TabellaCrud(repo, "ponteggi", [
            Colonna("nome", "Ponteggio / ubicazione", larghezza=220),
            Colonna("impresa_id", "Impresa che monta", "scelta", larghezza=190, scelte=self._imprese),
            Colonna("tipo", "Tipologia principale", "scelta", larghezza=200,
                    scelte=lambda: [(t, t) for t in pimus.TIPI_PONTEGGIO]),
            Colonna("altezza", "Altezza (m)", "decimale", larghezza=90, massimo=200),
            Colonna("lunghezza", "Sviluppo (m)", "decimale", larghezza=95, massimo=2000),
            Colonna("conforme_schemi", "Secondo schemi tipo", "scelta",
                    scelte=lambda: [(1, "Sì"), (0, "No (serve il progetto)")]),
        ], valori_nuovo=lambda: {"nome": "Ponteggio di facciata"})
        self.tabella.imposta_titolo("Ponteggi")
        genera = primario(QPushButton("Genera il PiMUS in Word..."))
        genera.clicked.connect(self._genera)
        self.tabella.aggiungi_pulsante("Unisci un altro ponteggio...", self._unisci)
        self.tabella.pulsanti.insertWidget(2, genera)
        self.tabella.selezione_cambiata.connect(self._seleziona)
        self.tabella.modificata.connect(self._elenco_modificato)

        self.avvisi = QLabel()
        self.avvisi.setWordWrap(True)
        self.avvisi.setStyleSheet("color: #D93B30;")

        self.dati = ModuloRecord(repo, "ponteggi", [
            (None, "Sistema di ponteggio e autorizzazione ministeriale (art. 131)"),
            ("fabbricante", "Fabbricante"),
            ("sistema", "Nome commerciale del sistema"),
            ("modello", "Modello o versione"),
            ("autorizzazione", "Autorizzazione ministeriale (numero e protocollo)"),
            ("aut_data", "Data dell'autorizzazione", "data"),
            ("aut_rinnovo", "Ultimo rinnovo (ogni dieci anni)", "data"),
            ("schemi_tipo", "Schemi tipo del libretto utilizzati", "testo_lungo"),
            (None, "Carichi, ancoraggi e appoggio"),
            ("classe_carico", "Classe di carico degli impalcati", "scelta", [n for n, _ in P.CLASSI_CARICO]),
            ("ancoraggi", "Descrizione degli ancoraggi (supporto, tasselli, prove di tenuta)"),
            ("piano_appoggio", "Piano di appoggio"),
            ("progettista", "Progettista (se è richiesto il progetto)"),
            ("sollevamento", "Attrezzature di sollevamento"),
            ("dpi", "DPI specifici"),
            (None, "Linee elettriche aeree (art. 117 e Allegato IX)"),
            ("linee_tensione", "Linea elettrica aerea vicina", "scelta", pimus.TENSIONI),
            ("linee_distanza", "Distanza minima dal ponteggio", "decimale", " m"),
        ])
        for campo in self.dati.campi.values():
            if hasattr(campo, "editingFinished"):
                campo.editingFinished.connect(self._aggiorna_avvisi)
        # la classe di carico entra nel calcolo del carico sugli appoggi
        self.dati.salvato = lambda _campo: (self.calcoli.carica(self.id_), self._aggiorna_avvisi())

        self.testi = TestiLiberi(repo, [(k, t) for k, t, _ in pimus.SEZIONI], altezza=90,
                                 contesto_ai=self._contesto_ai)
        testi_base = QPushButton("Inserisci i testi base nelle sezioni vuote")
        testi_base.clicked.connect(self._testi_base)
        contenitore_testi = QWidget()
        lt = QVBoxLayout(contenitore_testi)
        lt.addWidget(testi_base, alignment=Qt.AlignmentFlag.AlignLeft)
        lt.addWidget(self.testi)
        scorrimento = QScrollArea()
        scorrimento.setWidgetResizable(True)
        scorrimento.setWidget(contenitore_testi)

        self.verifiche = TabellaCrud(repo, "verifiche_ponteggio", [
            Colonna("momento", "Momento", "scelta", larghezza=170,
                    scelte=lambda: [(m, m) for m in ("Prima del montaggio", "Durante l'uso")]),
            Colonna("voce", "Verifica", "testo_lungo"),
            Colonna("esito", "Esito", "scelta", larghezza=140, scelte=lambda: [(e, e or "Da eseguire") for e in pimus.ESITI]),
            Colonna("note", "Note", larghezza=200),
        ])
        self.verifiche.imposta_titolo("Verifiche")
        carica = QPushButton("Carica l'elenco delle verifiche")
        carica.clicked.connect(self._carica_verifiche)
        self.verifiche.pulsanti.insertWidget(2, carica)

        self.geometria = EditorGeometria(repo)
        self.geometria.modificata.connect(self._geometria_cambiata)
        self.calcoli = PannelloCalcoli(repo)

        self.squadra = TabellaCrud(repo, "addetti_ponteggio", [
            Colonna("nome", "Nome e cognome", larghezza=200),
            Colonna("ruolo", "Ruolo", "scelta", larghezza=170, scelte=lambda: [(r, r) for r in P.RUOLI]),
            Colonna("corso_data", "Corso (data)", "data", larghezza=110),
            Colonna("corso_ente", "Ente formatore", larghezza=170),
            Colonna("aggiornamento_data", "Ultimo aggiornamento", "data", larghezza=140),
            Colonna("scadenza", "Valida fino al", "calcolata", calcola=_scadenza, larghezza=190,
                    suggerimento="4 anni dal corso o dall'ultimo aggiornamento (almeno 4 ore)"),
            Colonna("note", "Note"),
        ], valori_nuovo=lambda: {"ruolo": P.ADDETTO})
        self.squadra.imposta_titolo("Squadra di montaggio")
        self.squadra.aggiungi_pulsante("Dai lavoratori dell'impresa...", self._dai_lavoratori)
        self.squadra.modificata.connect(self._aggiorna_avvisi)
        nota_squadra = QLabel("Preposto e addetti devono avere il corso per il montaggio, lo smontaggio e la "
                              "trasformazione dei ponteggi (28 ore, Allegato XXI e Accordo Stato-Regioni del "
                              "17 aprile 2025), con aggiornamento di almeno 4 ore ogni 4 anni.")
        nota_squadra.setObjectName("hint")
        nota_squadra.setWordWrap(True)
        scheda_squadra = QWidget()
        ls = QVBoxLayout(scheda_squadra)
        ls.setContentsMargins(0, 6, 0, 0)
        ls.addWidget(self.squadra, 1)
        ls.addWidget(nota_squadra)

        self.allegati = TabellaCrud(repo, "allegati_ponteggio", [
            Colonna("tipo", "Tipo", "scelta", larghezza=220, scelte=lambda: [(t, t) for t in pimus.TIPI_ALLEGATO]),
            Colonna("titolo", "Titolo", "testo_lungo"),
            Colonna("file", "File", larghezza=320),
        ], valori_nuovo=lambda: {"tipo": pimus.TIPI_ALLEGATO[0]})
        self.allegati.imposta_titolo("File allegati al PiMUS")
        self.allegati.btn_aggiungi.hide()
        self.allegati.aggiungi_pulsante("Aggiungi file...", self._aggiungi_allegati)
        nota_allegati = QLabel("Immagini e PDF vengono inseriti in coda al PiMUS; i file restano nella loro cartella. "
                               "Il disegno esecutivo va firmato dal responsabile del cantiere (art. 134); se è "
                               "richiesto il progetto, allegarlo firmato dal progettista.")
        nota_allegati.setObjectName("hint")
        nota_allegati.setWordWrap(True)
        scheda_allegati = QWidget()
        la = QVBoxLayout(scheda_allegati)
        la.setContentsMargins(0, 6, 0, 0)
        la.addWidget(self.allegati, 1)
        la.addWidget(nota_allegati)

        self.schede = QTabWidget()
        scorrimento_dati = QScrollArea()
        scorrimento_dati.setWidgetResizable(True)
        scorrimento_dati.setFrameShape(QFrame.Shape.NoFrame)
        scorrimento_dati.setWidget(self.dati)
        self.schede.addTab(scorrimento_dati, "Dati del ponteggio")
        self.schede.addTab(self.geometria, "Disegno")
        self.schede.addTab(self.calcoli, "Calcoli e quantità")
        self.schede.addTab(scheda_squadra, "Squadra")
        self.schede.addTab(scorrimento, "Testi del PiMUS")
        self.schede.addTab(self.verifiche, "Verifiche (Allegato XIX)")
        self.schede.addTab(scheda_allegati, "Allegati")
        self.schede.currentChanged.connect(lambda _i: self._scheda_cambiata())
        self.schede.setEnabled(False)

        basso = QWidget()
        lb = QVBoxLayout(basso)
        lb.setContentsMargins(0, 0, 0, 0)
        # avvisi in un riquadro basso che scorre: il disegno sotto resta grande
        self.riquadro_avvisi = QScrollArea()
        self.riquadro_avvisi.setWidgetResizable(True)
        self.riquadro_avvisi.setFrameShape(QFrame.Shape.NoFrame)
        self.riquadro_avvisi.setWidget(self.avvisi)
        self.riquadro_avvisi.setMaximumHeight(64)
        lb.addWidget(self.riquadro_avvisi)
        lb.addWidget(self.schede)
        divisore = QSplitter(Qt.Orientation.Vertical)
        divisore.addWidget(self.tabella)
        divisore.addWidget(basso)
        divisore.setSizes([160, 640])
        self.layout_.addWidget(divisore)

    def _imprese(self):
        return [(None, "(da definire)")] + [
            (i["id"], i["ragione_sociale"] or f"Impresa {i['id']}") for i in self.repo.elenco("imprese")
        ]

    def _seleziona(self, id_: int | None) -> None:
        self.testi.salva_in_sospeso()
        self.id_ = id_
        self.schede.setEnabled(id_ is not None)
        self.dati.carica(id_)
        filtro = id_ if id_ is not None else -1
        self.testi.carica(lambda s, i=filtro: pimus.chiave_testo(i, s))
        self.verifiche.imposta_filtro(ponteggio_id=filtro)
        self.squadra.imposta_filtro(ponteggio_id=filtro)
        self.allegati.imposta_filtro(ponteggio_id=filtro)
        self.geometria.carica(id_)
        self.calcoli.carica(id_)
        self._aggiorna_avvisi()

    def _aggiorna_avvisi(self) -> None:
        p = self.repo.leggi("ponteggi", self.id_) if self.id_ is not None else None
        messaggi = pimus.avvisi_ponteggio(self.repo, p) if p else []
        self.avvisi.setText("\n".join(f"⚠ {m}" for m in messaggi))
        self.avvisi.setVisible(bool(messaggi))
        self.riquadro_avvisi.setVisible(bool(messaggi))
        self.riquadro_avvisi.setToolTip(self.avvisi.text())

    def _contesto_ai(self) -> str:
        p = self.repo.leggi("ponteggi", self.id_) if self.id_ is not None else {}
        # Senza nominativi (progettista, preposto, squadra): all'assistente non vanno dati personali.
        esclusi = ("id", "impresa_id", "progettista", "preposto", "squadra", "geometria")
        ponteggio = "\n".join(f"{k}: {v}" for k, v in (p or {}).items() if k not in esclusi and v)
        return f"{contesto_cantiere(self.repo)}\n\nPonteggio oggetto del PiMUS:\n{ponteggio}"

    def _elenco_modificato(self) -> None:
        """Altezza o tipologia cambiate nell'elenco: si ridisegna il ponteggio."""
        if self.id_ is not None:
            self.geometria.carica(self.id_)
            self.calcoli.carica(self.id_)
        self._aggiorna_avvisi()

    def _geometria_cambiata(self) -> None:
        # tipologia e sviluppo cambiano anche nell'elenco: si ricarica senza riaprire il ponteggio (i campi
        # che si stanno scrivendo non perdono il cursore)
        self.tabella.blockSignals(True)
        try:
            self.tabella.ricarica()
            self.tabella.seleziona(self.geometria.id_)
        finally:
            self.tabella.blockSignals(False)
        self._aggiorna_avvisi()

    def _scheda_cambiata(self) -> None:
        if self.schede.currentWidget() is self.calcoli:
            self.calcoli.carica(self.id_)
        elif self.schede.currentWidget() is self.geometria:
            self.geometria.carica(self.id_)

    def _unisci(self) -> None:
        """Porta in questo ponteggio i tratti, gli elementi, la squadra, le verifiche e gli allegati di un altro
        ponteggio del cantiere, che poi viene eliminato: due parti della stessa opera diventano un solo ponteggio."""
        if self.id_ is None:
            return
        altri = [p for p in self.repo.elenco("ponteggi") if p["id"] != self.id_]
        if not altri:
            QMessageBox.information(self, "Unisci ponteggi", "Nel cantiere non ci sono altri ponteggi da unire.")
            return
        from PySide6.QtWidgets import QInputDialog

        nomi = [f"{p['nome'] or 'Ponteggio'} ({p['id']})" for p in altri]
        scelta, ok = QInputDialog.getItem(self, "Unisci ponteggi", "Ponteggio da unire a questo:", nomi, 0, False)
        if not ok:
            return
        altro = altri[nomi.index(scelta)]
        risposta = QMessageBox.question(
            self, "Unisci ponteggi",
            f"I tratti, gli elementi, la squadra, le verifiche e gli allegati di «{altro['nome']}» passano in "
            "questo ponteggio, poi «" + (altro["nome"] or "Ponteggio") + "» viene eliminato. Continuare?")
        if risposta != QMessageBox.StandardButton.Yes:
            return
        self.unisci(altro["id"])

    def unisci(self, altro_id: int) -> None:
        questo = self.repo.leggi("ponteggi", self.id_)
        altro = self.repo.leggi("ponteggi", altro_id)
        g, g_altro = P.geometria(questo), P.geometria(altro)
        for t in g_altro["tratti"]:  # i tratti dell'altro mantengono la loro tipologia e altezza
            t["tipo"] = t["tipo"] or altro["tipo"]
            t["altezza"] = t["altezza"] or altro["altezza"]
        g = P.unisci(g, g_altro, P.tratti(questo, g))
        self.repo.aggiorna("ponteggi", self.id_, geometria=P.testo_geometria(g), lunghezza=P.sviluppo(g),
                           altezza=max(questo["altezza"], altro["altezza"]))
        for tabella in ("addetti_ponteggio", "verifiche_ponteggio", "allegati_ponteggio"):
            presenti = {(r.get("nome") or r.get("voce") or r.get("file")) for r in
                        self.repo.elenco(tabella, ponteggio_id=self.id_)}
            for r in self.repo.elenco(tabella, ponteggio_id=altro_id):
                if (r.get("nome") or r.get("voce") or r.get("file")) in presenti:
                    continue  # stesso addetto, stessa verifica o stesso file: non si duplica
                self.repo.aggiorna(tabella, r["id"], ponteggio_id=self.id_)
        self.repo.elimina("ponteggi", altro_id)
        id_ = self.id_
        self.tabella.ricarica()
        self.tabella.seleziona(id_)
        self._seleziona(id_)

    def _dai_lavoratori(self) -> None:
        """Aggiunge alla squadra i lavoratori dell'impresa che monta il ponteggio, scelti da un elenco."""
        if self.id_ is None:
            return
        p = self.repo.leggi("ponteggi", self.id_)
        filtro = {"impresa_id": p["impresa_id"]} if p["impresa_id"] else {}
        lavoratori = [l for l in self.repo.elenco("lavoratori", **filtro)
                      if f"{l['nome']} {l['cognome']}".strip()]
        if not lavoratori:
            QMessageBox.information(self, "Squadra", "L'impresa che monta il ponteggio non ha lavoratori in "
                                                     "anagrafica: aggiungi i nomi direttamente nella squadra.")
            return
        presenti = {a["lavoratore_id"] for a in self.repo.elenco("addetti_ponteggio", ponteggio_id=self.id_)}
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Lavoratori dell'impresa")
        elenco = QListWidget()
        for l in lavoratori:
            voce = QListWidgetItem(" ".join(v for v in (l["nome"], l["cognome"]) if v)
                                   + (f" · {l['mansione']}" if l["mansione"] else ""))
            voce.setData(Qt.ItemDataRole.UserRole, l)
            voce.setFlags(voce.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            voce.setCheckState(Qt.CheckState.Unchecked)
            if l["id"] in presenti:
                voce.setFlags(voce.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            elenco.addItem(voce)
        pulsanti = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        pulsanti.accepted.connect(dialogo.accept)
        pulsanti.rejected.connect(dialogo.reject)
        layout = QVBoxLayout(dialogo)
        layout.addWidget(QLabel("Scegli i lavoratori da aggiungere alla squadra di montaggio:"))
        layout.addWidget(elenco)
        layout.addWidget(pulsanti)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        self.aggiungi_lavoratori([elenco.item(i).data(Qt.ItemDataRole.UserRole) for i in range(elenco.count())
                                  if elenco.item(i).checkState() == Qt.CheckState.Checked])

    def aggiungi_lavoratori(self, lavoratori: list[dict]) -> None:
        for l in lavoratori:
            self.repo.inserisci("addetti_ponteggio", ponteggio_id=self.id_, lavoratore_id=l["id"],
                                nome=" ".join(v for v in (l["nome"], l["cognome"]) if v),
                                ruolo=P.PREPOSTO if "prepost" in (l["mansione"] or "").lower() else P.ADDETTO)
        self.squadra.ricarica()
        self._aggiorna_avvisi()

    def _aggiungi_allegati(self) -> None:
        if self.id_ is None:
            return
        file, _ = QFileDialog.getOpenFileNames(self, "File da allegare al PiMUS", "",
                                               "Immagini e PDF (*.png *.jpg *.jpeg *.bmp *.pdf)")
        for percorso in file:
            nome = Path(percorso).stem
            tipo = next((t for t in pimus.TIPI_ALLEGATO if t.split()[0].lower() in nome.lower()),
                        "Foto" if Path(percorso).suffix.lower() in (".jpg", ".jpeg") else pimus.TIPI_ALLEGATO[0])
            self.repo.inserisci("allegati_ponteggio", ponteggio_id=self.id_, tipo=tipo, titolo=nome, file=percorso)
        if file:
            self.allegati.ricarica()

    def _testi_base(self) -> None:
        for chiave, _, testo in pimus.SEZIONI:
            if not self.testi.editor[chiave].toPlainText().strip():
                self.testi.imposta_testo(chiave, testo)

    def _carica_verifiche(self) -> None:
        if self.id_ is None:
            return
        esistenti = {v["voce"] for v in self.repo.elenco("verifiche_ponteggio", ponteggio_id=self.id_)}
        for momento, voce in pimus.verifiche_per(P.tipologie(self.repo.leggi("ponteggi", self.id_))):
            if voce not in esistenti:
                self.repo.inserisci("verifiche_ponteggio", ponteggio_id=self.id_, momento=momento, voce=voce)
        self.verifiche.ricarica()

    def _genera(self) -> None:
        if self.id_ is None:
            QMessageBox.information(self, "PiMUS", "Seleziona prima un ponteggio.")
            return
        self.salva_in_sospeso()
        p = self.repo.leggi("ponteggi", self.id_)
        predefinito = self.repo.progetto.percorso.with_name(f"PiMUS - {p['nome'] or 'ponteggio'}.docx")
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva il PiMUS", str(predefinito), "Documento Word (*.docx)")
        if not percorso:
            return
        try:
            file = genera_pimus(self.repo, self.id_, percorso)
        except PermissionError:
            QMessageBox.warning(self, "Salvataggio non riuscito", "Impossibile salvare il file: verifica che non sia aperto in Word.")
            return
        from sicurcantiere.ui.anteprima import documento_creato
        from sicurcantiere.ui.pagine import AVVISO_RESPONSABILITA

        documento_creato(self, file, "PiMUS generato", AVVISO_RESPONSABILITA)

    def genera_principale(self) -> None:
        self._genera()

    def salva_in_sospeso(self) -> None:
        self.dati.salva_in_sospeso()
        self.testi.salva_in_sospeso()

    def aggiorna(self) -> None:
        self.tabella.ricarica()
