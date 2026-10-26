"""Schema grafico del ponteggio disegnato con Qt dai dati della geometria: vista tridimensionale
(assonometria ruotabile), pianta, prospetto di ogni lato e sezione tipo.

Lo stesso disegno compare nella scheda «Disegno» del programma e nel PiMUS in Word. È uno schema per il
PiMUS e per il disegno esecutivo: le misure vengono dai dati inseriti, gli elementi reali e i loro
collegamenti sono quelli del libretto del fabbricante.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

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
    "ancoraggio": "#D93B30",
    "muro": "#D8D4CC",
    "tetto": "#B9B2A6",
    "bordo_muro": "#A8A296",
    "mantovana": "#2E9C8F",
    "scala": "#6B4F3A",
    "terreno": "#8A7F6E",
    "testo": "#2B2B2B",
    "quota": "#5B5B5B",
}
SPESSORI = {"montante": 2.2, "traverso": 1.2, "corrente": 1.0, "parapetto": 1.4, "diagonale": 1.0,
            "ancoraggio": 2.2, "scala": 1.4, "mantovana": 1.2}


@dataclass
class Primitiva:
    tipo: str                                    # linea | faccia
    punti: list[tuple[float, float, float]]
    stile: str
    lato: int = 0


@dataclass
class Vista3D:
    rotazione: float = -35.0   # gradi attorno alla verticale
    inclinazione: float = 22.0  # gradi sopra l'orizzonte
    zoom: float = 1.0
    spostamento: tuple[float, float] = (0.0, 0.0)
    mostra_edificio: bool = True


# --- geometria nello spazio ---

def _percorso(g: dict[str, Any]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Origine e direzione di ogni lato: si percorre il perimetro girando a sinistra di 90° a ogni spigolo,
    con l'edificio a sinistra e il ponteggio a destra (verso l'esterno)."""
    x = y = 0.0
    dx, dy = 1.0, 0.0
    risultato = []
    for lato in g["lati"]:
        risultato.append(((x, y), (dx, dy)))
        x, y = x + dx * lato["lunghezza"], y + dy * lato["lunghezza"]
        dx, dy = -dy, dx
    return risultato


def _punto(origine, direzione, s: float, scostamento: float, z: float) -> tuple[float, float, float]:
    (ox, oy), (dx, dy) = origine, direzione
    nx, ny = dy, -dx  # normale verso l'esterno
    return (ox + dx * s + nx * scostamento, oy + dy * s + ny * scostamento, z)


def modello(ponteggio: dict[str, Any], g: dict[str, Any] | None = None,
            edificio: bool = True) -> list[Primitiva]:
    g = g or P.geometria(ponteggio)
    lati = P.lati(ponteggio, g)
    interno, esterno = g["distanza"], g["distanza"] + g["larghezza"]
    h_i = g["interpiano"]
    prim: list[Primitiva] = []

    n_lato = 0

    def linea(a, b, stile):
        prim.append(Primitiva("linea", [a, b], stile, n_lato))

    def faccia(punti, stile):
        prim.append(Primitiva("faccia", punti, stile, n_lato))

    for n_lato, ((origine, direzione), lato, dati) in enumerate(zip(_percorso(g), lati, g["lati"])):
        pt = lambda s, o, z: _punto(origine, direzione, s, o, z)  # noqa: E731
        cima = lato.livelli * h_i + P.ALTEZZA_PARAPETTO
        if edificio:
            h_muro = max(lato.altezza, lato.livelli * h_i) + 0.6
            faccia([pt(0, 0, 0), pt(dati["lunghezza"], 0, 0), pt(dati["lunghezza"], 0, h_muro), pt(0, 0, h_muro)],
                   "muro")
        partenza = P.inizio(lato, g)
        stilate = [partenza + k * g["campata"] for k in range(lato.campate + 1)]
        for s in stilate:
            for o in (interno, esterno):
                linea(pt(s, o, 0), pt(s, o, cima), "montante")
            for livello in range(1, lato.livelli + 1):
                linea(pt(s, interno, livello * h_i), pt(s, esterno, livello * h_i), "traverso")
        for livello in range(1, lato.livelli + 1):
            z = livello * h_i
            for k in range(lato.campate):
                a, b = stilate[k], stilate[k + 1]
                faccia([pt(a, interno, z), pt(b, interno, z), pt(b, esterno, z), pt(a, esterno, z)], "impalcato")
                for quota in (0.5, 1.0):
                    linea(pt(a, esterno, z + quota), pt(b, esterno, z + quota), "parapetto")
                    if g["distanza"] > P.DISTANZA_MASSIMA:
                        linea(pt(a, interno, z + quota), pt(b, interno, z + quota), "parapetto")
                if k % 5 == 0:  # diagonale di facciata, alternata a ogni livello
                    basso, alto = (a, b) if livello % 2 else (b, a)
                    linea(pt(basso, esterno, z - h_i), pt(alto, esterno, z), "diagonale")
            if g["forma"] == "aperta":
                for s in (stilate[0], stilate[-1]):
                    for quota in (0.5, 1.0):
                        linea(pt(s, interno, z + quota), pt(s, esterno, z + quota), "parapetto")
            if lato is lati[0]:  # scala interna nella prima campata
                linea(pt(stilate[0] + 0.15, (interno + esterno) / 2, z - h_i),
                      pt(stilate[1] - 0.15, (interno + esterno) / 2, z), "scala")
        if lato.mantovana and g["mantovana_livello"] <= lato.livelli:
            z = g["mantovana_livello"] * h_i
            sbalzo, salita = 1.5 * math.cos(math.radians(20)), 1.5 * math.sin(math.radians(20))
            for k in range(lato.campate):
                a, b = stilate[k], stilate[k + 1]
                faccia([pt(a, esterno, z), pt(b, esterno, z), pt(b, esterno + sbalzo, z + salita),
                        pt(a, esterno + sbalzo, z + salita)], "mantovana")
        for stilata, livello in P.posizioni_ancoraggi(lato, g):
            z = livello * h_i - 0.3
            linea(pt(stilate[stilata], interno, z), pt(stilate[stilata], 0, z), "ancoraggio")
    if edificio and g["forma"] == "chiusa":
        h_tetto = max(max(l.altezza, l.livelli * h_i) for l in lati) + 0.6
        n_lato = -1
        faccia([(o[0], o[1], h_tetto) for o, _ in _percorso(g)], "tetto")
    return prim


# --- proiezione e disegno 3D ---

def _proietta(p, rotazione: float, inclinazione: float) -> tuple[float, float, float]:
    """(x schermo, y schermo verso l'alto, profondità: più grande = più lontano)."""
    t, f = math.radians(rotazione), math.radians(inclinazione)
    x1 = p[0] * math.cos(t) - p[1] * math.sin(t)
    y1 = p[0] * math.sin(t) + p[1] * math.cos(t)
    return x1, y1 * math.sin(f) + p[2] * math.cos(f), y1 * math.cos(f) - p[2] * math.sin(f)


def disegna_3d(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], vista: Vista3D | None = None,
               g: dict[str, Any] | None = None) -> None:
    vista = vista or Vista3D()
    g = g or P.geometria(ponteggio)
    prim = modello(ponteggio, g, vista.mostra_edificio)
    if not prim:
        return
    proiettate = [[_proietta(p, vista.rotazione, vista.inclinazione) for p in pr.punti] for pr in prim]
    xs = [q[0] for pp in proiettate for q in pp]
    ys = [q[1] for pp in proiettate for q in pp]
    larghezza, altezza = max(max(xs) - min(xs), 1e-3), max(max(ys) - min(ys), 1e-3)
    scala = min((area.width() - 40) / larghezza, (area.height() - 40) / altezza) * vista.zoom
    cx = area.center().x() - (min(xs) + larghezza / 2) * scala + vista.spostamento[0]
    cy = area.center().y() + (min(ys) + altezza / 2) * scala + vista.spostamento[1]

    def schermo(q) -> QPointF:
        return QPointF(cx + q[0] * scala, cy - q[1] * scala)

    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    _terreno_3d(pittore, ponteggio, g, vista, schermo)
    # Ordine di disegno: prima i ponteggi dei lati che danno le spalle a chi guarda (stanno dietro l'edificio),
    # poi i muri, poi i ponteggi dei lati rivolti verso chi guarda; in ogni gruppo dal più lontano al più vicino.
    t = math.radians(vista.rotazione)
    verso_chi_guarda = [d[1] * math.sin(t) - d[0] * math.cos(t) < 0 for _, d in _percorso(g)]

    def gruppo(pr: Primitiva) -> float:
        if pr.stile == "tetto":
            return 2.5
        if pr.stile == "muro":
            return 2 if verso_chi_guarda[pr.lato] else 1
        return 3 if verso_chi_guarda[pr.lato] else 0

    ordine = sorted(range(len(prim)), key=lambda i: (gruppo(prim[i]),
                                                     -sum(q[2] for q in proiettate[i]) / len(proiettate[i])))
    spessore = max(0.6, min(2.0, scala / 25))
    for i in ordine:
        pr, pp = prim[i], proiettate[i]
        if pr.tipo == "faccia":
            colore = QColor(COLORI[pr.stile])
            colore.setAlpha(235 if pr.stile in ("muro", "tetto") else 215)
            pittore.setBrush(colore)
            pittore.setPen(QPen(QColor(COLORI["bordo_muro"] if pr.stile in ("muro", "tetto") else "#9C7F4E"), 0.6))
            pittore.drawPolygon(QPolygonF([schermo(q) for q in pp]))
        else:
            pittore.setPen(QPen(QColor(COLORI[pr.stile]), SPESSORI.get(pr.stile, 1.0) * spessore,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            pittore.drawLine(schermo(pp[0]), schermo(pp[1]))
            if pr.stile == "ancoraggio":
                pittore.setBrush(QColor(COLORI["ancoraggio"]))
                pittore.drawEllipse(schermo(pp[1]), 2.2 * spessore, 2.2 * spessore)
    pittore.restore()


def _terreno_3d(pittore, ponteggio, g, vista: Vista3D, schermo) -> None:
    punti = []
    for (origine, direzione), dati in zip(_percorso(g), g["lati"]):
        punti.append(_punto(origine, direzione, 0, g["distanza"] + g["larghezza"] + 1.5, 0))
        punti.append(_punto(origine, direzione, dati["lunghezza"], g["distanza"] + g["larghezza"] + 1.5, 0))
    if len(g["lati"]) == 1:
        o, d = _percorso(g)[0]
        punti += [_punto(o, d, g["lati"][0]["lunghezza"], -3, 0), _punto(o, d, 0, -3, 0)]
    colore = QColor(COLORI["terreno"])
    colore.setAlpha(40)
    pittore.setBrush(colore)
    pittore.setPen(Qt.PenStyle.NoPen)
    pittore.drawPolygon(QPolygonF([schermo(_proietta(p, vista.rotazione, vista.inclinazione)) for p in punti]))


# --- disegni in 2D ---

def _font(pittore: QPainter, pixel: float, grassetto: bool = False) -> None:
    f = QFont("Segoe UI")
    f.setPixelSize(max(8, round(pixel)))
    f.setBold(grassetto)
    pittore.setFont(f)


def _m(valore: float) -> str:
    return f"{valore:.2f}".replace(".", ",")


def _titolo(pittore: QPainter, area: QRectF, testo: str, sottotitolo: str = "") -> float:
    base = min(area.width(), area.height())
    _font(pittore, base / 32 + 4, True)
    pittore.setPen(QColor(COLORI["testo"]))
    pittore.drawText(QRectF(area.left() + 10, area.top() + 6, area.width() - 20, base / 18 + 8),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, testo)
    alto = area.top() + base / 18 + 14
    if sottotitolo:
        _font(pittore, base / 45 + 3)
        pittore.setPen(QColor(COLORI["quota"]))
        pittore.drawText(QRectF(area.left() + 10, alto - 4, area.width() - 20, base / 25 + 6),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sottotitolo)
        alto += base / 25 + 4
    return alto


def _alto_titolo(area: QRectF) -> float:
    base = min(area.width(), area.height())
    return area.top() + base / 18 + 14 + base / 25 + 4


def _scala_prospetto(area: QRectF, lato: P.Lato, g: dict[str, Any]) -> tuple[float, float, float, float, float]:
    """Origine (piede della prima stilata), scala in pixel per metro e margini del prospetto."""
    alto = _alto_titolo(area)
    lunghezza = lato.campate * g["campata"]
    cima = lato.livelli * g["interpiano"] + P.ALTEZZA_PARAPETTO
    margine_s, margine_b = area.width() * 0.09 + 20, area.height() * 0.08 + 18
    disegno = QRectF(area.left() + margine_s, alto + 8, area.width() - margine_s - 20, area.bottom() - margine_b - alto - 8)
    scala = max(1e-3, min(disegno.width() / lunghezza, disegno.height() / (cima + 0.4)))
    x0 = disegno.left() + (disegno.width() - lunghezza * scala) / 2
    y0 = disegno.top() + (cima + 0.2) * scala
    return x0, y0, scala, margine_s, margine_b


def nodo_prospetto(area: QRectF, ponteggio: dict[str, Any], indice: int, x: float, y: float,
                   g: dict[str, Any] | None = None) -> tuple[int, int] | None:
    """Stilata e livello del punto di ancoraggio più vicino al clic sul prospetto (None se troppo lontano)."""
    g = g or P.geometria(ponteggio)
    lati = P.lati(ponteggio, g)
    lato = lati[min(max(indice, 0), len(lati) - 1)]
    x0, y0, scala, _, _ = _scala_prospetto(area, lato, g)
    stilata = round((x - x0) / scala / g["campata"])
    livello = round(((y0 - y) / scala + 0.3) / g["interpiano"])
    if not (0 <= stilata <= lato.campate and 1 <= livello <= lato.livelli):
        return None
    dx = x - (x0 + stilata * g["campata"] * scala)
    dy = y - (y0 - (livello * g["interpiano"] - 0.3) * scala)
    return (stilata, livello) if math.hypot(dx, dy) <= max(12.0, 0.45 * g["campata"] * scala) else None


def disegna_prospetto(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], indice: int = 0,
                      g: dict[str, Any] | None = None) -> None:
    g = g or P.geometria(ponteggio)
    lati = P.lati(ponteggio, g)
    indice = min(max(indice, 0), len(lati) - 1)
    lato = lati[indice]
    h_i = g["interpiano"]
    lunghezza = lato.campate * g["campata"]
    cima = lato.livelli * h_i + P.ALTEZZA_PARAPETTO
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    _titolo(pittore, area, f"Prospetto · {lato.nome}",
            f"{lato.campate} campate da {_m(g['campata'])} m · {lato.livelli} impalcati ogni {_m(h_i)} m · "
            f"{(ponteggio.get('tipo') or 'telai prefabbricati').lower()} · ancoraggi in rosso")
    x0, y0, scala, margine_s, margine_b = _scala_prospetto(area, lato, g)

    def pt(s: float, z: float) -> QPointF:
        return QPointF(x0 + s * scala, y0 - z * scala)

    spessore = max(0.8, min(2.4, scala / 18))
    # terreno
    pittore.setPen(QPen(QColor(COLORI["terreno"]), spessore * 1.5))
    pittore.drawLine(pt(-0.6, 0), pt(lunghezza + 0.6, 0))
    tratteggio = QBrush(QColor(COLORI["terreno"]), Qt.BrushStyle.BDiagPattern)
    pittore.fillRect(QRectF(pt(-0.6, 0), pt(lunghezza + 0.6, -0.25)), tratteggio)
    stilate = [k * g["campata"] for k in range(lato.campate + 1)]
    facciata = -P.inizio(lato, g)
    pittore.fillRect(QRectF(pt(facciata, lato.altezza), pt(facciata + lato.lunghezza, 0)), QColor("#EFECE6"))
    # impalcati, parapetti, diagonali
    for livello in range(1, lato.livelli + 1):
        z = livello * h_i
        pittore.setPen(QPen(QColor(COLORI["impalcato"]), spessore * 2.4))
        pittore.drawLine(pt(0, z), pt(lunghezza, z))
        pittore.setPen(QPen(QColor(COLORI["parapetto"]), spessore))
        for quota in (0.5, 1.0):
            pittore.drawLine(pt(0, z + quota), pt(lunghezza, z + quota))
        pittore.setPen(QPen(QColor(COLORI["diagonale"]), spessore * 0.8))
        for k in range(0, lato.campate, 5):
            a, b = stilate[k], stilate[k + 1]
            basso, alto_ = (a, b) if livello % 2 else (b, a)
            pittore.drawLine(pt(basso, z - h_i), pt(alto_, z))
    # montanti e basette
    pittore.setPen(QPen(QColor(COLORI["montante"]), spessore * 1.6))
    for s in stilate:
        pittore.drawLine(pt(s, 0), pt(s, cima))
        pittore.fillRect(QRectF(pt(s - 0.12, 0.08), pt(s + 0.12, 0)), QColor(COLORI["montante"]))
    tipo = ponteggio.get("tipo") or ""
    if tipo in ("Tubi e giunti", "Multidirezionale"):
        pittore.setPen(QPen(QColor(COLORI["montante"]), spessore * 0.8))
        pittore.setBrush(QColor("#FFFFFF") if tipo == "Multidirezionale" else QColor(COLORI["montante"]))
        lato_simbolo = max(2.0, min(6.0, scala * 0.09))
        for s in stilate:
            quote = ([livello * h_i + q for livello in range(1, lato.livelli + 1) for q in (0, 0.5, 1.0)]
                     if tipo == "Tubi e giunti" else [k * 0.5 for k in range(1, int(cima / 0.5) + 1)])
            for z in quote:
                c = pt(s, z)
                if tipo == "Tubi e giunti":  # giunti ai nodi
                    pittore.drawRect(QRectF(c.x() - lato_simbolo, c.y() - lato_simbolo, 2 * lato_simbolo,
                                            2 * lato_simbolo))
                else:  # rosette ogni 50 cm
                    pittore.drawEllipse(c, lato_simbolo, lato_simbolo)
        pittore.setBrush(Qt.BrushStyle.NoBrush)
    # mantovana
    if lato.mantovana and g["mantovana_livello"] <= lato.livelli:
        z = g["mantovana_livello"] * h_i
        pittore.setPen(QPen(QColor(COLORI["mantovana"]), spessore * 1.4, Qt.PenStyle.DashLine))
        pittore.drawLine(pt(0, z + 0.35), pt(lunghezza, z + 0.35))
        _font(pittore, max(9, scala * 0.35))
        pittore.drawText(pt(lunghezza * 0.02, z + 0.45), "mantovana parasassi")
    # ancoraggi
    pittore.setPen(QPen(QColor(COLORI["ancoraggio"]), spessore))
    pittore.setBrush(QColor(COLORI["ancoraggio"]))
    raggio = max(2.5, min(7.0, scala * 0.14))
    for stilata, livello in P.posizioni_ancoraggi(lato, g):
        pittore.drawEllipse(pt(stilate[stilata], livello * h_i - 0.3), raggio, raggio)
    pittore.setBrush(Qt.BrushStyle.NoBrush)
    pittore.setPen(QPen(QColor("#9AA3AD"), spessore, Qt.PenStyle.DashLine))
    for stilata, livello in lato.tolti:  # tolti a mano: si vedono per poterli rimettere
        if stilata <= lato.campate and livello <= lato.livelli:
            pittore.drawEllipse(pt(stilate[stilata], livello * h_i - 0.3), raggio, raggio)
    # quote
    pittore.setBrush(Qt.BrushStyle.NoBrush)
    _font(pittore, max(11, min(20, scala * 0.4)))
    pittore.setPen(QColor(COLORI["quota"]))
    for livello in range(0, lato.livelli + 1):
        z = livello * h_i
        pittore.drawText(QRectF(area.left() + 4, pt(0, z).y() - 9, margine_s - 14, 18),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"+{_m(z)}")
    y_quota = pt(0, 0).y() + margine_b * 0.45
    pittore.drawLine(QPointF(pt(0, 0).x(), y_quota), QPointF(pt(lunghezza, 0).x(), y_quota))
    for s in (0, lunghezza):
        pittore.drawLine(QPointF(pt(s, 0).x(), y_quota - 5), QPointF(pt(s, 0).x(), y_quota + 5))
    pittore.drawText(QRectF(pt(0, 0).x(), y_quota + 2, lunghezza * scala, margine_b * 0.5),
                     Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                     f"{_m(lunghezza)} m (facciata {_m(lato.lunghezza)} m)")
    pittore.restore()


def disegna_pianta(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> None:
    g = g or P.geometria(ponteggio)
    lati = P.lati(ponteggio, g)
    percorso = _percorso(g)
    interno, esterno = g["distanza"], g["distanza"] + g["larghezza"]
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    alto = _titolo(pittore, area, "Pianta del ponteggio",
                   f"Sviluppo {_m(P.sviluppo(g))} m · larghezza {_m(g['larghezza'])} m · distanza dalla facciata "
                   f"{_m(g['distanza'])} m")
    punti = []
    for (o, d), lato in zip(percorso, lati):
        for s in (P.inizio(lato, g), P.inizio(lato, g) + lato.campate * g["campata"]):
            for off in (-1.0, esterno + 0.8):
                punti.append(_punto(o, d, s, off, 0))
    xs, ys = [p[0] for p in punti], [p[1] for p in punti]
    w, h = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
    disegno = QRectF(area.left() + 20, alto + 10, area.width() - 40, area.bottom() - alto - 30)
    scala = min(disegno.width() / w, disegno.height() / h)
    x0 = disegno.left() + (disegno.width() - w * scala) / 2 - min(xs) * scala
    y0 = disegno.top() + (disegno.height() - h * scala) / 2 + max(ys) * scala

    def pt(p) -> QPointF:
        return QPointF(x0 + p[0] * scala, y0 - p[1] * scala)

    # edificio: la linea delle facciate (chiusa se il perimetro è chiuso)
    contorno = [pt(o) for o, _ in percorso] + [pt(_punto(*percorso[-1], g["lati"][-1]["lunghezza"], 0, 0))]
    percorso_edificio = QPainterPath()
    percorso_edificio.addPolygon(QPolygonF(contorno))
    if g["forma"] == "chiusa":
        percorso_edificio.closeSubpath()
        pittore.fillPath(percorso_edificio, QBrush(QColor(COLORI["muro"]), Qt.BrushStyle.SolidPattern))
        pittore.fillPath(percorso_edificio, QBrush(QColor(COLORI["bordo_muro"]), Qt.BrushStyle.BDiagPattern))
    pittore.setPen(QPen(QColor("#555046"), max(2.0, scala * 0.12)))
    pittore.setBrush(Qt.BrushStyle.NoBrush)
    pittore.drawPath(percorso_edificio)
    spessore = max(0.8, min(2.0, scala / 20))
    _font(pittore, max(11, min(22, scala * 0.5)))
    for (o, d), lato in zip(percorso, lati):
        a = P.inizio(lato, g)
        b = a + lato.campate * g["campata"]
        fascia = QPolygonF([pt(_punto(o, d, a, interno, 0)), pt(_punto(o, d, b, interno, 0)),
                            pt(_punto(o, d, b, esterno, 0)), pt(_punto(o, d, a, esterno, 0))])
        colore = QColor(COLORI["impalcato"])
        colore.setAlpha(170)
        pittore.setBrush(colore)
        pittore.setPen(QPen(QColor(COLORI["montante"]), spessore))
        pittore.drawPolygon(fascia)
        for k in range(lato.campate + 1):
            s = a + k * g["campata"]
            pittore.drawLine(pt(_punto(o, d, s, interno, 0)), pt(_punto(o, d, s, esterno, 0)))
        pittore.setBrush(QColor(COLORI["ancoraggio"]))
        pittore.setPen(Qt.PenStyle.NoPen)
        for stilata in sorted({s for s, _ in P.posizioni_ancoraggi(lato, g)}):
            pittore.drawEllipse(pt(_punto(o, d, a + stilata * g["campata"], interno / 2, 0)), spessore * 2.2,
                                spessore * 2.2)
        pittore.setPen(QColor(COLORI["testo"]))
        centro = pt(_punto(o, d, lato.lunghezza / 2, esterno + 0.6, 0))
        pittore.save()
        pittore.translate(centro)
        angolo = -math.degrees(math.atan2(d[1], d[0]))
        if angolo > 90 or angolo <= -90:
            angolo += 180
        pittore.rotate(angolo)
        pittore.drawText(QRectF(-200, -2, 400, 24), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                         f"{lato.nome} · {_m(lato.lunghezza)} m")
        pittore.restore()
    pittore.restore()


def disegna_sezione(pittore: QPainter, area: QRectF, ponteggio: dict[str, Any], g: dict[str, Any] | None = None) -> None:
    g = g or P.geometria(ponteggio)
    lati = P.lati(ponteggio, g)
    lato = max(lati, key=lambda l: l.livelli)
    h_i = g["interpiano"]
    interno, esterno = g["distanza"], g["distanza"] + g["larghezza"]
    cima = lato.livelli * h_i + P.ALTEZZA_PARAPETTO
    pittore.save()
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    alto = _titolo(pittore, area, "Sezione tipo", "Larghezze amplificate due volte rispetto alle altezze")
    sinistra, destra = -0.6, esterno + 2.0
    disegno = QRectF(area.left() + 70, alto + 10, area.width() - 90, area.bottom() - alto - 40)
    sy = min(disegno.height() / (cima + 0.6), disegno.width() / ((destra - sinistra) * 2))
    sx = sy * 2
    x0 = disegno.left() + (disegno.width() - (destra - sinistra) * sx) / 2 - sinistra * sx
    y0 = disegno.top() + (cima + 0.3) * sy

    def pt(x: float, z: float) -> QPointF:
        return QPointF(x0 + x * sx, y0 - z * sy)

    spessore = max(0.8, min(2.4, sy / 16))
    pittore.fillRect(QRectF(pt(sinistra, cima + 0.2), pt(0, 0)), QBrush(QColor(COLORI["muro"])))
    pittore.fillRect(QRectF(pt(sinistra, cima + 0.2), pt(0, 0)), QBrush(QColor(COLORI["bordo_muro"]),
                                                                          Qt.BrushStyle.BDiagPattern))
    pittore.setPen(QPen(QColor(COLORI["terreno"]), spessore * 1.5))
    pittore.drawLine(pt(sinistra, 0), pt(destra, 0))
    pittore.setPen(QPen(QColor(COLORI["montante"]), spessore * 1.6))
    for x in (interno, esterno):
        pittore.drawLine(pt(x, 0), pt(x, cima))
    livelli_ancorati = {l for _, l in P.posizioni_ancoraggi(lato, g)}
    _font(pittore, max(11, min(20, sy * 0.4)))
    for livello in range(1, lato.livelli + 1):
        z = livello * h_i
        pittore.setPen(QPen(QColor(COLORI["impalcato"]), spessore * 3))
        pittore.drawLine(pt(interno, z), pt(esterno, z))
        pittore.setPen(QPen(QColor(COLORI["parapetto"]), spessore))
        for quota in (0.5, 1.0):
            pittore.drawLine(pt(esterno, z + quota), pt(esterno + 0.05, z + quota))
            pittore.drawEllipse(pt(esterno + 0.03, z + quota), spessore * 1.6, spessore * 1.6)
            if g["distanza"] > P.DISTANZA_MASSIMA:
                pittore.drawEllipse(pt(interno - 0.03, z + quota), spessore * 1.6, spessore * 1.6)
        if livello in livelli_ancorati:
            pittore.setPen(QPen(QColor(COLORI["ancoraggio"]), spessore * 1.6))
            pittore.drawLine(pt(-0.25, z - 0.3), pt(interno, z - 0.3))
        pittore.setPen(QColor(COLORI["quota"]))
        pittore.drawText(QRectF(area.left() + 2, pt(0, z).y() - 9, 62, 18),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"+{_m(z)}")
    if lato.mantovana and g["mantovana_livello"] <= lato.livelli:
        z = g["mantovana_livello"] * h_i
        pittore.setPen(QPen(QColor(COLORI["mantovana"]), spessore * 1.6))
        a = math.radians(20)
        pittore.drawLine(pt(esterno, z), pt(esterno + 1.5 * math.cos(a), z + 1.5 * math.sin(a)))
    pittore.setPen(QColor(COLORI["quota"]))
    base = pt(0, 0).y() + 14
    pittore.drawText(QRectF(pt(0, 0).x() - 40, base, (esterno * sx) + 80, 18), Qt.AlignmentFlag.AlignHCenter,
                     f"distanza {_m(interno)} · larghezza {_m(g['larghezza'])} m")
    pittore.restore()


# --- immagini per il documento ---

def disegna(pittore: QPainter, area: QRectF, tipo: str, ponteggio: dict[str, Any], indice: int = 0,
            vista: Vista3D | None = None, g: dict[str, Any] | None = None) -> None:
    if tipo == TRE_D:
        _titolo(pittore, area, "Vista d'insieme", "Schema tridimensionale · ancoraggi in rosso")
        disegna_3d(pittore, area.adjusted(0, area.height() * 0.08, 0, 0), ponteggio, vista, g)
    elif tipo == PIANTA:
        disegna_pianta(pittore, area, ponteggio, g)
    elif tipo == SEZIONE:
        disegna_sezione(pittore, area, ponteggio, g)
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
    """Disegni da inserire nel PiMUS: vista d'insieme, pianta, prospetto di ogni lato e sezione tipo."""
    from sicurcantiere.documenti.immagini import png

    g = P.geometria(ponteggio)
    risultato = [Tavola("Vista d'insieme", png(immagine(TRE_D, ponteggio))),
                 Tavola("Pianta", png(immagine(PIANTA, ponteggio)))]
    for n, lato in enumerate(g["lati"]):
        risultato.append(Tavola(f"Prospetto · {lato['nome']}", png(immagine(PROSPETTO, ponteggio, indice=n))))
    risultato.append(Tavola("Sezione tipo", png(immagine(SEZIONE, ponteggio, 1100, 1500)), orizzontale=False))
    return risultato
