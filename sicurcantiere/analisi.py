"""Calcoli sul progetto: livelli di rischio, interferenze, uomini-giorno, obblighi."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sicurcantiere import anagrafiche

# Matrice P x D (probabilità 1-4, danno 1-4).
CLASSI_RISCHIO = [
    (9, "Molto alto"),
    (6, "Alto"),
    (3, "Medio"),
    (1, "Basso"),
]

# Art. 99 c. 1 lett. c: notifica obbligatoria con impresa unica oltre questa soglia.
SOGLIA_UOMINI_GIORNO = 200


def livello_rischio(probabilita: int, danno: int) -> int:
    return int(probabilita) * int(danno)


def classe_rischio(livello: int) -> str:
    for soglia, nome in CLASSI_RISCHIO:
        if livello >= soglia:
            return nome
    return "Basso"


def data(valore: str | None) -> date | None:
    if not valore:
        return None
    try:
        return date.fromisoformat(valore)
    except ValueError:
        return None


def giorni_lavorativi(inizio: date, fine: date) -> int:
    """Giorni dal lunedì al venerdì compresi tra inizio e fine (estremi inclusi)."""
    if fine < inizio:
        return 0
    totale = (fine - inizio).days + 1
    settimane, resto = divmod(totale, 7)
    giorni = settimane * 5
    giorno = inizio + timedelta(days=settimane * 7)
    for _ in range(resto):
        if giorno.weekday() < 5:
            giorni += 1
        giorno += timedelta(days=1)
    return giorni


def fine_dopo_giorni_lavorativi(inizio: date, giorni: int) -> date:
    """Data dell'ultimo giorno di una lavorazione di `giorni` giorni lavorativi."""
    giorno = inizio
    while giorno.weekday() >= 5:
        giorno += timedelta(days=1)
    contati = 1
    while contati < max(giorni, 1):
        giorno += timedelta(days=1)
        if giorno.weekday() < 5:
            contati += 1
    return giorno


COSTO_UOMO_GIORNO = 250.0  # valore tipico, usato se nel cantiere il costo non è indicato


def durata_stimata(importo: float, incidenza_manodopera: float, costo_uomo_giorno: float,
                   lavoratori: int) -> int | None:
    """Giorni lavorativi stimati di una fase (Gantt analitico).

    uomini-giorno = importo x incidenza% / costo di un uomo-giorno;
    durata = uomini-giorno / lavoratori della squadra, arrotondata per eccesso.
    """
    if importo <= 0 or incidenza_manodopera <= 0 or costo_uomo_giorno <= 0 or lavoratori <= 0:
        return None
    ug = importo * incidenza_manodopera / 100 / costo_uomo_giorno
    return max(1, math.ceil(ug / lavoratori - 1e-9))


def uomini_giorno(fasi: list[dict[str, Any]]) -> int:
    totale = 0
    for f in fasi:
        inizio, fine = data(f.get("data_inizio")), data(f.get("data_fine"))
        if inizio and fine:
            totale += giorni_lavorativi(inizio, fine) * max(int(f.get("lavoratori") or 0), 0)
    return totale


def periodo_lavori(fasi: list[dict[str, Any]]) -> tuple[date, date] | None:
    inizi = [d for f in fasi if (d := data(f.get("data_inizio")))]
    fini = [d for f in fasi if (d := data(f.get("data_fine")))]
    if not inizi or not fini:
        return None
    return min(inizi), max(fini)


def livelli_fasi(rischi: list[dict[str, Any]]) -> dict[int, int]:
    """Livello di rischio massimo di ogni fase."""
    livelli: dict[int, int] = {}
    for r in rischi:
        livello = livello_rischio(r["probabilita"], r["danno"])
        livelli[r["fase_id"]] = max(livelli.get(r["fase_id"], 0), livello)
    return livelli


@dataclass(frozen=True)
class Interferenza:
    fase_a: dict[str, Any]
    fase_b: dict[str, Any]
    inizio: date
    fine: date
    gravita: int = 0  # livello di rischio massimo tra le due fasi

    @property
    def chiave(self) -> tuple[int, int]:
        return tuple(sorted((self.fase_a["id"], self.fase_b["id"])))  # type: ignore[return-value]


def _stessa(a: Any, b: Any) -> bool:
    return bool(a) and a == b


def interferenze(fasi: list[dict[str, Any]],
                 livelli: dict[int, int] | None = None) -> list[Interferenza]:
    """Coppie di fasi sovrapposte nel tempo eseguite da imprese diverse nella stessa zona.

    Le fasi senza impresa o senza zona sono considerate potenzialmente
    interferenti, finché il dato non viene indicato. Risultato ordinato per
    gravità decrescente e poi per data.
    """
    livelli = livelli or {}
    risultato = []
    datate = [
        (f, i, e)
        for f in fasi
        if (i := data(f.get("data_inizio"))) and (e := data(f.get("data_fine"))) and i <= e
    ]
    for n, (a, ia, fa) in enumerate(datate):
        for b, ib, fb in datate[n + 1:]:
            inizio, fine = max(ia, ib), min(fa, fb)
            if inizio > fine or giorni_lavorativi(inizio, fine) == 0:
                continue
            if _stessa(a.get("impresa_id"), b.get("impresa_id")):
                continue
            za, zb = (a.get("zona") or "").strip().lower(), (b.get("zona") or "").strip().lower()
            if za and zb and za != zb:
                continue
            gravita = max(livelli.get(a["id"], 0), livelli.get(b["id"], 0))
            risultato.append(Interferenza(a, b, inizio, fine, gravita))
    risultato.sort(key=lambda i: (-i.gravita, i.inizio))
    return risultato


@dataclass(frozen=True)
class Giornata:
    giorno: date
    lavoratori: int
    pericolosita: int


def andamento(fasi: list[dict[str, Any]], livelli: dict[int, int]) -> list[Giornata]:
    """Affollamento (lavoratori presenti) e pericolosità (rischio massimo) per giorno lavorativo."""
    periodo = periodo_lavori(fasi)
    if not periodo:
        return []
    intervalli = [
        (i, e, int(f.get("lavoratori") or 0), livelli.get(f["id"], 0))
        for f in fasi
        if (i := data(f.get("data_inizio"))) and (e := data(f.get("data_fine")))
    ]
    risultato = []
    giorno = periodo[0]
    while giorno <= periodo[1]:
        if giorno.weekday() < 5:
            attive = [(l, p) for i, e, l, p in intervalli if i <= giorno <= e]
            risultato.append(Giornata(
                giorno,
                sum(l for l, _ in attive),
                max((p for _, p in attive), default=0),
            ))
        giorno += timedelta(days=1)
    return risultato


def picco_lavoratori(fasi: list[dict[str, Any]]) -> int:
    return max((g.lavoratori for g in andamento(fasi, {})), default=0)


def totale_costi(costi: list[dict[str, Any]]) -> float:
    return round(sum(float(c["quantita"] or 0) * float(c["prezzo_unitario"] or 0) for c in costi), 2)


def imprese_esecutrici(imprese: list[dict[str, Any]], fasi: list[dict[str, Any]]) -> int:
    """Numero di imprese (escl. lavoratori autonomi) che eseguono almeno una fase.

    Se nessuna fase ha un'impresa assegnata si contano le imprese in elenco.
    """
    assegnate = {f["impresa_id"] for f in fasi if f.get("impresa_id")}
    candidati = [i for i in imprese if not anagrafiche.autonomo(i)]
    if assegnate:
        candidati = [i for i in candidati if i["id"] in assegnate]
    return len(candidati)


@dataclass(frozen=True)
class Obblighi:
    imprese: int
    uomini_giorno: int
    psc: bool
    notifica: bool

    def descrizione(self) -> list[str]:
        righe = [
            f"Imprese esecutrici: {self.imprese}",
            f"Entità presunta del cantiere: {self.uomini_giorno} uomini-giorno",
        ]
        if self.psc:
            righe.append("Nomina del CSP e del CSE e redazione del PSC obbligatorie (art. 90, commi 3 e 4).")
        else:
            righe.append("PSC non obbligatorio con un'unica impresa esecutrice (resta obbligatorio il POS "
                         "dell'impresa).")
        if self.notifica:
            righe.append("Notifica preliminare obbligatoria (art. 99).")
        else:
            righe.append("Notifica preliminare non obbligatoria.")
        return righe


def obblighi(imprese: list[dict[str, Any]], fasi: list[dict[str, Any]]) -> Obblighi:
    n = imprese_esecutrici(imprese, fasi)
    ug = uomini_giorno(fasi)
    piu_imprese = n > 1
    return Obblighi(
        imprese=n,
        uomini_giorno=ug,
        psc=piu_imprese,
        notifica=piu_imprese or ug >= SOGLIA_UOMINI_GIORNO,
    )


SOGLIA_ART_90_C11 = 100_000.0


def deroga_art_90_c11(cantiere: dict[str, Any]) -> bool:
    """Lavori privati non soggetti a permesso di costruire e di importo inferiore a 100.000 euro.

    In questo caso non serve il coordinatore per la progettazione: il PSC e il fascicolo li redige il
    coordinatore per l'esecuzione (art. 90, comma 11, del D.Lgs. 81/2008). Senza importo non si decide.
    """
    if cantiere.get("lavori_pubblici") or not cantiere.get("importo_lavori"):
        return False
    titolo = (cantiere.get("titolo_abilitativo") or "").lower()
    permesso = "permesso" in titolo or "pdc" in titolo.replace(".", "").replace(",", " ").split()
    return not permesso and cantiere["importo_lavori"] < SOGLIA_ART_90_C11
