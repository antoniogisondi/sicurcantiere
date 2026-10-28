"""Schema grafico del ponteggio disegnato con Qt dai dati della geometria.

Il ponteggio si costruisce una volta come modello tridimensionale (linee e facce: montanti, impalcati,
parapetti, ancoraggi e tutti gli elementi inseriti dal catalogo) e ogni vista ne è una proiezione:
- vista d'insieme: assonometria che si ruota e si ingrandisce;
- pianta: vista dall'alto di tutti i tratti, con l'edificio;
- prospetto: vista frontale di un tratto, con le quote degli impalcati;
- sezione: vista laterale di un tratto, con le larghezze amplificate per leggerle.
Così un elemento aggiunto (una mensola, una trave carraia, un telo) compare da solo in tutte le viste.

Lo stesso disegno compare nella scheda «Disegno» del programma e nel PiMUS in Word. È uno schema per il
PiMUS e per il disegno esecutivo: le misure vengono dai dati inseriti, gli elementi reali e i loro
collegamenti sono quelli del libretto del fabbricante.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF

from sicurcantiere import ponteggio as P

TRE_D, PIANTA, PROSPETTO, SEZIONE = "3d", "pianta", "prospetto", "sezione"

COLORI = {
    "montante": "#2F4858",
    "traverso": "#4F6D7A",
    "corrente": "#4F6D7A",
    "parapetto": "#E0A030",
    "diagonale": "#7A8B99",
    "impalcato": "#C9A66B",
    "legno": "#A97C50",
    "botola": "#7A5C3A",
    "ancoraggio": "#D93B30",
    "muro": "#D8D4CC",
    "tetto": "#B9B2A6",
    "bordo_muro": "#A8A296",
    "mantovana": "#2E9C8F",
    "scala": "#6B4F3A",
    "terreno": "#8A7F6E",
    "telo": "#6F9C83",
    "tabellone": "#3F6E9A",
    "tubi": "#B5651D",
    "torre": "#5B6770",
    "trave": "#22343F",
    "copertura": "#9AA3AD",
    "macchina": "#444C55",
    "terra": "#2E8B57",
    "segnale": "#E8B400",
    "testo": "#2B2B2B",
    "quota": "#5B5B5B",
    "selezione": "#2E9C8F",
}
SPESSORI = {"montante": 2.2, "traverso": 1.2, "corrente": 1.0, "parapetto": 1.4, "diagonale": 1.0,
            "ancoraggio": 2.2, "scala": 1.4, "mantovana": 1.2, "tubi": 1.6, "trave": 2.6, "torre": 1.6,
            "macchina": 2.0, "terra": 2.0}
ALFA = {"muro": 235, "tetto": 235, "telo": 110, "tabellone": 225, "copertura": 170, "mantovana": 210}


@dataclass
class Primitiva:
    tipo: str                                    # linea | faccia | punto
    punti: list[tuple[float, float, float]]
    stile: str
    lato: int = 0                                # tratto (-1: edificio comune)


@dataclass
class Vista3D:
    rotazione: float = -35.0   # gradi attorno alla verticale
    inclinazione: float = 22.0  # gradi sopra l'orizzonte
    zoom: float = 1.0
    spostamento: tuple[float, float] = (0.0, 0.0)
    mostra_edificio: bool = True


# --- modello tridimensionale ---

def modello(ponteggio: dict[str, Any], g: dict[str, Any] | None = None, edificio: bool = True,
            solo: int | None = None) -> list[Primitiva]:
    """Linee e facce del ponteggio (di un solo tratto con `solo`), in metri."""
    g = g or P.geometria(ponteggio)
    elenco = P.tratti(ponteggio, g)
    prim: list[Primitiva] = []
    for t in elenco:
        if solo is None or t.indice == solo:
            prim += _modello_tratto(t, g, edificio)
    if edificio and solo is None and P.chiuso(elenco):
        h = max(max(t.altezza, t.livelli * t.interpiano) + t.quota for t in elenco) + 0.6
        prim.append(Primitiva("faccia", [(t.origine[0], t.origine[1], h) for t in elenco], "tetto", -1))
    return prim


def _modello_tratto(t: P.Tratto, g: dict[str, Any], edificio: bool) -> list[Primitiva]:
    prim: list[Primitiva] = []
    n = t.indice

    def linea(a, b, stile):
        prim.append(Primitiva("linea", [a, b], stile, n))

    def faccia(punti, stile):
        prim.append(Primitiva("faccia", punti, stile, n))

    pt = t.punto
    h_i = t.interpiano
    interno, esterno = t.distanza, t.distanza + t.larghezza
    cima = t.livelli * h_i + P.ALTEZZA_PARAPETTO
    stilate = [t.inizio + k * t.campata for k in range(t.campate + 1)]
    elementi = P.elementi_tratto(g, n)

    def occupa(tipo: str) -> list[dict[str, Any]]:
        return [e for e in elementi if e["tipo"] == tipo]

    # stilate interrotte dalla trave carraia: i montanti partono dal primo impalcato
    sospese: set[int] = set()
    for e in occupa("trave_carraia"):
        sospese |= set(range(e["da"] + 1, e["a"] + 1))
    sommita = {c for e in occupa("parapetto_sommita") for c in range(e["da"], e["a"] + 1)}
    legno = {(c, l) for e in occupa("tavolato_legno") for c in range(e["da"], e["a"] + 1)
             for l in range(e["livello"], e["livello_a"] + 1)}

    if edificio:
        h_muro = max(t.altezza, t.livelli * h_i) + 0.6
        faccia([pt(0, 0, 0), pt(t.lunghezza, 0, 0), pt(t.lunghezza, 0, h_muro), pt(0, 0, h_muro)], "muro")
    for k, s in enumerate(stilate):
        base = h_i if k in sospese else 0.0
        alto = cima + (1.2 if (k in sommita or k - 1 in sommita) else 0)
        for o in (interno, esterno):
            linea(pt(s, o, base), pt(s, o, alto), "tubi" if t.tipo == "Tubi e giunti" else "montante")
        for livello in range(1, t.livelli + 1):
            linea(pt(s, interno, livello * h_i), pt(s, esterno, livello * h_i), "traverso")
    for livello in range(1, t.livelli + 1):
        z = livello * h_i
        for k in range(t.campate):
            a, b = stilate[k], stilate[k + 1]
            faccia([pt(a, interno, z), pt(b, interno, z), pt(b, esterno, z), pt(a, esterno, z)],
                   "legno" if (k, livello) in legno else "impalcato")
            for quota in (0.5, 1.0):
                linea(pt(a, esterno, z + quota), pt(b, esterno, z + quota), "parapetto")
            if k % 5 == 0:  # diagonale di facciata, alternata a ogni livello
                basso, alto_ = (a, b) if livello % 2 else (b, a)
                linea(pt(basso, esterno, z - h_i), pt(alto_, esterno, z), "diagonale")
    # testate (le estremità libere: un perimetro chiuso non le ha)
    for s in (stilate[0], stilate[-1]):
        for livello in range(1, t.livelli + 1):
            for quota in (0.5, 1.0):
                linea(pt(s, interno, livello * h_i + quota), pt(s, esterno, livello * h_i + quota), "parapetto")
    # parapetti di sommità
    for c in sommita:
        if c < t.campate:
            for quota in (1.6, 2.2):
                linea(pt(stilate[c], esterno, t.livelli * h_i + quota), pt(stilate[c + 1], esterno,
                                                                        t.livelli * h_i + quota), "parapetto")
    # mantovana dello schema
    if t.mantovana and g["mantovana_livello"] <= t.livelli:
        _mantovana(faccia, pt, stilate, 0, t.campate - 1, g["mantovana_livello"] * h_i, esterno)
    # ancoraggi
    for stilata, livello in P.posizioni_ancoraggi(t, g):
        z = livello * h_i - 0.3
        linea(pt(stilate[stilata], interno, z), pt(stilate[stilata], 0, z), "ancoraggio")
    # teli su tutta la facciata
    if g["teli"]:
        faccia([pt(stilate[0], esterno + 0.03, 0), pt(stilate[-1], esterno + 0.03, 0),
                pt(stilate[-1], esterno + 0.03, cima), pt(stilate[0], esterno + 0.03, cima)], "telo")
    # elementi inseriti
    for e in elementi:
        _elemento(e, t, stilate, interno, esterno, linea, faccia, prim)
    return prim


def _mantovana(faccia, pt, stilate, da, a, z, esterno) -> None:
    sbalzo, salita = 1.5 * math.cos(math.radians(20)), 1.5 * math.sin(math.radians(20))
    for k in range(da, a + 1):
        if k + 1 < len(stilate):
            faccia([pt(stilate[k], esterno, z), pt(stilate[k + 1], esterno, z),
                    pt(stilate[k + 1], esterno + sbalzo, z + salita), pt(stilate[k], esterno + sbalzo, z + salita)],
                   "mantovana")


def _elemento(e: dict[str, Any], t: P.Tratto, stilate: list[float], interno: float, esterno: float,
              linea: Callable, faccia: Callable, prim: list[Primitiva]) -> None:
    """Linee e facce di un elemento inserito dal catalogo."""
    pt, h_i, tipo = t.punto, t.interpiano, e["tipo"]
    da, a = min(e["da"], t.campate - 1), min(e["a"], t.campate - 1)
    s0, s1 = stilate[da], stilate[a + 1]
    livelli = range(max(1, e["livello"]), min(t.livelli, max(1, e["livello_a"])) + 1)
    cima = t.livelli * h_i + P.ALTEZZA_PARAPETTO

    def campate():
        return [(stilate[k], stilate[k + 1]) for k in range(da, a + 1)]

    if tipo in ("ancoraggio_tubo", "ancoraggio_puntone", "ancoraggio_doppio"):
        for livello in livelli:
            z = livello * h_i - 0.3
            for x0, x1 in campate():
                if tipo == "ancoraggio_tubo":  # tubo tra le stilate con due giunti, ancoraggio sul tubo
                    linea(pt(x0, interno, z), pt(x1, interno, z), "tubi")
                    x = x0 + (x1 - x0) * e["posizione"]
                    linea(pt(x, interno, z), pt(x, 0, z), "ancoraggio")
                elif tipo == "ancoraggio_puntone":
                    linea(pt(x0, interno, z + 0.15), pt(x0, 0, z + 0.15), "tubi")
                else:  # a V: due tiranti dalla stilata verso la facciata
                    linea(pt(x0, interno, z), pt(x0 - 0.4, 0, z), "ancoraggio")
                    linea(pt(x0, interno, z), pt(x0 + 0.4, 0, z), "ancoraggio")
    elif tipo == "trave_carraia":
        for o in (interno, esterno):
            linea(pt(s0, o, h_i), pt(s1, o, h_i), "trave")
            linea(pt(s0, o, h_i - 0.45), pt(s1, o, h_i - 0.45), "trave")
            passi = max(2, round((s1 - s0) / 0.6))
            for k in range(passi):
                x0 = s0 + (s1 - s0) * k / passi
                x1 = s0 + (s1 - s0) * (k + 1) / passi
                linea(pt(x0, o, h_i - (0.45 if k % 2 else 0)), pt(x1, o, h_i - (0 if k % 2 else 0.45)), "trave")
    elif tipo == "telaio_passo_pedonale":
        for s in sorted({s0, s1}):
            linea(pt(s, esterno + 0.6, 0), pt(s, esterno + 0.6, h_i * 0.75), "montante")
            linea(pt(s, esterno + 0.6, h_i * 0.75), pt(s, esterno, h_i), "montante")
    elif tipo in ("mensola_esterna", "disassamento"):
        sbalzo = 0.5 if tipo == "mensola_esterna" else 0.35
        for livello in livelli:
            z = livello * h_i
            for x0, x1 in campate():
                faccia([pt(x0, esterno, z), pt(x1, esterno, z), pt(x1, esterno + sbalzo, z),
                        pt(x0, esterno + sbalzo, z)], "impalcato")
                for quota in (0.5, 1.0):
                    linea(pt(x0, esterno + sbalzo, z + quota), pt(x1, esterno + sbalzo, z + quota), "parapetto")
            for s in {s0, s1, *[x for x, _ in campate()]}:
                linea(pt(s, esterno, z - 0.7), pt(s, esterno + sbalzo, z), "montante")
                linea(pt(s, esterno + sbalzo, z), pt(s, esterno + sbalzo, z + 1.0), "montante")
    elif tipo == "mensola_interna":
        largo = max(0.1, interno - 0.05)
        for livello in livelli:
            z = livello * h_i
            for x0, x1 in campate():
                faccia([pt(x0, interno - largo, z), pt(x1, interno - largo, z), pt(x1, interno, z),
                        pt(x0, interno, z)], "impalcato")
    elif tipo == "parapetto_interno":
        for livello in livelli:
            for quota in (0.5, 1.0):
                linea(pt(s0, interno, livello * h_i + quota), pt(s1, interno, livello * h_i + quota), "parapetto")
    elif tipo == "botola":
        for livello in livelli:
            for x0, x1 in campate():
                c = (x0 + x1) / 2
                m = (interno + esterno) / 2
                faccia([pt(c - 0.3, m - 0.25, livello * h_i + 0.01), pt(c + 0.3, m - 0.25, livello * h_i + 0.01),
                        pt(c + 0.3, m + 0.25, livello * h_i + 0.01), pt(c - 0.3, m + 0.25, livello * h_i + 0.01)],
                       "botola")
    elif tipo == "scala_interna":
        m = (interno + esterno) / 2
        for livello in livelli:
            for x0, x1 in campate():
                linea(pt(x0 + 0.15, m, (livello - 1) * h_i), pt(x1 - 0.15, m, livello * h_i), "scala")
    elif tipo == "diagonale_facciata":
        for livello in livelli:
            for x0, x1 in campate():
                linea(pt(x0, esterno, (livello - 1) * h_i), pt(x1, esterno, livello * h_i), "diagonale")
    elif tipo == "diagonale_pianta":
        for livello in livelli:
            for x0, x1 in campate():
                linea(pt(x0, interno, livello * h_i - 0.05), pt(x1, esterno, livello * h_i - 0.05), "diagonale")
    elif tipo == "mantovana":
        for livello in livelli:
            _mantovana(faccia, pt, stilate, da, a, livello * h_i, esterno)
    elif tipo in ("telo", "tabellone"):
        z0 = (min(livelli) - 1) * h_i if livelli else 0
        z1 = max(livelli) * h_i + 1.0 if livelli else cima
        faccia([pt(s0, esterno + 0.04, z0), pt(s1, esterno + 0.04, z0), pt(s1, esterno + 0.04, z1),
                pt(s0, esterno + 0.04, z1)], tipo)
    elif tipo in ("tunnel", "protezione_varco"):
        largo, alto = 1.5, 2.5
        faccia([pt(s0, esterno, alto), pt(s1, esterno, alto), pt(s1, esterno + largo, alto),
                pt(s0, esterno + largo, alto)], "copertura")
        if tipo == "tunnel":
            for s in {s0, s1, *[x for x, _ in campate()]}:
                linea(pt(s, esterno + largo, 0), pt(s, esterno + largo, alto), "montante")
    elif tipo == "castello_carico":
        o0, o1 = esterno + 0.15, esterno + 1.95
        for s in (s0, s1):
            for o in (o0, o1):
                linea(pt(s, o, 0), pt(s, o, cima), "torre")
        for k in range(1, t.livelli + 1):
            z = k * h_i
            faccia([pt(s0, o0, z), pt(s1, o0, z), pt(s1, o1, z), pt(s0, o1, z)], "impalcato")
            for quota in (0.5, 1.0):
                linea(pt(s0, o1, z + quota), pt(s1, o1, z + quota), "parapetto")
            linea(pt(s0, o1, z - h_i), pt(s1, o1, z), "diagonale")
    elif tipo == "partenza_bocca_lupo":
        for o in (interno, esterno):
            linea(pt(s0 - 0.3, o, 0.05), pt(s1 + 0.3, o, 0.05), "trave")
        faccia([pt(s0, interno - 0.05, -0.02), pt(s1, interno - 0.05, -0.02), pt(s1, esterno + 0.4, -0.02),
                pt(s0, esterno + 0.4, -0.02)], "copertura")
    elif tipo == "torre_scala":
        o0, o1 = esterno + 0.15, esterno + 1.65
        for s in (s0, s1):
            for o in (o0, o1):
                linea(pt(s, o, 0), pt(s, o, cima), "torre")
        for k in range(1, t.livelli + 1):
            linea(pt(s0, (o0 + o1) / 2, (k - 1) * h_i), pt(s1, (o0 + o1) / 2, k * h_i - h_i / 2), "scala")
            linea(pt(s1, (o0 + o1) / 2, k * h_i - h_i / 2), pt(s0, (o0 + o1) / 2, k * h_i), "scala")
    elif tipo == "piazzola_carico":
        for livello in livelli:
            z = livello * h_i
            faccia([pt(s0, esterno, z), pt(s1, esterno, z), pt(s1, esterno + 1.8, z), pt(s0, esterno + 1.8, z)],
                   "impalcato")
            for quota in (0.5, 1.0):
                linea(pt(s0, esterno + 1.8, z + quota), pt(s1, esterno + 1.8, z + quota), "parapetto")
                linea(pt(s0, esterno, z + quota), pt(s0, esterno + 1.8, z + quota), "parapetto")
            for s in (s0, s1):
                linea(pt(s, esterno, z - 1.0), pt(s, esterno + 1.8, z), "montante")
    elif tipo == "argano":
        for livello in livelli:
            z = livello * h_i
            linea(pt(s0, esterno, z), pt(s0, esterno, z + 1.8), "macchina")
            linea(pt(s0, esterno, z + 1.8), pt(s0, esterno + 1.0, z + 1.8), "macchina")
            linea(pt(s0, esterno + 1.0, z + 1.8), pt(s0, esterno + 1.0, z + 0.6), "ancoraggio")
    elif tipo == "montacarichi":
        o0, o1 = esterno + 0.4, esterno + 1.6
        for o in (o0, o1):
            linea(pt(s0, o, 0), pt(s0, o, cima + 1.0), "macchina")
        faccia([pt(s0, o0, 0.3), pt(s1, o0, 0.3), pt(s1, o1, 0.3), pt(s0, o1, 0.3)], "torre")
    elif tipo == "tubi_giunti":
        for livello in livelli or [1]:
            z = livello * h_i
            for x0, x1 in campate():
                linea(pt(x0, esterno + 0.08, z - h_i), pt(x1, esterno + 0.08, z), "tubi")
                linea(pt(x0, esterno + 0.08, z - h_i / 2), pt(x1, esterno + 0.08, z - h_i / 2), "tubi")
                linea(pt(x0, interno - 0.08, z - h_i / 2), pt(x1, interno - 0.08, z - h_i / 2), "tubi")
    elif tipo == "rinforzo_montante":
        for s in {s0, s1}:
            for o in (interno, esterno):
                linea(pt(s + 0.07, o, 0), pt(s + 0.07, o, cima), "tubi")
    elif tipo == "messa_terra":
        linea(pt(s0, esterno, 0.2), pt(s0, esterno + 0.4, -0.6), "terra")
    elif tipo in ("segnalazione", "cartello"):
        lato = 0.3 if tipo == "segnalazione" else 0.5
        faccia([pt(s0, esterno + 0.05, 1.6), pt(s0 + lato, esterno + 0.05, 1.6),
                pt(s0 + lato, esterno + 0.05, 1.6 + lato), pt(s0, esterno + 0.05, 1.6 + lato)], "segnale")


# --- proiezioni ---

Proiezione = Callable[[tuple[float, float, float]], tuple[float, float, float]]


def _assonometria(rotazione: float, inclinazione: float) -> Proiezione:
    t, f = math.radians(rotazione), math.radians(inclinazione)

    def proietta(p):
        x1 = p[0] * math.cos(t) - p[1] * math.sin(t)
        y1 = p[0] * math.sin(t) + p[1] * math.cos(t)
        return x1, y1 * math.sin(f) + p[2] * math.cos(f), y1 * math.cos(f) - p[2] * math.sin(f)
    return proietta


def _frontale(t: P.Tratto) -> Proiezione:
    """Prospetto del tratto: ascissa lungo la facciata, ordinata la quota; profondità verso l'esterno (più
    lontano = dietro)."""
    (ox, oy), (dx, dy), (nx, ny) = t.origine, t.direzione, t.normale

    def proietta(p):
        vx, vy = p[0] - ox, p[1] - oy
        return vx * dx + vy * dy, p[2], -(vx * nx + vy * ny)
    return proietta


def _laterale(t: P.Tratto, amplifica: float = 2.0) -> Proiezione:
    """Sezione del tratto: ascissa lo scostamento dalla facciata (amplificato), ordinata la quota."""
    (ox, oy), (dx, dy), (nx, ny) = t.origine, t.direzione, t.normale

    def proietta(p):
        vx, vy = p[0] - ox, p[1] - oy
        return (vx * nx + vy * ny) * amplifica, p[2], vx * dx + vy * dy
    return proietta


def _dall_alto(p):
    return p[0], p[1], -p[2]


@dataclass
class Trasformazione:
    """Da coordinate proiettate (m) a pixel e ritorno."""
    scala: float
    x0: float
    y0: float

    def schermo(self, x: float, y: float) -> QPointF:
        return QPointF(self.x0 + x * self.scala, self.y0 - y * self.scala)

    def metri(self, px: float, py: float) -> tuple[float, float]:
        return (px - self.x0) / self.scala, (self.y0 - py) / self.scala


def _adatta(punti: list[tuple[float, float]], area: QRectF, zoom: float = 1.0,
            spostamento: tuple[float, float] = (0.0, 0.0), margine: float = 20) -> Trasformazione:
    xs = [p[0] for p in punti] or [0, 1]
    ys = [p[1] for p in punti] or [0, 1]
    larghezza, altezza = max(max(xs) - min(xs), 1e-3), max(max(ys) - min(ys), 1e-3)
    scala = min((area.width() - 2 * margine) / larghezza, (area.height() - 2 * margine) / altezza) * zoom
    scala = max(scala, 1e-3)
    x0 = area.center().x() - (min(xs) + larghezza / 2) * scala + spostamento[0]
    y0 = area.center().y() + (min(ys) + altezza / 2) * scala + spostamento[1]
    return Trasformazione(scala, x0, y0)


def _disegna(pittore: QPainter, prim: list[Primitiva], proiettate: list[list[tuple[float, float, float]]],
             tr: Trasformazione, ordine: list[int], evidenzia: int | None = None, tratteggia_muro: bool = False) -> None:
    spessore = max(0.6, min(2.2, tr.scala / 25))
    for i in ordine:
        pr, pp = prim[i], proiettate[i]
        punti = [tr.schermo(q[0], q[1]) for q in pp]
        if pr.tipo == "faccia":
            colore = QColor(COLORI[pr.stile])
            colore.setAlpha(ALFA.get(pr.stile, 215))
            if evidenzia is not None and pr.lato == evidenzia and pr.stile == "impalcato":
                colore = QColor(COLORI["selezione"])
                colore.setAlpha(150)
            pittore.setBrush(colore)
            bordo = COLORI["bordo_muro"] if pr.stile in ("muro", "tetto") else "#9C7F4E"
            pittore.setPen(QPen(QColor(bordo), 0.6))
            pittore.drawPolygon(QPolygonF(punti))
            if tratteggia_muro and pr.stile == "muro":
                pittore.setBrush(QBrush(QColor(COLORI["bordo_muro"]), Qt.BrushStyle.BDiagPattern))
                pittore.drawPolygon(QPolygonF(punti))
        else:
            pittore.setPen(QPen(QColor(COLORI[pr.stile]), SPESSORI.get(pr.stile, 1.0) * spessore,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            pittore.drawLine(punti[0], punti[1])
            if pr.stile == "ancoraggio":
                pittore.setBrush(QColor(COLORI["ancoraggio"]))
                pittore.drawEllipse(punti[1], 2.2 * spessore, 2.2 * spessore)


def disegna_3d(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], vista: Vista3D | None = None,
               g: dict[str, Any] | None = None, evidenzia: int | None = None) -> None:
    vista = vista or Vista3D()
    g = g or P.geometria(ponteggio)
    prim = modello(ponteggio, g, vista.mostra_edificio)
    if not prim:
        return
    proietta = _assonometria(vista.rotazione, vista.inclinazione)
    proiettate = [[proietta(p) for p in pr.punti] for pr in prim]
    tr = _adatta([(q[0], q[1]) for pp in proiettate for q in pp], area, vista.zoom, vista.spostamento)
    # Ordine: prima i ponteggi dei tratti che danno le spalle a chi guarda (stanno dietro l'edificio), poi i
    # muri, poi i ponteggi rivolti verso chi guarda; in ogni gruppo dal più lontano al più vicino.
    t = math.radians(vista.rotazione)
    elenco = P.tratti(ponteggio, g)
    verso_chi_guarda = {tr_.indice: tr_.normale[0] * math.sin(t) + tr_.normale[1] * math.cos(t) < 0
                        for tr_ in elenco}

    def gruppo(pr: Primitiva) -> float:
        if pr.stile == "tetto":
            return 2.5
        if pr.stile == "muro":
            return 2 if verso_chi_guarda.get(pr.lato, True) else 1
        return 3 if verso_chi_guarda.get(pr.lato, True) else 0

    ordine = sorted(range(len(prim)), key=lambda i: (gruppo(prim[i]),
                                                     -sum(q[2] for q in proiettate[i]) / len(proiettate[i])))
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    _terreno_3d(pittore, elenco, proietta, tr)
    _disegna(pittore, prim, proiettate, tr, ordine, evidenzia)
    pittore.restore()


def _terreno_3d(pittore, elenco: list[P.Tratto], proietta, tr: Trasformazione) -> None:
    punti = []
    for t in elenco:
        fuori = t.distanza + t.larghezza + 1.5
        punti += [t.punto(0, fuori, -t.quota), t.punto(t.lunghezza, fuori, -t.quota)]
    if len(punti) < 3:
        return
    cx = sum(p[0] for p in punti) / len(punti)
    cy = sum(p[1] for p in punti) / len(punti)
    punti.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    colore = QColor(COLORI["terreno"])
    colore.setAlpha(40)
    pittore.setBrush(colore)
    pittore.setPen(Qt.PenStyle.NoPen)
    pittore.drawPolygon(QPolygonF([tr.schermo(*proietta(p)[:2]) for p in punti]))


# --- testi ---

def _font(pittore: QPainter, pixel: float, grassetto: bool = False) -> None:
    f = QFont("Segoe UI")
    f.setPixelSize(max(8, round(pixel)))
    f.setBold(grassetto)
    pittore.setFont(f)


def _m(valore: float) -> str:
    return f"{valore:.2f}".replace(".", ",")


def _alto_titolo(area: QRectF) -> float:
    base = min(area.width(), area.height())
    return area.top() + base / 18 + 14 + base / 25 + 4


def _titolo(pittore: QPainter, area: QRectF, testo: str, sottotitolo: str = "") -> float:
    base = min(area.width(), area.height())
    _font(pittore, base / 32 + 4, True)
    pittore.setPen(QColor(COLORI["testo"]))
    pittore.drawText(QRectF(area.left() + 10, area.top() + 6, area.width() - 20, base / 18 + 8),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, testo)
    if sottotitolo:
        _font(pittore, base / 45 + 3)
        pittore.setPen(QColor(COLORI["quota"]))
        pittore.drawText(QRectF(area.left() + 10, area.top() + base / 18 + 10, area.width() - 20, base / 25 + 6),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sottotitolo)
    return _alto_titolo(area)


# --- prospetto ---

def _tratto(ponteggio, g, indice) -> P.Tratto:
    elenco = P.tratti(ponteggio, g)
    return elenco[min(max(indice, 0), len(elenco) - 1)]


def _area_prospetto(area: QRectF) -> QRectF:
    alto = _alto_titolo(area)
    sinistra = area.width() * 0.07 + 30
    basso = area.height() * 0.07 + 22
    return QRectF(area.left() + sinistra, alto + 4, area.width() - sinistra - 10, area.bottom() - basso - alto - 4)


def _prospetto(ponteggio, g, indice, area):
    t = _tratto(ponteggio, g, indice)
    prim = modello(ponteggio, g, True, solo=t.indice)
    proietta = _frontale(t)
    proiettate = [[proietta(p) for p in pr.punti] for pr in prim]
    punti = [(q[0], q[1]) for pp in proiettate for q in pp] + [(t.inizio - 0.6, -0.3)]
    tr = _adatta(punti, _area_prospetto(area), margine=4)
    return t, prim, proiettate, tr


def disegna_prospetto(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], indice: int = 0,
                      g: dict[str, Any] | None = None) -> None:
    g = g or P.geometria(ponteggio)
    t, prim, proiettate, tr = _prospetto(ponteggio, g, indice, area)
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    _titolo(pittore, area, f"Prospetto · {t.nome}",
            f"{t.campate} campate da {_m(t.campata)} m · {t.livelli} impalcati ogni {_m(t.interpiano)} m · "
            f"{t.tipo.lower()} · ancoraggi in rosso")
    # dal fondo (facciata) al davanti
    ordine = sorted(range(len(prim)), key=lambda i: -sum(q[2] for q in proiettate[i]) / len(proiettate[i]))
    spessore = max(0.8, min(2.4, tr.scala / 18))
    pittore.setPen(QPen(QColor(COLORI["terreno"]), spessore * 1.5))
    x_a, x_b = t.inizio - 0.6, t.inizio + t.lunghezza_ponteggio + 0.6
    pittore.drawLine(tr.schermo(x_a, t.quota), tr.schermo(x_b, t.quota))
    pittore.fillRect(QRectF(tr.schermo(x_a, t.quota), tr.schermo(x_b, t.quota - 0.25)),
                     QBrush(QColor(COLORI["terreno"]), Qt.BrushStyle.BDiagPattern))
    _disegna(pittore, prim, proiettate, tr, ordine)
    # simboli della tipologia: giunti ai nodi o rosette
    stilate = [t.inizio + k * t.campata for k in range(t.campate + 1)]
    if t.tipo in ("Tubi e giunti", "Multidirezionale"):
        pittore.setPen(QPen(QColor(COLORI["montante"]), spessore * 0.8))
        pittore.setBrush(QColor("#FFFFFF") if t.tipo == "Multidirezionale" else QColor(COLORI["montante"]))
        lato_simbolo = max(2.0, min(6.0, tr.scala * 0.09))
        cima = t.livelli * t.interpiano + P.ALTEZZA_PARAPETTO
        for s in stilate:
            quote = ([l * t.interpiano + q for l in range(1, t.livelli + 1) for q in (0, 0.5, 1.0)]
                     if t.tipo == "Tubi e giunti" else [k * 0.5 for k in range(1, int(cima / 0.5) + 1)])
            for z in quote:
                c = tr.schermo(s, t.quota + z)
                if t.tipo == "Tubi e giunti":
                    pittore.drawRect(QRectF(c.x() - lato_simbolo, c.y() - lato_simbolo, 2 * lato_simbolo,
                                            2 * lato_simbolo))
                else:
                    pittore.drawEllipse(c, lato_simbolo, lato_simbolo)
    # ancoraggi (cerchi pieni) e ancoraggi dello schema tolti a mano (tratteggiati)
    raggio = max(2.5, min(7.0, tr.scala * 0.14))
    pittore.setPen(QPen(QColor(COLORI["ancoraggio"]), spessore))
    pittore.setBrush(QColor(COLORI["ancoraggio"]))
    for stilata, livello in P.posizioni_ancoraggi(t, g):
        pittore.drawEllipse(tr.schermo(stilate[stilata], t.quota + livello * t.interpiano - 0.3), raggio, raggio)
    pittore.setBrush(Qt.BrushStyle.NoBrush)
    pittore.setPen(QPen(QColor("#9AA3AD"), spessore, Qt.PenStyle.DashLine))
    for stilata, livello in t.tolti:
        if stilata <= t.campate and livello <= t.livelli:
            pittore.drawEllipse(tr.schermo(stilate[stilata], t.quota + livello * t.interpiano - 0.3), raggio, raggio)
    # quote degli impalcati e lunghezza
    _font(pittore, max(11, min(20, tr.scala * 0.4)))
    pittore.setPen(QColor(COLORI["quota"]))
    sinistra = _area_prospetto(area).left()
    for livello in range(0, t.livelli + 1):
        z = t.quota + livello * t.interpiano
        y = tr.schermo(0, z).y()
        pittore.drawText(QRectF(area.left() + 2, y - 9, sinistra - area.left() - 10, 18),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{z:+.2f}".replace(".", ","))
    # codici delle stilate (S1, S2...), gli stessi dell'elenco degli ancoraggi nel PiMUS
    _font(pittore, max(9, min(16, tr.scala * 0.3)))
    passo = max(1, round(28 / max(tr.scala * t.campata, 1)))
    for k, s in enumerate(stilate):
        if k % passo == 0 or k == len(stilate) - 1:
            c = tr.schermo(s, t.quota - 0.25)
            pittore.drawText(QRectF(c.x() - 20, c.y() + 1, 40, 14), Qt.AlignmentFlag.AlignHCenter, f"S{k + 1}")
    _font(pittore, max(11, min(20, tr.scala * 0.4)))
    xa, xb = tr.schermo(stilate[0], 0).x(), tr.schermo(stilate[-1], 0).x()
    y_quota = tr.schermo(0, t.quota - 0.25).y() + 20
    pittore.drawLine(QPointF(xa, y_quota), QPointF(xb, y_quota))
    for x in (xa, xb):
        pittore.drawLine(QPointF(x, y_quota - 5), QPointF(x, y_quota + 5))
    pittore.drawText(QRectF(xa, y_quota + 2, max(xb - xa, 10), 22), Qt.AlignmentFlag.AlignHCenter,
                     f"{_m(t.lunghezza_ponteggio)} m (facciata {_m(t.lunghezza)} m)")
    pittore.restore()


def punto_prospetto(area: QRectF, ponteggio: dict[str, Any], indice: int, x: float, y: float,
                    g: dict[str, Any] | None = None) -> tuple[float, float]:
    """Coordinate in metri (lungo la facciata, quota dal piede del tratto) del punto cliccato."""
    g = g or P.geometria(ponteggio)
    t, _, _, tr = _prospetto(ponteggio, g, indice, area)
    s, z = tr.metri(x, y)
    return s, z - t.quota


def nodo_prospetto(area: QRectF, ponteggio: dict[str, Any], indice: int, x: float, y: float,
                   g: dict[str, Any] | None = None) -> tuple[int, int] | None:
    """Stilata e livello del punto di ancoraggio più vicino al clic sul prospetto (None se troppo lontano)."""
    g = g or P.geometria(ponteggio)
    t, _, _, tr = _prospetto(ponteggio, g, indice, area)
    s, z = tr.metri(x, y)
    z -= t.quota
    stilata = round((s - t.inizio) / t.campata)
    livello = round((z + 0.3) / t.interpiano)
    if not (0 <= stilata <= t.campate and 1 <= livello <= t.livelli):
        return None
    distanza = math.hypot(s - (t.inizio + stilata * t.campata), z - (livello * t.interpiano - 0.3)) * tr.scala
    return (stilata, livello) if distanza <= max(12.0, 0.45 * t.campata * tr.scala) else None


def campata_prospetto(area: QRectF, ponteggio: dict[str, Any], indice: int, x: float, y: float,
                      g: dict[str, Any] | None = None) -> tuple[int, int] | None:
    """Campata (da 0) e impalcato (da 1; 0 a terra) del punto cliccato sul prospetto."""
    g = g or P.geometria(ponteggio)
    t = _tratto(ponteggio, g, indice)
    s, z = punto_prospetto(area, ponteggio, indice, x, y, g)
    campata = math.floor((s - t.inizio) / t.campata)
    if not 0 <= campata < t.campate or z < -1.0 or z > t.livelli * t.interpiano + 2.5:
        return None
    return campata, min(t.livelli, max(0, round(z / t.interpiano)))


# --- pianta ---

def _pianta(ponteggio, g, area):
    prim = modello(ponteggio, g, True)
    prim = [p for p in prim if p.stile not in ("tetto",)]
    proiettate = [[_dall_alto(p) for p in pr.punti] for pr in prim]
    alto = _alto_titolo(area)
    disegno = QRectF(area.left() + 10, alto + 4, area.width() - 20, area.bottom() - alto - 14)
    tr = _adatta([(q[0], q[1]) for pp in proiettate for q in pp], disegno, margine=30)
    return prim, proiettate, tr


def trasformazione_pianta(area: QRectF, ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> Trasformazione:
    return _pianta(ponteggio, g or P.geometria(ponteggio), area)[2]


def tratto_in_pianta(area: QRectF, ponteggio: dict[str, Any], x: float, y: float,
                     g: dict[str, Any] | None = None) -> int | None:
    """Tratto più vicino al punto cliccato sulla pianta (entro 1,5 m)."""
    g = g or P.geometria(ponteggio)
    mx, my = trasformazione_pianta(area, ponteggio, g).metri(x, y)
    migliore = None
    for t in P.tratti(ponteggio, g):
        (ox, oy), (dx, dy), (nx, ny) = t.origine, t.direzione, t.normale
        s = (mx - ox) * dx + (my - oy) * dy
        o = (mx - ox) * nx + (my - oy) * ny
        fuori_s = max(t.inizio - s, s - (t.inizio + t.lunghezza_ponteggio), 0)
        fuori_o = max(-o, o - (t.distanza + t.larghezza), 0)
        d = math.hypot(fuori_s, fuori_o)
        if d <= 1.5 and (migliore is None or d < migliore[0]):
            migliore = (d, t.indice)
    return migliore[1] if migliore else None


def disegna_pianta(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], g: dict[str, Any] | None = None,
                   evidenzia: int | None = None) -> None:
    g = g or P.geometria(ponteggio)
    elenco = P.tratti(ponteggio, g)
    prim, proiettate, tr = _pianta(ponteggio, g, area)
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    _titolo(pittore, area, "Pianta del ponteggio",
            f"Sviluppo {_m(P.sviluppo(g))} m · {len(elenco)} tratti · ancoraggi in rosso")
    if P.chiuso(elenco):  # edificio con il perimetro chiuso
        contorno = QPainterPath()
        contorno.addPolygon(QPolygonF([tr.schermo(*t.origine) for t in elenco]))
        contorno.closeSubpath()
        pittore.fillPath(contorno, QBrush(QColor(COLORI["muro"])))
        pittore.fillPath(contorno, QBrush(QColor(COLORI["bordo_muro"]), Qt.BrushStyle.BDiagPattern))
    pittore.setPen(QPen(QColor("#555046"), max(2.0, tr.scala * 0.12)))
    for t in elenco:  # linee delle facciate
        pittore.drawLine(tr.schermo(*t.origine), tr.schermo(*t.fine()))
    # dal basso verso l'alto: prima gli elementi a terra, poi gli impalcati
    ordine = sorted((i for i, p in enumerate(prim) if p.stile != "muro"),
                    key=lambda i: -sum(q[2] for q in proiettate[i]) / len(proiettate[i]))
    _disegna(pittore, prim, proiettate, tr, ordine, evidenzia)
    _font(pittore, max(11, min(22, tr.scala * 0.5)))
    for t in elenco:
        centro = tr.schermo(*t.punto(t.lunghezza / 2, t.distanza + t.larghezza + 0.7)[:2])
        pittore.save()
        pittore.translate(centro)
        angolo = -math.degrees(math.atan2(t.direzione[1], t.direzione[0]))
        if angolo > 90 or angolo <= -90:
            angolo += 180
        pittore.rotate(angolo)
        pittore.setPen(QColor(COLORI["selezione"] if t.indice == evidenzia else COLORI["testo"]))
        _font(pittore, max(11, min(22, tr.scala * 0.5)), t.indice == evidenzia)
        pittore.drawText(QRectF(-220, -12, 440, 24), Qt.AlignmentFlag.AlignCenter,
                         f"{t.nome} · {_m(t.lunghezza)} m" + ("" if len({x.tipo for x in elenco}) == 1
                                                             else f" · {t.tipo.lower()}"))
        pittore.restore()
    pittore.restore()


# --- sezione ---

def disegna_sezione(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], g: dict[str, Any] | None = None,
                    indice: int | None = None) -> None:
    g = g or P.geometria(ponteggio)
    elenco = P.tratti(ponteggio, g)
    t = elenco[indice] if indice is not None and 0 <= indice < len(elenco) else max(elenco, key=lambda x: x.livelli)
    prim = [p for p in modello(ponteggio, g, True, solo=t.indice)]
    proietta = _laterale(t)
    proiettate = [[proietta(p) for p in pr.punti] for pr in prim]
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    alto = _titolo(pittore, area, f"Sezione tipo · {t.nome}", "Larghezze amplificate due volte rispetto alle altezze")
    disegno = QRectF(area.left() + 70, alto + 6, area.width() - 90, area.bottom() - alto - 40)
    punti = [(q[0], q[1]) for pp in proiettate for q in pp] + [(-1.2, 0), (5.0, 0)]
    tr = _adatta(punti, disegno, margine=6)
    # facciata
    cima = t.livelli * t.interpiano + P.ALTEZZA_PARAPETTO + t.quota
    pittore.fillRect(QRectF(tr.schermo(-1.2, cima + 0.4), tr.schermo(0, t.quota)), QBrush(QColor(COLORI["muro"])))
    pittore.fillRect(QRectF(tr.schermo(-1.2, cima + 0.4), tr.schermo(0, t.quota)),
                     QBrush(QColor(COLORI["bordo_muro"]), Qt.BrushStyle.BDiagPattern))
    spessore = max(0.8, min(2.4, tr.scala / 16))
    pittore.setPen(QPen(QColor(COLORI["terreno"]), spessore * 1.5))
    pittore.drawLine(tr.schermo(-1.2, t.quota), tr.schermo(5.0, t.quota))
    prim_visibili = [i for i, p in enumerate(prim) if p.stile != "muro"]
    ordine = sorted(prim_visibili, key=lambda i: -sum(q[2] for q in proiettate[i]) / len(proiettate[i]))
    _disegna(pittore, prim, proiettate, tr, ordine)
    _font(pittore, max(11, min(20, tr.scala * 0.4)))
    pittore.setPen(QColor(COLORI["quota"]))
    for livello in range(1, t.livelli + 1):
        z = t.quota + livello * t.interpiano
        pittore.drawText(QRectF(area.left() + 2, tr.schermo(0, z).y() - 9, 62, 18),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{z:+.2f}".replace(".", ","))
    base = tr.schermo(0, t.quota).y() + 14
    pittore.drawText(QRectF(tr.schermo(-1, 0).x(), base, tr.scala * 7, 22), Qt.AlignmentFlag.AlignLeft,
                     f"distanza {_m(t.distanza)} · larghezza {_m(t.larghezza)} m")
    pittore.restore()


# --- immagini per il documento ---

def disegna(pittore: QPainter, area: QRectF, tipo: str, ponteggio: dict[str, Any], indice: int = 0,
            vista: Vista3D | None = None, g: dict[str, Any] | None = None, evidenzia: int | None = None) -> None:
    if tipo == TRE_D:
        _titolo(pittore, area, "Vista d'insieme", "Schema tridimensionale · ancoraggi in rosso")
        disegna_3d(pittore, area.adjusted(0, area.height() * 0.08, 0, 0), ponteggio, vista, g, evidenzia)
    elif tipo == PIANTA:
        disegna_pianta(pittore, area, ponteggio, g, evidenzia)
    elif tipo == SEZIONE:
        disegna_sezione(pittore, area, ponteggio, g, indice)
    else:
        disegna_prospetto(pittore, area, ponteggio, indice, g)


def immagine(tipo: str, ponteggio: dict[str, Any], larghezza: int = 1800, altezza: int = 1100, indice: int = 0,
             vista: Vista3D | None = None) -> QImage:
    from sicurcantiere.documenti.immagini import applicazione

    applicazione()
    img = QImage(larghezza, altezza, QImage.Format.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    pittore = QPainter(img)
    disegna(pittore, QRectF(0, 0, larghezza, altezza), tipo, ponteggio, indice, vista)
    pittore.end()
    return img


@dataclass
class Tavola:
    titolo: str
    png: bytes
    orizzontale: bool = True
    note: list[str] = field(default_factory=list)


def tavole(ponteggio: dict[str, Any]) -> list[Tavola]:
    """Disegni da inserire nel PiMUS: vista d'insieme, pianta, prospetto di ogni tratto e sezione tipo."""
    from sicurcantiere.documenti.immagini import png

    g = P.geometria(ponteggio)
    risultato = [Tavola("Vista d'insieme", png(immagine(TRE_D, ponteggio))),
                 Tavola("Pianta", png(immagine(PIANTA, ponteggio)))]
    for n, t in enumerate(g["tratti"]):
        risultato.append(Tavola(f"Prospetto · {t['nome']}", png(immagine(PROSPETTO, ponteggio, indice=n))))
    risultato.append(Tavola("Sezione tipo", png(immagine(SEZIONE, ponteggio, 1100, 1500, indice=-1)),
                            orizzontale=False))
    return risultato
