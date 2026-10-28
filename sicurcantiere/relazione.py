"""Sezioni a testo libero del PSC e rischi particolari (Allegato XV, punti 2.1.2, 2.1.4, 2.2 e 2.3).

Le sezioni sono divise in gruppi (le schede della pagina «Relazione del PSC»); per ognuna: chiave, titolo,
guida alla compilazione, riferimento di legge e importanza (obbligatoria o da compilare se pertinente).
I vecchi file con le sezioni «area» e «organizzazione» uniche restano leggibili: «area» diventa le
caratteristiche dell'area (migrazione del file) e «organizzazione» le note generali sull'organizzazione.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

OBBLIGATORIA, SE_PERTINENTE = "obbligatorio", "consigliato"


@dataclass(frozen=True)
class Sezione:
    chiave: str
    titolo: str
    guida: str
    riferimento: str
    livello: str = OBBLIGATORIA


GRUPPI: list[tuple[str, list[Sezione]]] = [
    ("Area e contesto", [
        Sezione("contesto", "Contesto in cui è collocata l'area di cantiere",
                "Dove si trova il cantiere: tipo di zona (urbana, extraurbana, condominio abitato...), edifici e "
                "attività vicine, accessi dalla viabilità pubblica, presenza di terzi.",
                "Allegato XV punto 2.1.2, lettera a), punto 2"),
        Sezione("area_caratteristiche", "Caratteristiche dell'area di cantiere",
                "Morfologia e dimensioni dell'area, presenza di linee elettriche aeree e di condutture sotterranee "
                "(gas, acqua, fognature, linee elettriche e telefoniche) e misure per evitarle.",
                "Allegato XV punto 2.2.1, lettera a)"),
        Sezione("area_esterni", "Fattori esterni che comportano rischi per il cantiere",
                "Traffico e lavori stradali vicini, altri cantieri, attività confinanti, corsi d'acqua (rischio "
                "di annegamento), condizioni meteo particolari; per ognuno le misure previste.",
                "Allegato XV punto 2.2.1, lettera b)"),
        Sezione("area_circostante", "Rischi che le lavorazioni comportano per l'area circostante",
                "Rumore, polveri, caduta di materiali, traffico dei mezzi verso abitazioni, scuole, strade e "
                "passanti; misure di protezione dei terzi.",
                "Allegato XV punto 2.2.1, lettera c)"),
        Sezione("idrogeologia", "Caratteristiche idrogeologiche del terreno e profilo altimetrico",
                "Natura del terreno, falda, pendenze; oppure il rinvio alla relazione geologica o geotecnica, se "
                "già redatta. Se non sono previsti scavi né opere nel terreno, indicarlo.",
                "Allegato XV punto 2.1.4", SE_PERTINENTE),
    ]),
    ("Organizzazione del cantiere", [
        Sezione("organizzazione", "Organizzazione generale del cantiere",
                "Note introduttive sull'organizzazione (facoltative): i punti richiesti dalla legge sono nelle "
                "sezioni che seguono.", "Allegato XV punto 2.2.2", SE_PERTINENTE),
        Sezione("org_recinzione", "Recinzione, accessi e segnalazioni",
                "Tipo e altezza della recinzione, cancelli e accessi pedonali e carrabili, cartelli e "
                "illuminazione.", "Allegato XV punto 2.2.2, lettera a)"),
        Sezione("org_servizi", "Servizi igienico-assistenziali",
                "Baracche, spogliatoi, servizi igienici, locali di riposo e refezione, acqua potabile; chi li "
                "installa e chi li mantiene.", "Allegato XV punto 2.2.2, lettera b), e Allegato XIII"),
        Sezione("org_viabilita", "Viabilità principale di cantiere",
                "Percorsi dei mezzi e dei pedoni, larghezze, pendenze, separazione tra mezzi e persone, senso di "
                "marcia.", "Allegato XV punto 2.2.2, lettera c)"),
        Sezione("org_impianti", "Impianti di alimentazione e reti principali",
                "Elettricità (quadro di cantiere, allacciamento), acqua, gas ed energia di qualsiasi tipo: chi li "
                "realizza e le dichiarazioni di conformità.", "Allegato XV punto 2.2.2, lettera d)"),
        Sezione("org_terra", "Impianto di terra e protezione contro le scariche atmosferiche",
                "Impianto di terra del cantiere, verifica della necessità di protezione dalle scariche "
                "atmosferiche per gru e ponteggi, denuncia e verifiche (D.P.R. 462/2001).",
                "Allegato XV punto 2.2.2, lettera e)"),
        Sezione("org_rls", "Consultazione dei rappresentanti dei lavoratori per la sicurezza",
                "Come le imprese mettono il PSC a disposizione dei loro RLS prima dell'inizio dei lavori e come "
                "il coordinatore raccoglie le loro osservazioni.", "Allegato XV punto 2.2.2, lettera f), e art. 102"),
        Sezione("org_coordinamento", "Cooperazione e coordinamento delle attività",
                "Come il coordinatore per l'esecuzione organizza la cooperazione e il coordinamento tra i datori di "
                "lavoro e la reciproca informazione (riunioni, verbali, comunicazioni).",
                "Allegato XV punto 2.2.2, lettera g), e art. 92, comma 1, lettera c)"),
        Sezione("org_mezzi", "Accesso dei mezzi di fornitura dei materiali",
                "Orari, percorsi e aree di sosta dei mezzi dei fornitori, assistenza a terra nelle manovre.",
                "Allegato XV punto 2.2.2, lettera h)", SE_PERTINENTE),
        Sezione("org_dislocazione", "Dislocazione degli impianti di cantiere",
                "Posizione di gru, betoniere, silos, quadri elettrici, baracche (riportata anche nella "
                "planimetria).", "Allegato XV punto 2.2.2, lettera i)"),
        Sezione("org_carico", "Zone di carico e scarico",
                "Dove si caricano e scaricano i materiali, delimitazioni e segnaletica, divieto di sosta sotto i "
                "carichi sospesi.", "Allegato XV punto 2.2.2, lettera l)"),
        Sezione("org_deposito", "Zone di deposito delle attrezzature e di stoccaggio dei materiali e dei rifiuti",
                "Aree di deposito e stoccaggio, cassoni dei rifiuti e loro gestione.",
                "Allegato XV punto 2.2.2, lettera m)"),
        Sezione("org_infiammabili", "Zone di deposito dei materiali con pericolo d'incendio o di esplosione",
                "Bombole, carburanti, solventi: dove sono depositati e con quali protezioni; se non sono "
                "presenti, indicarlo.", "Allegato XV punto 2.2.2, lettera n)", SE_PERTINENTE),
    ]),
    ("Scelte e coordinamento", [
        Sezione("scelte", "Scelte progettuali e organizzative, procedure e misure preventive generali",
                "Misure generali valide per tutto il cantiere, oltre a quelle di ogni fase.",
                "Allegato XV punto 2.1.2, lettera d), e punto 2.2.4", SE_PERTINENTE),
        Sezione("verifica_prescrizioni", "Modalità di verifica del rispetto delle prescrizioni sulle interferenze",
                "Come e quando il coordinatore per l'esecuzione verifica che lo sfasamento delle lavorazioni e le "
                "altre prescrizioni siano rispettati (sopralluoghi, riunioni, aggiornamento del cronoprogramma).",
                "Allegato XV punto 2.3.1"),
        Sezione("uso_comune", "Uso comune di apprestamenti, attrezzature, infrastrutture, mezzi e servizi",
                "Elementi usati da più imprese (ponteggi, servizi, quadro elettrico, gru...), chi li predispone, "
                "chi li mantiene e le regole d'uso.", "Allegato XV punto 2.1.2, lettera f), e punto 2.3.4"),
        Sezione("cooperazione", "Modalità di cooperazione, coordinamento e informazione tra le imprese",
                "Riunioni di coordinamento, scambio di informazioni tra datori di lavoro e lavoratori autonomi, "
                "verbali.", "Allegato XV punto 2.1.2, lettera g), e punto 2.3.5"),
        Sezione("emergenze", "Organizzazione del primo soccorso, antincendio ed evacuazione",
                "Gestione comune o affidata a ogni impresa, addetti, presidi, punto di raccolta, percorsi di "
                "evacuazione, chiamata dei soccorsi.", "Allegato XV punto 2.1.2, lettera h)"),
        Sezione("telefoni", "Telefoni e indirizzi delle strutture del territorio",
                "Pronto soccorso e ospedale più vicino, Vigili del fuoco, ASL, Carabinieri e Polizia locale, con "
                "indirizzi e numeri.", "Allegato XV punto 2.1.2, lettera h)", SE_PERTINENTE),
    ]),
]

SEZIONI_DETTAGLIO: dict[str, Sezione] = {s.chiave: s for _, gruppo in GRUPPI for s in gruppo}
# Elenco semplice (chiave, titolo), usato dalla pagina e dal documento.
SEZIONI: list[tuple[str, str]] = [(s.chiave, s.titolo) for s in SEZIONI_DETTAGLIO.values()]
OBBLIGATORIE = {s.chiave for s in SEZIONI_DETTAGLIO.values() if s.livello == OBBLIGATORIA}


# --- lavori comportanti rischi particolari (Allegato XI del D.Lgs. 81/2008) ---

CHIAVE_ALLEGATO_XI = "allegato_xi"
ALLEGATO_XI: list[tuple[str, str]] = [
    ("1", "Lavori che espongono a rischi di seppellimento o di sprofondamento a profondità superiore a 1,5 m o di "
          "caduta dall'alto da altezza superiore a 2 m, se particolarmente aggravati dalla natura dell'attività o "
          "dei procedimenti attuati oppure dalle condizioni ambientali del posto di lavoro o dell'opera"),
    ("1-bis", "Lavori che espongono al rischio di esplosione per l'innesco accidentale di un ordigno bellico "
              "inesploso rinvenuto durante le attività di scavo"),
    ("2", "Lavori che espongono a sostanze chimiche o biologiche che presentano rischi particolari o che "
          "comportano un'esigenza legale di sorveglianza sanitaria"),
    ("3", "Lavori con radiazioni ionizzanti che richiedono la designazione di zone controllate o sorvegliate"),
    ("4", "Lavori in prossimità di linee elettriche aeree a conduttori nudi in tensione"),
    ("5", "Lavori che espongono a un rischio di annegamento"),
    ("6", "Lavori in pozzi, sterri sotterranei e gallerie"),
    ("7", "Lavori subacquei con respiratori"),
    ("8", "Lavori in cassoni ad aria compressa"),
    ("9", "Lavori comportanti l'impiego di esplosivi"),
    ("10", "Lavori di montaggio o smontaggio di elementi prefabbricati pesanti"),
]


def leggi_allegato_xi(testo: str) -> dict:
    """{"verificato": bool, "voci": {numero: {"presente": bool, "misure": str}}}"""
    try:
        dati = json.loads(testo) if testo.strip() else {}
    except ValueError:
        dati = {}
    voci = dati.get("voci") if isinstance(dati.get("voci"), dict) else {}
    return {"verificato": bool(dati.get("verificato")),
            "voci": {n: {"presente": bool((voci.get(n) or {}).get("presente")),
                         "misure": str((voci.get(n) or {}).get("misure") or "")} for n, _ in ALLEGATO_XI}}


# --- rischi da analizzare nelle lavorazioni (Allegato XV punto 2.2.3) ---

CHIAVE_RISCHI_LAVORAZIONI = "rischi_2_2_3"
# (lettera, rischio, parole che lo fanno riconoscere nei rischi delle fasi)
RISCHI_LAVORAZIONI: list[tuple[str, str, tuple[str, ...]]] = [
    ("a", "Investimento da veicoli circolanti nell'area di cantiere", ("investiment",)),
    ("b", "Seppellimento negli scavi", ("seppelliment", "franament", "sprofond", "crollo delle pareti")),
    ("c", "Caduta dall'alto", ("caduta dall'alto", "cadute dall'alto", "caduta da")),
    ("d", "Insalubrità dell'aria nei lavori in galleria", ("galleri",)),
    ("e", "Instabilità delle pareti e della volta nei lavori in galleria", ("galleri",)),
    ("f", "Estese demolizioni o manutenzioni, se le modalità tecniche sono definite in fase di progetto",
     ("demoliz",)),
    ("g", "Incendio o esplosione connessi con lavorazioni e materiali pericolosi", ("incendi", "esplosion")),
    ("h", "Sbalzi eccessivi di temperatura", ("microclima", "temperatur", "colpo di calore", "freddo")),
    ("i", "Elettrocuzione", ("elettrocuz", "contatto elettric", "elettric")),
    ("l", "Rumore", ("rumore",)),
    ("m", "Uso di sostanze chimiche", ("chimic", "sostanz", "inalazione", "polveri")),
]


def leggi_rischi_lavorazioni(testo: str) -> dict:
    """{"verificato": bool, "voci": {lettera: {"presente": bool, "misure": str}}}"""
    try:
        dati = json.loads(testo) if testo.strip() else {}
    except ValueError:
        dati = {}
    voci = dati.get("voci") if isinstance(dati.get("voci"), dict) else {}
    return {"verificato": bool(dati.get("verificato")),
            "voci": {l: {"presente": bool((voci.get(l) or {}).get("presente")),
                         "misure": str((voci.get(l) or {}).get("misure") or "")} for l, _, _ in RISCHI_LAVORAZIONI}}


def fasi_per_rischio(fasi: list[dict], rischi: list[dict]) -> dict[str, list[dict]]:
    """Per ogni lettera del punto 2.2.3, le fasi che hanno un rischio corrispondente nelle loro schede."""
    per_fase: dict[int, str] = {}
    for r in rischi:
        per_fase[r["fase_id"]] = f"{per_fase.get(r['fase_id'], '')} {r['descrizione']} {r.get('fonte', '')}".lower()
    risultato: dict[str, list[dict]] = {}
    for lettera, _, parole in RISCHI_LAVORAZIONI:
        # le gallerie si riconoscono anche dal nome della lavorazione
        trovate = [f for f in fasi
                   if any(p in per_fase.get(f["id"], "") or
                          (lettera in "de" and p in f"{f.get('lavorazione', '')} {f.get('descrizione', '')}".lower())
                          for p in parole)]
        if trovate:
            risultato[lettera] = trovate
    return risultato


# --- contenuti della planimetria di cantiere (layout) ---

CHIAVE_CONTENUTI_PLANIMETRIA = "planimetria_contenuti"
CONTENUTI_PLANIMETRIA: list[tuple[str, bool]] = [  # (voce, essenziale)
    ("Recinzione del cantiere", True),
    ("Accessi pedonali e carrabili", True),
    ("Viabilità interna ed esterna", True),
    ("Zone di carico, scarico e stoccaggio dei materiali", True),
    ("Baraccamenti e servizi igienico-assistenziali", True),
    ("Posizione delle attrezzature fisse (gru, betoniere, silos)", True),
    ("Impianti elettrici e idrici di cantiere", True),
    ("Punti di scavo", False),
    ("Reti di scarico delle acque e fognature", False),
    ("Allacci ai servizi pubblici", False),
    ("Zone di deposito dei rifiuti e dei materiali infiammabili", False),
    ("Percorsi di emergenza e punto di raccolta", False),
]


def leggi_contenuti_planimetria(testo: str) -> set[str]:
    return {v for v in (testo or "").split(";") if v}


# --- ordigni bellici inesplosi (art. 91, comma 2-bis) ---

CHIAVE_ORDIGNI = "ordigni_bellici"
SCAVI = ("", "Sì", "No")  # «» = non indicato
ESITI_ORDIGNI = (
    "",
    "Rischio trascurabile: nessuna bonifica preventiva",
    "Bonifica preventiva necessaria (impresa specializzata, art. 104, comma 4-bis)",
    "Da approfondire prima dell'inizio dei lavori",
)


def leggi_ordigni(testo: str) -> dict:
    """{"scavi": "Sì"|"No"|"", "esito": ..., "motivazione": str}"""
    try:
        dati = json.loads(testo) if testo.strip() else {}
    except ValueError:
        dati = {}
    scavi = dati.get("scavi") if dati.get("scavi") in SCAVI else ""
    esito = dati.get("esito") if dati.get("esito") in ESITI_ORDIGNI else ""
    return {"scavi": scavi, "esito": esito, "motivazione": str(dati.get("motivazione") or "")}


def fasi_con_scavi(fasi: list[dict]) -> list[dict]:
    """Fasi che comportano scavi (dal nome della lavorazione o della fase)."""
    return [f for f in fasi if "scav" in f"{f.get('lavorazione', '')} {f.get('descrizione', '')}".lower()]


# --- categorie dei costi della sicurezza (Allegato XV punto 4.1.1) ---

CATEGORIE_COSTI: list[tuple[str, str]] = [
    ("a", "Apprestamenti previsti nel PSC"),
    ("b", "Misure preventive e protettive e DPI per lavorazioni interferenti"),
    ("c", "Impianti di terra, di protezione contro le scariche atmosferiche, antincendio, evacuazione fumi"),
    ("d", "Mezzi e servizi di protezione collettiva"),
    ("e", "Procedure previste nel PSC per specifici motivi di sicurezza"),
    ("f", "Interventi per lo sfasamento spaziale o temporale delle lavorazioni interferenti"),
    ("g", "Misure di coordinamento per l'uso comune di apprestamenti, attrezzature, infrastrutture, mezzi e "
          "servizi"),
]
