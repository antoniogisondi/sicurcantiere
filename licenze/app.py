"""Gestionale web delle licenze SicurCantiere: clienti, licenze, rinnovi, pagamenti e scadenze.

Gira sul server dell'ufficio e si può aprire anche da internet: chi lo apre dal browser deve
accedere con nome, password e (se attivato) il codice dell'app di autenticazione; dopo troppi
tentativi errati l'accesso si blocca per 15 minuti. Qui si firmano le licenze con la chiave
privata, che non lascia mai il server; i programmi dei clienti verificano il codice senza
collegarsi a niente.
"""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import time
from datetime import date, timedelta
from urllib.parse import quote

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from licenze import archivio, totp
from sicurcantiere import licenza

GIORNI_AVVISO = 30  # «in scadenza» nello stato della licenza
FINESTRE_CRUSCOTTO = (30, 60, 90)  # giorni di anticipo selezionabili nel cruscotto
DOWNLOAD = "https://github.com/antoniogisondi/sicurcantiere/releases/latest/download/SicurCantiere-setup.exe"
TIPI_INVIO = {"codice": "Codice consegnato", "promemoria": "Promemoria di rinnovo"}
BLOCCO_SECONDI = 15 * 60
TENTATIVI_UTENTE = 5  # tentativi sbagliati per nome utente prima del blocco
TENTATIVI_IP = 20  # tentativi sbagliati dallo stesso indirizzo prima del blocco
METODI_PAGAMENTO = ("Bonifico", "Carta", "PayPal", "Contanti", "Altro")


def crea_app(https: bool = True) -> Flask:
    """https=False solo per le prove in locale (python -m licenze prova)."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = archivio.segreto_sessione()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["SESSION_COOKIE_SECURE"] = https
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    if os.environ.get("SICURCANTIERE_LICENZE_PROXY") == "1":
        # Dietro Caddy (accesso da internet): l'indirizzo del visitatore arriva in X-Forwarded-For.
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.context_processor
    def comuni():
        return {"piani": licenza.PIANI, "token": _token(), "oggi": date.today().isoformat(),
                "utente": session.get("utente"), "con_2fa": session.get("2fa", False)}

    app.template_filter("data")(_data)

    @app.template_filter("istante")
    def istante(valore):
        """Data e ora (ora italiana) di un evento registrato in UTC."""
        if not valore:
            return "—"
        from datetime import datetime
        from zoneinfo import ZoneInfo

        try:
            return datetime.fromisoformat(valore).astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M")
        except (ValueError, KeyError):
            return str(valore)[:16]

    @app.template_filter("programmi")
    def programmi(valore):
        from licenze.attivazioni import nomi_programmi

        return nomi_programmi(valore) or "—"

    @app.template_filter("evento")
    def evento(riga):
        from licenze.attivazioni import descrizione

        return descrizione(riga["evento"], riga["esito"])

    @app.template_filter("milioni")
    def milioni(valore):
        return f"{(valore or 0) / 1_000_000:.2f}".replace(".", ",") + " mln"

    @app.template_filter("euro")
    def euro(valore):
        return f"{float(valore or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.before_request
    def controlli():
        atteso = session.get("token")
        if request.method == "POST" and (not atteso or not secrets.compare_digest(request.form.get("token", ""), atteso)):
            abort(400, "Modulo scaduto: ricarica la pagina.")
        if request.endpoint not in ("accesso", "static") and not session.get("utente"):
            return redirect(url_for("accesso", prossima=request.path))
        return None

    @app.after_request
    def intestazioni(risposta):
        risposta.headers.setdefault("Content-Security-Policy",
                                    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                                    "frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        risposta.headers.setdefault("X-Frame-Options", "DENY")
        risposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        risposta.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.endpoint != "static":
            risposta.headers.setdefault("Cache-Control", "no-store")
        return risposta

    @app.teardown_appcontext
    def chiudi_db(_errore):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    _rotte(app)
    return app


def _token() -> str:
    if "token" not in session:
        session["token"] = secrets.token_urlsafe(24)
    return session["token"]


def _db():
    """Connessione della richiesta: si chiude alla fine (le modifiche non confermate si annullano), così una
    pagina interrotta da un errore non lascia il database bloccato per le richieste successive."""
    if "db" not in g:
        g.db = archivio.connessione()
    return g.db


def _stato_licenza(riga) -> str:
    if riga["stato"] != "attiva":
        return riga["stato"]
    if riga["scadenza"] and riga["scadenza"] < date.today().isoformat():
        return "scaduta"
    if riga["scadenza"] and riga["scadenza"] <= (date.today() + timedelta(days=GIORNI_AVVISO)).isoformat():
        return "in scadenza"
    return "attiva"


def testo_consegna(l, nome_piano: str) -> str:
    validita = f", valida fino al {_data(l['scadenza'])}" if l["scadenza"] else ", senza scadenza"
    return (f"Gentile {l['cliente']},\n"
            f"le inviamo il codice della licenza SicurCantiere n. {l['codice_licenza']} (piano {nome_piano}{validita}, "
            f"per {l['postazioni']} {'postazione' if l['postazioni'] == 1 else 'postazioni'}):\n\n{l['codice']}\n\n"
            "Per attivare la licenza apra SicurCantiere, scelga Aiuto > Licenza..., incolli il codice e prema "
            "«Attiva la licenza»: il programma si collega a internet e attiva la licenza su quel PC. "
            f"La licenza vale per {l['postazioni']} {'PC' if l['postazioni'] == 1 else 'PC diversi'}; per spostarla "
            "su un altro PC usi «Disattiva questo PC» nella stessa finestra, oppure disattivi il vecchio PC da "
            "«PC della licenza...».\n"
            f"L'installatore aggiornato è disponibile all'indirizzo:\n{DOWNLOAD}\n\n"
            "La licenza è nominativa: il nome del titolare compare nel programma e nei documenti generati.\n\n"
            "Cordiali saluti")


def testo_promemoria(l, nome_piano: str) -> str:
    scade = date.fromisoformat(l["scadenza"]) < date.today() if l["scadenza"] else False
    return (f"Gentile {l['cliente']},\n"
            f"la sua licenza SicurCantiere n. {l['codice_licenza']} (piano {nome_piano}) "
            f"{'è scaduta' if scade else 'scade'} il {_data(l['scadenza'])}.\n\n"
            "Senza rinnovo il programma passa in sola lettura: i cantieri e i documenti già fatti restano "
            "consultabili, stampabili ed esportabili in PDF, ma non se ne possono creare di nuovi né modificarli. "
            "Rinnovando ora, la nuova scadenza decorre da quella attuale, senza perdere giorni.\n\n"
            "Se desidera rinnovare, risponda a questa email: le invieremo il nuovo codice.\n\n"
            "Cordiali saluti")


def _data(valore) -> str:
    if not valore:
        return "senza scadenza"
    anno, mese, giorno = str(valore)[:10].split("-")
    return f"{giorno}/{mese}/{anno}"


def mailto(destinatario: str, oggetto: str, corpo: str) -> str:
    return f"mailto:{quote(destinatario or '')}?subject={quote(oggetto)}&body={quote(corpo)}"


def _nuovo_identificativo(conn) -> str:
    """SC-<anno>-<numero>: il numero segue il più alto dell'anno (anche con licenze reinserite a salti)."""
    anno = date.today().year
    numeri = [int(r[0].rsplit("-", 1)[1]) for r in conn.execute(
        "SELECT codice_licenza FROM licenze WHERE codice_licenza LIKE ?", (f"SC-{anno}-%",))
        if r[0].rsplit("-", 1)[1].isdigit()]
    return f"SC-{anno}-{max(numeri, default=0) + 1:04d}"


def reinserisci_codice(conn, codice: str, email: str = "") -> tuple[str, bool]:
    """Rimette nel database un codice di licenza già emesso (per esempio dopo la perdita del database).

    Il codice contiene cliente, piano, emissione, scadenza e postazioni: si verifica la firma con la chiave
    delle licenze e si crea la licenza (e il cliente, se non c'è già con quel nome). Restituisce
    (identificativo, True se inserita / False se c'era già).
    """
    codice = "".join(codice.split())
    dati = licenza.leggi(codice, archivio.chiave_pubblica())  # ErroreLicenza se non è firmato da questa chiave
    if conn.execute("SELECT 1 FROM licenze WHERE codice = ? OR codice_licenza = ?", (codice, dati.id)).fetchone():
        return dati.id, False
    cliente = conn.execute("SELECT id FROM clienti WHERE nome = ?", (dati.cliente,)).fetchone()
    cliente_id = cliente[0] if cliente else conn.execute(
        "INSERT INTO clienti (nome, email) VALUES (?, ?)", (dati.cliente, email)).lastrowid
    conn.execute(
        "INSERT INTO licenze (codice_licenza, cliente_id, piano, emessa, scadenza, postazioni, prezzo, codice, note) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (dati.id, cliente_id, dati.piano, dati.emessa.isoformat(), dati.scadenza.isoformat() if dati.scadenza else None,
         dati.postazioni, codice, "Reinserita da un codice già emesso"))
    conn.commit()
    return dati.id, True


def emetti(conn, cliente_id: int, piano: str, scadenza: date | None, postazioni: int, prezzo: float,
           note: str = "", rinnovo_di: int | None = None) -> int:
    """Crea e firma una licenza; restituisce l'id della riga."""
    cliente = conn.execute("SELECT * FROM clienti WHERE id = ?", (cliente_id,)).fetchone()
    if cliente is None or piano not in licenza.PIANI:
        abort(400, "Cliente o piano non validi.")
    identificativo = _nuovo_identificativo(conn)
    dati = licenza.Licenza(id=identificativo, cliente=cliente["nome"], piano=piano, emessa=date.today(),
                           scadenza=scadenza, postazioni=postazioni)
    codice = licenza.firma(dati, archivio.chiave_privata())
    cur = conn.execute(
        "INSERT INTO licenze (codice_licenza, cliente_id, piano, emessa, scadenza, postazioni, prezzo, codice, "
        "rinnovo_di, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (identificativo, cliente_id, piano, dati.emessa.isoformat(), scadenza.isoformat() if scadenza else None,
         postazioni, prezzo, codice, rinnovo_di, note))
    conn.commit()
    return cur.lastrowid


def _bloccato(conn, nome: str, ip: str) -> bool:
    dal = time.time() - BLOCCO_SECONDI
    conn.execute("DELETE FROM accessi_falliti WHERE quando < ?", (dal,))
    per_nome = conn.execute("SELECT COUNT(*) FROM accessi_falliti WHERE nome = ?", (nome,)).fetchone()[0]
    per_ip = conn.execute("SELECT COUNT(*) FROM accessi_falliti WHERE ip = ?", (ip,)).fetchone()[0]
    return per_nome >= TENTATIVI_UTENTE or per_ip >= TENTATIVI_IP


def _controlla_accesso(conn, nome: str, password: str, codice: str):
    """Riga dell'utente se nome, password e (se attivato) codice dell'app sono giusti."""
    utente = conn.execute("SELECT * FROM utenti WHERE nome = ?", (nome,)).fetchone()
    if utente is None or not check_password_hash(utente["password"], password):
        return None
    if utente["totp"]:
        contatore = totp.verifica(utente["totp"], codice, utente["totp_ultimo"])
        if contatore is None:
            return None
        conn.execute("UPDATE utenti SET totp_ultimo = ? WHERE id = ?", (contatore, utente["id"]))
    return utente


def _rotte(app: Flask) -> None:
    @app.route("/accesso", methods=["GET", "POST"])
    def accesso():
        if request.method == "POST":
            conn = _db()
            nome, ip = request.form.get("nome", "").strip(), request.remote_addr or ""
            if _bloccato(conn, nome, ip):
                conn.commit()
                flash("Troppi tentativi non riusciti: riprova tra 15 minuti.", "errore")
                return render_template("accesso.html"), 429
            utente = _controlla_accesso(conn, nome, request.form.get("password", ""), request.form.get("codice", ""))
            if utente is None:
                conn.execute("INSERT INTO accessi_falliti (nome, ip, quando) VALUES (?, ?, ?)", (nome, ip, time.time()))
                conn.commit()
                flash("Nome, password o codice non corretti.", "errore")
                return render_template("accesso.html")
            conn.execute("DELETE FROM accessi_falliti WHERE nome = ?", (nome,))
            conn.commit()
            session.clear()
            session["utente"] = utente["nome"]
            session["2fa"] = bool(utente["totp"])
            session["token"] = secrets.token_urlsafe(24)
            session.permanent = True
            prossima = request.args.get("prossima", "")
            return redirect(prossima if prossima.startswith("/") and not prossima.startswith("//")
                            else url_for("cruscotto"))
        return render_template("accesso.html")

    @app.route("/esci", methods=["POST"])
    def esci():
        session.clear()
        return redirect(url_for("accesso"))

    @app.route("/")
    def cruscotto():
        conn = _db()
        oggi = date.today()
        giorni = request.args.get("giorni", type=int)
        giorni = giorni if giorni in FINESTRE_CRUSCOTTO else 60
        righe = conn.execute(
            "SELECT l.*, c.nome AS cliente, c.email, (SELECT MAX(data) FROM invii WHERE licenza_id = l.id AND "
            "tipo = 'promemoria') AS sollecito FROM licenze l JOIN clienti c ON c.id = l.cliente_id "
            "WHERE l.stato = 'attiva' AND l.scadenza IS NOT NULL AND l.scadenza <= ? ORDER BY l.scadenza",
            ((oggi + timedelta(days=giorni)).isoformat(),)).fetchall()
        in_scadenza = [r for r in righe if r["scadenza"] >= oggi.isoformat()]
        scadute = [r for r in righe if r["scadenza"] < oggi.isoformat()]
        numeri = {
            "token_ai": conn.execute("SELECT COALESCE(SUM(token_ingresso + token_uscita), 0) FROM consumi_ai "
                                     "WHERE data >= ?", (oggi.isoformat()[:7] + "-01",)).fetchone()[0],
            "clienti": conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0],
            "attive": conn.execute("SELECT COUNT(*) FROM licenze WHERE stato = 'attiva' AND "
                                   "(scadenza IS NULL OR scadenza >= ?)", (oggi.isoformat(),)).fetchone()[0],
            "incassato": conn.execute("SELECT COALESCE(SUM(importo), 0) FROM pagamenti WHERE data >= ?",
                                      (f"{oggi.year}-01-01",)).fetchone()[0],
        }
        recenti = conn.execute("SELECT l.*, c.nome AS cliente FROM licenze l JOIN clienti c ON c.id = l.cliente_id "
                               "ORDER BY l.id DESC LIMIT 8").fetchall()
        promemoria = {r["id"]: mailto(r["email"], f"Rinnovo licenza SicurCantiere {r['codice_licenza']}",
                                      testo_promemoria(r, licenza.PIANI[r["piano"]][0])) for r in righe}
        from licenze import attivazioni

        segnalazioni = attivazioni.segnalazioni(conn)
        conn.commit()
        return render_template("cruscotto.html", in_scadenza=in_scadenza, scadute=scadute, numeri=numeri,
                               recenti=recenti, anno=oggi.year, giorni=giorni, finestre=FINESTRE_CRUSCOTTO,
                               promemoria=promemoria, segnalazioni=segnalazioni)

    @app.route("/clienti")
    def clienti():
        cerca = request.args.get("cerca", "").strip()
        filtro = f"%{cerca}%"
        righe = _db().execute(
            "SELECT c.*, (SELECT MAX(scadenza) FROM licenze WHERE cliente_id = c.id AND stato = 'attiva') AS scadenza, "
            "(SELECT COUNT(*) FROM licenze WHERE cliente_id = c.id) AS n_licenze FROM clienti c "
            "WHERE c.nome LIKE ? OR c.email LIKE ? OR c.partita_iva LIKE ? ORDER BY c.nome",
            (filtro, filtro, filtro)).fetchall()
        return render_template("clienti.html", clienti=righe, cerca=cerca)

    campi_cliente = ("nome", "tipo", "partita_iva", "codice_fiscale", "email", "pec", "telefono", "indirizzo",
                     "codice_sdi", "note")

    @app.route("/clienti/nuovo", methods=["GET", "POST"])
    @app.route("/clienti/<int:id_>/modifica", methods=["GET", "POST"])
    def modifica_cliente(id_: int | None = None):
        conn = _db()
        cliente = conn.execute("SELECT * FROM clienti WHERE id = ?", (id_,)).fetchone() if id_ else None
        if id_ and cliente is None:
            abort(404)
        if request.method == "POST":
            valori = {k: request.form.get(k, "").strip() for k in campi_cliente}
            if not valori["nome"]:
                flash("Indica il nome o la ragione sociale.", "errore")
                return render_template("cliente_modifica.html", cliente=valori)
            if id_:
                conn.execute(f"UPDATE clienti SET {', '.join(f'{k} = ?' for k in campi_cliente)} WHERE id = ?",
                             (*valori.values(), id_))
            else:
                id_ = conn.execute(f"INSERT INTO clienti ({', '.join(campi_cliente)}) VALUES "
                                   f"({', '.join('?' for _ in campi_cliente)})", tuple(valori.values())).lastrowid
            conn.commit()
            flash("Cliente salvato.", "ok")
            return redirect(url_for("cliente", id_=id_))
        return render_template("cliente_modifica.html", cliente=cliente or {k: "" for k in campi_cliente})

    @app.route("/clienti/<int:id_>")
    def cliente(id_: int):
        conn = _db()
        c = conn.execute("SELECT * FROM clienti WHERE id = ?", (id_,)).fetchone()
        if c is None:
            abort(404)
        licenze_ = conn.execute("SELECT * FROM licenze WHERE cliente_id = ? ORDER BY id DESC", (id_,)).fetchall()
        pagamenti = conn.execute("SELECT p.*, l.codice_licenza FROM pagamenti p LEFT JOIN licenze l "
                                 "ON l.id = p.licenza_id WHERE p.cliente_id = ? ORDER BY p.data DESC",
                                 (id_,)).fetchall()
        from licenze import api

        attiva = next((l for l in licenze_ if _stato_licenza(l) in ("attiva", "in scadenza")), None)
        credito = api.situazione(conn, id_, attiva["piano"]) if attiva else None
        ricariche = conn.execute("SELECT * FROM ricariche_ai WHERE cliente_id = ? ORDER BY data DESC, id DESC",
                                 (id_,)).fetchall()
        consumi = conn.execute("SELECT substr(data, 1, 7) AS mese, motore, SUM(token_ingresso + token_uscita) AS token, "
                               "SUM(crediti) AS crediti, COUNT(*) AS richieste FROM consumi_ai WHERE cliente_id = ? "
                               "GROUP BY mese, motore ORDER BY mese DESC LIMIT 12", (id_,)).fetchall()
        from licenze import attivazioni

        pc = {}
        for l in licenze_:
            radice, attuale = attivazioni.catena(conn, l)
            if l["id"] == attuale["id"]:  # i PC si mostrano sulla licenza in vigore della catena
                pc[l["id"]] = (len(attivazioni.pc_attivi(conn, radice)),
                               attivazioni.posti(attuale, attivazioni.dati_catena(conn, radice)))
        conn.commit()
        return render_template("cliente.html", cliente=c, licenze=licenze_, pagamenti=pagamenti,
                               stato=_stato_licenza, metodi=METODI_PAGAMENTO, credito=credito,
                               ricariche=ricariche, consumi=consumi, pc=pc)

    @app.route("/clienti/<int:id_>/ricarica", methods=["POST"])
    def nuova_ricarica(id_: int):
        conn = _db()
        if conn.execute("SELECT id FROM clienti WHERE id = ?", (id_,)).fetchone() is None:
            abort(404)
        try:
            milioni = float((request.form.get("milioni") or "0").replace(",", "."))
            prezzo = float((request.form.get("prezzo") or "0").replace(",", "."))
        except ValueError:
            abort(400, "Valori non validi.")
        if milioni <= 0:
            flash("Indica quanti milioni di crediti aggiungere.", "errore")
            return redirect(url_for("cliente", id_=id_))
        conn.execute("INSERT INTO ricariche_ai (cliente_id, data, crediti, prezzo, note) VALUES (?, ?, ?, ?, ?)",
                     (id_, date.today().isoformat(), int(milioni * 1_000_000), prezzo, request.form.get("note", "")))
        conn.commit()
        flash(f"Ricarica di {milioni:g} milioni di crediti AI aggiunta.", "ok")
        return redirect(url_for("cliente", id_=id_))

    @app.route("/clienti/<int:id_>/licenza", methods=["POST"])
    def nuova_licenza(id_: int):
        f = request.form
        scadenza = None if f.get("senza_scadenza") else date.fromisoformat(f.get("scadenza") or
                                                                        (date.today() + timedelta(days=365)).isoformat())
        conn = _db()
        nuova = emetti(conn, id_, f.get("piano", "pos"), scadenza, int(f.get("postazioni") or 1),
                       float((f.get("prezzo") or "0").replace(",", ".")), f.get("note", ""))
        flash("Licenza emessa: copia il codice e invialo al cliente.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=nuova))

    @app.route("/licenze/<int:id_>")
    def dettaglio_licenza(id_: int):
        conn = _db()
        l = conn.execute("SELECT l.*, c.nome AS cliente, c.email FROM licenze l JOIN clienti c ON c.id = l.cliente_id "
                         "WHERE l.id = ?", (id_,)).fetchone()
        if l is None:
            abort(404)
        precedente = conn.execute("SELECT id, codice_licenza FROM licenze WHERE id = ?", (l["rinnovo_di"],)).fetchone()
        successiva = conn.execute("SELECT id, codice_licenza FROM licenze WHERE rinnovo_di = ?", (id_,)).fetchone()
        nome_piano = licenza.PIANI[l["piano"]][0]
        consegna, rinnovo = testo_consegna(l, nome_piano), testo_promemoria(l, nome_piano) if l["scadenza"] else ""
        invii = conn.execute("SELECT * FROM invii WHERE licenza_id = ? ORDER BY data DESC, id DESC", (id_,)).fetchall()
        from licenze import attivazioni

        att = attivazioni.scheda(conn, attivazioni.catena(conn, l)[0], con_verifiche=request.args.get("verifiche") == "1")
        conn.commit()
        return render_template(
            "licenza.html", l=l, stato=_stato_licenza(l), precedente=precedente, successiva=successiva, att=att,
            verifiche=request.args.get("verifiche") == "1",
            nome_piano=nome_piano, consegna=consegna, rinnovo=rinnovo, invii=invii, tipi_invio=TIPI_INVIO,
            email_consegna=mailto(l["email"], f"Licenza SicurCantiere {l['codice_licenza']}", consegna),
            email_rinnovo=mailto(l["email"], f"Rinnovo licenza SicurCantiere {l['codice_licenza']}", rinnovo)
            if rinnovo else "")

    @app.route("/licenze/<int:id_>/invio", methods=["POST"])
    def registra_invio(id_: int):
        conn = _db()
        l = conn.execute("SELECT l.id, c.email FROM licenze l JOIN clienti c ON c.id = l.cliente_id WHERE l.id = ?",
                         (id_,)).fetchone()
        tipo = request.form.get("tipo", "")
        if l is None or tipo not in TIPI_INVIO:
            abort(400)
        conn.execute("INSERT INTO invii (licenza_id, data, tipo, destinatario, utente) VALUES (?, ?, ?, ?, ?)",
                     (id_, date.today().isoformat(), tipo, l["email"], session.get("utente", "")))
        conn.commit()
        flash(f"Invio registrato: {TIPI_INVIO[tipo].lower()}.", "ok")
        return redirect(request.form.get("torna") if request.form.get("torna", "").startswith("/")
                        else url_for("dettaglio_licenza", id_=id_))

    @app.route("/registro")
    def registro():
        righe = _db().execute(
            "SELECT i.*, l.codice_licenza, l.id AS lid, c.nome AS cliente FROM invii i JOIN licenze l ON "
            "l.id = i.licenza_id JOIN clienti c ON c.id = l.cliente_id ORDER BY i.data DESC, i.id DESC").fetchall()
        return render_template("registro.html", righe=righe, tipi_invio=TIPI_INVIO)

    @app.route("/licenze/<int:id_>/rinnova", methods=["POST"])
    def rinnova(id_: int):
        conn = _db()
        vecchia = conn.execute("SELECT * FROM licenze WHERE id = ?", (id_,)).fetchone()
        if vecchia is None:
            abort(404)
        base = max(date.fromisoformat(vecchia["scadenza"]) if vecchia["scadenza"] else date.today(), date.today())
        piano = request.form.get("piano") or vecchia["piano"]
        nuova = emetti(conn, vecchia["cliente_id"], piano, base + timedelta(days=365), vecchia["postazioni"],
                       float((request.form.get("prezzo") or vecchia["prezzo"] or 0)), rinnovo_di=id_)
        conn.execute("UPDATE licenze SET stato = 'rinnovata' WHERE id = ?", (id_,))
        conn.commit()
        flash("Rinnovo emesso: invia al cliente il nuovo codice.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=nuova))

    @app.route("/licenze/<int:id_>/annulla", methods=["POST"])
    def annulla(id_: int):
        from licenze import attivazioni

        conn = _db()
        conn.execute("UPDATE licenze SET stato = 'annullata' WHERE id = ?", (id_,))
        attivazioni.registra_stato_licenza(conn, id_, "annullata", session.get("utente", ""))
        conn.commit()
        flash("Licenza annullata: al prossimo collegamento i PC attivati passano in sola lettura e non se ne possono "
              "attivare altri. I programmi senza attivazione (versioni precedenti) la usano fino alla scadenza.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=id_))

    @app.route("/licenze/<int:id_>/riattiva", methods=["POST"])
    def riattiva(id_: int):
        from licenze import attivazioni

        conn = _db()
        conn.execute("UPDATE licenze SET stato = 'attiva' WHERE id = ? AND stato = 'annullata'", (id_,))
        attivazioni.registra_stato_licenza(conn, id_, "riattivata", session.get("utente", ""))
        conn.commit()
        flash("Licenza riattivata: i PC tornano a funzionare al prossimo collegamento.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=id_))

    def _radice(conn, id_: int) -> int:
        from licenze import attivazioni

        riga = conn.execute("SELECT * FROM licenze WHERE id = ?", (id_,)).fetchone()
        if riga is None:
            abort(404)
        return attivazioni.catena(conn, riga)[0]

    @app.route("/licenze/<int:id_>/pc/<codice_pc>/disattiva", methods=["POST"])
    def disattiva_pc(id_: int, codice_pc: str):
        from licenze import attivazioni

        conn = _db()
        fatto = attivazioni.disattiva_da_gestionale(conn, _radice(conn, id_), codice_pc, session.get("utente", ""),
                                                    request.form.get("motivo", "").strip()[:200])
        conn.commit()
        flash("PC disattivato: il posto è libero e quel PC, al prossimo collegamento, dovrà essere riattivato."
              if fatto else "Il PC non risulta attivo su questa licenza.", "ok" if fatto else "errore")
        return redirect(url_for("dettaglio_licenza", id_=id_))

    @app.route("/licenze/<int:id_>/pc/<codice_pc>/ignora", methods=["POST"])
    def ignora_sospetto(id_: int, codice_pc: str):
        from licenze import attivazioni

        conn = _db()
        _radice(conn, id_)
        attivazioni.ignora_sospetto(conn, codice_pc, session.get("utente", ""))
        conn.commit()
        flash("Segnalazione ignorata.", "ok")
        return redirect(request.form.get("torna") if request.form.get("torna", "").startswith("/")
                        else url_for("dettaglio_licenza", id_=id_))

    @app.route("/licenze/<int:id_>/posti", methods=["POST"])
    def posti_extra(id_: int):
        from licenze import attivazioni

        conn = _db()
        try:
            numero = int(request.form.get("posti_extra") or 0)
        except ValueError:
            abort(400, "Numero non valido.")
        attivazioni.imposta_posti_extra(conn, _radice(conn, id_), numero, session.get("utente", ""))
        conn.commit()
        flash(f"Posti in più rispetto alla licenza: {max(0, min(numero, 100))}.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=id_))

    @app.route("/licenze/<int:id_>/trasferimenti", methods=["POST"])
    def sblocca_trasferimenti(id_: int):
        from licenze import attivazioni

        conn = _db()
        attivazioni.sblocca_trasferimenti(conn, _radice(conn, id_), session.get("utente", ""))
        conn.commit()
        flash("Trasferimenti sbloccati: il conteggio dei PC nuovi riparte da oggi.", "ok")
        return redirect(url_for("dettaglio_licenza", id_=id_))

    @app.route("/licenze/<int:id_>/offline", methods=["POST"])
    def attivazione_offline(id_: int):
        """File di attivazione per un cliente senza internet, dalla sua richiesta (file o testo incollato)."""
        from licenze import attivazioni

        conn = _db()
        radice = _radice(conn, id_)
        file = request.files.get("richiesta")
        testo = (file.read(100_000).decode("utf-8", errors="replace") if file and file.filename
                 else request.form.get("testo", ""))
        if not testo.strip():
            flash("Scegli il file di richiesta mandato dal cliente, oppure incollane il contenuto.", "errore")
            return redirect(url_for("dettaglio_licenza", id_=id_))
        if attivazioni.radice_della_richiesta(conn, testo) not in (None, radice):
            flash("La richiesta è di un'altra licenza: aprila dalla pagina della licenza giusta.", "errore")
            return redirect(url_for("dettaglio_licenza", id_=id_))
        try:
            risposta = attivazioni.attiva_offline(conn, testo)
        except attivazioni.Rifiuto as e:
            conn.commit()
            flash(f"Attivazione non creata: {e.messaggio}", "errore")
            return redirect(url_for("dettaglio_licenza", id_=id_))
        conn.commit()
        try:
            nome = json.loads(testo).get("nome_pc", "") or "PC"
        except ValueError:
            nome = "PC"
        nome = "".join(c for c in nome if c.isalnum() or c in "-_") or "PC"
        return Response(risposta, mimetype="application/json",
                        headers={"Content-Disposition": f"attachment; filename=attivazione-{nome}.sclic"})

    @app.route("/attivazioni")
    def pagina_attivazioni():
        from licenze import attivazioni

        conn = _db()
        giorni = request.args.get("giorni", type=int)
        giorni = giorni if giorni in (7, 30, 90) else 30
        tipo = request.args.get("tipo", "rifiuti")
        filtri = {
            "rifiuti": ("e.evento = 'attivazione' AND e.esito NOT IN ('nuovo_pc', 'stesso_pc')", "Tentativi rifiutati"),
            "attivazioni": ("e.evento IN ('attivazione', 'disattivazione')", "Attivazioni e disattivazioni"),
            "sicurezza": ("e.evento IN ('codice_errato', 'sospetto_clone') OR e.esito = 'altro_pc'",
                          "Codici errati e sospetti"),
            "gestionale": ("e.evento = 'gestionale'", "Interventi dal gestionale"),
        }
        condizione, _ = filtri.get(tipo, filtri["rifiuti"])
        from datetime import datetime, timezone

        dal = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat()
        eventi = conn.execute(
            "SELECT e.*, l.codice_licenza, l.cliente_id, c.nome AS cliente, p.nome AS nome_pc FROM eventi_licenza e "
            "LEFT JOIN licenze l ON l.id = e.radice_id LEFT JOIN clienti c ON c.id = l.cliente_id "
            f"LEFT JOIN pc_licenza p ON p.codice_pc = e.codice_pc WHERE ({condizione}) AND e.quando >= ? "
            "ORDER BY e.quando DESC, e.id DESC LIMIT 300", (dal,)).fetchall()
        segnalazioni = attivazioni.segnalazioni(conn, giorni=giorni)
        conn.commit()
        return render_template("attivazioni.html", eventi=eventi, segnalazioni=segnalazioni, giorni=giorni,
                               tipo=tipo, filtri={k: v[1] for k, v in filtri.items()})

    @app.route("/clienti/<int:id_>/pagamento", methods=["POST"])
    def nuovo_pagamento(id_: int):
        f = request.form
        conn = _db()
        conn.execute("INSERT INTO pagamenti (cliente_id, licenza_id, data, importo, metodo, fattura, note) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (id_, int(f["licenza_id"]) if f.get("licenza_id") else None, f.get("data") or date.today().isoformat(),
                      float((f.get("importo") or "0").replace(",", ".")), f.get("metodo", ""), f.get("fattura", ""),
                      f.get("note", "")))
        conn.commit()
        flash("Pagamento registrato.", "ok")
        return redirect(url_for("cliente", id_=id_))

    @app.route("/esporta.csv")
    def esporta():
        conn = _db()
        uscita = io.StringIO()
        scrittore = csv.writer(uscita, delimiter=";")
        scrittore.writerow(["Licenza", "Cliente", "Email", "Partita IVA", "Piano", "Emessa", "Scadenza", "Postazioni",
                            "Prezzo", "Stato"])
        for r in conn.execute("SELECT l.*, c.nome AS cliente, c.email, c.partita_iva FROM licenze l "
                              "JOIN clienti c ON c.id = l.cliente_id ORDER BY l.id"):
            scrittore.writerow([r["codice_licenza"], r["cliente"], r["email"], r["partita_iva"], r["piano"],
                                r["emessa"], r["scadenza"] or "", r["postazioni"], r["prezzo"], _stato_licenza(r)])
        return Response("﻿" + uscita.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=licenze.csv"})

    @app.route("/impostazioni")
    def impostazioni():
        return render_template("impostazioni.html", chiave=archivio.chiave_pubblica(),
                               cartella=archivio.cartella_dati())

    @app.route("/impostazioni/due-passaggi", methods=["GET", "POST"])
    def due_passaggi():
        """Attiva la verifica in due passaggi: QR code per l'app, poi conferma con il primo codice."""
        conn = _db()
        utente = conn.execute("SELECT * FROM utenti WHERE nome = ?", (session["utente"],)).fetchone()
        if request.method == "POST":
            if request.form.get("azione") == "disattiva":
                if not check_password_hash(utente["password"], request.form.get("password", "")):
                    flash("Password non corretta.", "errore")
                    return redirect(url_for("due_passaggi"))
                conn.execute("UPDATE utenti SET totp = '', totp_ultimo = 0 WHERE id = ?", (utente["id"],))
                conn.commit()
                session["2fa"] = False
                flash("Verifica in due passaggi disattivata.", "ok")
                return redirect(url_for("impostazioni"))
            segreto = session.get("totp_nuovo", "")
            contatore = totp.verifica(segreto, request.form.get("codice", ""))
            if contatore is None:
                flash("Codice non corretto: controlla l'ora del telefono e riprova.", "errore")
                return redirect(url_for("due_passaggi"))
            conn.execute("UPDATE utenti SET totp = ?, totp_ultimo = ? WHERE id = ?", (segreto, contatore, utente["id"]))
            conn.commit()
            session.pop("totp_nuovo", None)
            session["2fa"] = True
            flash("Verifica in due passaggi attivata: d'ora in poi all'accesso serve il codice dell'app.", "ok")
            return redirect(url_for("impostazioni"))
        if utente["totp"]:
            return render_template("due_passaggi.html", attiva=True)
        segreto = session.get("totp_nuovo") or totp.nuovo_segreto()
        session["totp_nuovo"] = segreto
        return render_template("due_passaggi.html", attiva=False, segreto=segreto,
                               qr=_qr(totp.indirizzo(segreto, utente["nome"])))


def _qr(testo: str) -> str:
    """QR code come immagine data: (vuoto se manca la libreria: resta il codice da scrivere a mano)."""
    try:
        import segno
    except ImportError:
        return ""
    return segno.make(testo, error="m").svg_data_uri(scale=5, border=2)


def crea_utente(nome: str, password: str) -> None:
    conn = archivio.connessione()
    conn.execute("INSERT INTO utenti (nome, password) VALUES (?, ?) ON CONFLICT(nome) DO UPDATE SET "
                 "password = excluded.password", (nome, generate_password_hash(password)))
    conn.commit()
