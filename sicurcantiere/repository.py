"""Lettura e scrittura dei dati di progetto."""

from __future__ import annotations

import json
from typing import Any

from sicurcantiere.db import Progetto

TABELLE_ELENCO = (
    "soggetti", "imprese", "lavoratori", "fasi", "rischi", "attrezzature",
    "costi", "revisioni", "interventi", "elaborati",
    "valutazioni", "ponteggi", "verifiche_ponteggio", "sostanze", "figure",
    "mansioni_lavoratori", "sostanze_fasi", "valutazioni_fasi", "allegati_psc",
    "addetti_ponteggio", "allegati_ponteggio", "rischi_ponteggio",
)
ORDINAMENTO = {
    "fasi": "data_inizio IS NULL, data_inizio, id",
    "revisioni": "documento, numero, id",
}


class Repository:
    def __init__(self, progetto: Progetto):
        self.progetto = progetto
        self._colonne: dict[str, set[str]] = {}
        for tabella in TABELLE_ELENCO + ("cantiere",):
            righe = progetto.query(f"PRAGMA table_info({tabella})")
            self._colonne[tabella] = {r["name"] for r in righe}

    def _verifica(self, tabella: str, campi: list[str] | set[str]) -> None:
        # I nomi di tabella e colonna non possono essere parametri SQL:
        # li accettiamo solo se esistono nello schema.
        colonne = self._colonne.get(tabella)
        if colonne is None:
            raise ValueError(f"Tabella sconosciuta: {tabella}")
        sconosciuti = set(campi) - colonne
        if sconosciuti:
            raise ValueError(f"Campi sconosciuti in {tabella}: {sorted(sconosciuti)}")

    # --- dati del cantiere (riga unica) ---

    def cantiere(self) -> dict[str, Any]:
        return dict(self.progetto.query("SELECT * FROM cantiere WHERE id = 1")[0])

    def aggiorna_cantiere(self, **valori: Any) -> None:
        self._verifica("cantiere", valori.keys())
        valori.pop("id", None)
        attuale = self.cantiere()
        valori = {k: v for k, v in valori.items() if attuale.get(k) != v}  # si scrive solo ciò che cambia
        if not valori:
            return
        assegnazioni = ", ".join(f"{c} = ?" for c in valori)
        with self.progetto.transazione() as c:
            c.execute(f"UPDATE cantiere SET {assegnazioni} WHERE id = 1", tuple(valori.values()))

    # --- tabelle elenco ---

    def elenco(self, tabella: str, **filtri: Any) -> list[dict[str, Any]]:
        self._verifica(tabella, filtri.keys())
        sql = f"SELECT * FROM {tabella}"
        if filtri:
            sql += " WHERE " + " AND ".join(f"{c} = ?" for c in filtri)
        sql += f" ORDER BY {ORDINAMENTO.get(tabella, 'id')}"
        return [dict(r) for r in self.progetto.query(sql, tuple(filtri.values()))]

    def leggi(self, tabella: str, id_: int) -> dict[str, Any] | None:
        self._verifica(tabella, [])
        righe = self.progetto.query(f"SELECT * FROM {tabella} WHERE id = ?", (id_,))
        return dict(righe[0]) if righe else None

    def codice_automatico(self, lavorazione: str = "", escludi: int | None = None) -> str:
        """Codice di una fase creata a mano: la sigla della sua lavorazione (quella dell'archivio o delle
        altre fasi con la stessa lavorazione, altrimenti «UT») e il primo numero libero."""
        from sicurcantiere.archivio import LAVORAZIONI, PREFISSO_UTENTE, prefisso_lavorazione

        fasi = [f for f in self.elenco("fasi") if f["id"] != escludi]
        prefisso = prefisso_lavorazione(lavorazione)
        if prefisso is None and lavorazione.strip():
            prefisso = next((f["codice"].split(".")[0] for f in fasi if f["lavorazione"] == lavorazione
                             and "." in f["codice"] and not f["codice"].startswith(PREFISSO_UTENTE + ".")), None)
        prefisso = prefisso or PREFISSO_UTENTE
        usati = {c for c in [f["codice"] for f in fasi] + [l["codice"] for l in LAVORAZIONI]
                 if c.startswith(prefisso + ".")}
        numeri = [int(c.split(".", 1)[1]) for c in usati if c.split(".", 1)[1].isdigit()]
        return f"{prefisso}.{max(numeri, default=0) + 1:02d}"

    def inserisci(self, tabella: str, **valori: Any) -> int:
        self._verifica(tabella, valori.keys())
        with self.progetto.transazione() as c:
            if valori:
                campi = ", ".join(valori)
                segnaposto = ", ".join("?" for _ in valori)
                cur = c.execute(
                    f"INSERT INTO {tabella} ({campi}) VALUES ({segnaposto})", tuple(valori.values())
                )
            else:
                cur = c.execute(f"INSERT INTO {tabella} DEFAULT VALUES")
            return int(cur.lastrowid)

    def aggiorna(self, tabella: str, id_: int, **valori: Any) -> None:
        self._verifica(tabella, valori.keys())
        attuale = self.leggi(tabella, id_) or {}
        # si scrive solo ciò che cambia: così «modifiche non salvate» vuol dire modifiche vere
        valori = {k: v for k, v in valori.items() if k not in attuale or attuale[k] != v}
        if not valori:
            return
        assegnazioni = ", ".join(f"{c} = ?" for c in valori)
        with self.progetto.transazione() as c:
            c.execute(
                f"UPDATE {tabella} SET {assegnazioni} WHERE id = ?", (*valori.values(), id_)
            )

    def elimina(self, tabella: str, id_: int) -> None:
        self._verifica(tabella, [])
        with self.progetto.transazione() as c:
            c.execute(f"DELETE FROM {tabella} WHERE id = ?", (id_,))

    # --- relazione (testi liberi per sezione) ---

    def testo(self, sezione: str) -> str:
        righe = self.progetto.query("SELECT testo FROM relazione WHERE sezione = ?", (sezione,))
        return righe[0]["testo"] if righe else ""

    def salva_testo(self, sezione: str, testo: str) -> None:
        with self.progetto.transazione() as c:
            c.execute(
                "INSERT INTO relazione (sezione, testo) VALUES (?, ?) "
                "ON CONFLICT(sezione) DO UPDATE SET testo = excluded.testo",
                (sezione, testo),
            )

    # --- valutazioni dei rischi specifici (parametri salvati in JSON) ---

    def dati_valutazione(self, id_: int) -> dict[str, Any]:
        riga = self.leggi("valutazioni", id_)
        if riga is None:
            return {}
        try:
            dati = json.loads(riga["dati"] or "{}")
        except json.JSONDecodeError:
            return {}
        return dati if isinstance(dati, dict) else {}

    def salva_dati_valutazione(self, id_: int, dati: dict[str, Any]) -> None:
        self.aggiorna("valutazioni", id_, dati=json.dumps(dati, ensure_ascii=False, sort_keys=True))

    # --- prescrizioni sulle interferenze (coppie di fasi) ---

    # --- rischi ---

    def rischi(self, **filtro: Any) -> list[dict[str, Any]]:
        """Rischi effettivamente presenti, esclusi quelli dichiarati non presenti."""
        return [r for r in self.elenco("rischi", **filtro) if not r["non_presente"]]

    def rischi_esclusi(self, **filtro: Any) -> list[dict[str, Any]]:
        return [r for r in self.elenco("rischi", **filtro) if r["non_presente"]]

    # --- lavorazioni in cui si usa una sostanza ---

    def fasi_sostanza(self, sostanza_id: int) -> list[int]:
        righe = self.progetto.query("SELECT fase_id FROM sostanze_fasi WHERE sostanza_id = ? ORDER BY fase_id",
                                    (sostanza_id,))
        return [r["fase_id"] for r in righe]

    def salva_fasi_sostanza(self, sostanza_id: int, fasi: list[int] | set[int]) -> None:
        with self.progetto.transazione() as c:
            c.execute("DELETE FROM sostanze_fasi WHERE sostanza_id = ?", (sostanza_id,))
            c.executemany("INSERT INTO sostanze_fasi (sostanza_id, fase_id) VALUES (?, ?)",
                          [(sostanza_id, f) for f in sorted(set(fasi))])

    # --- lavorazioni a cui si riferisce una valutazione dei rischi specifici ---

    def fasi_valutazione(self, valutazione_id: int) -> list[int]:
        righe = self.progetto.query(
            "SELECT fase_id FROM valutazioni_fasi WHERE valutazione_id = ? ORDER BY fase_id", (valutazione_id,))
        return [r["fase_id"] for r in righe]

    def salva_fasi_valutazione(self, valutazione_id: int, fasi: list[int] | set[int]) -> None:
        with self.progetto.transazione() as c:
            c.execute("DELETE FROM valutazioni_fasi WHERE valutazione_id = ?", (valutazione_id,))
            c.executemany("INSERT INTO valutazioni_fasi (valutazione_id, fase_id) VALUES (?, ?)",
                          [(valutazione_id, f) for f in sorted(set(fasi))])

    # --- mansioni dei lavoratori ---

    def mansioni(self, lavoratore_id: int) -> set[tuple[int, int | None]]:
        """Coppie (fase, attrezzatura) assegnate al lavoratore; attrezzatura None per la sola lavorazione."""
        righe = self.progetto.query("SELECT fase_id, attrezzatura_id FROM mansioni_lavoratori WHERE lavoratore_id = ?",
                                    (lavoratore_id,))
        return {(r["fase_id"], r["attrezzatura_id"]) for r in righe}

    def salva_mansioni(self, lavoratore_id: int, coppie: set[tuple[int, int | None]]) -> None:
        with self.progetto.transazione() as c:
            c.execute("DELETE FROM mansioni_lavoratori WHERE lavoratore_id = ?", (lavoratore_id,))
            c.executemany("INSERT INTO mansioni_lavoratori (lavoratore_id, fase_id, attrezzatura_id) VALUES (?, ?, ?)",
                          [(lavoratore_id, f, a) for f, a in sorted(coppie, key=lambda x: (x[0], x[1] or 0))])

    def lavoratori_fase(self, fase_id: int) -> list[dict[str, Any]]:
        righe = self.progetto.query(
            "SELECT DISTINCT l.* FROM lavoratori l JOIN mansioni_lavoratori m ON m.lavoratore_id = l.id "
            "WHERE m.fase_id = ? ORDER BY l.id", (fase_id,))
        return [dict(r) for r in righe]

    def prescrizioni(self) -> dict[tuple[int, int], str]:
        return {
            (r["fase_a"], r["fase_b"]): r["testo"]
            for r in self.progetto.query("SELECT * FROM prescrizioni")
        }

    def salva_prescrizione(self, fase_a: int, fase_b: int, testo: str) -> None:
        a, b = sorted((fase_a, fase_b))
        with self.progetto.transazione() as c:
            if testo.strip():
                c.execute(
                    "INSERT INTO prescrizioni (fase_a, fase_b, testo) VALUES (?, ?, ?) "
                    "ON CONFLICT(fase_a, fase_b) DO UPDATE SET testo = excluded.testo",
                    (a, b, testo),
                )
            else:
                c.execute("DELETE FROM prescrizioni WHERE fase_a = ? AND fase_b = ?", (a, b))

    # --- archivio ---

    def importa_lavorazione(self, lavorazione: dict[str, Any]) -> int:
        """Copia una lavorazione dell'archivio nel progetto come nuova fase.

        Vengono copiati anche le macchine e gli attrezzi, con i loro rischi.
        """
        from sicurcantiere.archivio import ATTREZZATURE

        with self.progetto.transazione() as c:
            fase_id = int(
                c.execute(
                    "INSERT INTO fasi (codice, descrizione, incidenza_manodopera, lavorazione, dettaglio, addetto) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (lavorazione["codice"], lavorazione["descrizione"],
                     lavorazione.get("incidenza_manodopera", 0), lavorazione.get("gruppo", ""),
                     lavorazione.get("dettaglio", ""), lavorazione.get("addetto", "")),
                ).lastrowid
            )
            self._inserisci_rischi(c, fase_id, "", lavorazione["rischi"])
            for nome in lavorazione.get("attrezzature", []):
                self._inserisci_attrezzatura(c, fase_id, nome, ATTREZZATURE[nome])
        return fase_id

    def aggiungi_attrezzatura(self, fase_id: int, nome: str) -> None:
        """Aggiunge alla fase una macchina o un attrezzo dell'archivio con i suoi rischi."""
        from sicurcantiere.archivio import ATTREZZATURE

        with self.progetto.transazione() as c:
            self._inserisci_attrezzatura(c, fase_id, nome, ATTREZZATURE[nome])

    def aggiungi_attrezzatura_proposta(self, fase_id: int, proposta: dict[str, Any]) -> None:
        """Aggiunge una macchina o un attrezzo proposto dall'assistente (o dall'archivio se il nome c'è)."""
        from sicurcantiere.archivio import ATTREZZATURE

        if proposta["nome"] in ATTREZZATURE:
            self.aggiungi_attrezzatura(fase_id, proposta["nome"])
            return
        scheda = {k: proposta.get(k, []) for k in ("prima", "durante", "dopo")}
        scheda["descrizione"] = proposta.get("descrizione", "")
        scheda["dpi"] = [d.strip() for d in proposta.get("dpi", "").split(",") if d.strip()]
        with self.progetto.transazione() as c:
            self._inserisci_attrezzatura(c, fase_id, proposta["nome"],
                                         {"tipo": proposta["tipo"], "rischi": proposta["rischi"], "scheda": scheda})

    def _inserisci_attrezzatura(self, c, fase_id: int, nome: str, attrezzatura: dict[str, Any]) -> None:
        from sicurcantiere.archivio_attrezzature import testo_misure

        scheda = attrezzatura.get("scheda", {})
        c.execute(
            "INSERT INTO attrezzature (fase_id, tipo, nome, descrizione, misure, dpi) VALUES (?, ?, ?, ?, ?, ?)",
            (fase_id, attrezzatura["tipo"], nome, scheda.get("descrizione", ""), testo_misure(scheda),
             "; ".join(scheda.get("dpi", []))),
        )
        self._inserisci_rischi(c, fase_id, nome, attrezzatura["rischi"])

    @staticmethod
    def _inserisci_rischi(c, fase_id: int, fonte: str, rischi: list[dict[str, Any]]) -> None:
        for r in rischi:
            c.execute(
                "INSERT INTO rischi (fase_id, fonte, descrizione, probabilita, danno, misure, dpi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fase_id, fonte, r["descrizione"], r["probabilita"], r["danno"], r["misure"], r["dpi"]),
            )
