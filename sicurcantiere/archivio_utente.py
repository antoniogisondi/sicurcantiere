"""Archivio delle anagrafiche dell'utente, comune a tutti i cantieri e ai tre programmi.

Contiene le persone (committenti, coordinatori, RSPP, medici competenti, preposti...), le
imprese con le loro figure e maestranze, le lavorazioni personalizzate (con macchine,
attrezzi e rischi) e i sistemi di ponteggio usati (fabbricante, autorizzazione ministeriale,
campate, pesi, libretto), così da non doverli riscrivere in ogni cantiere.
Si trova in un file SQLite nella cartella dei dati dell'utente.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sicurcantiere.repository import Repository

PERSONA = "persona"
IMPRESA = "impresa"
LAVORAZIONE = "lavorazione"
SISTEMA = "sistema_ponteggio"

# Dati del ponteggio e della sua geometria che descrivono il sistema (non il singolo cantiere).
CAMPI_SISTEMA = ("fabbricante", "sistema", "modello", "tipo", "autorizzazione", "aut_data", "aut_rinnovo",
                 "schemi_tipo", "classe_carico", "ancoraggi")
GEOMETRIA_SISTEMA = ("campata", "larghezza", "interpiano", "peso_proprio", "tipo_ancoraggio", "ancoraggi_campate",
                     "ancoraggi_livelli", "ancoraggi_rombo")
ALLEGATI_SISTEMA = ("Libretto del fabbricante", "Autorizzazione ministeriale", "Schema degli ancoraggi")

# Campi che non hanno senso fuori dal cantiere di origine.
_ESCLUSI = {"id", "impresa_id", "affidataria_id", "fase_id"}


def percorso_predefinito() -> Path:
    if os.environ.get("SICURCANTIERE_ARCHIVIO"):
        return Path(os.environ["SICURCANTIERE_ARCHIVIO"])
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "SicurCantiere" / "archivio.db"


def _pulisci(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in _ESCLUSI and k != "nota"}


class ArchivioAnagrafiche:
    def __init__(self, percorso: str | Path | None = None):
        self.percorso = Path(percorso) if percorso else percorso_predefinito()
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.percorso)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS voci (
                id INTEGER PRIMARY KEY,
                tipo TEXT NOT NULL,
                ruolo TEXT NOT NULL DEFAULT '',
                nome TEXT NOT NULL,
                dati TEXT NOT NULL,
                modificato TEXT NOT NULL
            )""")
        self.conn.commit()

    def chiudi(self) -> None:
        self.conn.close()

    # --- operazioni di base ---

    def salva(self, tipo: str, nome: str, dati: dict[str, Any], ruolo: str = "") -> int:
        """Inserisce la voce o aggiorna quella con lo stesso tipo, ruolo e nome."""
        nome = nome.strip()
        if not nome:
            raise ValueError("Indica il nominativo prima di salvarlo nell'archivio.")
        testo = json.dumps(dati, ensure_ascii=False)
        adesso = datetime.now().isoformat(timespec="seconds")
        riga = self.conn.execute(
            "SELECT id FROM voci WHERE tipo = ? AND ruolo = ? AND lower(nome) = lower(?)", (tipo, ruolo, nome)
        ).fetchone()
        with self.conn:
            if riga:
                self.conn.execute("UPDATE voci SET nome = ?, dati = ?, modificato = ? WHERE id = ?",
                                  (nome, testo, adesso, riga["id"]))
                return int(riga["id"])
            cur = self.conn.execute("INSERT INTO voci (tipo, ruolo, nome, dati, modificato) VALUES (?, ?, ?, ?, ?)",
                                    (tipo, ruolo, nome, testo, adesso))
            return int(cur.lastrowid)

    def elenco(self, tipo: str | None = None, testo: str = "") -> list[dict[str, Any]]:
        sql, parametri = "SELECT * FROM voci WHERE 1 = 1", []
        if tipo:
            sql += " AND tipo = ?"
            parametri.append(tipo)
        if testo.strip():
            sql += " AND (lower(nome) LIKE ? OR lower(ruolo) LIKE ?)"
            parametri += [f"%{testo.strip().lower()}%"] * 2
        sql += " ORDER BY ruolo, lower(nome)"
        return [self._voce(r) for r in self.conn.execute(sql, parametri)]

    def leggi(self, id_: int) -> dict[str, Any] | None:
        r = self.conn.execute("SELECT * FROM voci WHERE id = ?", (id_,)).fetchone()
        return self._voce(r) if r else None

    def elimina(self, id_: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM voci WHERE id = ?", (id_,))

    @staticmethod
    def _voce(r: sqlite3.Row) -> dict[str, Any]:
        return {"id": r["id"], "tipo": r["tipo"], "ruolo": r["ruolo"], "nome": r["nome"],
                "dati": json.loads(r["dati"]), "modificato": r["modificato"]}

    # --- dal cantiere all'archivio ---

    def salva_persona(self, record: dict[str, Any]) -> int:
        return self.salva(PERSONA, record.get("nome", ""), _pulisci(record), record.get("ruolo", ""))

    def salva_impresa(self, repo: Repository, impresa_id: int) -> int:
        impresa = repo.leggi("imprese", impresa_id)
        if impresa is None:
            raise ValueError("Impresa non trovata.")
        dati = _pulisci(impresa)
        dati["figure"] = [_pulisci(f) for f in repo.elenco("figure", impresa_id=impresa_id)]
        dati["lavoratori"] = [_pulisci(l) for l in repo.elenco("lavoratori", impresa_id=impresa_id)]
        return self.salva(IMPRESA, impresa["ragione_sociale"], dati)

    # --- dall'archivio al cantiere ---

    @staticmethod
    def _campi(repo: Repository, tabella: str, dati: dict[str, Any]) -> dict[str, Any]:
        colonne = repo._colonne[tabella] - _ESCLUSI
        return {k: v for k, v in dati.items() if k in colonne}

    def inserisci_persona(self, repo: Repository, voce: dict[str, Any], tabella: str, **extra: Any) -> int:
        """Inserisce la persona in «soggetti» o «figure», con i soli campi che la tabella prevede."""
        return repo.inserisci(tabella, **{**self._campi(repo, tabella, voce["dati"]), **extra})

    def inserisci_impresa(self, repo: Repository, voce: dict[str, Any]) -> int:
        dati = voce["dati"]
        impresa_id = repo.inserisci("imprese", **self._campi(repo, "imprese", dati))
        for f in dati.get("figure", []):
            repo.inserisci("figure", impresa_id=impresa_id, **self._campi(repo, "figure", f))
        for l in dati.get("lavoratori", []):
            repo.inserisci("lavoratori", impresa_id=impresa_id, **self._campi(repo, "lavoratori", l))
        return impresa_id

    # --- sistemi di ponteggio ---

    def salva_sistema(self, repo: Repository, ponteggio_id: int) -> int:
        """Salva il sistema del ponteggio (fabbricante, autorizzazione, campate, pesi, libretto) nell'archivio."""
        from sicurcantiere import ponteggio as P

        p = repo.leggi("ponteggi", ponteggio_id)
        if p is None:
            raise ValueError("Ponteggio non trovato.")
        dati = {k: p.get(k) for k in CAMPI_SISTEMA}
        g = P.geometria(p)
        dati["geometria"] = {k: g[k] for k in GEOMETRIA_SISTEMA}
        dati["allegati"] = [{k: a[k] for k in ("tipo", "titolo", "file")}
                            for a in repo.elenco("allegati_ponteggio", ponteggio_id=ponteggio_id)
                            if a["tipo"] in ALLEGATI_SISTEMA]
        nome = nome_sistema(dati)
        if not nome:
            raise ValueError("Indica almeno il fabbricante o il nome del sistema prima di salvarlo nell'archivio.")
        return self.salva(SISTEMA, nome, dati, p.get("tipo") or "")

    @staticmethod
    def applica_sistema(repo: Repository, ponteggio_id: int, voce: dict[str, Any]) -> None:
        """Copia il sistema dell'archivio nel ponteggio: dati, valori comuni della geometria, libretto e
        autorizzazione tra gli allegati (se non ci sono già)."""
        from sicurcantiere import ponteggio as P

        dati = voce["dati"]
        p = repo.leggi("ponteggi", ponteggio_id)
        g = P.geometria(p)
        g.update({k: v for k, v in (dati.get("geometria") or {}).items() if k in GEOMETRIA_SISTEMA})
        valori = {k: dati[k] for k in CAMPI_SISTEMA if dati.get(k) is not None}
        repo.aggiorna("ponteggi", ponteggio_id, geometria=P.testo_geometria(g), **valori)
        presenti = {a["file"] for a in repo.elenco("allegati_ponteggio", ponteggio_id=ponteggio_id)}
        for a in dati.get("allegati", []):
            if a.get("file") and a["file"] not in presenti:
                repo.inserisci("allegati_ponteggio", ponteggio_id=ponteggio_id, tipo=a.get("tipo", ""),
                               titolo=a.get("titolo", ""), file=a["file"])

    # --- lavorazioni personalizzate ---

    def salva_lavorazione(self, repo: Repository, fase_id: int, categoria: str = "") -> int:
        """Salva la fase del cantiere come lavorazione dell'utente, con attrezzature e rischi."""
        fase = repo.leggi("fasi", fase_id)
        if fase is None:
            raise ValueError("Lavorazione non trovata.")
        dati = {
            "codice": fase["codice"],
            "descrizione": fase["descrizione"],
            "incidenza_manodopera": fase["incidenza_manodopera"],
            "gruppo": fase["lavorazione"],
            "dettaglio": fase["dettaglio"],
            "addetto": fase["addetto"],
            "attrezzature": [{k: a[k] for k in ("nome", "tipo", "descrizione", "misure", "dpi")}
                             for a in repo.elenco("attrezzature", fase_id=fase_id)],
            "rischi": [{k: r[k] for k in ("fonte", "descrizione", "probabilita", "danno", "misure", "dpi",
                                          "non_presente", "motivazione")}
                       for r in repo.elenco("rischi", fase_id=fase_id)],
        }
        nome = " ".join(v for v in (fase["codice"], fase["descrizione"]) if v)
        return self.salva(LAVORAZIONE, nome, dati, categoria)

    @staticmethod
    def inserisci_lavorazione(repo: Repository, voce: dict[str, Any]) -> int:
        dati = voce["dati"]
        fase_id = repo.inserisci("fasi", codice=dati.get("codice", ""), descrizione=dati.get("descrizione", ""),
                                 incidenza_manodopera=dati.get("incidenza_manodopera", 0),
                                 lavorazione=dati.get("gruppo", ""), dettaglio=dati.get("dettaglio", ""),
                                 addetto=dati.get("addetto", ""))
        for a in dati.get("attrezzature", []):
            repo.inserisci("attrezzature", fase_id=fase_id, nome=a["nome"], tipo=a.get("tipo", ""),
                           **{k: a.get(k, "") for k in ("descrizione", "misure", "dpi")})
        for r in dati.get("rischi", []):
            repo.inserisci("rischi", fase_id=fase_id, **r)
        return fase_id



def nome_sistema(dati: dict[str, Any]) -> str:
    return " ".join(v for v in (dati.get("fabbricante", ""), dati.get("sistema", ""), dati.get("modello", ""))
                    if v).strip()
