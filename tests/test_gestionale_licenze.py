import re
from datetime import date, timedelta

import pytest

pytest.importorskip("flask")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SICURCANTIERE_LICENZE_DATI", str(tmp_path / "dati"))
    from licenze import archivio
    from licenze.app import crea_app, crea_utente

    pubblica = archivio.genera_chiave()
    monkeypatch.setenv("SICURCANTIERE_CHIAVE_LICENZE", pubblica)
    crea_utente("antonio", "una password lunga")
    app = crea_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.environ_base["wsgi.url_scheme"] = "https"  # cookie di sessione solo su HTTPS
    return client


def _token(client):
    with client.session_transaction() as s:
        return s.get("token") or ""


def _accedi(client, password="una password lunga", codice=""):
    client.get("/accesso")
    return client.post("/accesso", data={"nome": "antonio", "password": password, "codice": codice,
                                         "token": _token(client)})


def test_accesso_obbligatorio_e_token(client):
    assert client.get("/").status_code == 302  # senza accesso si va alla pagina di login
    assert "Content-Security-Policy" in client.get("/accesso").headers
    assert "non corretti" in _accedi(client, "sbagliata").get_data(as_text=True)
    assert _accedi(client).status_code == 302
    assert client.get("/").status_code == 200
    # un modulo senza token (richiesta da un altro sito) viene rifiutato
    assert client.post("/clienti/nuovo", data={"nome": "X"}).status_code == 400


def test_cliente_licenza_rinnovo_pagamento(client):
    from licenze import archivio
    from sicurcantiere import licenza

    _accedi(client)
    t = _token(client)
    r = client.post("/clienti/nuovo", data={"nome": "Studio Rossi", "email": "rossi@example.com", "token": t})
    cliente = int(r.headers["Location"].rsplit("/", 1)[1])
    scadenza = (date.today() + timedelta(days=365)).isoformat()
    r = client.post(f"/clienti/{cliente}/licenza", data={"piano": "completo", "scadenza": scadenza,
                                                         "postazioni": "2", "prezzo": "249", "token": t})
    pagina = client.get(r.headers["Location"]).get_data(as_text=True)
    codice = re.search(r"(SC1-[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)", pagina).group(1)
    l = licenza.leggi(codice)  # il programma riconosce la licenza firmata dal gestionale
    assert l.cliente == "Studio Rossi" and l.piano == "completo" and l.postazioni == 2
    assert l.scadenza.isoformat() == scadenza and l.id.startswith(f"SC-{date.today().year}-")
    assert "Aiuto &gt; Licenza" in pagina  # testo pronto per l'email

    id_licenza = int(r.headers["Location"].rsplit("/", 1)[1])
    r = client.post(f"/licenze/{id_licenza}/rinnova", data={"prezzo": "249", "token": t})
    rinnovo = client.get(r.headers["Location"]).get_data(as_text=True)
    nuovo = licenza.leggi(re.search(r"(SC1-[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)", rinnovo).group(1))
    assert nuovo.scadenza == l.scadenza + timedelta(days=365)
    conn = archivio.connessione()
    assert conn.execute("SELECT stato FROM licenze WHERE id = ?", (id_licenza,)).fetchone()[0] == "rinnovata"

    client.post(f"/clienti/{cliente}/pagamento", data={"importo": "249,00", "metodo": "Bonifico",
                                                       "fattura": "12/2026", "licenza_id": str(id_licenza), "token": t})
    scheda = client.get(f"/clienti/{cliente}").get_data(as_text=True)
    assert "249,00 €" in scheda and "12/2026" in scheda
    assert "Studio Rossi" in client.get("/clienti?cerca=rossi").get_data(as_text=True)
    csv = client.get("/esporta.csv").get_data(as_text=True)
    assert "Studio Rossi" in csv and csv.count("\n") == 3
    assert archivio.chiave_pubblica() in client.get("/impostazioni").get_data(as_text=True)


def test_blocco_dopo_troppi_tentativi(client):
    for _ in range(5):
        assert _accedi(client, "sbagliata").status_code == 200
    r = _accedi(client)  # bloccato anche con la password giusta
    assert r.status_code == 429 and "Troppi tentativi" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_verifica_in_due_passaggi(client):
    import time

    from licenze import totp

    _accedi(client)
    assert "due passaggi non è attiva" in client.get("/").get_data(as_text=True)
    pagina = client.get("/impostazioni/due-passaggi").get_data(as_text=True)
    assert "data:image/svg+xml" in pagina or "segno" not in pagina
    with client.session_transaction() as s:
        segreto = s["totp_nuovo"]
    adesso = int(time.time() // totp.PERIODO)
    client.post("/impostazioni/due-passaggi", data={"codice": "000000" if totp.codice(segreto, adesso) != "000000"
                                                     else "111111", "token": _token(client)})
    assert "due passaggi non è attiva" in client.get("/").get_data(as_text=True)  # codice sbagliato: non attivata
    client.post("/impostazioni/due-passaggi", data={"codice": totp.codice(segreto, adesso), "token": _token(client)})
    assert "due passaggi non è attiva" not in client.get("/").get_data(as_text=True)

    client.post("/esci", data={"token": _token(client)})
    assert _accedi(client).status_code == 200  # senza codice non si entra
    assert _accedi(client, codice=totp.codice(segreto, adesso)).status_code == 200  # codice già usato
    assert _accedi(client, codice=totp.codice(segreto, adesso + 1)).status_code == 302
    assert client.get("/").status_code == 200


def test_codici_totp_rfc6238():
    import base64

    from licenze import totp

    segreto = base64.b32encode(b"12345678901234567890").decode()
    assert totp.verifica(segreto, "287082", adesso=59) == 1
    assert totp.verifica(segreto, "287082", ultimo=1, adesso=59) is None
    assert totp.verifica(segreto, "287082", adesso=59 + 120) is None


def test_promemoria_e_registro_invii(client):
    from licenze import archivio

    _accedi(client)
    t = _token(client)
    r = client.post("/clienti/nuovo", data={"nome": "Studio Bianchi", "email": "bianchi@example.com", "token": t})
    cliente = int(r.headers["Location"].rsplit("/", 1)[1])
    scadenza = (date.today() + timedelta(days=45)).isoformat()
    r = client.post(f"/clienti/{cliente}/licenza", data={"piano": "pos", "scadenza": scadenza, "token": t})
    id_licenza = int(r.headers["Location"].rsplit("/", 1)[1])
    pagina = client.get(f"/licenze/{id_licenza}").get_data(as_text=True)
    assert "mailto:bianchi%40example.com?subject=" in pagina and "Promemoria di rinnovo" in pagina
    # scade fra 45 giorni: non compare a 30, compare a 60 (predefinito)
    assert "Studio Bianchi" not in client.get("/?giorni=30").get_data(as_text=True).split("Ultime licenze")[0]
    cruscotto = client.get("/").get_data(as_text=True)
    assert "Email di promemoria" in cruscotto and "<td>mai</td>" in cruscotto
    client.post(f"/licenze/{id_licenza}/invio", data={"tipo": "codice", "token": t})
    client.post(f"/licenze/{id_licenza}/invio", data={"tipo": "promemoria", "token": t, "torna": "/"})
    assert client.post(f"/licenze/{id_licenza}/invio", data={"tipo": "altro", "token": t}).status_code == 400
    registro = client.get("/registro").get_data(as_text=True)
    assert "Codice consegnato" in registro and "Promemoria di rinnovo" in registro and "bianchi@example.com" in registro
    assert "<td>mai</td>" not in client.get("/").get_data(as_text=True)
    assert archivio.connessione().execute("SELECT COUNT(*) FROM invii").fetchone()[0] == 2


def test_reinserisci_codice_dopo_la_perdita_del_database(client, tmp_path, capsys):
    from licenze import archivio
    from licenze.__main__ import main
    from licenze.app import _nuovo_identificativo
    from sicurcantiere import licenza

    privata = archivio.chiave_privata()
    anno = date.today().year
    codici = [licenza.firma(licenza.Licenza(f"SC-{anno}-{n:04d}", "Studio Rossi", "studio", date.today(),
                                            date.today() + timedelta(days=300), 3), privata) for n in (1, 3)]
    assert main(["reinserisci-codice", codici[0]]) == 0 and "reinserita" in capsys.readouterr().out
    assert main(["reinserisci-codice", codici[1]]) == 0
    assert main(["reinserisci-codice", codici[1]]) == 0 and "c'è già" in capsys.readouterr().out
    conn = archivio.connessione()
    righe = conn.execute("SELECT l.*, c.nome FROM licenze l JOIN clienti c ON c.id = l.cliente_id").fetchall()
    assert len(righe) == 2 and {r["nome"] for r in righe} == {"Studio Rossi"}  # un solo cliente
    assert righe[0]["piano"] == "studio" and righe[0]["postazioni"] == 3
    assert _nuovo_identificativo(conn) == f"SC-{anno}-0004"  # mai un numero già usato
    falso = licenza.firma(licenza.Licenza("X", "Y", "pos", date.today()), bytes(32))  # firmato da un'altra chiave
    assert main(["reinserisci-codice", falso]) == 1
