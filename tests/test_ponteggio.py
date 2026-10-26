"""Geometria, ancoraggi, carichi, elementi e squadra del ponteggio; PiMUS con disegni e allegati."""

import json
import sqlite3
from datetime import date

import pytest
from docx import Document

from sicurcantiere import pimus
from sicurcantiere import ponteggio as P
from sicurcantiere.db import MIGRAZIONI, Progetto
from sicurcantiere.repository import Repository


@pytest.fixture
def repo(tmp_path):
    progetto = Progetto(tmp_path / "p.spm", crea=True)
    yield Repository(progetto)
    progetto.chiudi()


def _ponteggio(**geometria):
    g = {"lati": [{"nome": "Nord", "lunghezza": 18}, {"nome": "Est", "lunghezza": 9, "altezza": 8}], **geometria}
    return {"id": 1, "nome": "Facciate", "altezza": 12, "lunghezza": 0, "tipo": "Telai prefabbricati",
            "classe_carico": P.CLASSI_CARICO[3][0], "conforme_schemi": 1, "autorizzazione": "x", "impresa_id": 1,
            "preposto": "", "progettista": "", "geometria": json.dumps(g)}


def test_geometria_predefinita_e_lati():
    p = _ponteggio()
    g = P.geometria(p)
    assert g["campata"] == 1.8 and g["interpiano"] == 2.0 and len(g["lati"]) == 2
    nord, est = P.lati(p, g)
    assert (nord.campate, nord.livelli) == (10, 6)  # 18 / 1,80 e 12 / 2,00
    assert (est.campate, est.livelli, est.altezza) == (5, 4, 8)
    assert P.sviluppo(g) == 27
    # senza geometria: un lato con lo sviluppo e il nome del ponteggio
    vecchio = P.geometria({"nome": "Sud", "lunghezza": 14, "geometria": "{}"})
    assert vecchio["lati"][0]["nome"] == "Sud" and vecchio["lati"][0]["lunghezza"] == 14
    assert P.geometria({"geometria": "non json"})["campata"] == 1.8


def test_ancoraggi_schema_e_modifiche_a_mano():
    p = _ponteggio()
    g = P.geometria(p)
    nord = P.lati(p, g)[0]
    schema = P.schema_ancoraggi(nord, g)
    assert (0, 2) in schema and (10, 2) in schema  # testate
    assert (1, 4) in schema and (1, 2) not in schema  # file sfalsate a rombo
    assert all(l in (2, 4, 6) for _, l in schema)  # ogni 2 livelli, sempre l'ultimo
    g = P.cambia_ancoraggio(g, p, 0, 3, 1)  # aggiunto
    g = P.cambia_ancoraggio(g, p, 0, 0, 2)  # tolto
    p["geometria"] = P.testo_geometria(g)
    g = P.geometria(p)
    nord = P.lati(p, g)[0]
    posizioni = P.posizioni_ancoraggi(nord, g)
    assert (3, 1) in posizioni and (0, 2) not in posizioni
    g = P.cambia_ancoraggio(g, p, 0, 0, 2)  # rimesso
    assert g["lati"][0]["tolti"] == []
    a = P.ancoraggi(p)
    assert a.numero > 10 and 0 < a.area_per_ancoraggio <= P.AREA_PER_ANCORAGGIO


def test_carico_sul_piano_di_appoggio():
    p = _ponteggio(terreno=100, area_appoggio=0.15, peso_proprio=0.3)
    s = P.appoggio(p)
    # peso 0,30 × 1,80 × 13 / 2 = 3,51; servizio 3,00 × 1,80 × 1,05 / 2 × 1,5 = 4,25
    assert s.carico_montante == pytest.approx(7.76, abs=0.01)
    assert s.pressione == pytest.approx(51.8, abs=0.1) and s.verificato
    debole = _ponteggio(terreno=20, area_appoggio=0.05)
    assert not P.appoggio(debole).verificato
    assert any("Piano di appoggio" in m for m in P.avvisi_geometria(debole))
    assert P.sovraccarico("Classe 2") == 1.5 and P.sovraccarico("boh") == 0


def test_elementi_per_tipologia():
    p = _ponteggio()
    voci = dict((n, q) for n, q, _ in P.elementi(p))
    assert voci["Telai (stilate × livelli)"] == 11 * 6 + 6 * 4
    assert voci["Basette regolabili"] == (11 + 6) * 2
    assert voci["Ancoraggi"] == P.ancoraggi(p).numero
    assert "Mantovana parasassi" in voci
    p["tipo"] = "Tubi e giunti"
    assert "Giunti ortogonali" in dict((n, q) for n, q, _ in P.elementi(p))
    p["geometria"] = json.dumps({"mantovana": False, "lati": [{"nome": "A", "lunghezza": 5}]})
    assert "Mantovana parasassi" not in dict((n, q) for n, q, _ in P.elementi(p))


def test_avvisi_geometria():
    assert any("parapetto anche sul lato interno" in m for m in P.avvisi_geometria(_ponteggio(distanza=0.35)))
    assert any("teli" in m for m in P.avvisi_geometria(_ponteggio(teli=True)))
    assert any("Ancoraggi" in m for m in P.avvisi_geometria(_ponteggio(ancoraggi_campate=6, ancoraggi_livelli=4)))
    assert P.avvisi_geometria(_ponteggio()) == []
    # un lato più alto di 20 m richiede il progetto anche se l'altezza del ponteggio è minore
    alto = _ponteggio(lati=[{"nome": "Torre", "lunghezza": 6, "altezza": 24}])
    assert any("art. 133" in m for m in pimus.avvisi(alto))


def test_formazione_della_squadra():
    oggi = date(2026, 10, 26)
    valido = {"nome": "Luca", "ruolo": P.PREPOSTO, "corso_data": "2020-03-01", "aggiornamento_data": "2024-02-01"}
    assert P.scadenza_formazione(valido) == date(2028, 2, 1)
    assert P.stato_formazione(valido, oggi) == "Valida"
    scaduto = {"nome": "Mario", "ruolo": P.ADDETTO, "corso_data": "2021-01-10", "aggiornamento_data": None}
    assert P.stato_formazione(scaduto, oggi) == "Aggiornamento scaduto"
    assert P.stato_formazione({"corso_data": "2022-12-01"}, oggi) == "In scadenza"
    assert P.stato_formazione({"corso_data": None}, oggi) == "Corso da indicare"
    messaggi = P.avvisi_squadra([valido, scaduto], oggi)
    assert len(messaggi) == 1 and "Mario" in messaggi[0] and "10/01/2025" in messaggi[0]
    assert any("preposto" in m for m in P.avvisi_squadra([scaduto], oggi))


def test_migrazione_porta_preposto_e_squadra(tmp_path):
    percorso = tmp_path / "vecchio.spm"
    conn = sqlite3.connect(percorso)
    for n, sql in enumerate(MIGRAZIONI[:-1], 1):
        conn.executescript(f"BEGIN;{sql};PRAGMA user_version = {n};COMMIT;")
    conn.execute("INSERT INTO ponteggi (nome, preposto, squadra) VALUES ('Nord', 'Luca Bianchi', 'Mario, Gino')")
    conn.commit()
    conn.close()
    progetto = Progetto(percorso)
    repo = Repository(progetto)
    addetti = repo.elenco("addetti_ponteggio")
    assert [(a["nome"], a["ruolo"]) for a in addetti] == [("Luca Bianchi", P.PREPOSTO), ("Mario, Gino", P.ADDETTO)]
    assert repo.elenco("ponteggi")[0]["geometria"] == "{}"
    progetto.chiudi()


def test_pimus_con_squadra_disegni_e_allegati(repo, tmp_path):
    from PySide6.QtGui import QColor, QImage

    from sicurcantiere.documenti.pimus import genera_pimus

    repo.aggiorna_cantiere(nome="Scuola", indirizzo="Via Roma 1", comune="Bari")
    impresa = repo.inserisci("imprese", ragione_sociale="Edil Ponteggi", datore_lavoro="Anna Verdi")
    p = repo.inserisci("ponteggi", nome="Facciate", impresa_id=impresa, altezza=10,
                       classe_carico=P.CLASSI_CARICO[3][0], geometria=_ponteggio()["geometria"])
    repo.inserisci("addetti_ponteggio", ponteggio_id=p, nome="Luca Bianchi", ruolo=P.PREPOSTO,
                   corso_data="2024-05-10", corso_ente="Scuola Edile")
    repo.inserisci("addetti_ponteggio", ponteggio_id=p, nome="Mario Rossi", corso_data="2023-01-15")
    immagine = tmp_path / "disegno esecutivo.png"
    img = QImage(40, 30, QImage.Format.Format_RGB32)
    img.fill(QColor("#336699"))
    img.save(str(immagine))
    repo.inserisci("allegati_ponteggio", ponteggio_id=p, tipo="Disegno esecutivo", titolo="Tavola 1",
                   file=str(immagine))
    repo.inserisci("allegati_ponteggio", ponteggio_id=p, tipo="Libretto del fabbricante", titolo="Libretto",
                   file=str(tmp_path / "manca.pdf"))
    file = genera_pimus(repo, p, tmp_path / "pimus.docx")
    doc = Document(file)
    testo = "\n".join([x.text for x in doc.paragraphs]
                      + [c.text for t in doc.tables for r in t.rows for c in r.cells])
    assert "Luca Bianchi" in testo and "Scuola Edile" in testo and "10/05/2028" in testo
    assert "Telai (stilate × livelli)" in testo and "ancoraggi" in testo
    assert "Verifica dell'appoggio" in testo and "verificata" in testo
    assert "Prospetto · Nord" in testo and "Sezione tipo" in testo
    assert "Allegato 1 · Disegno esecutivo" in testo and "File non trovato" in testo
    # vista d'insieme, pianta, 2 prospetti, sezione e il disegno allegato
    assert len(doc.inline_shapes) >= 6
