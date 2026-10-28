"""Esportazione del ponteggio in DXF per i programmi CAD.

Due file possibili, in metri, nel formato DXF R12 (AC1009) che leggono tutti i CAD:
- modello 3D: linee e facce (3DFACE) del modello tridimensionale, su un layer per tipo di elemento
  (montanti, impalcati, parapetti, ancoraggi, mantovane, teli, muri...);
- tavole 2D: pianta, prospetto di ogni tratto e sezione tipo, affiancati sul piano con titoli e quote,
  da completare in CAD come disegno esecutivo.

Il file si scrive senza librerie esterne: sezioni HEADER, TABLES (tipi di linea e layer), ENTITIES.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from sicurcantiere import disegno_ponteggio as D
from sicurcantiere import ponteggio as P

MODELLO_3D, TAVOLE_2D = "3d", "2d"

# stile del disegno -> (layer, colore AutoCAD)
LAYER: dict[str, tuple[str, int]] = {
    "montante": ("PONT_MONTANTI", 5),
    "traverso": ("PONT_TRAVERSI", 8),
    "corrente": ("PONT_CORRENTI", 8),
    "parapetto": ("PONT_PARAPETTI", 30),
    "diagonale": ("PONT_DIAGONALI", 9),
    "impalcato": ("PONT_IMPALCATI", 42),
    "legno": ("PONT_TAVOLATI", 33),
    "botola": ("PONT_BOTOLE", 35),
    "ancoraggio": ("PONT_ANCORAGGI", 1),
    "mantovana": ("PONT_MANTOVANE", 4),
    "scala": ("PONT_SCALE", 34),
    "telo": ("PONT_TELI", 3),
    "tabellone": ("PONT_TABELLONI", 150),
    "tubi": ("PONT_TUBI_GIUNTI", 32),
    "torre": ("PONT_TORRI", 8),
    "trave": ("PONT_TRAVI", 5),
    "copertura": ("PONT_COPERTURE", 9),
    "macchina": ("PONT_SOLLEVAMENTO", 250),
    "terra": ("PONT_MESSA_A_TERRA", 3),
    "segnale": ("PONT_SEGNALETICA", 2),
    "muro": ("EDIFICIO", 253),
    "tetto": ("EDIFICIO", 253),
}
TESTI = ("TESTI", 7)
QUOTE = ("QUOTE", 7)


class Dxf:
    """Raccolta delle entità e scrittura del file."""

    def __init__(self) -> None:
        self.entita: list[str] = []
        self.layer: dict[str, int] = {}

    def _usa(self, layer: tuple[str, int]) -> str:
        self.layer.setdefault(layer[0], layer[1])
        return layer[0]

    def linea(self, layer: tuple[str, int], a, b) -> None:
        a, b = (*a, 0.0)[:3], (*b, 0.0)[:3]
        self.entita.append(f"0\nLINE\n8\n{self._usa(layer)}\n10\n{a[0]:.4f}\n20\n{a[1]:.4f}\n30\n{a[2]:.4f}\n"
                           f"11\n{b[0]:.4f}\n21\n{b[1]:.4f}\n31\n{b[2]:.4f}\n")

    def faccia(self, layer: tuple[str, int], punti: list) -> None:
        punti = [(*p, 0.0)[:3] for p in punti]
        if len(punti) < 3:
            return
        # 3DFACE ha 3 o 4 vertici: i poligoni più grandi si dividono a ventaglio
        gruppi = [punti] if len(punti) <= 4 else [[punti[0], punti[i], punti[i + 1]] for i in range(1, len(punti) - 1)]
        for g in gruppi:
            g = g + [g[-1]] * (4 - len(g))
            codici = "".join(f"1{n}\n{p[0]:.4f}\n2{n}\n{p[1]:.4f}\n3{n}\n{p[2]:.4f}\n" for n, p in enumerate(g))
            self.entita.append(f"0\n3DFACE\n8\n{self._usa(layer)}\n{codici}")

    def testo(self, layer: tuple[str, int], punto, testo: str, altezza: float = 0.3, rotazione: float = 0.0) -> None:
        testo = testo.replace("\n", " ")
        self.entita.append(f"0\nTEXT\n8\n{self._usa(layer)}\n10\n{punto[0]:.4f}\n20\n{punto[1]:.4f}\n30\n0.0\n"
                           f"40\n{altezza:.3f}\n1\n{testo}\n50\n{rotazione:.2f}\n")

    def scrivi(self, percorso: str | Path) -> Path:
        percorso = Path(percorso)
        layer = "".join(f"0\nLAYER\n2\n{nome}\n70\n0\n62\n{colore}\n6\nCONTINUOUS\n"
                        for nome, colore in sorted(self.layer.items()))
        testo = (
            "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n0\nENDSEC\n"
            "0\nSECTION\n2\nTABLES\n"
            "0\nTABLE\n2\nLTYPE\n70\n1\n0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nContinua\n72\n65\n73\n0\n40\n0.0\n0\nENDTAB\n"
            f"0\nTABLE\n2\nLAYER\n70\n{len(self.layer)}\n{layer}0\nENDTAB\n"
            "0\nENDSEC\n"
            "0\nSECTION\n2\nENTITIES\n" + "".join(self.entita) + "0\nENDSEC\n0\nEOF\n")
        # R12: testo ANSI; i caratteri fuori dalla codepage Windows-1252 diventano «?»
        percorso.write_bytes(testo.encode("cp1252", errors="replace"))
        return percorso


def _primitive(dxf: Dxf, prim: list[D.Primitiva], proietta: Callable | None = None,
               dx: float = 0.0, dy: float = 0.0) -> tuple[float, float, float, float]:
    """Aggiunge le primitive (proiettate in 2D se `proietta`) e restituisce l'ingombro xmin, ymin, xmax, ymax."""
    xs, ys = [], []
    for pr in prim:
        punti = [proietta(p)[:2] if proietta else p for p in pr.punti]
        punti = [(p[0] + dx, p[1] + dy, *p[2:]) for p in punti]
        xs += [p[0] for p in punti]
        ys += [p[1] for p in punti]
        layer = LAYER.get(pr.stile, ("PONT_ALTRO", 7))
        if pr.tipo == "faccia":
            dxf.faccia(layer, punti)
        else:
            dxf.linea(layer, punti[0], punti[1])
    if not xs:
        return 0, 0, 0, 0
    return min(xs), min(ys), max(xs), max(ys)


def esporta(ponteggio: dict[str, Any], percorso: str | Path, tipo: str = MODELLO_3D) -> Path:
    g = P.geometria(ponteggio)
    dxf = Dxf()
    if tipo == MODELLO_3D:
        _primitive(dxf, D.modello(ponteggio, g, True))
        for t in P.tratti(ponteggio, g):
            x, y, _ = t.punto(t.lunghezza / 2, t.distanza + t.larghezza + 1.0)
            dxf.testo(TESTI, (x, y), t.nome, 0.4)
        return dxf.scrivi(percorso)

    # tavole 2D: pianta in alto, poi i prospetti dei tratti uno sotto l'altro, la sezione a destra
    elenco = P.tratti(ponteggio, g)
    prim = [p for p in D.modello(ponteggio, g, True) if p.stile not in ("muro", "tetto")]
    x0, y0, x1, y1 = _primitive(dxf, prim, D._dall_alto)
    for t in elenco:  # facciate e nomi dei tratti
        dxf.linea(LAYER["muro"], t.origine, t.fine())
        x, y, _ = t.punto(t.lunghezza / 2, t.distanza + t.larghezza + 1.0)
        dxf.testo(TESTI, (x, y), f"{t.nome} - {t.lunghezza:g} m".replace(".", ","), 0.35)
    dxf.testo(TESTI, (x0, y1 + 1.5), "PIANTA DEL PONTEGGIO", 0.6)
    cursore = y0 - 4.0
    for t in elenco:
        prim_t = D.modello(ponteggio, g, True, solo=t.indice)
        proietta = D._frontale(t)
        altezza = t.quota + t.livelli * t.interpiano + P.ALTEZZA_PARAPETTO + 2.5
        dy = cursore - altezza
        bx0, _, bx1, _ = _primitive(dxf, prim_t, proietta, dx=x0 - t.inizio, dy=dy)
        dxf.linea(QUOTE, (bx0 - 0.6, dy + t.quota), (bx1 + 0.6, dy + t.quota))
        for livello in range(0, t.livelli + 1):
            z = t.quota + livello * t.interpiano
            dxf.testo(QUOTE, (bx0 - 2.2, dy + z), f"{z:+.2f}".replace(".", ","), 0.25)
        dxf.testo(TESTI, (bx0, dy + altezza - 0.6), f"PROSPETTO - {t.nome}", 0.5)
        cursore = dy - 3.0
    # sezione del tratto più alto, a destra della pianta
    t = max(elenco, key=lambda x: x.livelli)
    _primitive(dxf, D.modello(ponteggio, g, True, solo=t.indice), D._laterale(t, 1.0), dx=x1 + 6.0, dy=y0)
    dxf.testo(TESTI, (x1 + 6.0, y0 + t.livelli * t.interpiano + 3.0), f"SEZIONE TIPO - {t.nome}", 0.5)
    _cartiglio(dxf, ponteggio, x1 + 6.0, cursore)
    return dxf.scrivi(percorso)


def _cartiglio(dxf: Dxf, p: dict[str, Any], x: float, y: float) -> None:
    """Cartiglio del disegno esecutivo (dati e caselle per le firme), da completare in CAD."""
    righe = [
        ("PONTEGGIO", p.get("nome", "")),
        ("SISTEMA", " ".join(v for v in (p.get("fabbricante", ""), p.get("sistema", "")) if v)),
        ("AUTORIZZAZIONE", p.get("autorizzazione", "")),
        ("SOVRACCARICO", p.get("classe_carico", "")),
        ("PERSONA COMPETENTE / PROGETTISTA", p.get("progettista") or p.get("redattore", "")),
        ("RESPONSABILE DEL CANTIERE", ""),
        ("DATA", ""),
    ]
    larghezza, alto = 16.0, 1.0
    for n in range(len(righe) + 1):
        dxf.linea(QUOTE, (x, y - n * alto), (x + larghezza, y - n * alto))
    for xx in (x, x + 6.0, x + larghezza):
        dxf.linea(QUOTE, (xx, y), (xx, y - len(righe) * alto))
    for n, (etichetta, valore) in enumerate(righe):
        dxf.testo(TESTI, (x + 0.2, y - n * alto - 0.65), etichetta, 0.25)
        dxf.testo(TESTI, (x + 6.2, y - n * alto - 0.65), str(valore or ""), 0.3)
    dxf.testo(TESTI, (x, y + 0.4), "CARTIGLIO DEL DISEGNO ESECUTIVO", 0.4)
