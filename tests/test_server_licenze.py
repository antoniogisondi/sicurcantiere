"""Server delle attivazioni con il modulo dei programmi (sicur_license) collegato davvero.

Il caso centrale: una licenza per N PC rifiuta il PC in più (N+1), qualunque sia N.
"""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("flask")

from sicur_license import custodia  # noqa: E402
from sicur_license.cliente import (  # noqa: E402
    ALTRO_PC,
    CODICE_ERRATO,
    LICENZA_REVOCATA,
    LICENZA_SCADUTA,
    PC_LIBERATO,
    POSTI_ESAURITI,
    TROPPE_RICHIESTE,
    TROPPI_TRASFERIMENTI,
    ErroreServer,
    Licenze,
)
from sicur_license.stato import ATTIVA, DA_ATTIVARE, REVOCATA_, SCADUTA  # noqa: E402

INIZIO = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


class Orologio:
    def __init__(self):
        self.ora = INIZIO

    def __call__(self):
        return self.ora

    def avanti(self, **durata):
        self.ora += timedelta(**durata)


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("SICURCANTIERE_LICENZE_DATI", str(tmp_path / "dati"))
    from licenze import api, archivio, attivazioni

    archivio.genera_chiave()
    monkeypatch.setenv("SICURCANTIERE_CHIAVE_LICENZE", archivio.chiave_pubblica())
    orologio = Orologio()
    monkeypatch.setattr(attivazioni, "adesso", orologio)
    app = api.crea_api()
    app.config["TESTING"] = True
    client = app.test_client()

    class Server:
        def __init__(self):
            self.orologio, self.client, self.cartella = orologio, client, tmp_path
            self.conn = archivio.connessione()
            self.cliente = self.conn.execute("INSERT INTO clienti (nome) VALUES ('Studio Rossi')").lastrowid
            self.conn.commit()

        def licenza(self, piano="completo", postazioni=3, scadenza=date(2027, 10, 22), rinnovo_di=None):
            from licenze.app import emetti

            id_ = emetti(self.conn, self.cliente, piano, scadenza, postazioni, 0, rinnovo_di=rinnovo_di)
            return self.conn.execute("SELECT codice FROM licenze WHERE id = ?", (id_,)).fetchone()[0], id_

        def trasporto(self, ip="203.0.113.10"):
            def invia(percorso, dati):
                r = self.client.post("/api/licenze/" + percorso, json=dati, environ_base={"REMOTE_ADDR": ip})
                return r.status_code, r.get_json()
            return invia

        def pc(self, nome, ip="203.0.113.10", programma="psc", cartella=None, **componenti):
            return PC(self, nome, ip, programma, componenti, cartella)

        def eventi(self, evento, esito=None):
            sql, valori = "SELECT * FROM eventi_licenza WHERE evento = ?", [evento]
            if esito:
                sql, valori = sql + " AND esito = ?", valori + [esito]
            return archivio.connessione().execute(sql, valori).fetchall()

    return Server()


class PC:
    """Un PC del cliente: la sua cartella della licenza e i suoi componenti."""

    def __init__(self, server, nome, ip, programma, componenti, cartella=None):
        from licenze import archivio

        self.server = server
        self.cartella = server.cartella / "pc" / (cartella or nome)
        valori = {"sistema": f"guid-{nome}", "hardware": f"scheda-{nome}", "nome": nome}
        valori.update({k[:-1] if k.endswith("_") else k: v for k, v in componenti.items()})
        self.licenze = Licenze(programma, archivio.radice_pubblica(), server.trasporto(ip), versione="0.23.0",
                               componenti=valori, nome=valori["nome"])

    def __getattr__(self, nome):
        import os

        os.environ["SICUR_LICENSE_CARTELLA"] = str(self.cartella)
        return getattr(self.licenze, nome)

    def esito(self, ora=None):
        import os

        os.environ["SICUR_LICENSE_CARTELLA"] = str(self.cartella)
        return self.licenze.esito(ora or self.server.orologio.ora)


@pytest.fixture(autouse=True)
def ripristina_cartella(monkeypatch, tmp_path):
    monkeypatch.setenv("SICUR_LICENSE_CARTELLA", str(tmp_path / "nessuna"))


# --- limite di PC: il PC in più rispetto alla licenza ---

@pytest.mark.parametrize("posti", [1, 2, 3, 5])
def test_pc_in_piu_rispetto_alla_licenza(server, posti):
    codice, _ = server.licenza(postazioni=posti)
    pcs = [server.pc(f"PC-{i}") for i in range(1, posti + 1)]
    for pc in pcs:
        pc.attiva(codice)
        assert pc.esito().tipo == ATTIVA
    in_piu = server.pc("PC-IN-PIU")
    with pytest.raises(ErroreServer) as rifiuto:
        in_piu.attiva(codice)
    e = rifiuto.value
    assert e.codice == POSTI_ESAURITI
    assert f"già attiva su {posti} PC su {posti}" in str(e)
    assert [p["nome"] for p in e.pc] == [f"PC-{i}" for i in range(1, posti + 1)]
    assert all(p["ultimo_uso"] and not p["questo"] for p in e.pc)
    assert e.dati["posti"] == posti and in_piu.esito().tipo == DA_ATTIVARE
    assert len(server.eventi("attivazione", POSTI_ESAURITI)) == 1  # il tentativo resta nel registro
    # riattivare un PC già attivo (anche dopo aver reinstallato il programma) non consuma posti
    pcs[0].attiva(codice)
    assert len(server.eventi("attivazione", "nuovo_pc")) == posti


def test_stesso_pc_con_un_componente_cambiato(server):
    codice, _ = server.licenza(postazioni=1)
    server.pc("UFFICIO").attiva(codice)
    # nuovo nome del PC: 2 componenti su 3 uguali, stesso posto (e il nome si aggiorna nell'elenco)
    rinominato = server.pc("UFFICIO", nome_="UFFICIO-NUOVO")
    rinominato.attiva(codice)
    assert rinominato.esito().tipo == ATTIVA
    assert [p["nome"] for p in rinominato.elenco_pc(codice)["pc"]] == ["UFFICIO-NUOVO"]
    # Windows reinstallato con lo stesso nome (quello attuale): MachineGuid nuovo, stesso PC
    server.pc("UFFICIO", nome_="UFFICIO-NUOVO", sistema="guid-reinstallato").attiva(codice)
    # un PC davvero diverso: rifiutato
    with pytest.raises(ErroreServer):
        server.pc("ALTRO").attiva(codice)


def test_trasferimento_self_service(server):
    codice, _ = server.licenza(postazioni=2)
    a, b, c = server.pc("A"), server.pc("B"), server.pc("C")
    a.attiva(codice)
    b.attiva(codice)
    with pytest.raises(ErroreServer):
        c.attiva(codice)
    elenco = c.elenco_pc(codice)
    assert elenco["attivi"] == 2 and elenco["posti"] == 2 and elenco["trasferimenti_rimasti"] == 2
    id_a = next(p["id"] for p in elenco["pc"] if p["nome"] == "A")
    assert c.libera(codice, id_a)["trasferimenti_rimasti"] == 2
    c.attiva(codice)
    assert c.esito().tipo == ATTIVA
    assert c.elenco_pc(codice)["trasferimenti_rimasti"] == 1
    # il PC liberato se ne accorge alla convalida e torna da attivare
    with pytest.raises(ErroreServer) as liberato:
        a.convalida()
    assert liberato.value.codice == PC_LIBERATO and a.esito().tipo == DA_ATTIVARE


def test_limite_trasferimenti_contro_il_posto_che_gira(server):
    codice, _ = server.licenza(postazioni=1)
    a, b = server.pc("A"), server.pc("B")
    a.attiva(codice)                      # 1ª attivazione: il posto della licenza
    a.disattiva()
    b.attiva(codice)                      # 1° trasferimento
    b.disattiva()
    a.attiva(codice)                      # 2° trasferimento
    a.disattiva()
    with pytest.raises(ErroreServer) as rifiuto:
        b.attiva(codice)                  # il terzo nello stesso mese: serve l'assistenza
    assert rifiuto.value.codice == TROPPI_TRASFERIMENTI and "assistenza" in str(rifiuto.value)
    server.orologio.avanti(days=31)
    b.attiva(codice)                      # passato il mese si può di nuovo
    assert b.esito().tipo == ATTIVA


def test_disattivazione_libera_il_posto(server):
    codice, _ = server.licenza(postazioni=1)
    a, b = server.pc("A"), server.pc("B")
    a.attiva(codice)
    a.disattiva()
    assert a.esito().tipo == DA_ATTIVARE
    b.attiva(codice)
    assert b.esito().tipo == ATTIVA
    a.disattiva()  # già disattivato: nessun errore


def test_convalida_rinnova_il_certificato(server):
    codice, _ = server.licenza()
    a = server.pc("A")
    primo = a.attiva(codice)
    server.orologio.avanti(days=10)
    rinnovato = a.convalida()
    assert rinnovato.emesso > primo.emesso and rinnovato.valido_fino == server.orologio.ora + timedelta(days=14)
    assert a.esito(server.orologio.ora + timedelta(days=13)).tipo == ATTIVA  # oltre i 14 giorni del primo


def test_rinnovo_della_licenza_mantiene_i_pc(server):
    codice, id_ = server.licenza(postazioni=1, scadenza=date(2026, 12, 31))
    a = server.pc("A")
    a.attiva(codice)
    nuovo_codice, _ = server.licenza(postazioni=1, scadenza=date(2027, 12, 31), rinnovo_di=id_)
    server.conn.execute("UPDATE licenze SET stato = 'rinnovata' WHERE id = ?", (id_,))
    server.conn.commit()
    assert a.convalida().scadenza_licenza == date(2027, 12, 31)  # stessa catena: il PC resta attivo
    a.attiva(nuovo_codice)  # anche con il nuovo codice è lo stesso PC: nessun posto in più
    assert len(server.eventi("attivazione", "nuovo_pc")) == 1
    with pytest.raises(ErroreServer):  # il posto resta uno solo
        server.pc("B").attiva(nuovo_codice)


def test_revoca(server):
    codice, id_ = server.licenza()
    a = server.pc("A")
    a.attiva(codice)
    server.conn.execute("UPDATE licenze SET stato = 'annullata' WHERE id = ?", (id_,))
    server.conn.commit()
    a.convalida()  # il server manda il certificato «revocato»: sola lettura subito, senza aspettare 14 giorni
    esito = a.esito()
    assert esito.tipo == REVOCATA_ and esito.sola_lettura
    with pytest.raises(ErroreServer) as rifiuto:
        server.pc("B").attiva(codice)
    assert rifiuto.value.codice == LICENZA_REVOCATA


def test_licenza_scaduta(server):
    codice, _ = server.licenza(scadenza=date(2026, 11, 30))
    a = server.pc("A")
    a.attiva(codice)
    server.orologio.avanti(days=45)
    a.convalida()  # il PC già attivo riceve il certificato con la scadenza: sola lettura
    assert a.esito().tipo == SCADUTA
    with pytest.raises(ErroreServer) as rifiuto:
        server.pc("B").attiva(codice)  # nessun PC nuovo su una licenza scaduta
    assert rifiuto.value.codice == LICENZA_SCADUTA and "30/11/2026" in str(rifiuto.value)


def test_programma_non_incluso_non_consuma_posti(server):
    codice, _ = server.licenza(piano="pos", postazioni=1)
    with pytest.raises(ErroreServer) as rifiuto:
        server.pc("A", programma="psc").attiva(codice)
    assert rifiuto.value.codice == "non_incluso" and "SicurCantiere PSC" in str(rifiuto.value)
    server.pc("A", programma="pos").attiva(codice)  # il posto è ancora libero


def test_codici_sbagliati_e_limite_per_indirizzo(server):
    codice, _ = server.licenza()
    curioso = server.pc("CURIOSO", ip="198.51.100.7")
    for i in range(10):
        with pytest.raises(ErroreServer) as rifiuto:
            curioso.attiva(f"SC1-codice-inventato-{i}")
        assert rifiuto.value.codice == CODICE_ERRATO
    with pytest.raises(ErroreServer) as bloccato:
        curioso.attiva(codice)  # bloccato anche con il codice giusto per un'ora
    assert bloccato.value.codice == TROPPE_RICHIESTE
    server.pc("CLIENTE", ip="203.0.113.50").attiva(codice)  # gli altri indirizzi non sono toccati
    server.orologio.avanti(hours=1, minutes=1)
    curioso.attiva(codice)


def test_indirizzo_del_tunnel_non_blocca_tutti(server):
    codice, _ = server.licenza(postazioni=5)
    for i in range(12):  # tutti da 127.0.0.1 (tunnel senza indirizzo del programma)
        with pytest.raises(ErroreServer):
            server.pc(f"X{i}", ip="127.0.0.1").attiva(f"SC1-sbagliato-{i}")
    server.pc("CLIENTE", ip="127.0.0.1").attiva(codice)


def test_certificato_alterato_o_copiato(server):
    codice, _ = server.licenza()
    a = server.pc("A")
    a.attiva(codice)
    # copia della cartella della licenza su un altro PC
    import shutil

    b = server.pc("B")
    shutil.copytree(a.cartella, b.cartella)
    with pytest.raises(ErroreServer) as copia:
        b.convalida()
    assert copia.value.codice == ALTRO_PC
    # certificato manomesso inviato al server
    stato, risposta = server.trasporto()("convalida", {"certificato": "{}", "impronte": ["", "", ""]})
    assert stato == 400 and risposta["errore"] == "certificato"


def test_macchina_virtuale_clonata_segnalata(server):
    codice, _ = server.licenza()
    a = server.pc("A", ip="203.0.113.10")
    a.attiva(codice)
    clone = server.pc("A", ip="192.0.2.99", cartella="clone")  # stessa impronta, altra rete
    import shutil

    shutil.copytree(a.cartella, clone.cartella)
    server.orologio.avanti(minutes=3)
    clone.convalida()
    assert len(server.eventi("sospetto_clone")) == 1
    from licenze import archivio

    assert "192.0.2.99" in archivio.connessione().execute("SELECT sospetto FROM pc_licenza").fetchone()[0]


def test_attivazione_offline_dal_gestionale(server):
    from licenze import archivio, attivazioni

    codice, _ = server.licenza(postazioni=1)
    a = server.pc("CANTIERE")
    richiesta = a.richiesta_offline(codice)
    conn = archivio.connessione()
    risposta = attivazioni.attiva_offline(conn, richiesta, server.orologio.ora)
    conn.commit()
    certificato = a.importa_offline(risposta)
    assert certificato.offline and certificato.valido_fino == server.orologio.ora + timedelta(days=90)
    assert a.esito(server.orologio.ora + timedelta(days=60)).tipo == ATTIVA
    with pytest.raises(attivazioni.Rifiuto) as pieno:  # il posto è occupato dal PC offline
        attivazioni.attiva_offline(conn, server.pc("ALTRO").richiesta_offline(codice), server.orologio.ora)
    assert pieno.value.codice == POSTI_ESAURITI
    with pytest.raises(attivazioni.Rifiuto):
        attivazioni.attiva_offline(conn, "non è una richiesta", server.orologio.ora)


def test_richieste_non_valide_e_errori_senza_dettagli(server, monkeypatch):
    t = server.trasporto()
    assert t("sconosciuta", {})[0] == 404
    stato, risposta = t("attiva", {"codice": "x", "impronte": "non una lista"})
    assert stato in (400, 404)
    r = server.client.post("/api/licenze/attiva", data="non json", content_type="application/json")
    assert r.status_code == 400
    from licenze import attivazioni

    def guasto(*_args, **_kwargs):
        raise RuntimeError("percorso segreto /var/lib/...")

    monkeypatch.setitem(attivazioni.AZIONI, "attiva", guasto)
    stato, risposta = t("attiva", {})
    assert stato == 500 and "segreto" not in json.dumps(risposta) and risposta["errore"] == "interno"


def test_chiave_di_servizio_si_rinnova(server):
    from licenze import archivio

    codice, _ = server.licenza()
    a = server.pc("A")
    a.attiva(codice)
    vecchia = json.loads((server.cartella / "dati" / "servizio.json").read_text())["privata"]
    server.orologio.avanti(days=160)  # mancano meno di 30 giorni alla fine della chiave di servizio
    a.convalida()
    nuova = json.loads((server.cartella / "dati" / "servizio.json").read_text())["privata"]
    assert nuova != vecchia and a.esito().tipo == ATTIVA
    # server separato senza chiave radice e con la chiave di servizio scaduta: non firma più
    (server.cartella / "dati" / "chiave_privata.pem").rename(server.cartella / "radice-al-sicuro.pem")
    server.orologio.avanti(days=200)
    with pytest.raises(FileNotFoundError):
        archivio.chiave_servizio(server.orologio.ora)


def test_collegamento_http_vero(server, tmp_path, monkeypatch):
    """Il programma usa urllib verso un server web vero (come attraverso il tunnel)."""
    import threading

    from werkzeug.serving import make_server

    from licenze import api, archivio
    from sicur_license.cliente import trasporto_http

    codice, _ = server.licenza(postazioni=1)
    web = make_server("127.0.0.1", 0, api.crea_api())
    threading.Thread(target=web.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("SICUR_LICENSE_CARTELLA", str(tmp_path / "http"))
        l = Licenze("psc", archivio.radice_pubblica(), trasporto_http(f"http://127.0.0.1:{web.server_port}"),
                    componenti={"sistema": "g", "hardware": "h", "nome": "N"})
        l.attiva(codice)
        assert l.esito(server.orologio.ora).tipo == ATTIVA and custodia.leggi_certificato()
    finally:
        web.shutdown()


def test_comandi_del_server(server, tmp_path, capsys):
    from licenze.__main__ import main

    codice, id_ = server.licenza(postazioni=2)
    a = server.pc("CANTIERE")
    richiesta = tmp_path / "richiesta.json"
    richiesta.write_text(a.richiesta_offline(codice), encoding="utf-8")
    assert main(["attivazione-offline", str(richiesta)]) == 0
    assert a.importa_offline((tmp_path / "richiesta.sclic").read_text(encoding="utf-8")).offline
    identificativo = server.conn.execute("SELECT codice_licenza FROM licenze WHERE id = ?", (id_,)).fetchone()[0]
    assert main(["pc", identificativo]) == 0
    uscita = capsys.readouterr().out
    assert "1 PC attivi su 2" in uscita and "CANTIERE" in uscita and "(offline)" in uscita
    assert main(["chiave-servizio"]) == 0


def test_programmi_usati_sullo_stesso_pc(server):
    """L'attivazione vale per il PC e per tutti i programmi della licenza: si annotano quelli usati."""
    from licenze import archivio

    codice, _ = server.licenza(piano="completo", postazioni=1)
    server.pc("CASA", programma="pimus", cartella="casa").attiva(codice)
    for programma in ("psc", "pos"):
        server.pc("CASA", programma=programma, cartella="casa").convalida()  # stesso certificato, altro programma
    riga = archivio.connessione().execute("SELECT programma FROM pc_licenza").fetchone()
    assert riga["programma"] == "psc,pos,pimus"
    from licenze.attivazioni import nomi_programmi, programmi_usati

    assert nomi_programmi(riga["programma"]) == "PSC, POS, PiMUS"
    assert programmi_usati("pos", "") == "pos" and programmi_usati("", "sconosciuto") == ""
