"""Comandi del gestionale delle licenze.

    python -m licenze genera-chiave     crea la chiave di firma (una volta sola) e stampa la pubblica
    python -m licenze crea-utente NOME  crea o aggiorna un utente (chiede la password)
    python -m licenze togli-2fa NOME    disattiva la verifica in due passaggi (telefono perso)
    python -m licenze chiave-pubblica   stampa la chiave pubblica da inserire nel programma
    python -m licenze prova             avvia il gestionale in locale su http://127.0.0.1:8080 (solo prove)
    python -m licenze attivazione-offline RICHIESTA [RISPOSTA]
                                        crea il file di attivazione offline per la richiesta di un cliente
    python -m licenze chiave-servizio   crea una nuova chiave di servizio (servizio.json) per il server delle
                                        attivazioni: da copiare sul server separato, se c'è
    python -m licenze pc CODICE_LICENZA elenca i PC attivi di una licenza (es. SC-2026-0012)
    python -m licenze reinserisci-codice [CODICE]
                                        rimette nel database un codice di licenza già emesso (se manca il
                                        codice, lo chiede: si può incollare dall'email di consegna)
    python -m licenze chiave-aggiornamenti
                                        crea la chiave che firma gli aggiornamenti del programma (una volta
                                        sola) e mostra cosa copiare su GitHub e cosa nel programma
"""

from __future__ import annotations

import getpass
import sys

from licenze import archivio


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "aiuto"):
        print(__doc__)
        return 0
    comando = argv[0]
    if comando == "genera-chiave":
        try:
            pubblica = archivio.genera_chiave()
        except FileExistsError as e:
            print(e)
            return 1
        print("Chiave di firma creata. Chiave pubblica da inserire nel programma:\n")
        print(pubblica)
        print("\nCopia subito chiave_privata.pem in un posto sicuro (vedi README).")
        return 0
    if comando == "chiave-pubblica":
        print(archivio.chiave_pubblica())
        return 0
    if comando == "crea-utente" and len(argv) == 2:
        from licenze.app import crea_utente

        password = getpass.getpass("Password: ")
        if len(password) < 10 or password != getpass.getpass("Ripeti la password: "):
            print("Password troppo corta (almeno 10 caratteri) o diversa.")
            return 1
        crea_utente(argv[1], password)
        print(f"Utente {argv[1]} pronto.")
        return 0
    if comando == "togli-2fa" and len(argv) == 2:
        conn = archivio.connessione()
        cambiati = conn.execute("UPDATE utenti SET totp = '', totp_ultimo = 0 WHERE nome = ?", (argv[1],)).rowcount
        conn.commit()
        print(f"Verifica in due passaggi disattivata per {argv[1]}." if cambiati else f"Utente {argv[1]} inesistente.")
        return 0 if cambiati else 1
    if comando == "attivazione-offline" and len(argv) in (2, 3):
        from pathlib import Path

        from licenze import attivazioni

        conn = archivio.connessione()
        try:
            testo = attivazioni.attiva_offline(conn, Path(argv[1]).read_text(encoding="utf-8"))
        except attivazioni.Rifiuto as e:
            print(f"Attivazione non creata: {e.messaggio}")
            return 1
        conn.commit()
        uscita = Path(argv[2] if len(argv) == 3 else Path(argv[1]).with_suffix(".sclic"))
        uscita.write_text(testo, encoding="utf-8")
        print(f"File di attivazione offline creato: {uscita} (valido {attivazioni.VALIDITA_OFFLINE.days} giorni)")
        return 0
    if comando == "chiave-servizio":
        dati = archivio.nuova_chiave_servizio()
        print(f"Nuova chiave di servizio valida fino al {dati['fino_al'][:10]}: {archivio.cartella_dati()}/servizio.json")
        return 0
    if comando == "pc" and len(argv) == 2:
        from licenze import attivazioni

        conn = archivio.connessione()
        riga = conn.execute("SELECT * FROM licenze WHERE codice_licenza = ?", (argv[1],)).fetchone()
        if riga is None:
            print(f"Licenza {argv[1]} inesistente.")
            return 1
        radice, attuale = attivazioni.catena(conn, riga)
        posti = attivazioni.posti(attuale, attivazioni.dati_catena(conn, radice))
        attivi = attivazioni.elenco(conn, radice)
        print(f"Licenza {attuale['codice_licenza']}: {len(attivi)} PC attivi su {posti}")
        for p in attivi:
            print(f"  {p['id']}  {p['nome']:<30} attivato {p['attivato']}  ultimo uso {p['ultimo_uso']}"
                  + ("  (offline)" if p["offline"] else ""))
        conn.commit()
        return 0
    if comando == "reinserisci-codice" and len(argv) <= 2:
        from licenze.app import reinserisci_codice
        from sicurcantiere import licenza

        codice = argv[1] if len(argv) == 2 else input("Incolla il codice di licenza (SC1-...): ")
        try:
            identificativo, nuova = reinserisci_codice(archivio.connessione(), codice)
        except licenza.ErroreLicenza as e:
            print(f"Codice non reinserito: {e} (deve essere firmato con la chiave delle licenze di questo server)")
            return 1
        print(f"Licenza {identificativo} reinserita." if nuova else f"La licenza {identificativo} c'è già.")
        return 0
    if comando == "chiave-aggiornamenti":
        import base64
        import secrets

        from sicur_license.certificato import pubblica_da_privata

        file = archivio.cartella_dati() / "chiave_aggiornamenti.key"
        if file.exists():
            privata = base64.b64decode(file.read_text().strip())
            print(f"La chiave degli aggiornamenti esiste già ({file}): non va rigenerata.\n")
        else:
            privata = secrets.token_bytes(32)
            file.write_text(base64.b64encode(privata).decode())
            file.chmod(0o600)
            print(f"Chiave degli aggiornamenti creata: {file}\n")
        print("1. Su GitHub, nel repository sicurcantiere: Settings > Secrets and variables > Actions >")
        print("   New repository secret. Nome: SICURCANTIERE_FIRMA_AGGIORNAMENTI  Valore (segreto, non darlo a nessuno):")
        print(f"\n   {base64.b64encode(privata).decode()}\n")
        print("2. Chiave pubblica da inserire nel programma (si può condividere):")
        print(f"\n   {base64.b64encode(pubblica_da_privata(privata)).decode()}\n")
        print("Conserva una copia del file della chiave insieme alla chiave delle licenze (vedi README).")
        return 0
    if comando == "prova":
        from licenze.app import crea_app

        crea_app(https=False).run(host="127.0.0.1", port=8080)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
