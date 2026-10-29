"""Aggiornamenti del programma: controllo dell'ultima versione pubblicata e scaricamento verificato.

Ogni versione pubblicata ha, accanto all'installatore, il file «SicurCantiere-setup.exe.firma»:
numero di versione, dimensione e impronta SHA-256 dell'installatore, firmati con la chiave degli
aggiornamenti (Ed25519) di SicurCantiere. Il programma contiene solo la chiave pubblica e installa un
aggiornamento solo se la firma è valida e il file scaricato corrisponde: un installatore sostituito o
modificato (anche di un byte) non viene avviato.

Le versioni sono pubblicate dal workflow «Installatore Windows» come release del repository,
con l'installatore anche sotto il nome fisso SicurCantiere-setup.exe. L'indirizzo si può
cambiare con la variabile SICURCANTIERE_URL_AGGIORNAMENTI (per esempio per un repository
pubblico che contiene solo gli installatori).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from sicurcantiere import __version__

URL_ULTIMA_VERSIONE = "https://api.github.com/repos/antoniogisondi/sicurcantiere/releases/latest"
NOME_INSTALLATORE = "SicurCantiere-setup.exe"
NOME_FIRMA = NOME_INSTALLATORE + ".firma"
# Chiave pubblica degli aggiornamenti (32 byte in base64), attiva dalla versione 0.27.1: ogni aggiornamento
# deve essere firmato con la chiave segreta corrispondente (sulla VM e nel segreto di GitHub).
CHIAVE_AGGIORNAMENTI = "ZrIYttQrTO3pxuxFk5CLWYeBBijka/bnZAHtMlUcgE8="


class ErroreAggiornamento(Exception):
    """Controllo o scaricamento non riuscito (rete assente, indirizzo non raggiungibile...)."""


@dataclass(frozen=True)
class Versione:
    numero: str
    url_installatore: str
    pagina: str
    note: str
    pubblicata: date | None = None
    url_firma: str = ""


def numero(testo: str) -> tuple[int, ...]:
    """«v0.13.1» -> (0, 13, 1); le parti non numeriche sono ignorate."""
    return tuple(int(n) for n in re.findall(r"\d+", testo)[:4])


def piu_recente(pubblicata: str, installata: str = __version__) -> bool:
    return numero(pubblicata) > numero(installata)


def url_controllo() -> str:
    return os.environ.get("SICURCANTIERE_URL_AGGIORNAMENTI") or URL_ULTIMA_VERSIONE


def ultima_versione(timeout: float = 8, apri: Callable = urllib.request.urlopen) -> Versione:
    """Ultima versione pubblicata, con l'indirizzo del suo installatore."""
    richiesta = urllib.request.Request(url_controllo(), headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"SicurCantiere/{__version__}"})
    try:
        with apri(richiesta, timeout=timeout) as risposta:
            dati = json.loads(risposta.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        raise ErroreAggiornamento(f"Impossibile controllare gli aggiornamenti: {e}") from e
    allegati = {a.get("name", ""): a.get("browser_download_url", "") for a in dati.get("assets") or []}
    url = allegati.get(NOME_INSTALLATORE) or next(
        (u for n, u in allegati.items() if n.lower().endswith("-setup.exe")), "")
    if not dati.get("tag_name") or not url:
        raise ErroreAggiornamento("La versione pubblicata non contiene l'installatore.")
    try:
        pubblicata = date.fromisoformat(str(dati.get("published_at") or "")[:10])
    except ValueError:
        pubblicata = None
    return Versione(dati["tag_name"].lstrip("v"), url, dati.get("html_url", ""), dati.get("body") or "", pubblicata,
                    allegati.get(NOME_FIRMA, ""))


def inclusa_nella_licenza(versione: Versione, scadenza: date | None) -> bool:
    """Con la licenza scaduta si ricevono solo le versioni pubblicate prima della scadenza."""
    return scadenza is None or versione.pubblicata is None or versione.pubblicata <= scadenza


def scarica(url: str, destinazione: str | Path, avanzamento: Callable[[int, int], bool] | None = None,
            timeout: float = 30, apri: Callable = urllib.request.urlopen) -> Path:
    """Scarica l'installatore; `avanzamento(letti, totale)` restituisce False per annullare."""
    destinazione = Path(destinazione)
    parziale = destinazione.with_name(destinazione.name + ".part")
    richiesta = urllib.request.Request(url, headers={"User-Agent": f"SicurCantiere/{__version__}"})
    try:
        with apri(richiesta, timeout=timeout) as risposta, open(parziale, "wb") as file:
            totale = int(risposta.headers.get("Content-Length") or 0)
            letti = 0
            while blocco := risposta.read(256 * 1024):
                file.write(blocco)
                letti += len(blocco)
                if avanzamento and avanzamento(letti, totale) is False:
                    raise ErroreAggiornamento("Scaricamento annullato.")
        if totale and letti != totale:
            raise ErroreAggiornamento("Scaricamento incompleto: riprova.")
        parziale.replace(destinazione)
    except OSError as e:
        raise ErroreAggiornamento(f"Scaricamento non riuscito: {e}") from e
    finally:
        parziale.unlink(missing_ok=True)
    return destinazione


# --- firma degli aggiornamenti ---

def chiave_aggiornamenti() -> str:
    return os.environ.get("SICURCANTIERE_CHIAVE_AGGIORNAMENTI") or CHIAVE_AGGIORNAMENTI


def _impronta(file: Path) -> tuple[str, int]:
    h, dimensione = hashlib.sha256(), 0
    with open(file, "rb") as f:
        while blocco := f.read(1024 * 1024):
            h.update(blocco)
            dimensione += len(blocco)
    return h.hexdigest(), dimensione


def firma_installatore(file: str | Path, versione: str, chiave_privata: bytes) -> str:
    """Testo del file .firma per un installatore (lo usa la pubblicazione, che ha la chiave privata)."""
    from sicur_license.certificato import firma_dati

    sha256, dimensione = _impronta(Path(file))
    dati = json.dumps({"versione": versione, "sha256": sha256, "dimensione": dimensione}, sort_keys=True,
                      separators=(",", ":")).encode()
    return json.dumps({"dati": base64.b64encode(dati).decode(),
                       "firma": base64.b64encode(firma_dati(chiave_privata, dati)).decode()})


def verifica_installatore(file: str | Path, versione: str, testo_firma: str, chiave: str | None = None) -> None:
    """ErroreAggiornamento se la firma non è valida o il file non è quello firmato per `versione`."""
    from sicur_license.certificato import verifica_dati

    errore = "L'aggiornamento scaricato non è verificato e non verrà installato"
    try:
        contenitore = json.loads(testo_firma)
        dati, firma = base64.b64decode(contenitore["dati"]), base64.b64decode(contenitore["firma"])
        pubblica = base64.b64decode(chiave or chiave_aggiornamenti())
    except (ValueError, KeyError, TypeError) as e:
        raise ErroreAggiornamento(f"{errore}: firma illeggibile.") from e
    if not verifica_dati(pubblica, dati, firma):
        raise ErroreAggiornamento(f"{errore}: firma non valida.")
    attesi = json.loads(dati)
    if attesi.get("versione") != versione:
        raise ErroreAggiornamento(f"{errore}: la firma è di un'altra versione.")
    sha256, dimensione = _impronta(Path(file))
    if (sha256, dimensione) != (attesi.get("sha256"), attesi.get("dimensione")):
        raise ErroreAggiornamento(f"{errore}: il file è diverso da quello pubblicato (scaricamento rovinato o file "
                                  "manomesso).")


def scarica_verificato(versione: Versione, destinazione: str | Path,
                       avanzamento: Callable[[int, int], bool] | None = None,
                       apri: Callable = urllib.request.urlopen) -> Path:
    """Scarica l'installatore e, con la chiave degli aggiornamenti, ne verifica la firma prima di usarlo."""
    if not chiave_aggiornamenti():
        return scarica(versione.url_installatore, destinazione, avanzamento, apri=apri)
    if not versione.url_firma:
        raise ErroreAggiornamento("La versione pubblicata non è firmata: l'aggiornamento non verrà installato.")
    richiesta = urllib.request.Request(versione.url_firma, headers={"User-Agent": f"SicurCantiere/{__version__}"})
    try:
        with apri(richiesta, timeout=30) as risposta:
            testo_firma = risposta.read(64 * 1024).decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ErroreAggiornamento(f"Impossibile scaricare la firma dell'aggiornamento: {e}") from e
    file = scarica(versione.url_installatore, destinazione, avanzamento, apri=apri)
    try:
        verifica_installatore(file, versione.numero, testo_firma)
    except ErroreAggiornamento:
        Path(file).unlink(missing_ok=True)
        raise
    return file
