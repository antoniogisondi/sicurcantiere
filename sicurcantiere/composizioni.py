"""Documenti composti e salvati nel cantiere.

Ogni composizione è una revisione del documento (POS di un'impresa, PSC, PiMUS di un ponteggio) con il suo
file Word:
- «bozza»: si ricompone quante volte serve (filigrana BOZZA, dati mancanti evidenziati);
- «emessa»: versione definitiva bloccata; per cambiarla si compone la revisione successiva;
- «consegnata»: emessa e consegnata (a chi e quando);
- «annullata»: resta nello storico ma non vale più.
Ogni composizione registra la sua riga nella tabella delle revisioni, che il documento stampa.
"""

from __future__ import annotations

import difflib
import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from sicurcantiere.documenti import composizione
from sicurcantiere.repository import Repository

BOZZA, EMESSA, CONSEGNATA, ANNULLATA = "bozza", "emessa", "consegnata", "annullata"
STATI = {BOZZA: "Bozza", EMESSA: "Emessa", CONSEGNATA: "Consegnata", ANNULLATA: "Annullata"}
CAMPI = ("id", "documento", "numero", "descrizione", "stato", "composta_il", "emessa_il", "consegnata_il",
         "consegnata_a", "conferma", "modificata_word", "revisione_id", "capitoli", "mancanti")


class ErroreComposizione(Exception):
    pass


def generatore(documento: str) -> Callable[[Repository, Path], Path]:
    """Funzione che genera il documento indicato (\"PSC\", \"POS:<id impresa>\")."""
    if documento == "PSC":
        from sicurcantiere.documenti.psc import genera_psc

        return genera_psc
    if documento.startswith("POS:"):
        from sicurcantiere.documenti.pos import genera_pos

        impresa = int(documento.split(":", 1)[1])
        return lambda repo, percorso: genera_pos(repo, impresa, percorso)
    if documento.startswith("PIMUS:"):
        from sicurcantiere.documenti.pimus import genera_pimus

        ponteggio = int(documento.split(":", 1)[1])
        return lambda repo, percorso: genera_pimus(repo, ponteggio, percorso)
    raise ValueError(f"Documento non componibile: {documento}")


def nome_documento(repo: Repository, documento: str) -> str:
    if documento.startswith("POS:"):
        impresa = repo.leggi("imprese", int(documento.split(":", 1)[1]))
        return f"POS - {impresa['ragione_sociale'] if impresa else 'impresa'}"
    if documento.startswith("PIMUS:"):
        ponteggio = repo.leggi("ponteggi", int(documento.split(":", 1)[1]))
        return f"PiMUS - {ponteggio['nome'] if ponteggio else 'ponteggio'}"
    return documento


def _riga(r) -> dict[str, Any]:
    d = {k: r[k] for k in CAMPI}
    d["capitoli"] = json.loads(d["capitoli"] or "[]")
    d["mancanti"] = json.loads(d["mancanti"] or "[]")
    return d


def elenco(repo: Repository, documento: str) -> list[dict[str, Any]]:
    """Composizioni del documento, dalla più recente (senza il file)."""
    righe = repo.progetto.query(f"SELECT {', '.join(CAMPI)} FROM composizioni WHERE documento = ? "
                                "ORDER BY numero DESC, id DESC", (documento,))
    return [_riga(r) for r in righe]


def leggi(repo: Repository, id_: int) -> dict[str, Any] | None:
    righe = repo.progetto.query(f"SELECT {', '.join(CAMPI)} FROM composizioni WHERE id = ?", (id_,))
    return _riga(righe[0]) if righe else None


def contenuto(repo: Repository, id_: int) -> bytes:
    righe = repo.progetto.query("SELECT file FROM composizioni WHERE id = ?", (id_,))
    return bytes(righe[0]["file"]) if righe and righe[0]["file"] is not None else b""


def bozza(repo: Repository, documento: str) -> dict[str, Any] | None:
    return next((c for c in elenco(repo, documento) if c["stato"] == BOZZA), None)


def numero_proposto(repo: Repository, documento: str) -> int:
    """Numero della prossima revisione: 0 alla prima emissione, poi il successivo all'ultima."""
    righe = repo.progetto.query("SELECT MAX(numero) AS n FROM revisioni WHERE documento = ?", (documento,))
    n = righe[0]["n"] if righe else None
    return 0 if n is None else n + 1


# --- personalizzazioni dei capitoli ---

def personalizzazioni(repo: Repository, documento: str) -> dict[str, dict[str, Any]]:
    righe = repo.progetto.query("SELECT * FROM personalizzazioni WHERE documento = ?", (documento,))
    return {r["capitolo"]: dict(r) for r in righe}


def salva_personalizzazione(repo: Repository, documento: str, capitolo: str, *, titolo: str = "",
                            modo: str = composizione.AGGIUNGI, testo: str = "", impronta: str = "",
                            escluso: bool = False) -> None:
    """Modifica di un capitolo; senza testo e senza esclusione la personalizzazione si toglie."""
    with repo.progetto.transazione() as c:
        if not testo.strip() and not escluso:
            c.execute("DELETE FROM personalizzazioni WHERE documento = ? AND capitolo = ?", (documento, capitolo))
            return
        c.execute(
            "INSERT INTO personalizzazioni (documento, capitolo, titolo, modo, testo, impronta, escluso) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(documento, capitolo) DO UPDATE SET titolo = excluded.titolo, "
            "modo = excluded.modo, testo = excluded.testo, impronta = excluded.impronta, escluso = excluded.escluso",
            (documento, capitolo, titolo, modo, testo, impronta, int(escluso)))


# --- composizione ---

def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def componi(repo: Repository, documento: str, descrizione: str = "", numero: int | None = None) -> dict[str, Any]:
    """Compone la bozza del documento (ricomponendo quella esistente, se c'è) e la salva nel cantiere."""
    attuale = bozza(repo, documento)
    if numero is None:
        numero = attuale["numero"] if attuale else numero_proposto(repo, documento)
    if not descrizione:
        descrizione = attuale["descrizione"] if attuale else ("Prima emissione" if numero == 0 else "")

    # la riga della revisione entra nel documento (copertina, intestazione, tabella delle revisioni)
    oggi = date.today().isoformat()
    revisione_id = attuale["revisione_id"] if attuale else None
    if revisione_id and repo.leggi("revisioni", revisione_id):
        repo.aggiorna("revisioni", revisione_id, numero=numero, data=oggi, descrizione=descrizione)
    else:
        revisione_id = repo.inserisci("revisioni", documento=documento, numero=numero, data=oggi,
                                      descrizione=descrizione)

    with tempfile.TemporaryDirectory() as cartella, \
            composizione.in_composizione(personalizzazioni(repo, documento)) as contesto:
        percorso = Path(cartella) / "documento.docx"
        generatore(documento)(repo, percorso)
        dati = percorso.read_bytes()

    valori = (documento, numero, descrizione, _adesso(), revisione_id, json.dumps(contesto.capitoli),
              json.dumps(contesto.mancanti), dati)
    with repo.progetto.transazione() as c:
        if attuale:
            c.execute("UPDATE composizioni SET documento = ?, numero = ?, descrizione = ?, composta_il = ?, "
                      "revisione_id = ?, capitoli = ?, mancanti = ?, file = ?, modificata_word = 0 WHERE id = ?",
                      (*valori, attuale["id"]))
            id_ = attuale["id"]
        else:
            id_ = c.execute("INSERT INTO composizioni (documento, numero, descrizione, composta_il, revisione_id, "
                            "capitoli, mancanti, file) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", valori).lastrowid
    return leggi(repo, id_)


def obbligatori_mancanti(c: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in c["mancanti"] if m["livello"] == composizione.OBBLIGATORIO]


def acquisisci_da_word(repo: Repository, id_: int, dati: bytes) -> None:
    """Il file della bozza modificato in Word diventa il file della composizione."""
    c = leggi(repo, id_)
    if c is None or c["stato"] != BOZZA:
        raise ErroreComposizione("Si possono riprendere da Word solo le bozze.")
    with repo.progetto.transazione() as conn:
        conn.execute("UPDATE composizioni SET file = ?, modificata_word = 1 WHERE id = ?", (dati, id_))


def emetti(repo: Repository, id_: int, conferma: str = "") -> dict[str, Any]:
    """Versione definitiva: senza filigrana né evidenziazioni, bloccata. Con dati obbligatori mancanti serve
    la conferma (che resta registrata)."""
    c = leggi(repo, id_)
    if c is None or c["stato"] != BOZZA:
        raise ErroreComposizione("Si può emettere solo una bozza.")
    if obbligatori_mancanti(c) and not conferma.strip():
        raise ErroreComposizione("Mancano dati obbligatori: per emettere serve la conferma.")
    definitivo = composizione.definitivo(contenuto(repo, id_))
    with repo.progetto.transazione() as conn:
        conn.execute("UPDATE composizioni SET stato = ?, emessa_il = ?, conferma = ?, file = ? WHERE id = ?",
                     (EMESSA, _adesso(), conferma.strip(), definitivo, id_))
    return leggi(repo, id_)


def segna_consegnata(repo: Repository, id_: int, destinatario: str, il: str | None = None) -> None:
    c = leggi(repo, id_)
    if c is None or c["stato"] not in (EMESSA, CONSEGNATA):
        raise ErroreComposizione("Si può consegnare solo un documento emesso.")
    with repo.progetto.transazione() as conn:
        conn.execute("UPDATE composizioni SET stato = ?, consegnata_il = ?, consegnata_a = ? WHERE id = ?",
                     (CONSEGNATA, il or date.today().isoformat(), destinatario.strip(), id_))


def annulla(repo: Repository, id_: int) -> None:
    """La bozza si elimina (con la sua riga di revisione); un documento emesso resta nello storico come
    annullato."""
    c = leggi(repo, id_)
    if c is None:
        return
    if c["stato"] == BOZZA:
        with repo.progetto.transazione() as conn:
            conn.execute("DELETE FROM composizioni WHERE id = ?", (id_,))
            if c["revisione_id"]:
                conn.execute("DELETE FROM revisioni WHERE id = ?", (c["revisione_id"],))
        return
    with repo.progetto.transazione() as conn:
        conn.execute("UPDATE composizioni SET stato = ? WHERE id = ?", (ANNULLATA, id_))
        if c["revisione_id"]:
            conn.execute("UPDATE revisioni SET descrizione = 'Annullata - ' || descrizione "
                         "WHERE id = ? AND descrizione NOT LIKE 'Annullata - %'", (c["revisione_id"],))


# --- confronto tra due revisioni ---

def confronta(vecchia: dict[str, Any], nuova: dict[str, Any]) -> list[dict[str, Any]]:
    """Capitoli aggiunti, tolti o cambiati tra due composizioni, con le righe cambiate."""
    prima = {c["chiave"]: c for c in vecchia["capitoli"] if not c.get("escluso")}
    dopo = {c["chiave"]: c for c in nuova["capitoli"] if not c.get("escluso")}
    esito = []
    for chiave in list(dopo) + [k for k in prima if k not in dopo]:
        a, b = prima.get(chiave), dopo.get(chiave)
        titolo = (b or a)["titolo"]
        if a is None:
            esito.append({"titolo": titolo, "stato": "aggiunto", "righe": [("+", r) for r in b["testo"].splitlines()]})
        elif b is None:
            esito.append({"titolo": titolo, "stato": "tolto", "righe": [("-", r) for r in a["testo"].splitlines()]})
        elif a["testo"] != b["testo"]:
            righe = []
            for riga in difflib.ndiff(a["testo"].splitlines(), b["testo"].splitlines()):
                if riga[:1] in "+-":
                    righe.append((riga[0], riga[2:]))
            esito.append({"titolo": titolo, "stato": "cambiato", "righe": righe})
    return esito
