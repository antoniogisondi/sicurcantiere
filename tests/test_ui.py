"""Prova di fumo dell'interfaccia (senza display)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    # In modalità offscreen Qt su Windows non trova da solo i caratteri di sistema.
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")

from sicurcantiere.archivio import LAVORAZIONI  # noqa: E402
from sicurcantiere.db import Progetto  # noqa: E402
from sicurcantiere.ui.finestra import FinestraPrincipale  # noqa: E402
from sicurcantiere.documenti.pos import chiave_testo  # noqa: E402
from sicurcantiere.repository import Repository  # noqa: E402
from sicurcantiere.ui.pagine import (  # noqa: E402
    PaginaCosti,
    PaginaDocumenti,
    PaginaFasi,
    PaginaImprese,
    PaginaInterferenze,
    PaginaSoggetti,
)

QDate = QtCore.QDate


@pytest.fixture(autouse=True)
def senza_dialoghi(monkeypatch):
    # I messaggi modali bloccherebbero il test.
    mb = QtWidgets.QMessageBox
    monkeypatch.setattr(mb, "warning", lambda *a, **k: mb.StandardButton.Ok)
    monkeypatch.setattr(mb, "critical", lambda *a, **k: mb.StandardButton.Ok)
    monkeypatch.setattr(mb, "question", lambda *a, **k: mb.StandardButton.Yes)
    monkeypatch.setattr(mb, "information", lambda *a, **k: mb.StandardButton.Ok)
    monkeypatch.setattr(mb, "exec", lambda self: mb.StandardButton.Save)  # «Modifiche non salvate»: Salva


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    a.setOrganizationName("SicurCantiereTest")
    a.setApplicationName("SicurCantiereTest")
    yield a
    # Distrugge i widget prima dell'uscita dell'interprete: lasciati al
    # garbage collector verrebbero liberati in ordine casuale (crash di Qt).
    for w in a.topLevelWidgets():
        w.close()
        w.deleteLater()
    a.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    a.processEvents()


def _pagina(finestra, classe):
    return next(pg for pg in finestra.pagine if isinstance(pg, classe))


def _colonna(tabella, campo):
    return next(i for i, c in enumerate(tabella.colonne) if c.campo == campo)


def test_apre_e_mostra_tutte_le_pagine(app, tmp_path):
    p = Progetto(tmp_path / "c.scs", crea=True)
    p.chiudi()
    f = FinestraPrincipale()
    f.apri_file(tmp_path / "c.scs")
    assert f.progetto is not None
    repo = f.pagine[0].repo
    a = repo.inserisci("imprese", ragione_sociale="Alfa")
    b = repo.inserisci("imprese", ragione_sociale="Beta")
    repo.importa_lavorazione(next(l for l in LAVORAZIONI if l["codice"] == "AL.21"))  # manodopera 50%
    for i in range(len(f.pagine)):
        f.navigazione.setCurrentRow(i)
        app.processEvents()

    fasi = _pagina(f, PaginaFasi)
    f.navigazione.setCurrentRow(f.pagine.index(fasi))
    t = fasi.fasi
    t.salva_cella(0, _colonna(t, "data_inizio"), "2025-10-06")
    t.salva_cella(0, _colonna(t, "data_fine"), "2025-10-01")  # fine prima dell'inizio: rifiutata
    assert repo.elenco("fasi")[0]["data_fine"] is None

    # Gantt analitico: 20.000 € x 50% / 250 = 40 ug, squadra 4 -> 10 giorni
    t.salva_cella(0, _colonna(t, "importo"), 20000.0)
    t.salva_cella(0, _colonna(t, "lavoratori"), 4)
    t.vista.selectRow(0)
    fasi._calcola_durata()
    assert repo.elenco("fasi")[0]["data_fine"] == "2025-10-17"
    assert fasi.dettaglio.isEnabled()
    n = len(fasi.rischi.righe())
    fasi.scelta_archivio.setCurrentText("Escavatore")
    fasi._aggiungi_attrezzatura()
    assert len(fasi.rischi.righe()) > n

    # Una seconda fase contemporanea di un'altra impresa crea un'interferenza.
    f2 = repo.inserisci("fasi", codice="X", impresa_id=b, data_inizio="2025-10-08", data_fine="2025-10-09")
    repo.aggiorna("fasi", repo.elenco("fasi")[0]["id"], impresa_id=a)
    pag = _pagina(f, PaginaInterferenze)
    f.navigazione.setCurrentRow(f.pagine.index(pag))
    assert pag.vista.rowCount() == 1
    # senza testo: «da scrivere» se grave, altrimenti vale la prescrizione generica
    assert pag.vista.item(0, 1).text().split("|")[1] in ("da scrivere", "generica")
    pag.testo.setPlainText("Lavorare in zone separate")
    pag.salva_in_sospeso()
    assert list(repo.prescrizioni().values()) == ["Lavorare in zone separate"]
    assert pag.vista.item(0, 1).text().endswith("|scritta")
    repo.elimina("fasi", f2)

    imprese = _pagina(f, PaginaImprese)
    f.navigazione.setCurrentRow(f.pagine.index(imprese))
    # nel PSC niente dati del POS: solo la verifica dell'idoneità e la patente a crediti
    assert [imprese.schede.tabText(i) for i in range(imprese.schede.count())] == ["Idoneità e patente"]
    # «Prepara il POS dell'impresa...» crea il file .spo dell'impresa selezionata
    assert any(b.text() == "Prepara il POS dell'impresa..." for b in imprese.findChildren(QtWidgets.QPushButton))
    imprese.tabella.ricarica()
    imprese.tabella.seleziona(a)
    file_pos = imprese.prepara_pos(str(tmp_path / "pos alfa"))
    assert file_pos.suffix == ".spo" and file_pos.is_file()
    # il verbale di idoneità si genera dalla scheda dell'impresa, non scegliendo l'impresa nei documenti
    verbale = imprese.idoneita.genera_verbale(str(tmp_path / "idoneita alfa.docx"))
    assert verbale is not None and verbale.is_file()
    copia = Progetto(file_pos)
    assert [i["id"] for i in Repository(copia).elenco("imprese")] == [a]
    copia.chiudi()

    costi = _pagina(f, PaginaCosti)
    f.navigazione.setCurrentRow(f.pagine.index(costi))
    costi.tabella.aggiungi()
    costi.tabella.salva_cella(0, _colonna(costi.tabella, "quantita"), 10.0)
    costi.tabella.salva_cella(0, _colonna(costi.tabella, "prezzo_unitario"), 2.5)
    assert "25,00" in costi.totale.text()

    doc = _pagina(f, PaginaDocumenti)
    f.navigazione.setCurrentRow(f.pagine.index(doc))
    assert doc.controlli.count() > 0
    assert doc.documenti == ("psc", "fascicolo", "notifica")
    assert not doc.con_impresa and doc._documento_composto() == "PSC"
    assert not any(type(pg).__name__ in ("PaginaValutazioni", "PaginaPonteggi") for pg in f.pagine)

    f.navigazione.setCurrentRow(0)
    f.pagine[0].campi["nome"].setText("Scuola")
    f.close()
    assert f.progetto is None
    p = Progetto(tmp_path / "c.scs")
    r = Repository(p)
    assert r.cantiere()["nome"] == "Scuola"
    p.chiudi()


def test_icone_e_tema(app):
    from sicurcantiere.ui import tema
    from sicurcantiere.ui.icone import NOMI, icona
    from sicurcantiere.ui.edizioni import EDIZIONI

    for nome in NOMI:
        assert not icona(nome, "#000000").pixmap(24, 24).toImage().isNull()
    assert {p.icona for e in EDIZIONI.values() for p in e.pagine} <= set(NOMI)
    for scuro in (True, False):
        for programma in ("psc", "pos", "pimus"):
            c = tema.applica(app, scuro, programma)
            assert app.palette().window().color().name().lower() == c["bg"].lower()
            foglio = app.styleSheet()
            assert "QListWidget#nav" in foglio and c["acc_s"] in foglio
            assert "@" not in foglio  # tutti i segnaposto sostituiti
    tema.applica(app, False, "pos")


def test_campi_numerici_visibili(app):
    # Regressione: con il foglio di stile, il testo dei campi numerici non deve sparire.
    from sicurcantiere.ui import tema

    tema.applica(app)
    s = QtWidgets.QDoubleSpinBox()
    s.setRange(0, 1e10)
    s.setValue(480000)
    s.resize(300, 30)
    s.show()
    app.processEvents()
    assert s.lineEdit().width() > 200
    s.close()


def test_riepilogo(app, tmp_path):
    from sicurcantiere.ui.riepilogo import ATTENZIONE, ERRORE, OK, calcola

    p = Progetto(tmp_path / "r.scs", crea=True)
    r = Repository(p)
    voci = {v.chiave: v for v in calcola(r)}
    # senza imprese e fasi nessun esito: «da determinare», non «non obbligatori»
    assert voci["psc"].valore == "Da determinare" and voci["psc"].stato != OK
    assert voci["notifica"].valore == "Da determinare" and voci["interferenze"].valore == "Da determinare"
    assert voci["importo"].valore == "Da indicare" and voci["importo"].stato == ATTENZIONE
    r.aggiorna_cantiere(importo_lavori=100000)
    a = r.inserisci("imprese", ragione_sociale="A")
    b = r.inserisci("imprese", ragione_sociale="B")
    f1 = r.importa_lavorazione(next(l for l in LAVORAZIONI if l["codice"] == "AL.29"))  # ponteggio
    f2 = r.inserisci("fasi", codice="X")
    r.aggiorna("fasi", f1, impresa_id=a, data_inizio="2025-10-06", data_fine="2025-10-10", lavoratori=3)
    r.aggiorna("fasi", f2, impresa_id=b, data_inizio="2025-10-08", data_fine="2025-10-09", lavoratori=2)
    r.inserisci("costi", quantita=1, prezzo_unitario=3000)
    voci = {v.chiave: v for v in calcola(r)}
    assert voci["psc"].stato == ATTENZIONE
    assert voci["interferenze"].valore == "1" and voci["interferenze"].stato == ERRORE
    assert voci["picco"].valore == "5"
    assert "3,0%" in voci["importo"].nota
    assert voci["controlli"].stato == ERRORE
    p.chiudi()


def test_gantt_trascinamento_e_zoom(app):
    from datetime import date

    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    from sicurcantiere.ui.gantt import ALTEZZA_INTESTAZIONE, ALTEZZA_RIGA, ZOOM, Gantt

    g = Gantt()
    fasi = [
        {"id": 1, "codice": "A", "descrizione": "", "impresa_id": 1, "zona": "", "lavoratori": 2,
         "data_inizio": "2025-10-06", "data_fine": "2025-10-10"},
        {"id": 2, "codice": "B", "descrizione": "", "impresa_id": 2, "zona": "", "lavoratori": 2,
         "data_inizio": "2025-10-08", "data_fine": "2025-10-09"},
    ]
    g.imposta_fasi(fasi, {}, {1: "Alfa", 2: "Beta"})
    assert g.colore_impresa(1) != g.colore_impresa(2)
    g.imposta_zoom("Giorni")
    g.show()
    app.processEvents()
    assert g.width() > 30 * ZOOM["Giorni"]
    g.grab()  # il disegno non deve sollevare eccezioni

    ricevuti = []
    g.fase_modificata.connect(lambda *a: ricevuti.append(a))
    y = ALTEZZA_INTESTAZIONE + ALTEZZA_RIGA // 2
    barra = g._rett_barra(0, date(2025, 10, 6), date(2025, 10, 10))
    # Sposta di 3 giorni trascinando dal centro.
    centro = QPoint(int(barra.center().x()), y)
    QTest.mousePress(g, QtCore.Qt.MouseButton.LeftButton, pos=centro)
    QTest.mouseMove(g, centro + QPoint(3 * ZOOM["Giorni"], 0))
    QTest.mouseRelease(g, QtCore.Qt.MouseButton.LeftButton, pos=centro + QPoint(3 * ZOOM["Giorni"], 0))
    assert ricevuti[-1] == (1, "2025-10-09", "2025-10-13")
    # Allunga di 2 giorni dal bordo destro.
    bordo = QPoint(int(barra.right()) - 2, y)
    QTest.mousePress(g, QtCore.Qt.MouseButton.LeftButton, pos=bordo)
    QTest.mouseMove(g, bordo + QPoint(2 * ZOOM["Giorni"], 0))
    QTest.mouseRelease(g, QtCore.Qt.MouseButton.LeftButton, pos=bordo + QPoint(2 * ZOOM["Giorni"], 0))
    assert ricevuti[-1] == (1, "2025-10-06", "2025-10-12")
    g.close()


def test_benvenuto_con_recenti(app, tmp_path):
    p = Progetto(tmp_path / "recente.scs", crea=True)
    Repository(p).aggiorna_cantiere(nome="Cantiere Rossi", comune="Lecce")
    p.chiudi()
    f = FinestraPrincipale()
    f.impostazioni.setValue("recenti", [str(tmp_path / "recente.scs"), str(tmp_path / "sparito.scs")])
    f._mostra_benvenuto()
    from sicurcantiere.ui.finestra import SchedaRecente

    schede = f.contenitore.widget(0).findChildren(SchedaRecente)
    assert len(schede) == 1
    testi = " ".join(l.text() for l in schede[0].findChildren(QtWidgets.QLabel))
    assert "Cantiere Rossi" in testi and "Lecce" in testi
    schede[0].click()
    assert f.progetto is not None and f.progetto.percorso.name == "recente.scs"
    f.close()


def test_programma_pos(app, tmp_path):
    from sicurcantiere.ai import Compilazione
    from sicurcantiere.ui.edizioni import POS
    from sicurcantiere.ui import valutazioni as ui_valutazioni
    from sicurcantiere.ui.valutazioni import PaginaValutazioni
    from sicurcantiere.valutazioni import METODI

    p = Progetto(tmp_path / "v.spo", crea=True)
    p.chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "v.spo")
    assert f.windowTitle() == "v.spo - SicurCantiere POS"
    assert [type(pg).__name__ for pg in f.pagine] == [
        "PaginaCantierePOS", "PaginaSoggettiPOS", "PaginaImpresePOS", "PaginaFasiPOS",
        "PaginaValutazioni", "PaginaSostanze", "PaginaDocumentiPOS"]
    repo = f.pagine[0].repo
    assert f.pagine[0].riepilogo is not None and "lavoratori" in f.pagine[0].riepilogo.tessere

    a = repo.inserisci("imprese", ragione_sociale="Alfa")
    imprese = _pagina(f, PaginaImprese)
    f.navigazione.setCurrentRow(f.pagine.index(imprese))
    imprese.tabella.seleziona(a)
    assert imprese.schede.count() == 6
    imprese.figure.campi["datore_lavoro"].setText("Mario Bianchi")
    f.salva()  # pulsante Salva: anche il campo ancora in modifica finisce nel file
    assert repo.leggi("imprese", a)["datore_lavoro"] == "Mario Bianchi"
    assert f.azione_salva.isEnabled() and "Salvato alle" in f.stato_salvataggio.text()
    imprese.figure.campi["rspp_datore"].setChecked(True)
    imprese.dati.campi["ccnl"].setCurrentText("Edilizia - artigianato")
    imprese.dati.campi["durc_scadenza"].setDate(QDate(2030, 5, 31))
    assert imprese.dati.valore("durc_scadenza") == "2030-05-31"
    imprese.elenco_figure.aggiungi()
    assert repo.elenco("figure", impresa_id=a)[0]["ruolo"] == "Preposto"
    b = repo.inserisci("imprese", ragione_sociale="Beta", tipo="Subappaltatrice")
    imprese.tabella.ricarica()
    imprese.tabella.seleziona(b)
    affidataria = imprese.dati.campi["affidataria_id"]
    affidataria.setCurrentIndex(affidataria.findData(a))
    assert repo.leggi("imprese", b)["affidataria_id"] == a
    imprese.tabella.seleziona(a)
    assert imprese.dati.valore("ccnl") == "Edilizia - artigianato"

    from sicurcantiere.ui.edizioni import PaginaFasiPOS

    lavorazioni = _pagina(f, PaginaFasiPOS)
    campi = [c.campo for c in lavorazioni.fasi.colonne]
    assert "data_inizio" not in campi and "importo" not in campi and "lavorazione" in campi
    assert lavorazioni.gantt.isHidden() or not lavorazioni.gantt.isVisible()

    # Maestranze: dettaglio, DPI, mansioni.
    from sicurcantiere.ui.maestranze import DialogoMansioni
    from sicurcantiere.ui.modulo import DialogoDPI

    fase = repo.importa_lavorazione(LAVORAZIONI[0])
    repo.aggiorna("fasi", fase, impresa_id=a)
    imprese.lavoratori.tabella.aggiungi()
    lav = repo.elenco("lavoratori", impresa_id=a)[0]
    assert lav["autonomo"] == 0
    imprese.lavoratori.tabella.seleziona(lav["id"])
    det = imprese.lavoratori.dettaglio
    det.campi["form_base"].setChecked(True)
    det.campi["data_nascita"].setDate(QDate(1966, 5, 20))
    assert repo.leggi("lavoratori", lav["id"])["data_nascita"] == "1966-05-20"
    dialogo_dpi = DialogoDPI(["casco"], ["guanti", "Imbracatura speciale"])
    dialogo_dpi._suggeriti()
    assert dialogo_dpi.scelti()[:1] == ["casco"] and "guanti" in dialogo_dpi.scelti()
    assert "Imbracatura speciale" in dialogo_dpi.scelti()
    mansioni = DialogoMansioni(repo, repo.leggi("lavoratori", lav["id"]))
    radice = mansioni.albero.topLevelItem(0)
    assert radice.foreground(0).color().name() == "#c0392b"  # nessun lavoratore ancora assegnato
    radice.child(0).setCheckState(0, QtCore.Qt.CheckState.Checked)  # spunta anche la lavorazione
    mansioni._conferma()
    assert {f for f, _ in repo.mansioni(lav["id"])} == {fase}
    assert len(repo.mansioni(lav["id"])) == 2
    imprese.autonomi.tabella.aggiungi()
    assert repo.elenco("lavoratori", impresa_id=a, autonomo=1)
    assert imprese.lavoratori.tabella.vista.rowCount() == 1

    soggetti = _pagina(f, PaginaSoggetti)
    f.navigazione.setCurrentRow(f.pagine.index(soggetti))
    soggetti.committente_rl.setChecked(True)
    assert repo.cantiere()["committente_rl"] == 1
    imprese.testi_pos.editor["rumore"].setPlainText("Sotto 80 dB(A)")

    pv = _pagina(f, PaginaValutazioni)
    f.navigazione.setCurrentRow(f.pagine.index(pv))
    pv.tabella.aggiungi()
    v = max(x["id"] for x in repo.elenco("valutazioni"))
    pv.tabella.seleziona(v)
    assert pv.editor.metodo.chiave == "niosh"
    pv.editor.campi["peso"].setValue(30)
    assert "Indice" in pv.esito.indice.text()
    pv.salva_in_sospeso()
    assert repo.dati_valutazione(v)["peso"] == 30
    # Risultato dell'assistente applicato all'editor e salvato.
    dati = {**METODI["niosh"].dati_predefiniti(), "peso": 12}
    pv._applica_ai(v, METODI["niosh"], Compilazione("Casseforme", "Carpentiere", dati, ["Ipotesi 1"]))
    riga = repo.leggi("valutazioni", v)
    assert riga["titolo"] == "Casseforme" and repo.dati_valutazione(v)["ipotesi_ai"] == ["Ipotesi 1"]
    # Cambio di metodo: l'editor mostra la tabella dei compiti.
    pv.tabella.salva_cella(pv.tabella.vista.currentRow(), 1, "ocra")
    assert pv.editor.metodo.chiave == "ocra" and pv.editor.tabella.rowCount() >= 1
    pv.editor._aggiungi_compito()
    pv.salva_in_sospeso()
    assert len(repo.dati_valutazione(v)["compiti"]) == 2
    # Più lavorazioni per la stessa valutazione.
    f1 = repo.inserisci("fasi", codice="A", descrizione="Getti")
    f2 = repo.inserisci("fasi", codice="B", descrizione="Massetti")
    class Finto(ui_valutazioni.DialogoFasi):
        def exec(self):
            for i in range(self.elenco.count()):
                self.elenco.item(i).setCheckState(QtCore.Qt.CheckState.Checked)
            return True

    ui_valutazioni.DialogoFasi, originale = Finto, ui_valutazioni.DialogoFasi
    try:
        pv._scegli_lavorazioni()
    finally:
        ui_valutazioni.DialogoFasi = originale
    assert {f1, f2} <= set(repo.fasi_valutazione(v)) and len(repo.fasi_valutazione(v)) == len(repo.elenco("fasi"))
    cella = pv.tabella.vista.item(pv.tabella.vista.currentRow(), 3)
    assert cella.text() == f"{len(repo.elenco('fasi'))} lavorazioni"
    assert "A Getti" in cella.toolTip() and "B Massetti" in cella.toolTip()
    assert "gruppo" in pv.tabella.vista.horizontalHeaderItem(2).toolTip()

    doc = _pagina(f, PaginaDocumenti)
    f.navigazione.setCurrentRow(f.pagine.index(doc))
    assert doc.documenti == ("pos", "sostanze", "dpi", "tesserini", "schede", "idoneita")
    messaggi = [doc.controlli.item(i).text() for i in range(doc.controlli.count())]
    assert any("medico competente" in m for m in messaggi)
    assert "error" in f.stato_controlli.text()
    f.close()
    p = Progetto(tmp_path / "v.spo")
    r = Repository(p)
    impresa = r.leggi("imprese", a)
    assert r.leggi("lavoratori", lav["id"])["form_base"] == 1
    assert impresa["datore_lavoro"] == "Mario Bianchi" and impresa["rspp_datore"] == 1
    assert impresa["ccnl"] == "Edilizia - artigianato" and impresa["durc_scadenza"] == "2030-05-31"
    assert r.testo(chiave_testo(a, "rumore")) == "Sotto 80 dB(A)"
    p.chiudi()


def test_programma_pimus(app, tmp_path):
    from sicurcantiere import pimus
    from sicurcantiere.ui.edizioni import PIMUS
    from sicurcantiere.ui.ponteggi import PaginaPonteggi

    p = Progetto(tmp_path / "p.spm", crea=True)
    p.chiudi()
    f = FinestraPrincipale(PIMUS)
    f.apri_file(tmp_path / "p.spm")
    repo = f.pagine[0].repo
    assert f.pagine[0].riepilogo is None
    pp = _pagina(f, PaginaPonteggi)
    f.navigazione.setCurrentRow(f.pagine.index(pp))
    pp.tabella.aggiungi()
    pid = repo.elenco("ponteggi")[0]["id"]
    pp.tabella.seleziona(pid)
    assert pp.avvisi.text()
    pp._testi_base()
    pp._carica_verifiche()
    assert len(repo.elenco("verifiche_ponteggio", ponteggio_id=pid)) > 10
    assert repo.testo(pimus.chiave_testo(pid, "uso")).startswith("È vietato")
    assert f._pagina_principale() is pp

    # disegno: tratti, tipologia per tratto, ancoraggi ed elementi dal prospetto
    from sicurcantiere import ponteggio as P

    g = pp.geometria
    g.tratti.item(0, 1).setText("18")
    g._aggiungi_tratto()
    assert g.tratti.currentRow() == 1
    g.t_tipo.setCurrentIndex(g.t_tipo.findData("Tubi e giunti"))
    salvato = repo.leggi("ponteggi", pid)
    assert salvato["lunghezza"] == 28
    tratti = P.tratti(salvato)
    assert [t.nome for t in tratti] == ["Ponteggio di facciata", "Est"]
    assert [t.tipo for t in tratti] == ["Telai prefabbricati", "Tubi e giunti"]
    g.vista.nodo.emit(0, 1, 1)
    assert [1, 1] in P.geometria(repo.leggi("ponteggi", pid))["tratti"][0]["aggiunti"]
    g.strumento.setCurrentIndex(g.strumento.findData("ancoraggio_tubo"))
    g.vista.campata.emit(0, 2, 3)
    g.strumento.setCurrentIndex(g.strumento.findData("trave_carraia"))
    g.vista.campata.emit(0, 4, 2)
    elementi = P.geometria(repo.leggi("ponteggi", pid))["elementi"]
    assert [(e["tipo"], e["da"], e["livello"]) for e in elementi] == [("ancoraggio_tubo", 2, 3), ("trave_carraia", 4, 0)]
    assert g.elementi.rowCount() == 2
    g.elementi.item(1, 2).setText("5-6")  # la trave occupa due campate
    assert P.geometria(repo.leggi("ponteggi", pid))["elementi"][1]["a"] == 5
    # tratto staccato e ruotato
    g.t_posizione.setCurrentIndex(1)
    g.t_angolo.setValue(45)
    assert P.tratti(repo.leggi("ponteggi", pid))[1].angolo == 45
    for n in range(len(g.gruppo.buttons())):
        g.gruppo.button(n).click()
        g.vista.grab()  # ogni vista si disegna senza errori
    pp.schede.setCurrentWidget(pp.calcoli)
    assert "ancoraggi" in pp.calcoli.ancoraggi.text() and pp.calcoli.elementi.rowCount() > 5
    voci = [pp.calcoli.elementi.item(r, 0).text() for r in range(pp.calcoli.elementi.rowCount())]
    assert "Ancoraggio su tubo e giunto" in voci and "Trave per passo carraio" in voci

    # rischi del montaggio e testi base con la tipologia
    pp._carica_rischi()
    pp._carica_rischi()  # la seconda volta non duplica
    assert len(repo.elenco("rischi_ponteggio", ponteggio_id=pid)) == len(pimus.RISCHI_MONTAGGIO)
    for chiave, _, _ in pimus.SEZIONI:
        pp.testi.imposta_testo(chiave, "")
    pp._testi_base()
    pp.testi.salva_in_sospeso()
    assert "spinotti" in repo.testo(pimus.chiave_testo(pid, "montaggio"))
    assert "raccordi in tubi e giunti" in repo.testo(pimus.chiave_testo(pid, "montaggio"))

    # sistema di ponteggio dall'archivio
    from sicurcantiere.archivio_utente import SISTEMA, ArchivioAnagrafiche

    repo.aggiorna("ponteggi", pid, fabbricante="Acme", sistema="T105", autorizzazione="n. 1")
    archivio = ArchivioAnagrafiche()
    archivio.salva_sistema(repo, pid)
    voce = archivio.elenco(SISTEMA)[0]
    archivio.chiudi()
    monkeypatch_dialogo = __import__("sicurcantiere.ui.archivio_anagrafiche", fromlist=["x"]).DialogoAnagrafiche
    originale_exec, originale_scelta = monkeypatch_dialogo.exec, monkeypatch_dialogo.scelta
    monkeypatch_dialogo.exec = lambda self: True
    monkeypatch_dialogo.scelta = lambda self: voce
    try:
        terzo = repo.inserisci("ponteggi", nome="Nuovo")
        pp.tabella.ricarica()
        pp.tabella.seleziona(terzo)
        pp._sistema_dall_archivio()
    finally:
        monkeypatch_dialogo.exec, monkeypatch_dialogo.scelta = originale_exec, originale_scelta
    assert repo.leggi("ponteggi", terzo)["fabbricante"] == "Acme"
    repo.elimina("ponteggi", terzo)
    pp.tabella.ricarica()
    pp.tabella.seleziona(pid)

    # due ponteggi diventano uno
    pp.tabella.aggiungi()
    secondo = max(r["id"] for r in repo.elenco("ponteggi"))
    repo.aggiorna("ponteggi", secondo, nome="Corpo basso", altezza=6)
    repo.inserisci("verifiche_ponteggio", ponteggio_id=secondo, voce="Verifica del corpo basso")
    pp.tabella.seleziona(pid)
    pp.unisci(secondo)
    assert [r["id"] for r in repo.elenco("ponteggi")] == [pid]
    unito = repo.leggi("ponteggi", pid)
    assert len(P.tratti(unito)) == 3 and P.tratti(unito)[2].altezza == 6
    assert any(v["voce"] == "Verifica del corpo basso" for v in repo.elenco("verifiche_ponteggio", ponteggio_id=pid))

    # squadra dai lavoratori dell'impresa
    impresa = repo.inserisci("imprese", ragione_sociale="Edil")
    repo.aggiorna("ponteggi", pid, impresa_id=impresa)
    repo.inserisci("lavoratori", impresa_id=impresa, nome="Luca", cognome="Bianchi", mansione="Preposto")
    pp.aggiungi_lavoratori(repo.elenco("lavoratori", impresa_id=impresa))
    addetti = repo.elenco("addetti_ponteggio", ponteggio_id=pid)
    assert [(a["nome"], a["ruolo"]) for a in addetti] == [("Luca Bianchi", P.PREPOSTO)]
    assert "Luca Bianchi: indicare la data del corso" in pp.avvisi.text()

    # registro dei controlli, verbali, duplicazione
    from datetime import date

    from sicurcantiere.ui import anteprima

    pp.registro.aggiungi()
    controllo = repo.elenco("registro_ponteggio", ponteggio_id=pid)[0]
    assert controllo["data"] == date.today().isoformat() and controllo["eseguita_da"] == "Luca Bianchi"
    repo.aggiorna("registro_ponteggio", controllo["id"], esito=pimus.NON_IDONEO, interventi="Rinforzo")
    pp.registro.modificata.emit()
    assert "esito negativo" in pp.avvisi.text()
    pp.verbali.aggiungi()
    verbale = repo.elenco("verbali_ponteggio", ponteggio_id=pid)[0]
    pp.verbali.seleziona(verbale["id"])
    creati = []
    originale_salva, originale_creato = QtWidgets.QFileDialog.getSaveFileName, anteprima.documento_creato
    QtWidgets.QFileDialog.getSaveFileName = lambda *a, **k: (str(tmp_path / "doc.docx"), "")
    anteprima.documento_creato = lambda _w, file, *a, **k: creati.append(file)
    try:
        pp._genera_verbale()
        pp._stampa_registro()
    finally:
        QtWidgets.QFileDialog.getSaveFileName, anteprima.documento_creato = originale_salva, originale_creato
    assert len(creati) == 2
    pp.schede.setCurrentWidget(pp.composizioni.parentWidget())
    assert pp.composizioni.documento() == f"PIMUS:{pid}"
    from sicurcantiere import composizioni as comp

    comp.componi(repo, f"PIMUS:{pid}", "Prima emissione", 0)
    pp.composizioni.ricarica()
    assert pp.composizioni.tabella.rowCount() == 1
    pp._duplica()
    assert len(repo.elenco("ponteggi")) == 2 and pp.id_ != pid
    assert pp.composizioni.tabella.rowCount() == 0  # il documento composto resta al ponteggio di origine
    assert not repo.elenco("registro_ponteggio", ponteggio_id=pp.id_)
    f.close()


def test_nuovo_file_con_estensione_del_programma(app, tmp_path, monkeypatch):
    from sicurcantiere.ui.edizioni import POS

    f = FinestraPrincipale(POS)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "Cliente X"), ""))
    f.nuovo()
    assert f.progetto.percorso.name == "Cliente X.spo"
    f.close()


def test_pagina_sostanze(app, tmp_path, monkeypatch):
    from sicurcantiere.ui import sostanze as ui_sostanze
    from sicurcantiere.ui.edizioni import POS
    from sicurcantiere.ui.sostanze import PaginaSostanze
    from tests.test_sostanze import _pdf

    scheda = tmp_path / "Cemento.pdf"
    _pdf(scheda, ["Nome commerciale: Cemento CEM II", "Avvertenza: Pericolo",
                  "H315 H317 H318 H335", "Data di revisione: 01/02/2024"])
    p = Progetto(tmp_path / "s.spo", crea=True)
    p.chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "s.spo")
    repo = f.pagine[0].repo
    a = repo.inserisci("imprese", ragione_sociale="Alfa")
    pagina = _pagina(f, PaginaSostanze)
    f.navigazione.setCurrentRow(f.pagine.index(pagina))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(scheda), ""))
    chiamate = []
    monkeypatch.setattr(ui_sostanze, "esegui_ai", lambda *a: chiamate.append(a))
    monkeypatch.setattr(ui_sostanze, "ai_attiva", lambda: True)
    pagina._importa_pdf()
    s = repo.elenco("sostanze")[0]
    assert s["nome"] == "Cemento CEM II" and s["impresa_id"] == a
    assert s["codici_h"] == "H315, H317, H318, H335" and s["data_sds"] == "2024-02-01"
    assert "Corrosivo" in pagina.classificazione.testo.text()
    assert len(chiamate) == 1  # l'utente ha accettato il completamento con l'AI
    pagina._applica_ai(s["id"], {"produttore": "Beta spa", "codici_h": "H315, H319", "dpi": "Guanti",
                                 "nome": "Altro nome", "data_revisione": "2020-01-01"})
    s = repo.leggi("sostanze", s["id"])
    assert s["produttore"] == "Beta spa" and s["dpi"] == "Guanti"
    assert s["nome"] == "Cemento CEM II" and s["data_sds"] == "2024-02-01"  # dati del PDF mantenuti
    assert s["codici_h"] == "H315, H317, H318, H335, H319"
    # Più lavorazioni per la stessa sostanza.
    from sicurcantiere.ui.sostanze import DialogoLavorazioni

    f1 = repo.inserisci("fasi", codice="A", descrizione="Getti")
    f2 = repo.inserisci("fasi", codice="B", descrizione="Massetti")
    dialogo = DialogoLavorazioni(repo, s["id"])
    for i in range(dialogo.elenco.count()):
        dialogo.elenco.item(i).setCheckState(QtCore.Qt.CheckState.Checked)
    assert dialogo.scelte() == [f1, f2]
    repo.salva_fasi_sostanza(s["id"], dialogo.scelte())
    pagina.tabella.ricarica()
    assert "A Getti; B Massetti" in pagina.tabella.vista.item(0, 2).text()
    f.close()


def test_dialogo_archivio_lavorazioni(app, tmp_path):
    from sicurcantiere.archivio_utente import ArchivioAnagrafiche
    from sicurcantiere.ui.pagine import DialogoArchivio

    p = Progetto(tmp_path / "a.spo", crea=True)
    r = Repository(p)
    fase = r.importa_lavorazione(LAVORAZIONI[0])
    archivio = ArchivioAnagrafiche()
    archivio.salva_lavorazione(r, fase)
    archivio.chiudi()
    d = DialogoArchivio()
    nodi = [d.albero.topLevelItem(i).text(0) for i in range(d.albero.topLevelItemCount())]
    assert nodi[0] == "Allestimento e smobilizzo del cantiere" and nodi[-1] == "Lavorazioni personalizzate"
    utente = d.albero.topLevelItem(d.albero.topLevelItemCount() - 1)
    utente.child(0).setCheckState(0, QtCore.Qt.CheckState.Checked)
    d.tipologia.setCurrentText("Restauri")  # la spunta resta dopo il cambio di tipologia
    nodi = [d.albero.topLevelItem(i).text(0) for i in range(d.albero.topLevelItemCount())]
    assert "Lavori stradali" not in nodi
    scelte = d.selezionate()
    assert len(scelte) == 1 and "dati" in scelte[0]
    d.filtro.setText("ponteggio")
    assert not d.albero.topLevelItem(0).isHidden()
    d.deleteLater()
    p.chiudi()


def test_foto_cantiere_pos(app, tmp_path, monkeypatch):
    from sicurcantiere import segnaletica
    from sicurcantiere.ui.edizioni import POS, PaginaCantierePOS

    Progetto(tmp_path / "f.spo", crea=True).chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "f.spo")
    pagina = _pagina(f, PaginaCantierePOS)
    foto = [str(segnaletica.SEGNALI[k].file) for k in ("casco", "guanti")]
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: (foto, ""))
    pagina.foto._aggiungi()
    pagina.foto._aggiungi()  # nessun doppione
    assert pagina.foto.elenco.count() == 2 and pagina.foto.percorsi() == foto
    pagina.foto.elenco.setCurrentRow(0)
    pagina.foto._rimuovi()
    assert pagina.foto.percorsi() == foto[1:]
    f.close()


def test_attrezzature_suggerite_e_completate_con_ai(app, tmp_path, monkeypatch):
    from sicurcantiere.ui.edizioni import POS, PaginaFasiPOS

    Progetto(tmp_path / "m.spo", crea=True).chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "m.spo")
    pagina = _pagina(f, PaginaFasiPOS)
    repo = pagina.repo
    fase = repo.inserisci("fasi", codice="A", descrizione="Tagli di murature")
    assert "raggruppa" in pagina.fasi.vista.horizontalHeaderItem(0).toolTip()  # il codice non è una colonna
    monkeypatch.setattr(type(pagina), "_scegli_proposte", lambda self, t, n, testi: list(range(len(testi))))

    rumore = {"descrizione": "Rumore", "probabilita": 3, "danno": 2, "misure": "Cuffie", "dpi": "Otoprotettori"}
    pagina._scegli_attrezzature(fase, [
        {"nome": "Escavatore", "tipo": "Macchina", "descrizione": "", "prima": [], "durante": [], "dopo": [],
         "dpi": "", "rischi": []},
        {"nome": "Mola a disco", "tipo": "Attrezzo", "descrizione": "Mola portatile", "prima": ["controllare"],
         "durante": [], "dopo": [], "dpi": "occhiali, guanti", "rischi": [rumore]},
    ])
    attrezzature = {a["nome"]: a for a in repo.elenco("attrezzature", fase_id=fase)}
    assert attrezzature["Escavatore"]["descrizione"]  # scheda dell'archivio
    assert attrezzature["Mola a disco"]["dpi"] == "occhiali; guanti"
    assert "Prima dell'uso: 1) controllare." in attrezzature["Mola a disco"]["misure"]
    rischi = {(r["descrizione"], r["fonte"]) for r in repo.elenco("rischi", fase_id=fase)}
    assert ("Rumore", "Mola a disco") in rischi and ("Vibrazioni al corpo intero", "Escavatore") in rischi

    # Attrezzo scritto a mano, completato dall'assistente senza toccare i campi già compilati.
    trapano = repo.inserisci("attrezzature", fase_id=fase, tipo="Attrezzo", nome="Avvitatore", dpi="guanti")
    pagina._applica_attrezzatura(trapano, {
        "nome": "Avvitatore", "tipo": "Attrezzo", "descrizione": "Avvitatore a batteria",
        "prima": ["caricare la batteria"], "durante": [], "dopo": [], "dpi": "occhiali",
        "rischi": [{**rumore, "descrizione": "Movimenti ripetitivi degli arti superiori"}]})
    a = repo.leggi("attrezzature", trapano)
    assert a["descrizione"] == "Avvitatore a batteria" and a["dpi"] == "guanti" and "caricare" in a["misure"]
    assert ("Movimenti ripetitivi degli arti superiori", "Avvitatore") in {
        (r["descrizione"], r["fonte"]) for r in repo.elenco("rischi", fase_id=fase)}
    f.close()


def test_spunta_rischio_non_presente(app, tmp_path):
    from sicurcantiere.ui.edizioni import POS, PaginaFasiPOS

    Progetto(tmp_path / "n.spo", crea=True).chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "n.spo")
    pagina = _pagina(f, PaginaFasiPOS)
    repo = pagina.repo
    fase = repo.inserisci("fasi", codice="A", descrizione="Getti")
    rischio = repo.inserisci("rischi", fase_id=fase, descrizione="Rumore")
    pagina.fasi.ricarica()
    pagina.fasi.seleziona(fase)
    tabella = pagina.rischi
    colonna = next(i for i, c in enumerate(tabella.colonne) if c.campo == "non_presente")
    item = tabella.vista.item(0, colonna)
    assert item.checkState() == QtCore.Qt.CheckState.Unchecked
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    assert repo.leggi("rischi", rischio)["non_presente"] == 1
    tabella.vista.item(0, colonna).setCheckState(QtCore.Qt.CheckState.Unchecked)
    assert repo.leggi("rischi", rischio)["non_presente"] == 0
    f.close()


def test_nuovo_su_cantiere_esistente_non_lo_cancella(app, tmp_path, monkeypatch):
    from sicurcantiere.db import cartella_copie
    from sicurcantiere.ui.edizioni import POS

    p = Progetto(tmp_path / "Cliente.spo", crea=True)
    Repository(p).aggiorna_cantiere(nome="Scuola di Bari")
    p.chiudi()
    opzioni = []

    def salva(*a, **k):
        opzioni.append(k.get("options"))
        return str(tmp_path / "Cliente.spo"), ""

    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", salva)
    f = FinestraPrincipale(POS)
    # Scelto per sbaglio da «Nuovo cantiere»: si apre il cantiere, nessuna sostituzione.
    monkeypatch.setattr(f, "_scelta_file_esistente", lambda percorso: "apri")
    f.nuovo()
    assert opzioni == [QtWidgets.QFileDialog.Option.DontConfirmOverwrite]
    assert f.pagine[0].repo.cantiere()["nome"] == "Scuola di Bari"
    f._chiudi_progetto()
    monkeypatch.setattr(f, "_scelta_file_esistente", lambda percorso: "annulla")
    f.nuovo()
    assert f.progetto is None
    # Sostituito su richiesta esplicita: il vecchio resta tra le copie di sicurezza.
    monkeypatch.setattr(f, "_scelta_file_esistente", lambda percorso: "sostituisci")
    f.nuovo()
    assert f.pagine[0].repo.cantiere()["nome"] == ""
    copie = sorted(cartella_copie().glob("Cliente-*.spo"))
    assert copie and Repository(Progetto(copie[-1])).cantiere()["nome"] == "Scuola di Bari"
    f.close()


def test_controllo_aggiornamenti(app, monkeypatch):
    from sicurcantiere import aggiornamenti
    from sicurcantiere.ui import aggiornamenti as ui_aggiornamenti
    from sicurcantiere.ui.edizioni import POS

    nuova = aggiornamenti.Versione("99.0.0", "https://example.com/s.exe", "https://example.com", "")
    monkeypatch.setattr(aggiornamenti, "ultima_versione", lambda: nuova)
    proposte = []
    monkeypatch.setattr(ui_aggiornamenti, "proponi", lambda finestra, v: proposte.append(v))
    f = FinestraPrincipale(POS)
    ui_aggiornamenti.controlla(f, manuale=True)
    QtCore.QThreadPool.globalInstance().waitForDone(5000)
    QtWidgets.QApplication.processEvents()
    assert proposte == [nuova]
    assert f.avviso_aggiornamento.text() == "Aggiornamento disponibile: versione 99.0.0"
    # Il controllo automatico si ripete al massimo una volta al giorno.
    monkeypatch.setattr(aggiornamenti, "ultima_versione", lambda: pytest.fail("controllo ripetuto"))
    ui_aggiornamenti.controlla(f)
    QtCore.QThreadPool.globalInstance().waitForDone(5000)
    f.close()


def test_nuovo_tema_navigazione_e_controlli(app, tmp_path):
    from sicurcantiere.ui import tema
    from sicurcantiere.ui.edizioni import POS, PaginaDocumentiPOS, PaginaFasiPOS, PaginaImpresePOS

    p = Progetto(tmp_path / "t.spo", crea=True)
    r = Repository(p)
    r.aggiorna_cantiere(nome="Scuola", comune="Bari", provincia="BA")
    r.inserisci("imprese", ragione_sociale="Alfa")  # mancano datore di lavoro e lavoratori: errori
    p.chiudi()
    f = FinestraPrincipale(POS)
    assert not f.navigazione.isEnabled() and f.navigazione.count() == len(POS.pagine)  # pagine già elencate
    f.apri_file(tmp_path / "t.spo")
    assert f.nome_cantiere.text() == "Scuola" and f.luogo_cantiere.text() == "Bari (BA)"
    assert f.stato_controlli.property("level") == "error"
    imprese = f.pagine.index(_pagina(f, PaginaImpresePOS))
    voce = f.navigazione.item(imprese)
    assert voce.data(QtCore.Qt.ItemDataRole.UserRole) == imprese + 1
    assert voce.data(QtCore.Qt.ItemDataRole.UserRole + 1) == "error" and voce.data(QtCore.Qt.ItemDataRole.UserRole + 2)
    # Doppio clic su un controllo: si va alla pagina da correggere.
    documenti = _pagina(f, PaginaDocumentiPOS)
    f.navigazione.setCurrentRow(f.pagine.index(documenti))
    riga = next(i for i in range(documenti.controlli.count())
                if documenti.controlli.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == "Impresa")
    documenti._vai_al_controllo(documenti.controlli.item(riga))
    assert f.navigazione.currentRow() == imprese
    # La prima riga viene selezionata e le tabelle hanno il titolo con il conteggio.
    pagina_imprese = f.pagine[imprese]
    assert pagina_imprese.tabella.id_selezionato() is not None
    assert pagina_imprese.tabella.conteggio.text() == "1"
    fasi = _pagina(f, PaginaFasiPOS)
    colonna = next(i for i, c in enumerate(fasi.rischi.colonne) if c.campo == "livello")
    assert isinstance(fasi.rischi.vista.itemDelegateForColumn(colonna), tema.DelegatoLivello)
    f.close()


def test_assistente_ai_spento_di_serie(app, monkeypatch):
    from sicurcantiere.ui import lavoro_ai
    from sicurcantiere.ui.pagine import pulsante_ai

    stato = {"attiva": False}
    monkeypatch.setattr(lavoro_ai, "ai_attiva", lambda: stato["attiva"])
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    pagina = QWidget()
    pulsante = pulsante_ai("Suggerisci")
    QVBoxLayout(pagina).addWidget(pulsante)
    pagina.show()
    assert pulsante.isHidden()  # spento: il pulsante non compare
    stato["attiva"] = True
    lavoro_ai.aggiorna_pulsanti_ai()
    assert pulsante.isVisible()
    # Acceso: un pulsante ancora senza pagina non si mostra da solo (finestra lampo),
    # ma compare con la pagina in cui viene inserito.
    altro = pulsante_ai("Altro")
    assert not altro.isVisible()
    lavoro_ai.aggiorna_pulsanti_ai()
    assert not altro.isVisible()
    pagina.layout().addWidget(altro)
    app.processEvents()
    assert altro.isVisible()
    pagina.close()
    stato["attiva"] = False
    chiamate = []
    lavoro_ai.esegui_ai(None, "x", lambda ai: chiamate.append(ai), lambda r: None)
    assert chiamate == []  # niente parte verso il fornitore
    assert "Stati Uniti" in lavoro_ai.SEDI["avanzato"]
    # La sede la comunica il server (riga SEDE di ai.env) e il programma la ricorda.
    lavoro_ai._ricorda_sedi({"motori": {"standard": {"sede": "Scaleway, in Francia (UE)", "disponibile": True}}})
    assert lavoro_ai.sede("standard") == "Scaleway, in Francia (UE)"
    lavoro_ai.impostazioni_comuni().remove(lavoro_ai.CHIAVE_SEDE + "standard")
    assert lavoro_ai.sede("standard") == lavoro_ai.SEDI["standard"]


def test_contesto_ai_senza_dati_personali(tmp_path):
    from sicurcantiere.ui.pagine import contesto_cantiere

    p = Progetto(tmp_path / "c.spo", crea=True)
    r = Repository(p)
    r.aggiorna_cantiere(nome="Casa Rossi", indirizzo="Via Verdi 3", comune="Bari", natura_opera="Ristrutturazione")
    r.inserisci("soggetti", ruolo="Committente", nome="Mario Rossi")
    r.inserisci("imprese", ragione_sociale="Edil Bianchi di Luigi Bianchi", tipo="Affidataria")
    testo = contesto_cantiere(r)
    assert "Mario Rossi" not in testo and "Bianchi" not in testo and "Via Verdi" not in testo
    assert "Committente" in testo and "Affidataria" in testo and "Bari" in testo
    p.chiudi()


def test_guida_e_avviso_responsabilita(app):
    from sicurcantiere.ui.guida import DialogoGuida
    from sicurcantiere.ui.pagine import AVVISO_RESPONSABILITA

    d = DialogoGuida("POS")
    testo = d.findChild(QtWidgets.QTextBrowser).toPlainText()
    assert "Come si compila un POS" in testo and "disattivato per impostazione predefinita" in testo
    assert "firmato" in AVVISO_RESPONSABILITA


def test_licenza_prova_e_programma_non_incluso(app, tmp_path, monkeypatch):
    import base64
    from datetime import date, timedelta

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from sicurcantiere import licenza
    from sicurcantiere.ui import licenza as licenza_ui
    from sicurcantiere.ui.edizioni import POS, PSC

    impostazioni = QtCore.QSettings(str(tmp_path / "comune.ini"), QtCore.QSettings.Format.IniFormat)
    monkeypatch.setattr(licenza_ui, "impostazioni_comuni", lambda: impostazioni)
    privata = Ed25519PrivateKey.generate()
    pubblica = privata.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setenv("SICURCANTIERE_CHIAVE_LICENZE", base64.b64encode(pubblica).decode())
    grezza = privata.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                   serialization.NoEncryption())

    # Prova: parte al primo avvio, un solo cantiere.
    for nome in ("a.spo", "b.spo"):
        Progetto(tmp_path / nome, crea=True).chiudi()
    f = FinestraPrincipale(POS)
    assert f.stato_licenza.text().startswith("Prova gratuita: 30")
    f.apri_file(tmp_path / "a.spo")
    assert f.progetto is not None
    f._chiudi_progetto()
    assert not f.sola_lettura
    f.apri_file(tmp_path / "b.spo")  # secondo cantiere: solo in lettura
    assert f.progetto is not None and f.sola_lettura and "(sola lettura)" in f.windowTitle()
    f.apri_file(tmp_path / "a.spo")  # il primo resta modificabile
    assert f.progetto is not None and not f.sola_lettura
    f.close()

    # Prova finita: i cantieri si aprono in sola lettura, nessun cantiere nuovo.
    impostazioni.setValue("prova/inizio", (date.today() - timedelta(days=40)).isoformat())
    f = FinestraPrincipale(POS)
    assert f.stato_licenza.text() == "Sola lettura: licenza mancante"
    f.apri_file(tmp_path / "a.spo")
    assert f.progetto is not None and f.sola_lettura and not f.azione_salva.isEnabled()
    f.close()

    # Licenza POS: il POS funziona, il PSC mostra «Non incluso nella tua licenza».
    codice = licenza.firma(licenza.Licenza("L-1", "Studio Rossi", "pos", date.today()), grezza)
    impostazioni.setValue("licenza/codice", codice)
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "b.spo")
    assert f.progetto is not None and not f.sola_lettura
    assert f.stato_licenza.text() == "Licenza POS · Studio Rossi"
    f.close()
    f = FinestraPrincipale(PSC)
    testi = [w.text() for w in f.findChildren(QtWidgets.QLabel)]
    assert "Non incluso nella tua licenza" in testi
    assert any("PSC non è incluso" in t for t in testi)
    f.close()


def test_nuovo_pos_da_psc(app, tmp_path, monkeypatch):
    from sicurcantiere.ui import importa_psc as ui_psc
    from sicurcantiere.ui.edizioni import POS
    from tests.test_importa_psc import _analisi

    analisi = _analisi()
    dialogo = ui_psc.DialogoImpresePSC(analisi)
    assert dialogo.imprese.count() == 2 and dialogo.fasi.count() == 2
    assert dialogo.fasi.item(0).checkState() == QtCore.Qt.CheckState.Checked  # assegnata dal PSC
    dialogo.imprese.item(1).setCheckState(QtCore.Qt.CheckState.Checked)
    dialogo.impresa_fasi.setCurrentIndex(1)
    dialogo.fasi.item(0).setCheckState(QtCore.Qt.CheckState.Checked)  # aggiunta a mano a Beta Gru
    scelte = dialogo.scelte()
    assert [i["ragione_sociale"] for i, _ in scelte] == ["Beta Gru"]
    assert len(scelte[0][1]) == 2
    dialogo._tutte_le_fasi(False)
    assert dialogo.scelte()[0][1] == []
    dialogo._tutte_le_fasi(True)  # «Seleziona tutte»
    assert len(dialogo.scelte()[0][1]) == dialogo.fasi.count() == 2

    f = FinestraPrincipale(POS)
    assert "Nuovo POS da un &PSC..." in [a.text() for a in f.menuBar().actions()[0].menu().actions()]
    # senza assistente AI attivo spiega cosa fare, senza chiedere il file
    mostrati = []
    monkeypatch.setattr(ui_psc.lavoro_ai, "ai_attiva", lambda: False)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a: mostrati.append(a[2]))
    f.nuovo_da_psc()
    assert "Prepara il POS dell'impresa" in mostrati[0]
    f.close()


def test_lettura_in_background_senza_bloccare(app):
    import time

    from sicurcantiere.ui import importa_psc as ui_psc

    risultati, passi = [], []

    def lavoro(avanzamento):
        for n in range(1, 4):
            avanzamento(n, 3, f"pagina {n}")
            passi.append(n)
        return "fatto"

    ui_psc.in_background(None, "Prova", "Lettura...", lavoro, risultati.append)
    limite = time.time() + 10
    while not risultati and time.time() < limite:
        app.processEvents()  # la finestra resta reattiva mentre il lavoro procede
        time.sleep(0.01)
    assert risultati == ["fatto"] and passi == [1, 2, 3]


def test_assistente_incluso_nella_licenza(app, monkeypatch):
    import base64
    from datetime import date

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from sicurcantiere import ai, licenza
    from sicurcantiere.ui import lavoro_ai

    privata = Ed25519PrivateKey.generate()
    grezza = privata.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                   serialization.NoEncryption())
    monkeypatch.setenv("SICURCANTIERE_CHIAVE_LICENZE", base64.b64encode(privata.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    monkeypatch.setenv("SICURCANTIERE_SERVER_AI", "https://vm.esempio.ts.net")
    imp = lavoro_ai.impostazioni_comuni()
    imp.setValue("ai/anthropic/chiave", "sk-vecchia")  # chiave di una versione precedente
    imp.setValue(lavoro_ai.CHIAVE_ATTIVO, True)

    # senza licenza: l'assistente non c'è, anche se era acceso
    imp.remove("licenza/codice")
    assert not lavoro_ai.ai_attiva() and not imp.contains("ai/anthropic/chiave")
    d = lavoro_ai.DialogoImpostazioniAI()
    assert not d.attiva.isEnabled() and "Aiuto > Licenza" in lavoro_ai.perche_non_disponibile()
    d.close()

    # licenza Completo: motore Standard, nessuna chiave da inserire
    imp.setValue("licenza/codice", licenza.firma(licenza.Licenza("L-1", "Studio", "completo", date.today()), grezza))
    assert lavoro_ai.ai_attiva()
    imp.setValue(lavoro_ai.CHIAVE_MOTORE, ai.AVANZATO)
    a = lavoro_ai.assistente()
    assert a.fornitore == ai.INTEGRATO and a.modello == ai.STANDARD  # l'avanzato è solo nello Studio
    d = lavoro_ai.DialogoImpostazioniAI()
    assert d.attiva.isEnabled() and d.motore.count() == 1 and "server SicurCantiere" in d.destinazione.text()
    d.close()

    # piano Studio: c'è anche Claude
    imp.setValue("licenza/codice", licenza.firma(licenza.Licenza("L-2", "Studio", "studio", date.today()), grezza))
    assert lavoro_ai.assistente().modello == ai.AVANZATO
    d = lavoro_ai.DialogoImpostazioniAI()
    assert d.motore.count() == 2
    d.close()

    # licenza scaduta: niente assistente
    imp.setValue("licenza/codice", licenza.firma(licenza.Licenza(
        "L-3", "Studio", "studio", date(2020, 1, 1), scadenza=date(2021, 1, 1)), grezza))
    assert not lavoro_ai.ai_attiva()
    for voce in ("licenza/codice", lavoro_ai.CHIAVE_ATTIVO, lavoro_ai.CHIAVE_MOTORE):
        imp.remove(voce)


@pytest.mark.parametrize("chiave", ["pos", "psc", "pimus"])
def test_apertura_senza_finestre_lampo(app, tmp_path, chiave):
    """Aprendo un cantiere nessun elemento deve comparire come finestra a sé (icone che lampeggiano)."""
    from sicurcantiere.ui.edizioni import EDIZIONI

    edizione = EDIZIONI[chiave]
    file = tmp_path / f"c{edizione.estensione}"
    Progetto(file, crea=True).chiudi()
    f = FinestraPrincipale(edizione)
    f.show()
    app.processEvents()
    lampi = []

    class Spia(QtCore.QObject):
        def eventFilter(self, oggetto, evento):
            if evento.type() == QtCore.QEvent.Type.Show and oggetto.isWidgetType() and oggetto.isWindow() \
                    and oggetto is not f:
                lampi.append(type(oggetto).__name__)
            return False

    spia = Spia()
    app.installEventFilter(spia)
    try:
        f.apri_file(file)
        app.processEvents()
        for i in range(len(f.pagine)):
            f.navigazione.setCurrentRow(i)
            app.processEvents()
    finally:
        app.removeEventFilter(spia)
        f.close()
    assert lampi == []


def test_codice_fase_automatico_e_licenza_nascosta(app, tmp_path):
    from sicurcantiere import archivio
    from sicurcantiere.ui import licenza as licenza_ui
    from sicurcantiere.ui.edizioni import POS, PaginaFasiPOS

    Progetto(tmp_path / "c.spo", crea=True).chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "c.spo")
    pagina = _pagina(f, PaginaFasiPOS)
    f.navigazione.setCurrentRow(f.pagine.index(pagina))
    pagina.fasi.aggiungi()
    fase = pagina.repo.elenco("fasi")[0]
    assert fase["codice"] == "UT.01"  # nessun codice da inventare
    pagina.fasi.salva_cella(0, 0, archivio.LAVORAZIONI[0]["gruppo"])  # la lavorazione dà la sigla
    assert pagina.repo.leggi("fasi", fase["id"])["codice"].startswith("AL.")
    f.close()

    d = licenza_ui.DialogoLicenza("pos", "SicurCantiere POS")
    assert d.codice.echoMode() == QtWidgets.QLineEdit.EchoMode.Password
    d.mostra.setChecked(True)
    assert d.codice.echoMode() == QtWidgets.QLineEdit.EchoMode.Normal
    d.close()


def test_chiusura_con_modifiche_non_salvate(app, tmp_path, monkeypatch):
    from sicurcantiere.app import traduci_in_italiano
    from sicurcantiere.ui.edizioni import POS

    mb = QtWidgets.QMessageBox
    file = tmp_path / "c.spo"
    Progetto(file, crea=True).chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(file)
    assert not f.modifiche_non_salvate()  # appena aperto e solo guardato: niente domanda
    f.pagine[0].salva_in_sospeso()
    assert not f.modifiche_non_salvate()

    f.pagine[0].campi["nome"].setText("Scuola")  # modifica fatta dall'utente nella pagina
    assert f.modifiche_non_salvate()
    monkeypatch.setattr(mb, "exec", lambda self: mb.StandardButton.Cancel)
    assert not f.conferma_chiusura() and f.progetto is not None  # Annulla: resta aperto
    monkeypatch.setattr(mb, "exec", lambda self: mb.StandardButton.Discard)
    f.chiudi_cantiere()  # Non salvare: il file torna com'era all'apertura
    assert f.progetto is None
    p = Progetto(file)
    assert Repository(p).cantiere()["nome"] == ""
    p.chiudi()

    f.apri_file(file)
    f.pagine[0].campi["nome"].setText("Scuola")
    monkeypatch.setattr(mb, "exec", lambda self: mb.StandardButton.Save)
    f.close()  # Salva: le modifiche restano
    p = Progetto(file)
    assert Repository(p).cantiere()["nome"] == "Scuola"
    p.chiudi()

    assert traduci_in_italiano(app)  # pulsanti standard di Qt in italiano
    pulsanti = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    assert pulsanti.buttons()[0].text() == "Annulla"


def test_nessuna_finestra_lampo_con_ai_accesa(app, tmp_path, monkeypatch):
    from sicurcantiere import autoverifica
    from sicurcantiere.ui import lavoro_ai

    monkeypatch.setattr(lavoro_ai, "ai_attiva", lambda: True)
    file = tmp_path / "c.scs"
    Progetto(file, crea=True).chiudi()
    f = FinestraPrincipale()
    f.show()

    def apri():
        f.apri_file(file)
        for i in range(len(f.pagine)):
            f.navigazione.setCurrentRow(i)
            app.processEvents()
        f.salva()
        f.apri_file(file)
        app.processEvents()

    assert autoverifica._finestre_comparse(f, apri) == []
    f.salva()
    f.close()


def test_documenti_composti_pos(app, tmp_path, monkeypatch):
    from sicurcantiere import composizioni as comp
    from sicurcantiere.ui import composizioni as ui_comp
    from sicurcantiere.ui.edizioni import POS, PaginaDocumentiPOS, PaginaImpresePOS

    p = Progetto(tmp_path / "c.spo", crea=True)
    r = Repository(p)
    r.aggiorna_cantiere(nome="Villa", comune="Bari", indirizzo="Via Roma 1")
    impresa = r.inserisci("imprese", ragione_sociale="Alfa", datore_lavoro="Mario Bianchi")
    p.chiudi()
    f = FinestraPrincipale(POS)
    f.apri_file(tmp_path / "c.spo")
    repo = f.pagine[0].repo
    documenti = _pagina(f, PaginaDocumentiPOS)
    f.navigazione.setCurrentRow(f.pagine.index(documenti))
    pannello = documenti.composizioni
    assert pannello.tabella.rowCount() == 0 and not pannello.p_emetti.isEnabled()

    risposte = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "question",
                        lambda *a, **k: risposte.append(a[2]) or QtWidgets.QMessageBox.StandardButton.No)
    monkeypatch.setattr(ui_comp.DialogoComponi, "exec", lambda self: QtWidgets.QDialog.DialogCode.Accepted)
    f._genera_principale()  # «Genera POS»: compone la bozza
    assert pannello.tabella.rowCount() == 1 and pannello.tabella.item(0, 1).text() == "Bozza"
    assert "obbligatori" in risposte[-1]
    assert documenti.schede.currentWidget() is pannello.mancanti
    assert pannello.p_componi.text().startswith("Ricomponi") and pannello.p_emetti.isEnabled()
    # Doppio clic su un dato mancante: si va alla pagina in cui si compila.
    riga = next(i for i in range(pannello.mancanti.count())
                if pannello.mancanti.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == "Figure della sicurezza")
    pannello._vai_al_dato(pannello.mancanti.item(riga))
    assert f.navigazione.currentRow() == f.pagine.index(_pagina(f, PaginaImpresePOS))
    f.navigazione.setCurrentRow(f.pagine.index(documenti))

    # Capitoli: si toglie un capitolo e si aggiunge un testo; restano alla composizione successiva.
    c = comp.elenco(repo, f"POS:{impresa}")[0]
    dialogo = ui_comp.DialogoCapitoli(repo, f"POS:{impresa}", c["capitoli"], documenti)
    riga = next(i for i, cap in enumerate(c["capitoli"]) if cap["chiave"] == "segnaletica-prevista-nel-cantiere")
    dialogo.elenco.item(riga).setCheckState(QtCore.Qt.CheckState.Unchecked)
    riga = next(i for i, cap in enumerate(c["capitoli"]) if cap["chiave"] == "allegati-e-firme")
    dialogo.elenco.setCurrentRow(riga)
    dialogo.testo.setPlainText("Allegato: planimetria del cantiere.")
    dialogo.elenco.setCurrentRow(0)
    dialogo._salva()
    salvate = comp.personalizzazioni(repo, f"POS:{impresa}")
    assert salvate["segnaletica-prevista-nel-cantiere"]["escluso"] == 1
    assert salvate["allegati-e-firme"]["testo"] == "Allegato: planimetria del cantiere."
    assert pannello.componi()
    c = comp.elenco(repo, f"POS:{impresa}")[0]
    assert any(cap["chiave"] == "segnaletica-prevista-nel-cantiere" and cap["escluso"] for cap in c["capitoli"])

    # Emissione con dati obbligatori mancanti: servono spunta e motivo.
    emetti = ui_comp.DialogoEmetti(c, "POS", documenti)
    ok = emetti.bottoni.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()
    emetti.spunta.setChecked(True)
    assert not ok.isEnabled()
    emetti.motivo.setText("dati in arrivo dall'impresa")
    assert ok.isEnabled() and "dati in arrivo" in emetti.conferma()

    def accetta(dialogo):
        dialogo.spunta.setChecked(True)
        dialogo.motivo.setText("dati in arrivo")
        return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(ui_comp.DialogoEmetti, "exec", accetta)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **k: None)
    pannello.emetti()
    assert pannello.tabella.item(0, 1).text() == "Emessa" and not pannello.p_emetti.isEnabled()
    assert pannello.p_consegna.isEnabled()

    # Esporta e confronto.
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "pos.docx"), ""))
    pannello.esporta()
    assert (tmp_path / "pos.docx").stat().st_size > 10000
    nuova = comp.componi(repo, f"POS:{impresa}", "Seconda")
    pannello.ricarica()
    assert pannello.tabella.rowCount() == 2 and pannello.tabella.item(0, 0).text() == "1"
    assert "Rev. 0" in ui_comp.html_confronto(comp.leggi(repo, c["id"]), nuova)
    f.close()


def test_annulla_ripeti_ricerca_e_modelli(app, tmp_path, monkeypatch):
    from sicurcantiere import modelli
    from sicurcantiere.ui import modelli as ui_modelli
    from sicurcantiere.ui import ricerca as ui_ricerca
    from sicurcantiere.ui.edizioni import EDIZIONI
    from sicurcantiere.ui.primo_avvio import DialogoPrimoAvvio

    monkeypatch.setenv("SICURCANTIERE_MODELLI", str(tmp_path / "modelli"))
    for chiave, edizione in EDIZIONI.items():
        f = FinestraPrincipale(edizione)
        assert not f.azione_annulla.isEnabled() and not f.azione_cerca.isEnabled()
        f._carica(Progetto(tmp_path / f"{chiave}{edizione.estensione}", crea=True))
        f.navigazione.setCurrentRow(2)
        f._aggiorna_stato()
        repo = f.pagine[0].repo
        repo.inserisci("imprese", ragione_sociale="Edil Alfa")
        f._aggiorna_stato()
        assert f.azione_annulla.isEnabled() and f.azione_cerca.isEnabled()

        # «Annulla» toglie l'impresa e resta sulla stessa pagina; «Ripeti» la rimette
        f.annulla()
        assert f.pagine[0].repo.elenco("imprese") == []
        assert f.contenitore.currentWidget() is f.pagine[2] and f.azione_ripeti.isEnabled()
        f.ripeti()
        assert [i["ragione_sociale"] for i in f.pagine[0].repo.elenco("imprese")] == ["Edil Alfa"]
        assert f.modifiche_non_salvate()

        # Ricerca: il risultato porta alla pagina dell'impresa
        dialogo = ui_ricerca.DialogoRicerca(f.pagine[0].repo, f.vai_a_sezione, f)
        dialogo.campo.setText("alfa")
        dialogo._primo()
        assert dialogo.result() == QtWidgets.QDialog.DialogCode.Accepted
        assert any(isinstance(p, (PaginaImprese,)) or "Imprese" in p.sezioni_controlli
                   for p in [f.pagine[f.navigazione.currentRow()]])

        # Modello: salvato dal cantiere aperto, poi un nuovo cantiere che ne riparte
        monkeypatch.setattr(ui_modelli, "chiedi_nome_modello", lambda *a: "Tipo")
        f.salva_come_modello()
        modello = modelli.elenco(edizione.estensione)[0]
        monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                            lambda *a, **k: (str(tmp_path / f"nuovo-{chiave}"), ""))
        f._nuovo(modello)
        assert f.progetto.percorso.name == f"nuovo-{chiave}{edizione.estensione}"
        assert [i["ragione_sociale"] for i in f.pagine[0].repo.elenco("imprese")] == ["Edil Alfa"]
        f.close()

    panoramica = DialogoPrimoAvvio("SicurCantiere PSC", "PSC")
    for _ in range(panoramica.pila.count() - 1):
        panoramica._vai(1)
    assert panoramica.avanti.text() == "Inizia"
    panoramica.close()


@pytest.mark.skipif(not __import__("shutil").which("soffice"), reason="serve LibreOffice")
def test_anteprima_pdf_della_bozza(app, tmp_path):
    from sicurcantiere import composizioni
    from sicurcantiere.documenti import pdf
    from sicurcantiere.ui.anteprima import DialogoAnteprima

    repo = Repository(Progetto(tmp_path / "a.scs", crea=True))
    repo.aggiorna_cantiere(nome="Scuola")
    bozza = composizioni.componi(repo, "PSC")
    contenuto = pdf.converti_dati(composizioni.contenuto(repo, bozza["id"]))
    dialogo = DialogoAnteprima(contenuto, "PSC", "PSC - Scuola")
    assert dialogo.documento.pageCount() > 5
    dialogo._zoom(1.2)
    dialogo.close()
    repo.progetto.chiudi()


def test_finestra_sta_su_un_portatile(app, tmp_path):
    """Con tutte le pagine caricate la finestra deve poter stare su uno schermo 1366x768."""
    from sicurcantiere.ui.edizioni import EDIZIONI

    for chiave, edizione in EDIZIONI.items():
        f = FinestraPrincipale(edizione)
        f._carica(Progetto(tmp_path / f"p{edizione.estensione}", crea=True))
        f.resize(1366, 740)
        for riga in range(len(f.pagine)):
            f.navigazione.setCurrentRow(riga)
        assert f.minimumSizeHint().width() <= 1366, chiave
        assert f.minimumSizeHint().height() <= 720, chiave
        f.close()


def test_revisione_ux_elenco_dettaglio_e_documenti(app, tmp_path):
    from sicurcantiere import controlli
    from sicurcantiere.ui.pagine import PaginaSoggetti

    p = Progetto(tmp_path / "ux.scs", crea=True)
    p.chiudi()
    f = FinestraPrincipale()
    f.apri_file(tmp_path / "ux.scs")
    repo = f.pagine[0].repo

    # elenco e dettaglio: «Aggiungi» apre il pannello sul primo campo e i campi si salvano da lì
    sog = _pagina(f, PaginaSoggetti)
    f.navigazione.setCurrentRow(f.pagine.index(sog))
    assert sog.tabella.dettaglio is not None
    sog.tabella.aggiungi()
    nuovo = sog.tabella.id_selezionato()
    nome = sog.tabella.dettaglio.editori["nome"]
    nome.setText("Ing. Bianchi")
    nome.editingFinished.emit()
    assert repo.leggi("soggetti", nuovo)["nome"] == "Ing. Bianchi"
    assert any(b.text().startswith("+ ") for b in sog._pulsanti_ruoli)  # ruoli obbligatori da inserire

    # rischi: filtri sopra l'elenco
    fasi = _pagina(f, PaginaFasi)
    repo.importa_lavorazione(next(l for l in LAVORAZIONI if l["codice"] == "AL.21"))
    f.navigazione.setCurrentRow(f.pagine.index(fasi))
    fasi.fasi.seleziona_prima()
    tutti = len(fasi.rischi.righe())
    nome_alti, _ = fasi.rischi._filtri[1][1], None
    fasi.rischi._scegli_filtro(fasi.rischi._filtri[1][0])
    visibili = sum(1 for r in range(fasi.rischi.vista.rowCount()) if not fasi.rischi.vista.isRowHidden(r))
    assert 0 < visibili <= tutti and "Alti" in nome_alti

    # documenti: stato in testa e cose da sistemare con la loro pagina
    doc = _pagina(f, PaginaDocumenti)
    f.navigazione.setCurrentRow(f.pagine.index(doc))
    assert "non è ancora pronto" in doc.stato.text() or "si può comporre" in doc.stato.text()
    assert doc.controlli.count() > 0 and doc.pulsante_componi.isVisible() is not None

    # spazi da riempire e dichiarazioni esplicite
    fid = repo.elenco("fasi")[0]["id"]
    repo.aggiorna("fasi", fid, addetto="Sig. Rossi_", modalita="attestato del _____")
    assert any("spazi da riempire" in s.messaggio for s in controlli.controlla(repo))
    assert any(s.sezione == "Fascicolo" for s in controlli.controlla(repo))
    repo.salva_testo(controlli.NESSUN_INTERVENTO, "1")
    assert not any(s.sezione == "Fascicolo" for s in controlli.controlla(repo))
    f.salva()
    f.close()


def test_psc_rischi_2_2_3_planimetria_e_lavori_pubblici(app, tmp_path):
    import json

    from sicurcantiere import relazione
    from sicurcantiere.ui.pagine import PaginaDatiGenerali
    from sicurcantiere.ui.relazione_psc import AllegatiPSC, RischiParticolari

    repo = Repository(Progetto(tmp_path / "p.scs", crea=True))
    f = repo.importa_lavorazione(LAVORAZIONI[0])
    repo.inserisci("rischi", fase_id=f, descrizione="Caduta dall'alto", probabilita=2, danno=3)
    r = RischiParticolari(repo)
    r.carica()
    spunta, misure, etichetta = r.voci_223["c"]
    assert etichetta.text().startswith("Nelle fasi:")
    r.verificato_223.setChecked(True)
    spunta.setChecked(True)
    misure.setText("Parapetti e ponteggi")
    r.salva()
    dati = json.loads(repo.testo(relazione.CHIAVE_RISCHI_LAVORAZIONI))
    assert dati["verificato"] and dati["voci"]["c"] == {"presente": True, "misure": "Parapetti e ponteggi"}

    a = AllegatiPSC(repo)
    a.carica()
    a.contenuti["Recinzione del cantiere"].setChecked(True)
    assert relazione.leggi_contenuti_planimetria(repo.testo(relazione.CHIAVE_CONTENUTI_PLANIMETRIA)) == {
        "Recinzione del cantiere"}

    pagina = PaginaDatiGenerali(repo)
    pagina.aggiorna()
    pagina.pubblici.setChecked(True)
    assert repo.cantiere()["lavori_pubblici"] == 1
