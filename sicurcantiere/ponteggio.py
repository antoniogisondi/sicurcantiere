"""Geometria del ponteggio, quantità degli elementi, ancoraggi, verifica del piano di appoggio e formazione
della squadra di montaggio.

La geometria (salvata in JSON nella colonna ponteggi.geometria) descrive il ponteggio come una sequenza di
lati lungo il perimetro dell'edificio: ogni lato ha la sua lunghezza e, se diversa, la sua altezza; tra un
lato e il successivo il perimetro gira di 90°. Campata, larghezza degli impalcati, interpiano e distanza
dalla facciata sono comuni a tutto il ponteggio.

Le quantità, gli ancoraggi e il carico sugli appoggi sono stime per preparare il PiMUS e controllare che i
dati siano coerenti: non sostituiscono il libretto del fabbricante, gli schemi tipo autorizzati né il
progetto, quando è richiesto (art. 133).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

# Classi di carico degli impalcati (UNI EN 12811-1, carico uniformemente distribuito in kN/m²).
CLASSI_CARICO: list[tuple[str, float]] = [
    ("Classe 1 – 0,75 kN/m² (ispezione)", 0.75),
    ("Classe 2 – 1,50 kN/m² (manutenzione, pitture)", 1.50),
    ("Classe 3 – 2,00 kN/m² (intonaci, lavori leggeri)", 2.00),
    ("Classe 4 – 3,00 kN/m² (muratura, costruzione)", 3.00),
    ("Classe 5 – 4,50 kN/m² (muratura pesante, rivestimenti)", 4.50),
    ("Classe 6 – 6,00 kN/m² (depositi di materiale)", 6.00),
]

# Portanza indicativa del piano di appoggio (kPa = kN/m²): valori prudenziali per un primo controllo. Con
# terreni incerti o carichi elevati si usa il valore di un'indagine o della relazione geotecnica.
TERRENI: list[tuple[str, float]] = [
    ("Terreno di riporto o vegetale non compattato", 50),
    ("Terreno naturale compatto", 100),
    ("Ghiaia o misto stabilizzato compattato", 200),
    ("Asfalto o battuto su sottofondo compatto", 300),
    ("Platea o marciapiede in calcestruzzo", 500),
]

# Larghezze tipiche degli impalcati e campate dei sistemi più diffusi (m): proposte, non vincoli.
CAMPATE = [1.80, 2.50, 2.57, 3.07]
LARGHEZZE = [0.75, 1.05]

AREA_PER_ANCORAGGIO = 22.0  # m² di facciata per ancoraggio: valore di riferimento usuale, vale il libretto
DISTANZA_MASSIMA = 0.20  # m dalla facciata oltre i quali serve il parapetto anche sul lato interno
ALTEZZA_PARAPETTO = 1.0  # m sopra l'ultimo impalcato
ANNI_AGGIORNAMENTO = 4  # formazione degli addetti ai ponteggi: aggiornamento ogni 4 anni (almeno 4 ore)

PREDEFINITA: dict[str, Any] = {
    "forma": "aperta",           # aperta: lati in sequenza; chiusa: il perimetro si richiude
    "lati": [],                   # [{"nome", "lunghezza", "altezza" (0 = quella del ponteggio)}]
    "campata": 1.80,
    "larghezza": 1.05,
    "interpiano": 2.00,
    "distanza": 0.20,
    "ancoraggi_campate": 2,       # un ancoraggio ogni N campate...
    "ancoraggi_livelli": 2,       # ...e ogni N livelli
    "ancoraggi_rombo": True,      # file sfalsate (a rombo) o allineate
    "mantovana": True,
    "mantovana_livello": 2,       # livello dell'impalcato con la mantovana parasassi
    "teli": False,                # teli o reti sulla facciata: aumentano l'azione del vento
    "peso_proprio": 0.30,         # kN per m² di facciata (dal libretto)
    "terreno": 100.0,             # portanza del piano di appoggio, kPa
    "area_appoggio": 0.15,        # m² di ripartizione sotto ogni basetta
}


@dataclass
class Lato:
    nome: str
    lunghezza: float
    altezza: float
    campate: int
    livelli: int
    mantovana: bool = True
    aggiunti: tuple[tuple[int, int], ...] = ()  # ancoraggi aggiunti a mano (stilata, livello)
    tolti: tuple[tuple[int, int], ...] = ()     # ancoraggi dello schema tolti a mano


def geometria(ponteggio: dict[str, Any]) -> dict[str, Any]:
    """Geometria del ponteggio con i valori predefiniti per le voci mancanti; senza lati se ne crea uno
    con lo sviluppo e il nome del ponteggio."""
    try:
        salvata = json.loads(ponteggio.get("geometria") or "{}")
    except (TypeError, ValueError):
        salvata = {}
    g = {**PREDEFINITA, **(salvata if isinstance(salvata, dict) else {})}
    lati = [l for l in g.get("lati") or [] if isinstance(l, dict)]
    if not lati:
        lati = [{"nome": ponteggio.get("nome") or "Facciata", "lunghezza": float(ponteggio.get("lunghezza") or 0) or 10.0,
                 "altezza": 0}]
    g["lati"] = [{"nome": str(l.get("nome") or f"Lato {n}"), "lunghezza": _numero(l.get("lunghezza"), 0),
                  "altezza": _numero(l.get("altezza"), 0), "mantovana": bool(l.get("mantovana", True)),
                  "aggiunti": _coppie(l.get("aggiunti")), "tolti": _coppie(l.get("tolti"))}
                 for n, l in enumerate(lati, 1)]
    for chiave in ("campata", "larghezza", "interpiano", "distanza", "peso_proprio", "terreno", "area_appoggio"):
        g[chiave] = _numero(g[chiave], PREDEFINITA[chiave])
    g["campata"] = max(g["campata"], 0.5)
    g["larghezza"] = max(g["larghezza"], 0.3)
    g["interpiano"] = max(g["interpiano"], 1.0)
    g["area_appoggio"] = max(g["area_appoggio"], 0.01)
    for chiave in ("ancoraggi_campate", "ancoraggi_livelli", "mantovana_livello"):
        g[chiave] = max(1, int(_numero(g[chiave], PREDEFINITA[chiave])))
    for chiave in ("ancoraggi_rombo", "mantovana", "teli"):
        g[chiave] = bool(g[chiave])
    g["forma"] = "chiusa" if g.get("forma") == "chiusa" else "aperta"
    return g


def testo_geometria(g: dict[str, Any]) -> str:
    return json.dumps(g, ensure_ascii=False, sort_keys=True)


def _coppie(valore: Any) -> list[list[int]]:
    coppie = []
    for v in valore or []:
        try:
            a, b = int(v[0]), int(v[1])
        except (TypeError, ValueError, IndexError):
            continue
        if a >= 0 and b >= 1 and [a, b] not in coppie:
            coppie.append([a, b])
    return sorted(coppie)


def _numero(valore: Any, predefinito: float) -> float:
    try:
        n = float(valore)
    except (TypeError, ValueError):
        return predefinito
    return n if math.isfinite(n) and n >= 0 else predefinito


def livelli(altezza: float, interpiano: float) -> int:
    """Numero di impalcati: uno ogni interpiano fino all'altezza indicata (almeno uno)."""
    return max(1, int(altezza / interpiano + 1e-6)) if altezza > 0 else 1


def lati(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> list[Lato]:
    g = g or geometria(ponteggio)
    altezza = float(ponteggio.get("altezza") or 0)
    risultato = []
    for l in g["lati"]:
        h = l["altezza"] or altezza or g["interpiano"]
        risultato.append(Lato(l["nome"], l["lunghezza"], h, max(1, math.ceil(l["lunghezza"] / g["campata"] - 1e-6)),
                              livelli(h, g["interpiano"]), g["mantovana"] and l.get("mantovana", True),
                              tuple(tuple(c) for c in l.get("aggiunti", [])),
                              tuple(tuple(c) for c in l.get("tolti", []))))
    return risultato


def inizio(lato: Lato, g: dict[str, Any]) -> float:
    """Posizione della prima stilata rispetto all'inizio della facciata: le campate sono centrate sulla
    facciata, così l'eccedenza si divide tra le due estremità (negativa = il ponteggio sporge)."""
    return (lato.lunghezza - lato.campate * g["campata"]) / 2


def sviluppo(g: dict[str, Any]) -> float:
    return round(sum(l["lunghezza"] for l in g["lati"]), 2)


def altezza_massima(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> float:
    return max((l.altezza for l in lati(ponteggio, g)), default=0.0)


# --- ancoraggi ---

def posizioni_ancoraggi(lato: Lato, g: dict[str, Any]) -> list[tuple[int, int]]:
    """Ancoraggi di un lato come (stilata, livello): quelli dello schema, più quelli aggiunti a mano e meno
    quelli tolti a mano sul prospetto."""
    posizioni = set(schema_ancoraggi(lato, g)) | set(lato.aggiunti)
    posizioni -= set(lato.tolti)
    return sorted((s, l) for s, l in posizioni if 0 <= s <= lato.campate and 1 <= l <= lato.livelli)


def schema_ancoraggi(lato: Lato, g: dict[str, Any]) -> list[tuple[int, int]]:
    """Ancoraggi dello schema: ogni N campate e ogni N livelli, sfalsati a rombo se richiesto, più le
    stilate di estremità a ogni livello ancorato (le testate sono le più sollecitate)."""
    passo_c, passo_l = g["ancoraggi_campate"], g["ancoraggi_livelli"]
    posizioni = set()
    livelli_ancorati = list(range(passo_l, lato.livelli + 1, passo_l))
    if lato.livelli and (not livelli_ancorati or livelli_ancorati[-1] != lato.livelli):
        livelli_ancorati.append(lato.livelli)  # l'ultimo impalcato è sempre ancorato
    for n, livello in enumerate(livelli_ancorati):
        sfasamento = passo_c // 2 if g["ancoraggi_rombo"] and n % 2 else 0
        for stilata in range(sfasamento, lato.campate + 1, passo_c):
            posizioni.add((stilata, livello))
        posizioni.add((0, livello))
        posizioni.add((lato.campate, livello))
    return sorted(posizioni)


@dataclass
class Ancoraggi:
    numero: int
    area_facciata: float
    area_per_ancoraggio: float
    maglia: str


def ancoraggi(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> Ancoraggi:
    g = g or geometria(ponteggio)
    elenco = lati(ponteggio, g)
    numero = sum(len(posizioni_ancoraggi(l, g)) for l in elenco)
    area = sum(l.campate * g["campata"] * l.livelli * g["interpiano"] for l in elenco)
    maglia = (f"una ogni {g['ancoraggi_campate']} campate ({_m(g['ancoraggi_campate'] * g['campata'])}) e ogni "
              f"{g['ancoraggi_livelli']} livelli ({_m(g['ancoraggi_livelli'] * g['interpiano'])})"
              + (", a rombo" if g["ancoraggi_rombo"] else ", allineati") + ", più le testate")
    return Ancoraggi(numero, round(area, 1), round(area / numero, 1) if numero else 0.0, maglia)


# --- carichi sul piano di appoggio ---

def sovraccarico(classe: str) -> float:
    """Carico degli impalcati in kN/m² dalla classe scelta (0 se non riconosciuta)."""
    testo = (classe or "").strip().lower()
    for nome, valore in CLASSI_CARICO:
        if testo == nome.lower() or testo.startswith(nome.split(" –")[0].lower()):
            return valore
    return 0.0


@dataclass
class Appoggio:
    carico_montante: float   # kN sul montante più caricato
    pressione: float         # kPa sotto la ripartizione
    portanza: float          # kPa del piano di appoggio
    area_minima: float       # m² di ripartizione che servirebbero
    sovraccarico: float      # kN/m² usato nel calcolo

    @property
    def verificato(self) -> bool:
        return self.pressione <= self.portanza


def appoggio(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> Appoggio:
    """Stima del carico sul montante più caricato e della pressione sul terreno.

    Peso proprio: il valore per m² di facciata moltiplicato per la campata e l'altezza, diviso tra i due
    montanti della stilata. Sovraccarico: un impalcato pieno e quello adiacente al 50% (UNI EN 12811-1),
    sulla metà della larghezza che compete a ogni montante.
    """
    g = g or geometria(ponteggio)
    q = sovraccarico(ponteggio.get("classe_carico", "")) or CLASSI_CARICO[2][1]
    h = altezza_massima(ponteggio, g) + ALTEZZA_PARAPETTO
    peso = g["peso_proprio"] * g["campata"] * h / 2
    livelli_caricati = min(1.5, livelli(h - ALTEZZA_PARAPETTO, g["interpiano"]))
    servizio = q * g["campata"] * g["larghezza"] / 2 * livelli_caricati
    carico = peso + servizio
    portanza = g["terreno"] or TERRENI[1][1]
    return Appoggio(round(carico, 2), round(carico / g["area_appoggio"], 1), portanza,
                    round(carico / portanza, 3), q)


# --- elementi ---

def elementi(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> list[tuple[str, int | float, str]]:
    """Elenco indicativo degli elementi per tipologia: (elemento, quantità, unità)."""
    g = g or geometria(ponteggio)
    tipo = ponteggio.get("tipo") or "Telai prefabbricati"
    elenco = lati(ponteggio, g)
    stilate = sum(l.campate + 1 for l in elenco)
    nodi = sum((l.campate + 1) * l.livelli for l in elenco)
    campate_livelli = sum(l.campate * l.livelli for l in elenco)
    testate = 2 * len(elenco) if g["forma"] == "aperta" else 0
    testate_livelli = sum(2 * l.livelli for l in elenco) if g["forma"] == "aperta" else 0
    diagonali = sum(max(1, math.ceil(l.campate / 5)) * l.livelli for l in elenco)
    tavole = max(1, math.ceil(g["larghezza"] / 0.5 - 1e-6))
    metri_altezza = sum((l.campate + 1) * (l.livelli * g["interpiano"] + ALTEZZA_PARAPETTO) for l in elenco)
    voci: list[tuple[str, int | float, str]]
    if tipo == "Tubi e giunti":
        voci = [
            ("Tubi per montanti", round(metri_altezza * 2, 1), "m"),
            ("Tubi per traversi", nodi, "n."),
            ("Tubi per correnti e parapetti", round(sum(l.lunghezza * l.livelli for l in elenco) * 4, 1), "m"),
            ("Giunti ortogonali", nodi * 6, "n."),
            ("Giunti girevoli (diagonali)", diagonali * 2, "n."),
            ("Tubi per diagonali di facciata", diagonali, "n."),
        ]
    elif tipo == "Multidirezionale":
        voci = [
            ("Montanti", math.ceil(metri_altezza * 2 / 2), "n. (da 2 m)"),
            ("Traversi", nodi, "n."),
            ("Correnti e parapetti", campate_livelli * 3, "n."),
            ("Diagonali di facciata", diagonali, "n."),
        ]
    else:  # telai prefabbricati, montanti e traversi prefabbricati
        voci = [
            ("Telai (stilate × livelli)", nodi, "n."),
            ("Correnti e parapetti", campate_livelli * 2, "n."),
            ("Diagonali di facciata", diagonali, "n."),
        ]
    voci += [
        ("Basette regolabili", stilate * 2, "n."),
        ("Impalcati", campate_livelli * tavole, "n."),
        ("Tavole fermapiede", campate_livelli + testate_livelli, "n."),
    ]
    if testate:
        voci.append(("Parapetti di testata", testate_livelli, "n."))
    voci.append(("Ancoraggi", ancoraggi(ponteggio, g).numero, "n."))
    con_mantovana = sum(l.campate for l in elenco if l.mantovana and g["mantovana_livello"] <= l.livelli)
    if con_mantovana:
        voci.append(("Mantovana parasassi", con_mantovana, "campate"))
    voci.append(("Scale interne con botola", max(l.livelli for l in elenco), "n."))
    return voci


def cambia_ancoraggio(g: dict[str, Any], ponteggio: dict[str, Any], indice: int, stilata: int,
                      livello: int) -> dict[str, Any]:
    """Aggiunge o toglie a mano l'ancoraggio in (stilata, livello) del lato `indice`; restituisce la geometria
    aggiornata."""
    lato = lati(ponteggio, g)[indice]
    dati = g["lati"][indice]
    coppia = [stilata, livello]
    presente = (stilata, livello) in posizioni_ancoraggi(lato, g)
    nello_schema = (stilata, livello) in schema_ancoraggi(lato, g)
    dati["aggiunti"] = [c for c in dati["aggiunti"] if c != coppia]
    dati["tolti"] = [c for c in dati["tolti"] if c != coppia]
    if presente and nello_schema:
        dati["tolti"].append(coppia)
    elif not presente and not nello_schema:
        dati["aggiunti"].append(coppia)
    return g


# --- avvisi sulla geometria ---

def avvisi_geometria(ponteggio: dict[str, Any]) -> list[str]:
    g = geometria(ponteggio)
    messaggi = []
    if not any(l["lunghezza"] for l in g["lati"]):
        messaggi.append("Indicare la lunghezza dei lati del ponteggio nella scheda «Disegno».")
    if g["distanza"] > DISTANZA_MASSIMA:
        messaggi.append(f"Distanza dalla facciata di {_m(g['distanza'])}: oltre {_m(DISTANZA_MASSIMA)} serve il "
                        "parapetto anche sul lato interno.")
    a = ancoraggi(ponteggio, g)
    if a.area_per_ancoraggio > AREA_PER_ANCORAGGIO:
        messaggi.append(f"Ancoraggi: {_n(a.area_per_ancoraggio, 1)} m² di facciata per ancoraggio, più del "
                        f"riferimento usuale di {AREA_PER_ANCORAGGIO:g} m². Verificare con lo schema del libretto.")
    if g["teli"]:
        messaggi.append("Con teli o reti sulla facciata l'azione del vento aumenta: ancoraggi secondo lo schema del "
                        "libretto per ponteggi con teli o secondo il progetto.")
    s = appoggio(ponteggio, g)
    if not s.verificato:
        messaggi.append(f"Piano di appoggio: pressione stimata di {_n(s.pressione)} kPa sotto ogni basetta, oltre la "
                        f"portanza di {_n(s.portanza)} kPa. Aumentare la ripartizione ad almeno "
                        f"{_n(s.area_minima, 2)} m² per basetta.")
    return messaggi


# --- formazione della squadra ---

PREPOSTO, ADDETTO = "Preposto", "Addetto al montaggio"
RUOLI = [PREPOSTO, ADDETTO]


def _data(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore)) if valore else None
    except ValueError:
        return None


def scadenza_formazione(addetto: dict[str, Any]) -> date | None:
    """Fine della validità: 4 anni dal corso o dall'ultimo aggiornamento."""
    ultima = max((d for d in (_data(addetto.get("corso_data")), _data(addetto.get("aggiornamento_data"))) if d),
                 default=None)
    if ultima is None:
        return None
    try:
        return ultima.replace(year=ultima.year + ANNI_AGGIORNAMENTO)
    except ValueError:  # 29 febbraio
        return ultima.replace(year=ultima.year + ANNI_AGGIORNAMENTO, day=28)


def stato_formazione(addetto: dict[str, Any], oggi: date | None = None) -> str:
    oggi = oggi or date.today()
    scadenza = scadenza_formazione(addetto)
    if scadenza is None:
        return "Corso da indicare"
    if scadenza < oggi:
        return "Aggiornamento scaduto"
    if (scadenza - oggi).days <= 60:
        return "In scadenza"
    return "Valida"


def avvisi_squadra(addetti: list[dict[str, Any]], oggi: date | None = None) -> list[str]:
    messaggi = []
    nominati = [a for a in addetti if a["nome"].strip()]
    if not any(a["ruolo"] == PREPOSTO for a in nominati):
        messaggi.append("Indicare il preposto alle operazioni di montaggio e smontaggio (art. 136, comma 6).")
    if not any(a["ruolo"] != PREPOSTO for a in nominati):
        messaggi.append("Indicare gli addetti al montaggio nella scheda «Squadra».")
    for a in nominati:
        stato = stato_formazione(a, oggi)
        if stato == "Corso da indicare":
            messaggi.append(f"{a['nome']}: indicare la data del corso per addetti ai ponteggi (Allegato XXI).")
        elif stato == "Aggiornamento scaduto":
            messaggi.append(f"{a['nome']}: aggiornamento della formazione scaduto il "
                            f"{scadenza_formazione(a).strftime('%d/%m/%Y')} (ogni {ANNI_AGGIORNAMENTO} anni).")
    return messaggi


def _m(valore: float) -> str:
    return f"{valore:.2f} m".replace(".", ",")


def _n(valore: float, cifre: int = 0) -> str:
    return f"{valore:,.{cifre}f}".replace(",", "X").replace(".", ",").replace("X", ".")
