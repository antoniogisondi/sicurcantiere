"""Documenti composti e salvati nel cantiere: bozze, emissione, consegna, capitoli modificati, confronto."""

from __future__ import annotations

import hashlib
import html
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from sicurcantiere import composizioni as comp
from sicurcantiere.documenti import composizione
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema
from sicurcantiere.ui.icone import icona


def _data_ora(valore: str | None) -> str:
    if not valore:
        return ""
    try:
        d = datetime.fromisoformat(valore)
    except ValueError:
        return valore
    return d.strftime("%d/%m/%Y %H:%M") if "T" in valore else d.strftime("%d/%m/%Y")


def cartella_lavoro() -> Path:
    """Copie dei documenti aperte in Word, accanto alle copie di sicurezza dei cantieri."""
    from sicurcantiere.db import cartella_copie

    return cartella_copie().parent / "documenti aperti in Word"


def _riassunto_mancanti(c: dict[str, Any]) -> str:
    obbligatori = len(comp.obbligatori_mancanti(c))
    totale = len(c["mancanti"])
    if not totale:
        return "nessuno"
    return f"{obbligatori} obbligatori · {totale} in tutto" if obbligatori else f"{totale} non obbligatori"


class PannelloComposizioni(QWidget):
    """Elenco delle composizioni di un documento (POS dell'impresa scelta, PSC) e azioni su di esse.

    `documento()` restituisce la chiave del documento corrente (\"POS:3\", \"PSC\") o None.
    La lista dei dati da completare (`mancanti`) la colloca la pagina dove preferisce.
    """

    COLONNE = ("Rev.", "Stato", "Composta il", "Descrizione", "Dati mancanti", "Note")

    def __init__(self, repo: Repository, documento: Callable[[], str | None], nome: str, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.documento = documento
        self.nome = nome  # «POS», «PSC»
        self._copie: dict[int, tuple[Path, float]] = {}

        # Riquadro come gli elenchi delle altre pagine: titolo con il numero di documenti e pulsanti
        # nell'intestazione, tabella sotto, nota in fondo.
        self.setObjectName("card")
        self.titolo = QLabel("Documenti composti", self)
        self.titolo.setObjectName("cardTitle")
        self.conteggio = QLabel("0", self)
        self.conteggio.setObjectName("countBadge")
        intestazione = QFrame(self)
        intestazione.setObjectName("cardHeader")
        lay_intestazione = QHBoxLayout(intestazione)
        lay_intestazione.setContentsMargins(12, 6, 10, 6)
        lay_intestazione.addWidget(self.titolo)
        lay_intestazione.addWidget(self.conteggio)
        lay_intestazione.addSpacing(8)

        self.p_componi = QPushButton(f"Componi la bozza del {nome}", intestazione)
        tema.imposta_variante(self.p_componi, "primary")
        self.p_apri = QPushButton("Apri in Word", intestazione)
        self.p_anteprima = QPushButton("Anteprima", intestazione)
        self.p_capitoli = QPushButton("Capitoli...", intestazione)
        self.p_emetti = QPushButton("Emetti...", intestazione)
        self.p_altro = QPushButton("Altro", intestazione)
        menu = QMenu(self.p_altro)
        self.p_riprendi = menu.addAction("Riprendi le modifiche fatte in Word")
        self.p_consegna = menu.addAction("Segna come consegnato...")
        self.p_esporta = menu.addAction("Esporta in Word...")
        self.p_esporta_pdf = menu.addAction("Esporta in PDF...")
        self.p_confronta = menu.addAction("Confronta con la revisione precedente")
        menu.addSeparator()
        self.p_annulla = menu.addAction("Annulla")
        self.p_altro.setMenu(menu)
        from sicurcantiere.ui import sola_lettura

        sola_lettura.consenti(self.p_apri, self.p_anteprima, self.p_altro)
        self.p_componi.setToolTip("Compone il documento dai dati del cantiere e lo salva qui come bozza: se c'è già "
                                  "una bozza, la ricompone con i dati aggiornati.")
        self.p_apri.setToolTip("Apre il documento in Word. Le bozze si possono modificare e poi riprendere qui; "
                               "le revisioni emesse si aprono in sola lettura.")
        self.p_capitoli.setToolTip("Togli capitoli, aggiungi o sostituisci testo: le modifiche restano valide "
                                   "anche nelle composizioni successive.")
        self.p_emetti.setToolTip("Emette la versione definitiva: senza filigrana BOZZA, con i dati mancanti come righe "
                                 "da compilare a mano. Una revisione emessa non è più modificabile.")
        menu.setToolTipsVisible(True)
        self.p_riprendi.setToolTip("Salva nel cantiere la bozza modificata in Word (dopo averla salvata in Word).")
        self.p_confronta.setToolTip("Mostra le differenze, capitolo per capitolo, rispetto alla revisione "
                                    "precedente (o tra le due revisioni selezionate).")
        self.p_annulla.setToolTip("Bozza: la elimina. Revisione emessa: la segna come annullata e la conserva "
                                  "nello storico.")
        self.p_anteprima.setToolTip("Mostra il documento pagina per pagina, senza aprire Word; da qui si può "
                                    "salvare in PDF.")
        self.p_esporta_pdf.setToolTip("Salva il documento in PDF, per l'invio al committente o alle imprese.")
        for pulsante, slot in ((self.p_componi, self.componi), (self.p_anteprima, self.anteprima),
                               (self.p_apri, self.apri_in_word),
                               (self.p_capitoli, self.modifica_capitoli), (self.p_emetti, self.emetti)):
            pulsante.clicked.connect(lambda _=False, s=slot: s())
            lay_intestazione.addWidget(pulsante)
        lay_intestazione.addWidget(self.p_altro)
        lay_intestazione.addStretch()
        for azione, slot in ((self.p_riprendi, self.riprendi_da_word), (self.p_consegna, self.consegna),
                             (self.p_esporta, self.esporta), (self.p_esporta_pdf, self.esporta_pdf),
                             (self.p_confronta, self.confronta),
                             (self.p_annulla, self.annulla)):
            azione.triggered.connect(lambda _=False, s=slot: s())

        self.tabella = QTableWidget(0, len(self.COLONNE), self)
        self.tabella.setHorizontalHeaderLabels(self.COLONNE)
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setShowGrid(False)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.verticalHeader().setDefaultSectionSize(36)
        self.tabella.setItemDelegateForColumn(1, tema.DelegatoStato({
            comp.STATI[comp.BOZZA]: ("warn_bg", "warn"), comp.STATI[comp.EMESSA]: ("ok_bg", "ok"),
            comp.STATI[comp.CONSEGNATA]: ("acc_soft", "acc_tx"), comp.STATI[comp.ANNULLATA]: ("surface2", "tx3"),
        }, self.tabella))
        intestazione_tabella = self.tabella.horizontalHeader()
        intestazione_tabella.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        intestazione_tabella.setStretchLastSection(False)
        for colonna, larghezza in ((0, 46), (1, 110), (2, 122), (4, 165), (5, 160)):
            self.tabella.setColumnWidth(colonna, larghezza)
        intestazione_tabella.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabella.setWordWrap(False)
        self.tabella.itemSelectionChanged.connect(self._aggiorna_pulsanti)
        self.tabella.itemDoubleClicked.connect(lambda _: self.apri_in_word())

        self.avviso = QLabel(self)
        self.avviso.setObjectName("hint")
        self.avviso.setWordWrap(True)
        self.avviso.setContentsMargins(12, 6, 12, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(intestazione)
        layout.addWidget(self.tabella, 1)
        layout.addWidget(self.avviso)

        # lista dei dati da completare della composizione selezionata (la pagina la mette dove vuole)
        self.mancanti = QListWidget()
        self.mancanti.setSpacing(2)
        self.mancanti.itemDoubleClicked.connect(self._vai_al_dato)
        self.mancanti.itemActivated.connect(self._vai_al_dato)
        self.ricarica()

    # --- elenco ---

    def _elenco(self) -> list[dict[str, Any]]:
        documento = self.documento()
        return comp.elenco(self.repo, documento) if documento else []

    def ricarica(self) -> None:
        selezionata = self.selezionata()
        scelto = selezionata["id"] if selezionata else None
        self._righe = self._elenco()
        self.tabella.setRowCount(len(self._righe))
        self.conteggio.setText(str(len(self._righe)))
        c = tema.correnti()
        for r, voce in enumerate(self._righe):
            note = []
            if voce["stato"] == comp.CONSEGNATA:
                note.append(f"consegnata il {_data_ora(voce['consegnata_il'])}"
                            + (f" a {voce['consegnata_a']}" if voce["consegnata_a"] else ""))
            elif voce["stato"] == comp.EMESSA:
                note.append(f"emessa il {_data_ora(voce['emessa_il'])}")
            if voce["modificata_word"]:
                note.append("modificata in Word")
            if voce["conferma"]:
                note.append("emessa con dati mancanti")
            valori = (str(voce["numero"]), comp.STATI.get(voce["stato"], voce["stato"]), _data_ora(voce["composta_il"]),
                      voce["descrizione"], _riassunto_mancanti(voce) if voce["stato"] == comp.BOZZA else
                      ("—" if not voce["conferma"] else "righe da compilare a mano"), "; ".join(note))
            for col, testo in enumerate(valori):
                item = QTableWidgetItem(testo)
                item.setData(Qt.ItemDataRole.UserRole, voce["id"])
                if voce["stato"] == comp.ANNULLATA:
                    item.setForeground(QBrush(QColor(c["tx3"])))
                item.setToolTip(voce["conferma"] if col == 5 and voce["conferma"] else testo)
                self.tabella.setItem(r, col, item)
        riga = next((r for r, v in enumerate(self._righe) if v["id"] == scelto), 0 if self._righe else -1)
        if riga >= 0:
            self.tabella.selectRow(riga)
        self._aggiorna_avviso()
        self._aggiorna_pulsanti()

    def _aggiorna_avviso(self) -> None:
        documento = self.documento()
        if not documento:
            self.avviso.setText(f"Inserisci l'impresa per comporre il {self.nome}.")
        elif not self._righe:
            self.avviso.setText(f"Nessun documento composto. «Componi la bozza» crea il {self.nome} dai dati del "
                                "cantiere e lo conserva qui: da questo elenco puoi aprirlo, ricomporlo, emetterlo e "
                                "segnarlo come consegnato.")
        else:
            modificate = [v for v in self._righe if self._modificata_in_word(v)]
            self.avviso.setText("La bozza è stata modificata in Word: scegli «Altro» > «Riprendi le modifiche fatte "
                                "in Word» per salvarla nel cantiere." if modificate else
                                "Fai doppio clic su un documento per aprirlo in Word.")

    def selezionata(self) -> dict[str, Any] | None:
        righe = sorted({i.row() for i in self.tabella.selectedIndexes()}) if self.tabella.rowCount() else []
        if not righe or not getattr(self, "_righe", None) or righe[0] >= len(self._righe):
            return None
        return self._righe[righe[0]]

    def _selezionate(self) -> list[dict[str, Any]]:
        righe = sorted({i.row() for i in self.tabella.selectedIndexes()})
        return [self._righe[r] for r in righe if r < len(self._righe)]

    def _aggiorna_pulsanti(self) -> None:
        c = self.selezionata()
        stato = c["stato"] if c else None
        self.p_componi.setEnabled(bool(self.documento()))
        self.p_componi.setText("Ricomponi la bozza" if any(v["stato"] == comp.BOZZA for v in
                                                                             getattr(self, "_righe", []))
                               else f"Componi la bozza del {self.nome}")
        self.p_altro.setEnabled(c is not None)
        self.p_apri.setEnabled(c is not None)
        self.p_anteprima.setEnabled(c is not None)
        self.p_esporta_pdf.setEnabled(c is not None)
        self.p_riprendi.setEnabled(bool(c) and stato == comp.BOZZA and self._modificata_in_word(c))
        self.p_capitoli.setEnabled(bool(self.documento()) and bool(getattr(self, "_righe", [])))
        self.p_emetti.setEnabled(stato == comp.BOZZA)
        self.p_consegna.setEnabled(stato in (comp.EMESSA, comp.CONSEGNATA))
        self.p_esporta.setEnabled(c is not None)
        self.p_confronta.setEnabled(c is not None and len(getattr(self, "_righe", [])) > 1)
        self.p_annulla.setEnabled(c is not None and stato != comp.ANNULLATA)
        self.p_annulla.setText("Elimina la bozza" if stato == comp.BOZZA else "Annulla la revisione...")
        from sicurcantiere.ui import sola_lettura

        if sola_lettura.attiva():  # licenza non valida: si aprono, si vedono e si esportano i documenti già fatti
            for azione in (self.p_componi, self.p_capitoli, self.p_emetti, self.p_riprendi, self.p_consegna,
                           self.p_annulla):
                azione.setEnabled(False)
        self._mostra_mancanti(c)

    def _mostra_mancanti(self, c: dict[str, Any] | None) -> None:
        self.mancanti.clear()
        if c is None:
            self.mancanti.addItem("Componi la bozza per vedere i dati ancora da completare.")
            return
        if c["stato"] != comp.BOZZA:
            self.mancanti.addItem("Documento emesso: " + (c["conferma"] or "completo al momento dell'emissione."))
            return
        if not c["mancanti"]:
            self.mancanti.addItem("Nessun dato mancante: la bozza è completa.")
            return
        colori = tema.correnti()
        for livello in (composizione.OBBLIGATORIO, composizione.CONSIGLIATO, composizione.FACOLTATIVO):
            obbligatorio = livello == composizione.OBBLIGATORIO
            for m in (m for m in c["mancanti"] if m["livello"] == livello):
                dove = " · ".join(v for v in (m["capitolo"] and f"cap. {m['capitolo']}",
                                              m["sezione"] and f"si compila in «{m['sezione']}»") if v)
                # come i «Controlli di completezza»: livello · dove, poi il dato
                item = QListWidgetItem(icona("errore" if obbligatorio else "avviso",
                                             colori["err"] if obbligatorio else colori["warn"]),
                                       f"{composizione.LIVELLI[livello]}" + (f" · {dove}" if dove else "")
                                       + f"\n{m['dato'][:1].upper()}{m['dato'][1:]}")
                item.setForeground(QBrush(QColor(colori["err"] if obbligatorio else colori["tx"])))
                item.setData(Qt.ItemDataRole.UserRole, m["sezione"])
                item.setToolTip("Fai doppio clic per aprire la pagina in cui si compila il dato")
                self.mancanti.addItem(item)

    def _vai_al_dato(self, item: QListWidgetItem) -> None:
        vai = getattr(self.window(), "vai_a_sezione", None)
        if vai is not None and item.data(Qt.ItemDataRole.UserRole):
            vai(item.data(Qt.ItemDataRole.UserRole))

    # --- copie aperte in Word ---

    def _nome_file(self, c: dict[str, Any]) -> str:
        cantiere = self.repo.cantiere()["nome"] or self.repo.progetto.percorso.stem
        nome = f"{comp.nome_documento(self.repo, c['documento'])} - {cantiere} - Rev {c['numero']}"
        if c["stato"] == comp.BOZZA:
            nome += " (bozza)"
        return re.sub(r'[\\/:*?"<>|]+', "-", nome).strip()

    def _percorso_copia(self, c: dict[str, Any]) -> Path:
        impronta = hashlib.sha1(str(self.repo.progetto.percorso.resolve()).lower().encode(),
                                usedforsecurity=False).hexdigest()[:6]
        return cartella_lavoro() / f"{self._nome_file(c)} [{impronta}-{c['id']}].docx"

    def _modificata_in_word(self, c: dict[str, Any]) -> bool:
        copia = self._copie.get(c["id"])
        if not copia or not copia[0].is_file():
            return False
        return copia[0].stat().st_mtime > copia[1] + 0.5

    def apri_in_word(self) -> None:
        c = self.selezionata()
        if c is None:
            return
        percorso = self._percorso_copia(c)
        if self._modificata_in_word(c):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(percorso)))  # già aperta e modificata: non si tocca
            return
        try:
            percorso.parent.mkdir(parents=True, exist_ok=True)
            if percorso.exists():
                os.chmod(percorso, stat.S_IWRITE | stat.S_IREAD)
            percorso.write_bytes(comp.contenuto(self.repo, c["id"]))
            if c["stato"] != comp.BOZZA:
                os.chmod(percorso, stat.S_IREAD)  # revisione emessa: sola lettura
        except PermissionError:
            QMessageBox.information(self, "Apri in Word", "Il documento è già aperto in Word.")
            return
        except OSError as e:
            QMessageBox.warning(self, "Apri in Word", f"Impossibile preparare il file:\n{e}")
            return
        self._copie[c["id"]] = (percorso, percorso.stat().st_mtime)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(percorso)))
        self._aggiorna_avviso()

    def riprendi_da_word(self) -> None:
        c = self.selezionata()
        if c is None or c["id"] not in self._copie:
            return
        percorso, _ = self._copie[c["id"]]
        try:
            dati = percorso.read_bytes()
        except OSError as e:
            QMessageBox.warning(self, "Riprendi da Word", f"Impossibile leggere il file:\n{e}\n\n"
                                                          "Salva e chiudi il documento in Word, poi riprova.")
            return
        comp.acquisisci_da_word(self.repo, c["id"], dati)
        self._copie[c["id"]] = (percorso, percorso.stat().st_mtime)
        self.ricarica()
        QMessageBox.information(self, "Riprendi da Word", "Le modifiche fatte in Word sono salvate nel cantiere.")

    # --- azioni ---

    def componi(self) -> bool:
        documento = self.documento()
        if not documento:
            QMessageBox.information(self, "Componi", "Seleziona prima il ponteggio." if self.nome == "PiMUS" else
                                    f"Inserisci prima l'impresa per comporre il {self.nome}.")
            return False
        attuale = comp.bozza(self.repo, documento)
        if attuale and (attuale["modificata_word"] or self._modificata_in_word(attuale)):
            if QMessageBox.question(
                    self, "Ricomponi la bozza",
                    "La bozza è stata modificata in Word: ricomponendola dai dati del cantiere quelle modifiche si "
                    "perdono.\n\nPer conservare un testo anche nelle prossime composizioni usa «Capitoli...»."
                    "\n\nVuoi ricomporla comunque?") != QMessageBox.StandardButton.Yes:
                return False
        if attuale is None:
            dialogo = DialogoComponi(comp.numero_proposto(self.repo, documento), self.nome, self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return False
            numero, descrizione = dialogo.valori()
        else:
            numero, descrizione = attuale["numero"], attuale["descrizione"]
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            nuova = comp.componi(self.repo, documento, descrizione, numero)
        except PermissionError:
            QMessageBox.warning(self, "Componi", "Impossibile salvare il documento: verifica che non sia aperto in "
                                                "Word.")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self._copie.pop(nuova["id"], None)
        self.ricarica()
        obbligatori = len(comp.obbligatori_mancanti(nuova))
        messaggio = (f"Bozza della Rev. {nuova['numero']} composta e salvata nel cantiere.\n\n"
                     + (f"Mancano {obbligatori} dati obbligatori e {len(nuova['mancanti']) - obbligatori} altri: "
                        "sono evidenziati in giallo nel documento ed elencati in «Dati da completare»."
                        if obbligatori else
                        f"Dati non obbligatori da completare: {len(nuova['mancanti'])}." if nuova["mancanti"]
                        else "Nessun dato mancante.")
                     + "\n\nVuoi aprirla in Word?")
        if QMessageBox.question(self, "Bozza composta", messaggio) == QMessageBox.StandardButton.Yes:
            self.apri_in_word()
        return True

    def modifica_capitoli(self) -> None:
        documento = self.documento()
        righe = getattr(self, "_righe", [])
        if not documento or not righe:
            return
        dialogo = DialogoCapitoli(self.repo, documento, righe[0]["capitoli"], self)
        if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.cambiato:
            if comp.bozza(self.repo, documento) and QMessageBox.question(
                    self, "Capitoli", "Modifiche salvate. Vuoi ricomporre ora la bozza per applicarle?") \
                    == QMessageBox.StandardButton.Yes:
                self.componi()

    def emetti(self) -> None:
        c = self.selezionata()
        if c is None or c["stato"] != comp.BOZZA:
            return
        if self._modificata_in_word(c):
            risposta = QMessageBox.question(
                self, "Emetti", "La bozza aperta in Word contiene modifiche non ancora riprese. Vuoi riprenderle "
                                "prima dell'emissione?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if risposta == QMessageBox.StandardButton.Cancel:
                return
            if risposta == QMessageBox.StandardButton.Yes:
                self.riprendi_da_word()
                c = comp.leggi(self.repo, c["id"])
        dialogo = DialogoEmetti(c, self.nome, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            comp.emetti(self.repo, c["id"], dialogo.conferma())
        except comp.ErroreComposizione as e:
            QMessageBox.warning(self, "Emetti", str(e))
            return
        self._copie.pop(c["id"], None)
        self.ricarica()
        QMessageBox.information(self, "Emetti", f"Rev. {c['numero']} emessa: il documento definitivo è salvato nel "
                                                "cantiere. Puoi aprirlo, esportarlo e segnarlo come consegnato.")

    def consegna(self) -> None:
        c = self.selezionata()
        if c is None:
            return
        dialogo = DialogoConsegna(c, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        destinatario, il = dialogo.valori()
        comp.segna_consegnata(self.repo, c["id"], destinatario, il)
        self.ricarica()

    def esporta(self) -> None:
        c = self.selezionata()
        if c is None:
            return
        predefinito = self.repo.progetto.percorso.with_name(f"{self._nome_file(c)}.docx")
        percorso, _ = QFileDialog.getSaveFileName(self, "Esporta in Word", str(predefinito), "Documento Word (*.docx)")
        if not percorso:
            return
        try:
            Path(percorso).write_bytes(comp.contenuto(self.repo, c["id"]))
        except PermissionError:
            QMessageBox.warning(self, "Esporta", "Impossibile salvare il file: verifica che non sia aperto in Word.")
            return
        if QMessageBox.question(self, "Esporta", f"Documento salvato: {Path(percorso).name}. Vuoi aprirlo ora?") \
                == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(percorso))

    def anteprima(self) -> None:
        from sicurcantiere.ui import anteprima

        c = self.selezionata()
        if c is not None:
            nome = self._nome_file(c)
            anteprima.mostra(self, comp.contenuto(self.repo, c["id"]), nome, nome, self.apri_in_word)

    def esporta_pdf(self) -> None:
        from sicurcantiere.documenti import pdf
        from sicurcantiere.ui.importa_psc import in_background

        c = self.selezionata()
        if c is None:
            return
        if not pdf.disponibile():
            QMessageBox.information(self, "Esporta in PDF", "Per creare il PDF serve Microsoft Word oppure "
                                                            "LibreOffice installato su questo computer.")
            return
        predefinito = self.repo.progetto.percorso.with_name(f"{self._nome_file(c)}.pdf")
        percorso, _ = QFileDialog.getSaveFileName(self, "Esporta in PDF", str(predefinito), "PDF (*.pdf)")
        if not percorso:
            return
        contenuto = comp.contenuto(self.repo, c["id"])

        def converti(_avanzamento):
            dati = pdf.converti_dati(contenuto)
            Path(percorso).write_bytes(dati)
            return percorso

        def fatto(salvato: str) -> None:
            if QMessageBox.question(self, "Esporta in PDF", f"PDF salvato: {Path(salvato).name}. Vuoi aprirlo "
                                    "ora?") == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(salvato))

        in_background(self, "Esporta in PDF", "Creazione del PDF in corso...", converti, fatto)

    def confronta(self) -> None:
        scelte = self._selezionate()
        if len(scelte) >= 2:
            nuova, vecchia = scelte[0], scelte[-1]
        else:
            nuova = self.selezionata()
            if nuova is None:
                return
            precedenti = [v for v in self._righe if (v["numero"], v["id"]) < (nuova["numero"], nuova["id"])
                          and v["stato"] != comp.ANNULLATA]
            if not precedenti:
                QMessageBox.information(self, "Confronta", "Non esiste una revisione precedente da confrontare.")
                return
            vecchia = precedenti[0]
        DialogoConfronto(vecchia, nuova, self).exec()

    def annulla(self) -> None:
        c = self.selezionata()
        if c is None:
            return
        if c["stato"] == comp.BOZZA:
            domanda = (f"Vuoi eliminare la bozza della Rev. {c['numero']}? Viene eliminata anche la relativa riga "
                       "della tabella delle revisioni.")
        else:
            domanda = (f"Vuoi annullare la Rev. {c['numero']}? Resta nello storico come annullata e non è più "
                       "valida; l'operazione non è reversibile.")
        if QMessageBox.question(self, "Annulla", domanda) != QMessageBox.StandardButton.Yes:
            return
        comp.annulla(self.repo, c["id"])
        self._copie.pop(c["id"], None)
        self.ricarica()


class DialogoComponi(QDialog):
    def __init__(self, numero: int, nome: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Componi la bozza del {nome}")
        layout = QFormLayout(self)
        self.numero = QSpinBox(self)
        self.numero.setRange(0, 99)
        self.numero.setValue(numero)
        self.descrizione = QLineEdit("Prima emissione" if numero == 0 else "", self)
        self.descrizione.setPlaceholderText("Motivo della revisione, per esempio «Ingresso nuova lavorazione»")
        layout.addRow("Revisione n.", self.numero)
        layout.addRow("Descrizione delle modifiche", self.descrizione)
        nota = QLabel("La revisione viene riportata nella tabella delle revisioni del documento. La bozza si può "
                      "ricomporre tutte le volte necessarie, fino all'emissione.", self)
        nota.setObjectName("hint")
        nota.setWordWrap(True)
        layout.addRow(nota)
        bottoni = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bottoni.button(QDialogButtonBox.StandardButton.Ok).setText("Componi")
        bottoni.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        bottoni.accepted.connect(self.accept)
        bottoni.rejected.connect(self.reject)
        layout.addRow(bottoni)
        self.resize(520, 0)

    def valori(self) -> tuple[int, str]:
        return self.numero.value(), self.descrizione.text().strip()


class DialogoEmetti(QDialog):
    """Conferma dell'emissione; con dati obbligatori mancanti serve una conferma esplicita con il motivo."""

    def __init__(self, c: dict[str, Any], nome: str, parent=None):
        super().__init__(parent)
        self.c = c
        self.obbligatori = comp.obbligatori_mancanti(c)
        self.setWindowTitle(f"Emetti la Rev. {c['numero']} del {nome}")
        layout = QVBoxLayout(self)
        testo = QLabel(
            "Il documento emesso è la versione definitiva: senza filigrana BOZZA, senza il riepilogo dei dati "
            "mancanti e senza i commenti di SicurCantiere; i dati rimasti vuoti diventano righe da compilare a "
            "mano. Dopo l'emissione non è più modificabile: per cambiarlo si compone la revisione successiva.", self)
        testo.setWordWrap(True)
        layout.addWidget(testo)
        self.spunta = None
        self.motivo = None
        if self.obbligatori:
            avviso = QLabel(f"<b>Mancano {len(self.obbligatori)} dati obbligatori per legge:</b>", self)
            layout.addWidget(avviso)
            elenco = QListWidget(self)
            for m in self.obbligatori:
                elenco.addItem(f"{m['dato'][:1].upper()}{m['dato'][1:]}"
                               + (f"  —  cap. {m['capitolo']}" if m["capitolo"] else ""))
            elenco.setMaximumHeight(160)
            layout.addWidget(elenco)
            self.spunta = QCheckBox("Emetto comunque il documento: i dati mancanti verranno compilati a mano "
                                    "prima della firma", self)
            self.motivo = QLineEdit(self)
            self.motivo.setPlaceholderText("Motivo (obbligatorio), per esempio «dati comunicati dall'impresa "
                                           "dopo la consegna»")
            layout.addWidget(self.spunta)
            layout.addWidget(self.motivo)
            nota = QLabel("La conferma resta registrata con la revisione.", self)
            nota.setObjectName("hint")
            layout.addWidget(nota)
            self.spunta.toggled.connect(self._verifica)
            self.motivo.textChanged.connect(self._verifica)
        firmatario = ("dal coordinatore per la sicurezza" if nome.upper().startswith("PSC") else
                      "dal datore di lavoro dell'impresa esecutrice")
        avvertenza = QLabel(f"Il documento va riletto, completato dove necessario e firmato {firmatario}: il "
                            "programma è uno strumento di redazione e non sostituisce la valutazione dei rischi.",
                            self)
        avvertenza.setWordWrap(True)
        avvertenza.setObjectName("hint")
        tema.imposta_stato(avvertenza, "warning")
        layout.addWidget(avvertenza)
        self.bottoni = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                        self)
        self.bottoni.button(QDialogButtonBox.StandardButton.Ok).setText("Emetti")
        self.bottoni.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        self.bottoni.accepted.connect(self.accept)
        self.bottoni.rejected.connect(self.reject)
        layout.addWidget(self.bottoni)
        self._verifica()
        self.resize(600, 0)

    def _verifica(self) -> None:
        pronto = not self.obbligatori or (self.spunta.isChecked() and bool(self.motivo.text().strip()))
        self.bottoni.button(QDialogButtonBox.StandardButton.Ok).setEnabled(pronto)

    def conferma(self) -> str:
        if not self.obbligatori:
            return ""
        dati = "; ".join(m["dato"] for m in self.obbligatori)
        return (f"Emessa il {datetime.now():%d/%m/%Y alle %H:%M} con {len(self.obbligatori)} dati obbligatori "
                f"mancanti ({dati}). Motivo: {self.motivo.text().strip()}")


class DialogoConsegna(QDialog):
    def __init__(self, c: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Consegna della Rev. {c['numero']}")
        layout = QFormLayout(self)
        self.destinatario = QLineEdit(c["consegnata_a"], self)
        self.destinatario.setPlaceholderText("Per esempio: CSE ing. Rossi, via PEC")
        self.data = QDateEdit(self)
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.fromString(c["consegnata_il"], "yyyy-MM-dd") if c["consegnata_il"]
                          else QDate.currentDate())
        layout.addRow("Consegnata a", self.destinatario)
        layout.addRow("Data di consegna", self.data)
        bottoni = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bottoni.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        bottoni.accepted.connect(self.accept)
        bottoni.rejected.connect(self.reject)
        layout.addRow(bottoni)
        self.resize(460, 0)

    def valori(self) -> tuple[str, str]:
        return self.destinatario.text().strip(), self.data.date().toString("yyyy-MM-dd")


class DialogoCapitoli(QDialog):
    """Capitoli del documento: includere o togliere, aggiungere testo in fondo o sostituire il contenuto.
    Le modifiche restano anche quando il documento si ricompone."""

    def __init__(self, repo: Repository, documento: str, capitoli: list[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.repo = repo
        self.documento = documento
        self.capitoli = capitoli
        self.cambiato = False
        salvate = comp.personalizzazioni(repo, documento)
        self.stato: dict[str, dict[str, Any]] = {}
        for cap in capitoli:
            p = salvate.get(cap["chiave"], {})
            self.stato[cap["chiave"]] = {"escluso": bool(p.get("escluso")), "modo": p.get("modo") or
                                         composizione.AGGIUNGI, "testo": p.get("testo", ""),
                                         "impronta": p.get("impronta", ""), "visto": False}
        self.setWindowTitle("Modifica i capitoli")
        layout = QVBoxLayout(self)
        guida = QLabel("Togli la spunta ai capitoli da non stampare. Per ogni capitolo puoi aggiungere un testo in "
                       "fondo o sostituire il contenuto composto dal programma (il titolo e il riferimento di legge "
                       "restano). Le modifiche valgono per le prossime composizioni.", self)
        guida.setWordWrap(True)
        guida.setObjectName("hint")
        layout.addWidget(guida)
        divisore = QSplitter(self)
        self.elenco = QListWidget(divisore)
        for cap in capitoli:
            item = QListWidgetItem(cap["titolo"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if self.stato[cap["chiave"]]["escluso"]
                               else Qt.CheckState.Checked)
            self._segna(item, cap)
            self.elenco.addItem(item)
        destra = QWidget(divisore)
        dl = QVBoxLayout(destra)
        dl.setContentsMargins(8, 0, 0, 0)
        self.titolo = QLabel(destra)
        self.titolo.setObjectName("sectionTitle")
        self.titolo.setWordWrap(True)
        self.avviso = QLabel(destra)
        self.avviso.setWordWrap(True)
        self.avviso.setStyleSheet(f"color: {tema.correnti()['warn']};")
        self.generato = QTextBrowser(destra)
        dl.addWidget(self.titolo)
        dl.addWidget(self.avviso)
        dl.addWidget(QLabel("Testo composto dal programma (ultima composizione):", destra))
        dl.addWidget(self.generato, 2)
        modi = QHBoxLayout()
        self.aggiungi = QRadioButton("Aggiungi il mio testo in fondo al capitolo", destra)
        self.sostituisci = QRadioButton("Sostituisci il contenuto con il mio testo", destra)
        modi.addWidget(self.aggiungi)
        modi.addWidget(self.sostituisci)
        modi.addStretch()
        dl.addLayout(modi)
        self.testo = QPlainTextEdit(destra)
        self.testo.setPlaceholderText("Il tuo testo. Una riga per paragrafo; le righe che iniziano con «- » "
                                      "diventano un elenco puntato.")
        dl.addWidget(self.testo, 2)
        divisore.addWidget(self.elenco)
        divisore.addWidget(destra)
        divisore.setSizes([280, 620])
        layout.addWidget(divisore, 1)
        bottoni = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
                                   self)
        bottoni.button(QDialogButtonBox.StandardButton.Save).setText("Salva")
        bottoni.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        bottoni.accepted.connect(self._salva)
        bottoni.rejected.connect(self.reject)
        layout.addWidget(bottoni)
        self._corrente: str | None = None
        self.elenco.currentRowChanged.connect(self._mostra)
        self.elenco.itemChanged.connect(self._spunta)
        if capitoli:
            self.elenco.setCurrentRow(0)
        self.resize(980, 640)

    def _segna(self, item: QListWidgetItem, cap: dict[str, Any]) -> None:
        s = self.stato[cap["chiave"]]
        segni = []
        if s["testo"].strip():
            segni.append("testo sostituito" if s["modo"] == composizione.SOSTITUISCI else "testo aggiunto")
        if cap.get("cambiato") and not s["visto"] and s["testo"].strip():
            segni.append("da ricontrollare")
        item.setToolTip("; ".join(segni))
        f = item.font()
        f.setItalic(bool(s["testo"].strip()))
        item.setFont(f)

    def _memorizza(self) -> None:
        if self._corrente is None:
            return
        s = self.stato[self._corrente]
        s["testo"] = self.testo.toPlainText()
        s["modo"] = composizione.SOSTITUISCI if self.sostituisci.isChecked() else composizione.AGGIUNGI

    def _mostra(self, riga: int) -> None:
        self._memorizza()
        if riga < 0:
            return
        cap = self.capitoli[riga]
        self._corrente = cap["chiave"]
        s = self.stato[cap["chiave"]]
        s["visto"] = True
        self.titolo.setText(cap["titolo"])
        self.avviso.setText("Il contenuto composto dal programma è cambiato dopo la tua modifica: ricontrolla che il "
                            "tuo testo sia ancora valido." if cap.get("cambiato") and s["testo"].strip() else "")
        self.avviso.setVisible(bool(self.avviso.text()))
        self.generato.setPlainText(cap.get("generato", cap["testo"]) or "(capitolo senza testo)")
        (self.sostituisci if s["modo"] == composizione.SOSTITUISCI else self.aggiungi).setChecked(True)
        self.testo.setPlainText(s["testo"])

    def _spunta(self, item: QListWidgetItem) -> None:
        riga = self.elenco.row(item)
        if 0 <= riga < len(self.capitoli):
            self.stato[self.capitoli[riga]["chiave"]]["escluso"] = item.checkState() == Qt.CheckState.Unchecked

    def _salva(self) -> None:
        self._memorizza()
        salvate = comp.personalizzazioni(self.repo, self.documento)
        for cap in self.capitoli:
            s = self.stato[cap["chiave"]]
            prima = salvate.get(cap["chiave"])
            impronta = cap["impronta"] if s["visto"] or not prima else prima["impronta"]
            nuovo = (bool(s["escluso"]), s["modo"] if s["testo"].strip() else composizione.AGGIUNGI,
                     s["testo"].strip(), impronta)
            vecchio = ((bool(prima["escluso"]), prima["modo"], prima["testo"].strip(), prima["impronta"]) if prima
                       else (False, composizione.AGGIUNGI, "", impronta))
            if nuovo == vecchio:
                continue
            comp.salva_personalizzazione(self.repo, self.documento, cap["chiave"], titolo=cap["titolo"],
                                         modo=nuovo[1], testo=nuovo[2], impronta=impronta, escluso=nuovo[0])
            self.cambiato = True
        self.accept()


class DialogoConfronto(QDialog):
    def __init__(self, vecchia: dict[str, Any], nuova: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Confronto tra la Rev. {vecchia['numero']} e la Rev. {nuova['numero']}")
        layout = QVBoxLayout(self)
        vista = QTextBrowser(self)
        vista.setHtml(html_confronto(vecchia, nuova))
        layout.addWidget(vista)
        bottoni = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        bottoni.button(QDialogButtonBox.StandardButton.Close).setText("Chiudi")
        bottoni.rejected.connect(self.reject)
        layout.addWidget(bottoni)
        self.resize(900, 640)


def html_confronto(vecchia: dict[str, Any], nuova: dict[str, Any]) -> str:
    c = tema.correnti()
    cambiamenti = comp.confronta(vecchia, nuova)
    parti = [f"<p>Rev. {vecchia['numero']} ({_data_ora(vecchia['composta_il'])}) → Rev. {nuova['numero']} "
             f"({_data_ora(nuova['composta_il'])})</p>"]
    if not cambiamenti:
        parti.append("<p><b>Nessuna differenza nel testo dei capitoli.</b></p>")
    etichette = {"aggiunto": "capitolo aggiunto", "tolto": "capitolo tolto", "cambiato": "capitolo modificato"}
    for voce in cambiamenti:
        parti.append(f"<h3>{html.escape(voce['titolo'])} <span style='font-weight:normal;color:{c['tx2']}'>— "
                     f"{etichette[voce['stato']]}</span></h3>")
        for segno, riga in voce["righe"][:400]:
            colore = c["ok"] if segno == "+" else c["err"]
            decorazione = "" if segno == "+" else "text-decoration:line-through;"
            parti.append(f"<div style='color:{colore};{decorazione}'>{segno} {html.escape(riga)}</div>")
    return "".join(parti)
