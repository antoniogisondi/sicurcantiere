"""I programmi della famiglia SicurCantiere.

Condividono archivi, motore dei documenti e interfaccia; ognuno ha le sue
pagine, la sua estensione di file e i suoi controlli:

- SicurCantiere PSC: coordinatore (PSC, fascicolo dell'opera, notifica preliminare);
- SicurCantiere POS: impresa esecutrice (POS, valutazioni dei rischi specifici, DPI);
- SicurCantiere PiMUS: ponteggi.

I file hanno la stessa struttura interna, quindi ogni programma può aprire
anche i file degli altri (per esempio il POS può partire dal file del PSC).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from sicurcantiere import controlli, pimus
from sicurcantiere.prepara_pos import prepara_pos
from sicurcantiere.repository import Repository
from sicurcantiere.ui import tema
from sicurcantiere.ui.pagine import (
    Pagina,
    PaginaCosti,
    PaginaDatiGenerali,
    PaginaDocumenti,
    PaginaFascicolo,
    PaginaFasi,
    PaginaImprese,
    PaginaInterferenze,
    PaginaRelazione,
    PaginaSoggetti,
)
from sicurcantiere.ui.ponteggi import PaginaPonteggi
from sicurcantiere.ui.riepilogo import calcola_pos
from sicurcantiere.ui.sostanze import PaginaSostanze
from sicurcantiere.ui.valutazioni import PaginaValutazioni


@dataclass(frozen=True)
class Edizione:
    chiave: str
    nome: str
    sottotitolo: str
    estensione: str
    descrizione_file: str
    colore: str
    pagine: tuple[type[Pagina], ...]
    azione_principale: str  # testo del pulsante nella barra degli strumenti
    controlla: Callable[[Repository], list[controlli.Segnalazione]]


# --- PSC: solo quanto serve al coordinatore ---

class PaginaImpresePSC(PaginaImprese):
    titolo = "Imprese e lavoratori autonomi"
    voce = "Imprese"
    schede_visibili = ("idoneita",)

    def __init__(self, repo: Repository):
        super().__init__(repo)
        # il collegamento con SicurCantiere POS è l'azione principale della pagina
        prepara = self.tabella.aggiungi_pulsante("Prepara il POS dell'impresa...", self.prepara_pos)
        tema.imposta_variante(prepara, "primary")
        prepara.setToolTip("Crea il file del POS dell'impresa selezionata con i dati del PSC (fasi, rischi, "
                           "interferenze e prescrizioni), da completare in SicurCantiere POS.")

    def prepara_pos(self, destinazione: str | None = None) -> Path | None:
        """File .spo con i dati dell'impresa selezionata, da completare in SicurCantiere POS."""
        id_ = self.tabella.id_selezionato()
        impresa = self.repo.leggi("imprese", id_) if id_ is not None else None
        if impresa is None:
            QMessageBox.information(self, "Prepara il POS", "Seleziona l'impresa di cui preparare il POS.")
            return None
        if not destinazione:
            nome = " - ".join(v for v in (self.repo.cantiere()["nome"], impresa["ragione_sociale"]) if v) or "POS"
            nome = "".join(c for c in nome if c not in '<>:"/\\|?*').strip()
            proposta = str(self.repo.progetto.percorso.with_name(f"POS {nome}.spo"))
            destinazione, _ = QFileDialog.getSaveFileName(self, "Prepara il POS dell'impresa", proposta,
                                                          "Cantiere POS (*.spo)")
            if not destinazione:
                return None
        percorso = Path(destinazione).with_suffix(".spo")
        try:
            prepara_pos(self.repo, impresa["id"], percorso)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Prepara il POS", f"Il file non è stato creato:\n{e}")
            return None
        if not QApplication.platformName() == "offscreen" and QMessageBox.question(
                self, "Prepara il POS",
                f"Creato il file del POS di {impresa['ragione_sociale'] or 'questa impresa'}:\n{percorso}\n\n"
                "Contiene i dati del cantiere e dell'impresa, le lavorazioni assegnate con rischi e attrezzature e le "
                "prescrizioni sulle interferenze. Vuoi aprirlo ora in SicurCantiere POS per completarlo?",
        ) == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(percorso)))
        return percorso


class PaginaDocumentiPSC(PaginaDocumenti):
    # il PSC comprende tutte le imprese e i lavoratori autonomi: nessun documento si sceglie per impresa
    # (il verbale di idoneità si genera dalla scheda «Idoneità e patente» di ciascuna)
    documenti = ("psc", "fascicolo", "notifica")
    principale = "psc"


# --- POS: dal punto di vista dell'impresa esecutrice ---

class PaginaCantierePOS(PaginaDatiGenerali):
    titolo = "Cantiere"
    voce = "Cantiere"
    sottotitolo = "Dati generali dell'opera. I numeri qui sotto si aggiornano mentre compili le altre pagine."
    funzione_riepilogo = staticmethod(calcola_pos)

    def __init__(self, repo: Repository):
        super().__init__(repo)
        self.foto = FotoCantiere(repo)
        self.corpo.addWidget(self.foto, 1)

    def aggiorna(self) -> None:
        super().aggiorna()
        self.foto.aggiorna()


class FotoCantiere(QFrame):
    """Foto del cantiere riportate nel POS (capitolo «Lavoro»), in un riquadro a destra dei dati."""

    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self.elenco = QListWidget()
        self.elenco.setViewMode(QListWidget.ViewMode.IconMode)
        self.elenco.setIconSize(QSize(120, 90))
        self.elenco.setGridSize(QSize(136, 120))
        self.elenco.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.elenco.setMovement(QListWidget.Movement.Static)
        self.elenco.setWordWrap(True)
        self.elenco.setToolTip("Le foto restano nella loro cartella: il cantiere ne memorizza solo il percorso.")
        aggiungi = QPushButton("Aggiungi foto...")
        aggiungi.clicked.connect(self._aggiungi)
        rimuovi = QPushButton("Rimuovi")
        tema.imposta_variante(rimuovi, "quiet")
        rimuovi.clicked.connect(self._rimuovi)
        pulsanti = QHBoxLayout()
        pulsanti.addWidget(aggiungi)
        pulsanti.addWidget(rimuovi)
        pulsanti.addStretch()
        corpo = QVBoxLayout()
        corpo.addWidget(self.elenco, 1)
        corpo.addLayout(pulsanti)
        riquadro = tema.cornice("Foto del cantiere", corpo, (10, 10, 10, 12))
        self.conteggio = QLabel()
        self.conteggio.setObjectName("hint")
        riquadro.intestazione.addWidget(self.conteggio)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(riquadro)

    def percorsi(self) -> list[str]:
        return [r for r in self.repo.testo("foto_cantiere").splitlines() if r.strip()]

    def aggiorna(self) -> None:
        self.elenco.clear()
        for percorso in self.percorsi():
            voce = QListWidgetItem(QIcon(percorso), Path(percorso).name)
            voce.setToolTip(percorso if Path(percorso).is_file() else f"{percorso}\n(file non trovato)")
            self.elenco.addItem(voce)
        n = self.elenco.count()
        self.conteggio.setText(f"{n} foto" if n else "nessuna foto")

    def _aggiungi(self) -> None:
        file, _ = QFileDialog.getOpenFileNames(self, "Foto del cantiere", "", "Immagini (*.png *.jpg *.jpeg *.bmp)")
        if file:
            self.repo.salva_testo("foto_cantiere", "\n".join(dict.fromkeys(self.percorsi() + file)))
            self.aggiorna()

    def _rimuovi(self) -> None:
        riga = self.elenco.currentRow()
        if riga < 0:
            return
        percorsi = self.percorsi()
        del percorsi[riga]
        self.repo.salva_testo("foto_cantiere", "\n".join(percorsi))
        self.aggiorna()


class PaginaSoggettiPOS(PaginaSoggetti):
    titolo = "Committente e CSE"
    sottotitolo = "Committente, responsabile dei lavori, coordinatori e direzione lavori del cantiere."
    voce = "Committente e CSE"


class PaginaImpresePOS(PaginaImprese):
    titolo = "Impresa e lavoratori"
    sottotitolo = "Seleziona un'impresa e compila qui sotto i suoi dati, le figure della sicurezza e le maestranze."
    voce = "Impresa e lavoratori"


class PaginaFasiPOS(PaginaFasi):
    titolo = "Lavorazioni e rischi"
    sottotitolo = ("Importa le fasi dall'archivio: portano con sé macchine, attrezzi, rischi e misure, "
                   "che puoi completare nelle schede qui sotto.")
    voce = "Lavorazioni e rischi"
    cronoprogramma = False


class PaginaDocumentiPOS(PaginaDocumenti):
    titolo = "POS e controlli"
    sottotitolo = "Genera i documenti in Word dopo aver risolto gli errori segnalati dai controlli."
    voce = "POS e controlli"
    documenti = ("pos", "sostanze", "dpi", "tesserini", "schede", "idoneita")
    principale = "pos"
    controlla = staticmethod(controlli.sincronizza_e_controlla_pos)


# --- PiMUS ---

class PaginaCantierePimus(PaginaDatiGenerali):
    titolo = "Cantiere"
    voce = "Cantiere"
    funzione_riepilogo = None


class PaginaImpresePimus(PaginaImprese):
    titolo = "Impresa che monta il ponteggio"
    voce = "Impresa"
    schede_visibili = ("dati", "figure")


def controlla_pimus(repo: Repository) -> list[controlli.Segnalazione]:
    segnalazioni = []
    c = repo.cantiere()
    if not (c["indirizzo"].strip() and c["comune"].strip()):
        segnalazioni.append(controlli.Segnalazione(controlli.ERRORE, "Cantiere", "Indicare l'indirizzo del cantiere."))
    ponteggi = repo.elenco("ponteggi")
    if not ponteggi:
        segnalazioni.append(controlli.Segnalazione(controlli.ERRORE, "Ponteggi", "Inserire almeno un ponteggio."))
    for p in ponteggi:
        for messaggio in pimus.avvisi_ponteggio(repo, p):
            segnalazioni.append(controlli.Segnalazione(controlli.AVVISO, p["nome"] or "Ponteggio", messaggio))
    return segnalazioni


PSC = Edizione(
    chiave="psc", nome="SicurCantiere PSC",
    sottotitolo="Piano di sicurezza e coordinamento, fascicolo dell'opera, notifica preliminare",
    estensione=".scs", descrizione_file="Cantiere PSC", colore="#E8792B",
    pagine=(PaginaDatiGenerali, PaginaSoggetti, PaginaImpresePSC, PaginaFasi, PaginaInterferenze,
            PaginaCosti, PaginaRelazione, PaginaFascicolo, PaginaDocumentiPSC),
    azione_principale="Genera PSC", controlla=controlli.controlla,
)

POS = Edizione(
    chiave="pos", nome="SicurCantiere POS",
    sottotitolo="Piano operativo di sicurezza, valutazioni dei rischi specifici, sostanze pericolose, DPI",
    estensione=".spo", descrizione_file="Cantiere POS", colore="#2E86C1",
    pagine=(PaginaCantierePOS, PaginaSoggettiPOS, PaginaImpresePOS, PaginaFasiPOS, PaginaValutazioni,
            PaginaSostanze, PaginaDocumentiPOS),
    azione_principale="Genera POS", controlla=controlli.sincronizza_e_controlla_pos,
)

PIMUS = Edizione(
    chiave="pimus", nome="SicurCantiere PiMUS",
    sottotitolo="Piano di montaggio, uso e smontaggio dei ponteggi",
    estensione=".spm", descrizione_file="Ponteggi PiMUS", colore="#2E9C8F",
    pagine=(PaginaCantierePimus, PaginaImpresePimus, PaginaPonteggi),
    azione_principale="Genera il PiMUS", controlla=controlla_pimus,
)

EDIZIONI: dict[str, Edizione] = {e.chiave: e for e in (PSC, POS, PIMUS)}
ESTENSIONI = tuple(e.estensione for e in EDIZIONI.values())
