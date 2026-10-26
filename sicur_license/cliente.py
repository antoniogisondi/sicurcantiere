"""Collegamento con il server delle licenze e gestione della licenza su questo PC.

Richieste al server (POST con JSON, tutte sotto /api/licenze/):
- attiva      {codice, sale, impronte, nome_pc, programma, versione}  → {certificato}
- convalida   {certificato, impronte, versione}                       → {certificato}
- disattiva   {certificato, impronte}                                 → {ok}
- pc          {codice, sale, impronte}                → {pc: [...], posti, attivi, trasferimenti_rimasti}
- libera      {codice, sale, impronte, pc}            → {ok, trasferimenti_rimasti}
Gli errori hanno {errore, messaggio} e, con i posti esauriti, l'elenco dei PC attivi.

Il sale delle impronte lo assegna il server (uno per licenza): alla prima richiesta il programma
non lo conosce, il server risponde con l'errore «sale» e il sale giusto, e il programma ripete la
richiesta una volta con le impronte ricalcolate.

L'attivazione offline usa due file: la richiesta (creata qui, da mandare all'assistenza) e il
certificato restituito, che ha una scadenza propria perché un file offline non si può revocare.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

from sicur_license import custodia, impronta
from sicur_license.certificato import REVOCATA, Certificato, ErroreCertificato, leggi_certificato, ora_utc
from sicur_license.stato import OROLOGIO, Esito, valuta

POSTI_ESAURITI, CODICE_ERRATO, LICENZA_SCADUTA, LICENZA_REVOCATA, TROPPI_TRASFERIMENTI, TROPPE_RICHIESTE = (
    "posti_esauriti", "codice_errato", "scaduta", "revocata", "troppi_trasferimenti", "troppe_richieste")
SALE, PC_LIBERATO, ALTRO_PC = "sale", "pc_liberato", "altro_pc"

# (stato HTTP, risposta) per una richiesta: sostituibile nei test
Trasporto = Callable[[str, dict], tuple[int, dict]]


class ErroreRete(Exception):
    """Server non raggiungibile: il programma continua con il certificato che ha."""


class ErroreServer(Exception):
    """Il server ha rifiutato la richiesta (codice errato, posti esauriti, ...)."""

    def __init__(self, codice: str, messaggio: str, dati: dict | None = None):
        super().__init__(messaggio)
        self.codice = codice
        self.dati = dati or {}

    @property
    def pc(self) -> list[dict]:
        return list(self.dati.get("pc") or [])


def trasporto_http(url_base: str, timeout: float = 15) -> Trasporto:
    sicuro = url_base.lower().startswith(("https://", "http://"))  # mai file: o altri schemi

    def invia(percorso: str, dati: dict) -> tuple[int, dict]:
        if not sicuro:
            raise ErroreRete("Indirizzo del server delle licenze non valido.")
        richiesta = urllib.request.Request(
            url_base.rstrip("/") + "/api/licenze/" + percorso, data=json.dumps(dati).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "SicurCantiere"}, method="POST")
        try:
            with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:  # nosec B310
                return risposta.status, json.loads(risposta.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ErroreRete("Server delle licenze non raggiungibile.") from e
    return invia


@dataclass
class Licenze:
    """La licenza di un programma su questo PC: verifica, attivazione, convalida, disattivazione."""

    programma: str                # «psc», «pos», «pimus»...
    radice_pubblica: bytes        # chiave pubblica radice (32 byte)
    trasporto: Trasporto | None = None
    versione: str = ""
    data_versione: date | None = None
    componenti: dict[str, str] | None = None  # valori dei componenti (nei test); None = di questo PC
    nome: str = ""                # nome del PC mostrato nell'elenco; vuoto = quello di Windows
    _impronte: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def nome_del_pc(self) -> str:
        return self.nome or impronta.nome_pc()

    # --- impronte ---

    def impronte(self, sale: str) -> list[str]:
        if sale not in self._impronte:
            if self.componenti is None:
                memoria = custodia.leggi_memoria()
                salvate = memoria.get("impronte", {})
                if sale not in salvate:  # su Windows il calcolo interroga la scheda madre: si fa una volta
                    salvate[sale] = impronta.calcola(sale)
                    custodia.salva_memoria({**memoria, "impronte": salvate})
                self._impronte[sale] = list(salvate[sale])
            else:
                self._impronte[sale] = impronta.calcola(sale, self.componenti)
        return self._impronte[sale]

    # --- stato ---

    def certificato(self) -> tuple[Certificato | None, str]:
        testo = custodia.leggi_certificato()
        if not testo:
            return None, ""
        try:
            return leggi_certificato(testo, self.radice_pubblica), ""
        except ErroreCertificato as e:
            return None, str(e)

    def esito(self, ora: datetime | None = None) -> Esito:
        ora = ora or ora_utc()
        certificato, errore = self.certificato()
        impronte = self.impronte(certificato.sale) if certificato else []
        esito = valuta(certificato, self.programma, impronte, ora, custodia.ultima_ora_vista(),
                       self.data_versione, errore)
        if esito.tipo != OROLOGIO:
            custodia.registra_ora(ora)
        return esito

    # --- server ---

    def _invia(self, percorso: str, dati: dict) -> dict:
        if self.trasporto is None:
            raise ErroreRete("Indirizzo del server delle licenze non impostato.")
        stato, risposta = self.trasporto(percorso, dati)
        if stato >= 400 or risposta.get("errore"):
            raise ErroreServer(str(risposta.get("errore") or f"http_{stato}"),
                               str(risposta.get("messaggio") or "Il server delle licenze ha rifiutato la richiesta."),
                               risposta)
        return risposta

    def _salva(self, testo: str, impronte: list[str]) -> Certificato:
        certificato = leggi_certificato(testo, self.radice_pubblica)
        if not impronta.stesso_pc(list(certificato.impronte), impronte):
            raise ErroreCertificato("Il certificato ricevuto è di un altro PC.")
        custodia.salva_certificato(testo)
        custodia.registra_ora(certificato.emesso)
        return certificato

    def _sale(self, codice: str) -> str:
        return str(custodia.leggi_memoria().get("sali", {}).get(codice, ""))

    def _con_sale(self, percorso: str, codice: str, dati: dict) -> tuple[dict, list[str]]:
        """Richiesta con codice e impronte; se il sale non è quello della licenza, si ripete con quello giusto."""
        sale = self._sale(codice)
        for _ in range(2):
            impronte = self.impronte(sale) if sale else ["", "", ""]
            try:
                return self._invia(percorso, {**dati, "codice": codice, "sale": sale, "impronte": impronte}), impronte
            except ErroreServer as e:
                nuovo = str(e.dati.get("sale") or "")
                if e.codice != SALE or not nuovo or nuovo == sale:
                    raise
                sale = nuovo
                memoria = custodia.leggi_memoria()
                custodia.salva_memoria({**memoria, "sali": {**memoria.get("sali", {}), codice: sale}})
        raise ErroreServer(SALE, "Il server delle licenze non ha accettato l'impronta del PC.")

    def attiva(self, codice: str) -> Certificato:
        """Attiva questo PC; ErroreServer con codice POSTI_ESAURITI ed elenco dei PC se non c'è posto."""
        codice = impronta.normalizza_codice(codice)
        risposta, impronte = self._con_sale("attiva", codice, {"nome_pc": self.nome_del_pc(),
                                                              "programma": self.programma,
                                                              "versione": self.versione})
        certificato = self._salva(str(risposta.get("certificato", "")), impronte)
        custodia.salva_memoria({**custodia.leggi_memoria(), "codice": codice})
        return certificato

    def convalida(self) -> Certificato | None:
        """Rinnova il certificato (in sottofondo, a ogni avvio). ErroreRete se non c'è connessione:
        il programma continua con il certificato che ha."""
        certificato, _ = self.certificato()
        if certificato is None:
            return None
        impronte = self.impronte(certificato.sale)
        try:
            risposta = self._invia("convalida", {"certificato": custodia.leggi_certificato(), "impronte": impronte,
                                                 "versione": self.versione, "programma": self.programma})
        except ErroreServer as e:
            if e.dati.get("certificato"):  # licenza revocata: il server manda il certificato aggiornato
                return self._salva(str(e.dati["certificato"]), impronte)
            if e.codice in (PC_LIBERATO, ALTRO_PC):  # il posto di questo PC è stato liberato
                custodia.elimina_certificato()
            raise
        return self._salva(str(risposta.get("certificato", "")), impronte)

    def disattiva(self) -> None:
        """Libera il posto di questo PC sul server e cancella il certificato salvato."""
        certificato, _ = self.certificato()
        if certificato is not None:
            try:
                self._invia("disattiva", {"certificato": custodia.leggi_certificato(),
                                          "impronte": self.impronte(certificato.sale)})
            except ErroreServer as e:
                if e.codice not in (PC_LIBERATO, ALTRO_PC):  # già liberato: basta cancellarlo qui
                    raise
        custodia.elimina_certificato()

    def elenco_pc(self, codice: str) -> dict:
        """PC attivi della licenza, con nome e ultimo utilizzo («questo» indica questo PC)."""
        return self._con_sale("pc", impronta.normalizza_codice(codice), {})[0]

    def libera(self, codice: str, pc: str) -> dict:
        """Disattiva un altro PC della licenza (trasferimento): poi si può attivare questo."""
        return self._con_sale("libera", impronta.normalizza_codice(codice), {"pc": pc,
                                                                             "nome_pc": self.nome_del_pc()})[0]

    def codice_salvato(self) -> str:
        return str(custodia.leggi_memoria().get("codice", ""))

    # --- attivazione offline ---

    def richiesta_offline(self, codice: str) -> str:
        """Testo del file di richiesta da mandare all'assistenza (solo impronte, nessun dato in chiaro)."""
        codice = impronta.normalizza_codice(codice)
        sale = self._sale(codice) or impronta.sale_provvisorio()
        return json.dumps({"tipo": "richiesta_attivazione_offline", "codice": codice, "sale": sale,
                           "impronte": self.impronte(sale),
                           "nome_pc": self.nome_del_pc(), "programma": self.programma, "versione": self.versione,
                           "creata": ora_utc().isoformat()}, ensure_ascii=False, indent=1)

    def importa_offline(self, testo: str) -> Certificato:
        """Installa il certificato ricevuto per l'attivazione offline."""
        try:
            sale = json.loads(_dati_certificato(testo))["sale"]
        except (ValueError, KeyError, TypeError) as e:
            raise ErroreCertificato("Il file non è un'attivazione di SicurCantiere.") from e
        return self._salva(testo, self.impronte(str(sale)))


def _dati_certificato(testo: str) -> str:
    import base64

    return base64.b64decode(json.loads(testo)["certificato"]["dati"]).decode("utf-8")


def url_server() -> str:
    """Indirizzo del server delle licenze (variabile d'ambiente per i test e per il cambio di server)."""
    return os.environ.get("SICUR_LICENSE_SERVER", "")


__all__ = ["ErroreRete", "ErroreServer", "Licenze", "REVOCATA", "trasporto_http", "url_server"]
