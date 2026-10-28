"""Finestra dell'archivio delle anagrafiche dell'utente (persone e imprese ricorrenti)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sicurcantiere.archivio_utente import IMPRESA, PERSONA, SISTEMA, ArchivioAnagrafiche
from sicurcantiere.repository import Repository

RUOLO_ID = Qt.ItemDataRole.UserRole


def _descrizione(voce: dict[str, Any]) -> str:
    d = voce["dati"]
    if voce["tipo"] == SISTEMA:
        g = d.get("geometria") or {}
        parti = [f"autorizzazione {d['autorizzazione']}" if d.get("autorizzazione") else "",
                 f"campata {g['campata']:g} m".replace(".", ",") if g.get("campata") else "",
                 f"larghezza {g['larghezza']:g} m".replace(".", ",") if g.get("larghezza") else "",
                 f"{len(d.get('allegati', []))} documenti" if d.get("allegati") else ""]
    elif voce["tipo"] == IMPRESA:
        parti = [d.get("tipo", ""), d.get("partita_iva", ""), d.get("comune", "")]
        figure, lavoratori = len(d.get("figure", [])), len(d.get("lavoratori", []))
        parti.append(f"{figure} figure, {lavoratori} lavoratori")
    else:
        parti = [d.get("qualifica", ""), d.get("telefono", ""), d.get("email", "")]
    return " - ".join(p for p in parti if p)


class DialogoAnagrafiche(QDialog):
    """Elenco delle voci in archivio raggruppate per ruolo; con scelta=False serve solo a gestirle."""

    def __init__(self, archivio: ArchivioAnagrafiche, tipo: str | None = None, scelta: bool = True,
                 genitore: QWidget | None = None):
        super().__init__(genitore)
        self.archivio = archivio
        self.tipo = tipo
        self.setWindowTitle("Archivio anagrafiche")
        self.resize(720, 520)
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca per nome o ruolo...")
        self.cerca.textChanged.connect(self._carica)
        self.albero = QTreeWidget()
        self.albero.setHeaderLabels(["Nominativo", "Dettagli", "Aggiornato"])
        self.albero.setColumnWidth(0, 260)
        self.albero.setColumnWidth(1, 300)
        self.albero.itemDoubleClicked.connect(lambda item, _c: scelta and item.data(0, RUOLO_ID) and self.accept())
        elimina = QPushButton("Elimina dall'archivio")
        elimina.clicked.connect(self._elimina)
        aiuto = QLabel("Le voci si aggiungono dai cantieri con il pulsante «Salva in archivio». "
                       f"File dell'archivio: {archivio.percorso}")
        aiuto.setWordWrap(True)
        aiuto.setObjectName("pageSubtitle")
        tasti = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel if scelta \
            else QDialogButtonBox.StandardButton.Close
        pulsanti = QDialogButtonBox(tasti)
        pulsanti.accepted.connect(self.accept)
        pulsanti.rejected.connect(self.reject)
        if scelta:
            pulsanti.button(QDialogButtonBox.StandardButton.Ok).setText("Inserisci nel cantiere")
        riga = QHBoxLayout()
        riga.addWidget(elimina)
        riga.addStretch()
        riga.addWidget(pulsanti)
        layout = QVBoxLayout(self)
        layout.addWidget(self.cerca)
        layout.addWidget(self.albero)
        layout.addWidget(aiuto)
        layout.addLayout(riga)
        self._carica()

    def _carica(self) -> None:
        self.albero.clear()
        gruppi: dict[str, QTreeWidgetItem] = {}
        for voce in self.archivio.elenco(self.tipo, self.cerca.text()):
            gruppo_nome = ("Imprese e lavoratori autonomi" if voce["tipo"] == IMPRESA else
                           f"Sistemi di ponteggio · {voce['ruolo'] or 'tipologia non indicata'}"
                           if voce["tipo"] == SISTEMA else (voce["ruolo"] or "Senza ruolo"))
            if gruppo_nome not in gruppi:
                gruppi[gruppo_nome] = QTreeWidgetItem(self.albero, [gruppo_nome])
                font = gruppi[gruppo_nome].font(0)
                font.setBold(True)
                gruppi[gruppo_nome].setFont(0, font)
            item = QTreeWidgetItem(gruppi[gruppo_nome], [voce["nome"], _descrizione(voce),
                                                          voce["modificato"].replace("T", " ")[:16]])
            item.setData(0, RUOLO_ID, voce["id"])
        self.albero.expandAll()

    def scelta(self) -> dict[str, Any] | None:
        item = self.albero.currentItem()
        id_ = item.data(0, RUOLO_ID) if item else None
        return self.archivio.leggi(id_) if id_ else None

    def _elimina(self) -> None:
        voce = self.scelta()
        if voce is None:
            return
        if QMessageBox.question(self, "Archivio", f"Vuoi eliminare «{voce['nome']}» dall'archivio?") \
                == QMessageBox.StandardButton.Yes:
            self.archivio.elimina(voce["id"])
            self._carica()


def prendi_persona(genitore: QWidget, repo: Repository, tabella: str, **extra: Any) -> int | None:
    """Sceglie una persona dall'archivio e la inserisce in «soggetti» o «figure»."""
    archivio = ArchivioAnagrafiche()
    try:
        dialogo = DialogoAnagrafiche(archivio, PERSONA, genitore=genitore)
        if dialogo.exec() and (voce := dialogo.scelta()):
            return archivio.inserisci_persona(repo, voce, tabella, **extra)
        return None
    finally:
        archivio.chiudi()


def salva_persona(genitore: QWidget, repo: Repository, tabella: str, id_: int | None) -> None:
    record = repo.leggi(tabella, id_) if id_ is not None else None
    if record is None:
        QMessageBox.information(genitore, "Archivio", "Seleziona prima la riga da salvare.")
        return
    archivio = ArchivioAnagrafiche()
    try:
        archivio.salva_persona(record)
    except ValueError as e:
        QMessageBox.warning(genitore, "Archivio", str(e))
        return
    finally:
        archivio.chiudi()
    QMessageBox.information(genitore, "Archivio", f"«{record['nome']}» salvato nell'archivio anagrafiche.")


def prendi_impresa(genitore: QWidget, repo: Repository) -> int | None:
    archivio = ArchivioAnagrafiche()
    try:
        dialogo = DialogoAnagrafiche(archivio, IMPRESA, genitore=genitore)
        if dialogo.exec() and (voce := dialogo.scelta()):
            return archivio.inserisci_impresa(repo, voce)
        return None
    finally:
        archivio.chiudi()


def salva_impresa(genitore: QWidget, repo: Repository, id_: int | None) -> None:
    if id_ is None:
        QMessageBox.information(genitore, "Archivio", "Seleziona prima l'impresa da salvare.")
        return
    archivio = ArchivioAnagrafiche()
    try:
        archivio.salva_impresa(repo, id_)
    except ValueError as e:
        QMessageBox.warning(genitore, "Archivio", str(e))
        return
    finally:
        archivio.chiudi()
    QMessageBox.information(genitore, "Archivio", "Impresa salvata nell'archivio con figure e maestranze.")


def prendi_sistema(genitore: QWidget, repo: Repository, ponteggio_id: int) -> bool:
    """Sceglie un sistema di ponteggio dall'archivio e lo applica al ponteggio."""
    archivio = ArchivioAnagrafiche()
    try:
        dialogo = DialogoAnagrafiche(archivio, SISTEMA, genitore=genitore)
        dialogo.setWindowTitle("Sistemi di ponteggio in archivio")
        if dialogo.exec() and (voce := dialogo.scelta()):
            archivio.applica_sistema(repo, ponteggio_id, voce)
            return True
        return False
    finally:
        archivio.chiudi()


def salva_sistema(genitore: QWidget, repo: Repository, ponteggio_id: int | None) -> None:
    if ponteggio_id is None:
        QMessageBox.information(genitore, "Archivio", "Seleziona prima il ponteggio.")
        return
    archivio = ArchivioAnagrafiche()
    try:
        archivio.salva_sistema(repo, ponteggio_id)
    except ValueError as e:
        QMessageBox.warning(genitore, "Archivio", str(e))
        return
    finally:
        archivio.chiudi()
    QMessageBox.information(genitore, "Archivio", "Sistema di ponteggio salvato nell'archivio: fabbricante, "
                                                  "autorizzazione, campate, pesi e libretto si ritrovano negli "
                                                  "altri cantieri.")


def gestisci(genitore: QWidget) -> None:
    archivio = ArchivioAnagrafiche()
    try:
        DialogoAnagrafiche(archivio, scelta=False, genitore=genitore).exec()
    finally:
        archivio.chiudi()
