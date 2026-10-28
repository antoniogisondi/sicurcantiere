"""Geometria del ponteggio, elementi, quantità, ancoraggi, verifica del piano di appoggio e formazione della
squadra di montaggio.

La geometria (salvata in JSON nella colonna ponteggi.geometria) descrive il ponteggio come un insieme di
**tratti**, tutti dello stesso ponteggio. Ogni tratto segue una linea di facciata ed è indipendente dagli
altri: ha la sua tipologia (un raccordo in tubi e giunti dentro un ponteggio a telai), la sua posizione e il
suo angolo in pianta (anche un tratto ruotato o staccato), lunghezza, altezza, quota di partenza, campata,
larghezza e distanza dalla facciata. Un tratto «collegato» parte dalla fine del precedente e gira
dell'angolo indicato (90° agli spigoli). Sopra i tratti si inseriscono gli elementi del catalogo
(elementi_ponteggio): mensole, travi carraie, teli, scale, piazzole di carico...

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

from sicurcantiere import elementi_ponteggio as E

TIPI_PONTEGGIO = [
    "Telai prefabbricati",
    "Tubi e giunti",
    "Montanti e traversi prefabbricati",
    "Multidirezionale",
]

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
DISTANZA_MASSIMA = 0.20  # m dalla facciata oltre i quali serve il parapetto anche sul lato interno (art. 138)
ALTEZZA_PARAPETTO = 1.0  # m: i montanti superano l'ultimo impalcato di almeno 1 m (art. 138)
ANNI_AGGIORNAMENTO = 4  # formazione degli addetti ai ponteggi: aggiornamento ogni 4 anni (almeno 4 ore)

PREDEFINITA: dict[str, Any] = {
    "versione": 2,
    "tratti": [],
    "elementi": [],
    "campata": 1.80,
    "larghezza": 1.05,
    "interpiano": 2.00,
    "distanza": 0.20,
    "ancoraggi_campate": 2,       # un ancoraggio ogni N campate...
    "ancoraggi_livelli": 2,       # ...e ogni N livelli
    "ancoraggi_rombo": True,      # file sfalsate (a rombo) o allineate
    "tipo_ancoraggio": E.TIPI_ANCORAGGIO[0],
    "mantovana": True,
    "mantovana_livello": 2,       # livello dell'impalcato con la mantovana parasassi
    "teli": False,                # teli o reti su tutta la facciata
    "peso_proprio": 0.30,         # kN per m² di facciata (dal libretto)
    "terreno": 100.0,             # portanza del piano di appoggio, kPa
    "area_appoggio": 0.15,        # m² di ripartizione sotto ogni basetta
}

# voci di un tratto: None = valore comune del ponteggio
TRATTO: dict[str, Any] = {
    "nome": "", "tipo": "", "lunghezza": 10.0, "altezza": 0.0, "quota": 0.0,
    "collegato": True, "svolta": 90.0, "x": 0.0, "y": 0.0, "angolo": 0.0, "spostamento": 0.0,
    "campata": None, "larghezza": None, "distanza": None, "verso": "esterno",
    "mantovana": True, "aggiunti": [], "tolti": [],
}


@dataclass
class Tratto:
    """Un tratto calcolato: posizione in pianta, campate e livelli."""
    nome: str
    lunghezza: float
    altezza: float
    campate: int
    livelli: int
    mantovana: bool = True
    aggiunti: tuple[tuple[int, int], ...] = ()  # ancoraggi aggiunti a mano (stilata, livello)
    tolti: tuple[tuple[int, int], ...] = ()     # ancoraggi dello schema tolti a mano
    tipo: str = ""
    campata: float = 1.8
    larghezza: float = 1.05
    distanza: float = 0.2
    interpiano: float = 2.0
    quota: float = 0.0
    origine: tuple[float, float] = (0.0, 0.0)
    direzione: tuple[float, float] = (1.0, 0.0)
    angolo: float = 0.0
    verso: int = 1                  # 1: ponteggio a destra della linea di facciata; -1 a sinistra
    spostamento: float = 0.0
    indice: int = 0

    @property
    def lunghezza_ponteggio(self) -> float:
        return self.campate * self.campata

    @property
    def inizio(self) -> float:
        """Prima stilata rispetto all'inizio della facciata: campate centrate, più lo spostamento scelto."""
        return (self.lunghezza - self.lunghezza_ponteggio) / 2 + self.spostamento

    @property
    def normale(self) -> tuple[float, float]:
        dx, dy = self.direzione
        return (dy * self.verso, -dx * self.verso)

    def punto(self, s: float, scostamento: float, z: float = 0.0) -> tuple[float, float, float]:
        """Punto nello spazio: s lungo la facciata, scostamento verso il ponteggio, z dalla quota del tratto."""
        (ox, oy), (dx, dy), (nx, ny) = self.origine, self.direzione, self.normale
        return (ox + dx * s + nx * scostamento, oy + dy * s + ny * scostamento, self.quota + z)

    def fine(self) -> tuple[float, float]:
        (ox, oy), (dx, dy) = self.origine, self.direzione
        return ox + dx * self.lunghezza, oy + dy * self.lunghezza


Lato = Tratto  # nome usato nelle versioni precedenti


# --- lettura e normalizzazione della geometria ---

def geometria(ponteggio: dict[str, Any]) -> dict[str, Any]:
    """Geometria del ponteggio con i valori predefiniti per le voci mancanti. I file della versione con i
    «lati» a 90° diventano tratti collegati; senza tratti se ne crea uno con lo sviluppo e il nome del
    ponteggio."""
    try:
        salvata = json.loads(ponteggio.get("geometria") or "{}")
    except (TypeError, ValueError):
        salvata = {}
    salvata = salvata if isinstance(salvata, dict) else {}
    g = {**PREDEFINITA, **salvata}
    tratti = [t for t in g.get("tratti") or [] if isinstance(t, dict)]
    if not tratti and salvata.get("lati"):
        tratti = [{**l, "collegato": n > 0, "svolta": 90.0} for n, l in enumerate(salvata["lati"])
                  if isinstance(l, dict)]
    if not tratti:
        tratti = [{"nome": ponteggio.get("nome") or "Facciata",
                   "lunghezza": float(ponteggio.get("lunghezza") or 0) or 10.0}]
    g["tratti"] = [_tratto(t, n) for n, t in enumerate(tratti, 1)]
    g.pop("lati", None)
    g.pop("forma", None)
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
    g["tipo_ancoraggio"] = str(g.get("tipo_ancoraggio") or PREDEFINITA["tipo_ancoraggio"])
    g["elementi"] = [e for e in (E.normalizza(x) for x in g.get("elementi") or [] if isinstance(x, dict))
                     if e is not None and e["tratto"] < len(g["tratti"])]
    g["versione"] = 2
    return g


def _tratto(t: dict[str, Any], n: int) -> dict[str, Any]:
    r = {**TRATTO, **t}
    risultato = {
        "nome": str(r["nome"] or f"Tratto {n}"),
        "tipo": str(r["tipo"] or ""),
        "lunghezza": _numero(r["lunghezza"], 0),
        "altezza": _numero(r["altezza"], 0),
        "quota": _numero(r["quota"], 0, negativo=True),
        "collegato": bool(r["collegato"]) and n > 1,
        "svolta": _numero(r["svolta"], 90, negativo=True),
        "x": _numero(r["x"], 0, negativo=True),
        "y": _numero(r["y"], 0, negativo=True),
        "angolo": _numero(r["angolo"], 0, negativo=True),
        "spostamento": _numero(r["spostamento"], 0, negativo=True),
        "verso": "interno" if r["verso"] == "interno" else "esterno",
        "mantovana": bool(r["mantovana"]),
        "aggiunti": _coppie(r["aggiunti"]),
        "tolti": _coppie(r["tolti"]),
    }
    for chiave, minimo in (("campata", 0.5), ("larghezza", 0.3), ("distanza", 0.0)):
        valore = r.get(chiave)
        risultato[chiave] = None if valore in (None, "") else max(minimo, _numero(valore, minimo))
    return risultato


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


def _numero(valore: Any, predefinito: float, negativo: bool = False) -> float:
    try:
        n = float(valore)
    except (TypeError, ValueError):
        return predefinito
    return n if math.isfinite(n) and (negativo or n >= 0) else predefinito


def livelli(altezza: float, interpiano: float) -> int:
    """Numero di impalcati: uno ogni interpiano fino all'altezza indicata (almeno uno)."""
    return max(1, int(altezza / interpiano + 1e-6)) if altezza > 0 else 1


def tratti(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> list[Tratto]:
    """Tratti calcolati, con la posizione in pianta: i collegati partono dalla fine del precedente."""
    g = g or geometria(ponteggio)
    altezza = float(ponteggio.get("altezza") or 0)
    tipo_ponteggio = ponteggio.get("tipo") or TIPI_PONTEGGIO[0]
    risultato: list[Tratto] = []
    for n, t in enumerate(g["tratti"]):
        campata = t["campata"] or g["campata"]
        h = t["altezza"] or altezza or g["interpiano"]
        if t["collegato"] and risultato:
            precedente = risultato[-1]
            origine = precedente.fine()
            angolo = precedente.angolo + t["svolta"]
        else:
            origine, angolo = (t["x"], t["y"]), t["angolo"]
        a = math.radians(angolo)
        risultato.append(Tratto(
            t["nome"], t["lunghezza"], h, max(1, math.ceil(t["lunghezza"] / campata - 1e-6)),
            livelli(h, g["interpiano"]), g["mantovana"] and t["mantovana"],
            tuple(tuple(c) for c in t["aggiunti"]), tuple(tuple(c) for c in t["tolti"]),
            t["tipo"] or tipo_ponteggio, campata, t["larghezza"] or g["larghezza"],
            g["distanza"] if t["distanza"] is None else t["distanza"], g["interpiano"], t["quota"], origine,
            (round(math.cos(a), 12), round(math.sin(a), 12)), angolo % 360, -1 if t["verso"] == "interno" else 1,
            t["spostamento"], n))
    return risultato


lati = tratti  # nome usato nelle versioni precedenti


def inizio(tratto: Tratto, g: dict[str, Any] | None = None) -> float:
    return tratto.inizio


def chiuso(elenco: list[Tratto]) -> bool:
    """Il perimetro si richiude: la fine dell'ultimo tratto torna all'inizio del primo."""
    if len(elenco) < 3:
        return False
    (x0, y0), (x1, y1) = elenco[0].origine, elenco[-1].fine()
    return math.hypot(x1 - x0, y1 - y0) < 0.05


def sviluppo(g: dict[str, Any]) -> float:
    return round(sum(t["lunghezza"] for t in g["tratti"]), 2)


def altezza_massima(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> float:
    return max((t.altezza for t in tratti(ponteggio, g)), default=0.0)


def tipologie(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> list[str]:
    """Tipologie presenti nel ponteggio, nell'ordine dei tratti."""
    visti: list[str] = []
    for t in tratti(ponteggio, g):
        if t.tipo not in visti:
            visti.append(t.tipo)
    return visti


# --- ancoraggi ---

def posizioni_ancoraggi(tratto: Tratto, g: dict[str, Any]) -> list[tuple[int, int]]:
    """Ancoraggi di un tratto come (stilata, livello): quelli dello schema, più quelli aggiunti a mano e meno
    quelli tolti a mano sul prospetto."""
    posizioni = set(schema_ancoraggi(tratto, g)) | set(tratto.aggiunti)
    posizioni -= set(tratto.tolti)
    return sorted((s, l) for s, l in posizioni if 0 <= s <= tratto.campate and 1 <= l <= tratto.livelli)


def schema_ancoraggi(tratto: Tratto, g: dict[str, Any]) -> list[tuple[int, int]]:
    """Ancoraggi dello schema: ogni N campate e ogni N livelli, sfalsati a rombo se richiesto, più le
    stilate di estremità a ogni livello ancorato (le testate sono le più sollecitate)."""
    passo_c, passo_l = g["ancoraggi_campate"], g["ancoraggi_livelli"]
    posizioni = set()
    livelli_ancorati = list(range(passo_l, tratto.livelli + 1, passo_l))
    if tratto.livelli and (not livelli_ancorati or livelli_ancorati[-1] != tratto.livelli):
        livelli_ancorati.append(tratto.livelli)  # l'ultimo impalcato è sempre ancorato
    for n, livello in enumerate(livelli_ancorati):
        sfasamento = passo_c // 2 if g["ancoraggi_rombo"] and n % 2 else 0
        for stilata in range(sfasamento, tratto.campate + 1, passo_c):
            posizioni.add((stilata, livello))
        posizioni.add((0, livello))
        posizioni.add((tratto.campate, livello))
    return sorted(posizioni)


@dataclass
class Ancoraggi:
    numero: int
    area_facciata: float
    area_per_ancoraggio: float
    maglia: str


def ancoraggi(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> Ancoraggi:
    g = g or geometria(ponteggio)
    elenco = tratti(ponteggio, g)
    numero = sum(len(posizioni_ancoraggi(t, g)) for t in elenco)
    numero += sum(int(E.quantita(e)) for e in g["elementi"] if e["tipo"] in ("ancoraggio_tubo", "ancoraggio_doppio"))
    area = sum(t.lunghezza_ponteggio * t.livelli * t.interpiano for t in elenco)
    campata = elenco[0].campata if elenco else g["campata"]
    maglia = (f"una ogni {g['ancoraggi_campate']} campate ({_m(g['ancoraggi_campate'] * campata)}) e ogni "
              f"{g['ancoraggi_livelli']} livelli ({_m(g['ancoraggi_livelli'] * g['interpiano'])})"
              + (", a rombo" if g["ancoraggi_rombo"] else ", allineati") + ", più le testate")
    return Ancoraggi(numero, round(area, 1), round(area / numero, 1) if numero else 0.0, maglia)


def cambia_ancoraggio(g: dict[str, Any], ponteggio: dict[str, Any], indice: int, stilata: int,
                      livello: int) -> dict[str, Any]:
    """Aggiunge o toglie a mano l'ancoraggio in (stilata, livello) del tratto `indice`; restituisce la
    geometria aggiornata."""
    tratto = tratti(ponteggio, g)[indice]
    dati = g["tratti"][indice]
    coppia = [stilata, livello]
    presente = (stilata, livello) in posizioni_ancoraggi(tratto, g)
    nello_schema = (stilata, livello) in schema_ancoraggi(tratto, g)
    dati["aggiunti"] = [c for c in dati["aggiunti"] if c != coppia]
    dati["tolti"] = [c for c in dati["tolti"] if c != coppia]
    if presente and nello_schema:
        dati["tolti"].append(coppia)
    elif not presente and not nello_schema:
        dati["aggiunti"].append(coppia)
    return g


# --- elementi inseriti a mano ---

def elementi_tratto(g: dict[str, Any], indice: int) -> list[dict[str, Any]]:
    return [e for e in g["elementi"] if e["tratto"] == indice]


def cambia_elemento(g: dict[str, Any], tipo: str, indice: int, campata: int, livello: int) -> dict[str, Any]:
    """Inserisce l'elemento `tipo` nella campata e al livello indicati, o lo toglie se c'è già (clic sul
    prospetto). Un elemento che occupa più campate o livelli viene tolto per intero."""
    v = E.voce(tipo)
    if v is None:
        return g
    livello = 0 if v.a_terra else max(1, livello)
    for e in g["elementi"]:
        if (e["tipo"] == tipo and e["tratto"] == indice and e["da"] <= campata <= e["a"]
                and e["livello"] <= livello <= e["livello_a"]):
            g["elementi"].remove(e)
            return g
    g["elementi"].append(E.normalizza({"tipo": tipo, "tratto": indice, "da": campata, "a": campata,
                                       "livello": livello, "livello_a": livello}))
    return g


def ha_elemento(g: dict[str, Any], tipo: str) -> bool:
    return any(e["tipo"] == tipo for e in g["elementi"])


# --- unione e copia di tratti ---

def unisci(g: dict[str, Any], altro: dict[str, Any], tratti_g: list[Tratto]) -> dict[str, Any]:
    """Aggiunge a `g` i tratti e gli elementi della geometria `altro` (un altro ponteggio dello stesso
    cantiere): il primo tratto dell'altro diventa un tratto staccato, posato dopo l'ultimo tratto di `g`."""
    base = len(g["tratti"])
    ultimo = tratti_g[-1] if tratti_g else None
    x, y = ultimo.fine() if ultimo else (0.0, 0.0)
    primo = altro["tratti"][0] if altro["tratti"] else {"x": 0.0, "y": 0.0}
    dx, dy = x + 2.0 - primo["x"], y - primo["y"]  # l'altro ponteggio si posa 2 m dopo la fine di questo
    for n, t in enumerate(altro["tratti"]):
        copia = dict(t)
        if n == 0 or not copia["collegato"]:
            copia["collegato"] = False
            copia["x"], copia["y"] = copia["x"] + dx, copia["y"] + dy
        g["tratti"].append(copia)
    for e in altro["elementi"]:
        g["elementi"].append({**e, "tratto": e["tratto"] + base})
    return g


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
    tratto: str = ""         # tratto più sollecitato

    @property
    def verificato(self) -> bool:
        return self.pressione <= self.portanza


def appoggio(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> Appoggio:
    """Stima del carico sul montante più caricato e della pressione sul terreno, sul tratto più sollecitato.

    Peso proprio: il valore per m² di facciata moltiplicato per la campata e l'altezza, diviso tra i due
    montanti della stilata. Sovraccarico: un impalcato pieno e quello adiacente al 50% (UNI EN 12811-1),
    sulla metà della larghezza che compete a ogni montante.
    """
    g = g or geometria(ponteggio)
    q = sovraccarico(ponteggio.get("classe_carico", "")) or CLASSI_CARICO[2][1]
    peggiore = None
    for t in tratti(ponteggio, g):
        h = t.livelli * t.interpiano + ALTEZZA_PARAPETTO
        peso = g["peso_proprio"] * t.campata * h / 2
        servizio = q * t.campata * t.larghezza / 2 * min(1.5, t.livelli)
        carico = peso + servizio
        if peggiore is None or carico > peggiore[0]:
            peggiore = (carico, t.nome)
    carico, nome = peggiore or (0.0, "")
    portanza = g["terreno"] or TERRENI[1][1]
    return Appoggio(round(carico, 2), round(carico / g["area_appoggio"], 1), portanza,
                    round(carico / portanza, 3), q, nome)


# --- elementi e quantità ---

def _voci_struttura(tipo: str, elenco: list[Tratto], g: dict[str, Any]) -> list[tuple[str, float, str]]:
    """Elementi della struttura di base dei tratti di una tipologia."""
    if not elenco:
        return []
    stilate = sum(t.campate + 1 for t in elenco)
    nodi = sum((t.campate + 1) * t.livelli for t in elenco)
    campate_livelli = sum(t.campate * t.livelli for t in elenco)
    giunzioni = sum((t.campate + 1) * max(0, t.livelli - 1) for t in elenco)  # giunzioni dei montanti
    diagonali = sum(max(1, math.ceil(t.campate / 5)) * t.livelli for t in elenco)
    impalcati = sum(t.campate * t.livelli * max(1, math.ceil(t.larghezza / 0.5 - 1e-6)) for t in elenco)
    metri_altezza = sum((t.campate + 1) * (t.livelli * t.interpiano + ALTEZZA_PARAPETTO) for t in elenco)
    metri_correnti = sum(t.lunghezza_ponteggio * t.livelli for t in elenco)
    voci: list[tuple[str, float, str]]
    if tipo == "Tubi e giunti":
        voci = [
            ("Tubi per montanti", round(metri_altezza * 2, 1), "m"),
            ("Tubi per traversi", nodi, "n."),
            ("Tubi per correnti, parapetti e fermapiede", round(metri_correnti * 5, 1), "m"),
            ("Giunti ortogonali", nodi * 6, "n."),
            ("Giunti girevoli (diagonali)", diagonali * 2, "n."),
            ("Giunti di testa (manicotti) per le giunzioni dei montanti", giunzioni * 2, "n."),
            ("Tubi per diagonali di facciata", diagonali, "n."),
            ("Basette fisse o regolabili", stilate * 2, "n."),
        ]
    elif tipo == "Multidirezionale":
        voci = [
            ("Collari o basi di partenza", stilate * 2, "n."),
            ("Montanti con rosette (da 2 m)", math.ceil(metri_altezza * 2 / 2), "n."),
            ("Traversi", nodi, "n."),
            ("Correnti e parapetti", campate_livelli * 3, "n."),
            ("Diagonali di facciata", diagonali, "n."),
            ("Cunei e spinotti di giunzione", giunzioni * 2, "n."),
            ("Basette regolabili", stilate * 2, "n."),
        ]
    else:  # telai prefabbricati, montanti e traversi prefabbricati
        voci = [
            ("Telai (stilate × livelli)", nodi, "n."),
            ("Spinotti di collegamento tra i telai", giunzioni * 2, "n."),
            ("Correnti e parapetti", campate_livelli * 2, "n."),
            ("Diagonali di facciata", diagonali, "n."),
            ("Basette regolabili", stilate * 2, "n."),
        ]
    voci += [
        ("Impalcati", impalcati, "n."),
        ("Tavole fermapiede", campate_livelli, "n."),
    ]
    return voci


def elementi(ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> list[tuple[str, float, str]]:
    """Elenco indicativo degli elementi: struttura per tipologia (con la tipologia tra parentesi quando nel
    ponteggio ce n'è più d'una), testate, ancoraggi, mantovane, scale e gli elementi inseriti a mano."""
    g = g or geometria(ponteggio)
    elenco = tratti(ponteggio, g)
    tipi = tipologie(ponteggio, g)
    voci: list[tuple[str, float, str]] = []
    for tipo in tipi:
        for nome, q, u in _voci_struttura(tipo, [t for t in elenco if t.tipo == tipo], g):
            voci.append((f"{nome} ({tipo.lower()})" if len(tipi) > 1 else nome, q, u))
    testate = 0 if chiuso(elenco) else sum(2 * t.livelli for t in elenco)
    if testate:
        voci.append(("Parapetti di testata", testate, "n."))
    a = ancoraggi(ponteggio, g)
    voci.append((f"Ancoraggi ({g['tipo_ancoraggio'].lower()})", a.numero, "n."))
    voci.append(("Tasselli o dispositivi di fissaggio alla costruzione", a.numero, "n."))
    con_mantovana = sum(t.campate for t in elenco if t.mantovana and g["mantovana_livello"] <= t.livelli)
    if con_mantovana:
        voci.append(("Mantovana parasassi", con_mantovana, "campate"))
    if g["teli"]:
        voci.append(("Teli o reti su tutta la facciata", round(a.area_facciata, 1), "m²"))
    if not ha_elemento(g, "scala_interna") and not ha_elemento(g, "torre_scala"):
        voci.append(("Scale interne con botola", max(t.livelli for t in elenco), "n."))
    # elementi inseriti a mano, sommati per tipo
    somme: dict[str, float] = {}
    for e in g["elementi"]:
        t = elenco[e["tratto"]]
        somme[e["tipo"]] = somme.get(e["tipo"], 0) + E.quantita(e, t.campata, t.interpiano)
    if somme.get("ancoraggio_tubo"):  # il tubo e i due giunti di ogni ancoraggio su tubo
        n = int(somme["ancoraggio_tubo"])
        voci.append(("Tubi per ancoraggi su tubo e giunto", n, "n."))
        voci.append(("Giunti ortogonali per ancoraggi su tubo", n * 2, "n."))
    for chiave, q in somme.items():
        v = E.voce(chiave)
        voci.append((v.nome, round(q, 1) if isinstance(q, float) and not q.is_integer() else int(q),
                     "campate" if v.per == "campata" and v.unita == "n." else v.unita))
    return voci


# --- avvisi sulla geometria ---

def avvisi_geometria(ponteggio: dict[str, Any]) -> list[str]:
    g = geometria(ponteggio)
    elenco = tratti(ponteggio, g)
    messaggi = []
    if not any(t["lunghezza"] for t in g["tratti"]):
        messaggi.append("Indicare la lunghezza dei tratti del ponteggio nella scheda «Disegno».")
    for t in elenco:
        if t.distanza > DISTANZA_MASSIMA and not any(
                e["tipo"] in ("parapetto_interno", "mensola_interna") for e in elementi_tratto(g, t.indice)):
            messaggi.append(f"{t.nome}: distanza dalla facciata di {_m(t.distanza)}; oltre {_m(DISTANZA_MASSIMA)} "
                            "serve il parapetto anche sul lato interno o una mensola interna (art. 138).")
    if len({t.interpiano for t in elenco}) > 1:
        messaggi.append("I tratti hanno interpiani diversi: verificare i raccordi tra gli impalcati.")
    a = ancoraggi(ponteggio, g)
    if a.area_per_ancoraggio > AREA_PER_ANCORAGGIO:
        messaggi.append(f"Ancoraggi: {_n(a.area_per_ancoraggio, 1)} m² di facciata per ancoraggio, più del "
                        f"riferimento usuale di {AREA_PER_ANCORAGGIO:g} m². Verificare con lo schema del libretto.")
    tipi_inseriti = {e["tipo"] for e in g["elementi"]}
    if g["teli"]:
        tipi_inseriti.add("telo")
    for chiave in sorted(tipi_inseriti):
        v = E.voce(chiave)
        if v and v.avviso:
            messaggi.append(v.avviso)
    if len(tipologie(ponteggio, g)) > 1:
        messaggi.append("Il ponteggio unisce tipologie diverse: i raccordi tra i sistemi devono essere previsti dal "
                        "libretto o dal progetto (art. 133).")
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
