"""Generazione del PiMUS (art. 136 e Allegato XXII del D.Lgs. 81/2008).

Stessa impaginazione del PSC e del POS, nel colore del programma: copertina, capitoli numerati secondo
l'Allegato XXII, dati mancanti evidenziati.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document

from sicurcantiere import anagrafiche, pimus
from sicurcantiere import elementi_ponteggio as E
from sicurcantiere import ponteggio as P
from sicurcantiere.documenti import stile
from sicurcantiere.documenti.comune import data_it, indirizzo_cantiere, salva
from sicurcantiere.documenti.composizione import CONSIGLIATO, OBBLIGATORIO, Manca
from sicurcantiere.repository import Repository

CANTIERE, IMPRESA, PONTEGGI = "Cantiere", "Impresa", "Ponteggi"


def genera_pimus(repo: Repository, ponteggio_id: int, destinazione: str | Path) -> Path:
    with stile.colori_documento(*stile.COLORI_PIMUS):
        return _genera(repo, ponteggio_id, destinazione)


def _misura(valore: float) -> str:
    return f"{valore:g} m".replace(".", ",") if valore else ""


def _data(valore) -> str:
    return data_it(valore) if valore else ""


def _genera(repo: Repository, ponteggio_id: int, destinazione: str | Path) -> Path:
    p = repo.leggi("ponteggi", ponteggio_id)
    if p is None:
        raise ValueError("Ponteggio inesistente")
    c = repo.cantiere()
    impresa = (repo.leggi("imprese", p["impresa_id"]) if p["impresa_id"] else None) or {}
    testi = {chiave: repo.testo(pimus.chiave_testo(ponteggio_id, chiave)) for chiave, _, _ in pimus.SEZIONI}
    titoli = {chiave: titolo for chiave, titolo, _ in pimus.SEZIONI}
    comune = f"{c['comune']} ({c['provincia']})" if c["provincia"] else c["comune"]
    data_documento = data_it(date.today())
    g = P.geometria(p)
    lati = P.lati(p, g)
    altezza = max(p["altezza"], P.altezza_massima(p, g))
    progetto_richiesto = altezza > pimus.ALTEZZA_SENZA_PROGETTO or not p["conforme_schemi"]
    addetti = [a for a in repo.elenco("addetti_ponteggio", ponteggio_id=ponteggio_id) if a["nome"].strip()]
    preposti = [a["nome"] for a in addetti if a["ruolo"] == P.PREPOSTO]
    preposto = ", ".join(preposti) or p["preposto"]
    allegati = repo.elenco("allegati_ponteggio", ponteggio_id=ponteggio_id)

    doc = Document()
    stile.imposta_stili(doc)
    stile.imposta_pagina(doc, " · ".join(v for v in (c["nome"], comune) if v),
                         (f"PiMUS · {p['nome']}".strip(" ·"), data_documento))
    stile.copertina(
        doc,
        comune=comune,
        titolo="Piano di montaggio, uso e smontaggio del ponteggio",
        riferimento="D.Lgs. 9 aprile 2008, n. 81 · art. 136 e Allegato XXII",
        voci=[("Cantiere", indirizzo_cantiere(c) or Manca("indirizzo del cantiere", CANTIERE)),
              ("Ponteggio", p["nome"] or Manca("ubicazione del ponteggio", PONTEGGI)),
              ("Tipologia", ", ".join(P.tipologie(p, g)))],
        data_luogo=f"{c['comune'] or ''}, {data_documento}".strip(", "),
        firme=[("Il datore di lavoro dell'impresa che esegue il montaggio", impresa.get("datore_lavoro", "")),
               ("Il preposto alle operazioni", preposto)],
        impresa=[impresa.get("ragione_sociale") or c["nome"] or "Ponteggio", anagrafiche.sede(impresa)
                 if impresa else ""],
        logo=impresa.get("logo", ""),
    )

    avvisi = pimus.avvisi(p, addetti)
    if avvisi:
        stile.banda(doc, "Avvertenze")
        for avviso in avvisi:
            stile.nota(doc, avviso, avviso=True)

    stile.capitolo(doc, "Dati identificativi del luogo di lavoro", "Allegato XXII, punto 1", nuova_pagina=True)
    stile.scheda(doc, [
        ("Opera", c["nome"] or Manca("denominazione dell'opera", CANTIERE)),
        ("Indirizzo del cantiere", indirizzo_cantiere(c) or Manca("indirizzo del cantiere", CANTIERE)),
        ("Ubicazione del ponteggio", p["nome"] or Manca("ubicazione del ponteggio", PONTEGGI)),
    ])

    stile.capitolo(doc, "Datore di lavoro che esegue montaggio, trasformazione e smontaggio",
                   "Allegato XXII, punto 2")
    stile.scheda(doc, [
        ("Impresa", impresa.get("ragione_sociale") or Manca("impresa che monta il ponteggio", PONTEGGI)),
        ("Sede", anagrafiche.sede(impresa) if impresa else ""),
        ("Partita IVA", impresa.get("partita_iva", "")),
        ("Datore di lavoro", impresa.get("datore_lavoro") or Manca("datore di lavoro dell'impresa", IMPRESA)),
    ])

    stile.capitolo(doc, "Squadra di lavoratori e preposto", "Allegato XXII, punto 3, e art. 136, comma 6")
    if addetti:
        stile.tabella_colorata(
            doc, ["Nome e cognome", "Ruolo", "Corso (data ed ente)", "Ultimo aggiornamento", "Valido fino al"],
            [[a["nome"], a["ruolo"], " · ".join(v for v in (_data(a["corso_data"]), a["corso_ente"]) if v) or "—",
              _data(a["aggiornamento_data"]) or "—",
              data_it(P.scadenza_formazione(a)) if P.scadenza_formazione(a) else "da indicare"] for a in addetti],
            8.5, larghezze=[4.4, 3.4, 4.2, 2.8, 2.6])
        if not preposti:
            stile.testo(doc, "", "preposto alle operazioni", PONTEGGI, OBBLIGATORIO)
    else:
        stile.scheda(doc, [
            ("Preposto alle operazioni", p["preposto"] or Manca("preposto al montaggio", PONTEGGI)),
            ("Addetti al montaggio", p["squadra"] or Manca("addetti al montaggio", PONTEGGI)),
        ])
    doc.add_paragraph("Gli addetti al montaggio, alla trasformazione e allo smontaggio hanno frequentato il corso "
                      "di formazione previsto dall'Allegato XXI (art. 136, comma 6), di 28 ore, con aggiornamento "
                      "di almeno 4 ore ogni 4 anni, e operano sotto la diretta sorveglianza del preposto.")

    stile.capitolo(doc, "Identificazione del ponteggio", "Allegato XXII, punto 4")
    scadenza = pimus.scadenza_autorizzazione(p)
    stile.scheda(doc, [
        ("Tipologia", ", ".join(P.tipologie(p, g)) or Manca("tipologia del ponteggio", PONTEGGI)),
        ("Fabbricante", p["fabbricante"] or Manca("fabbricante", PONTEGGI)),
        ("Sistema", " · ".join(v for v in (p.get("sistema", ""), p["modello"]) if v)),
        ("Autorizzazione ministeriale", p["autorizzazione"] or Manca("autorizzazione ministeriale (art. 131)",
                                                                     PONTEGGI)),
        ("Data e rinnovo", " · ".join(v for v in (
            f"rilasciata il {data_it(p['aut_data'])}" if p.get("aut_data") else "",
            f"rinnovata il {data_it(p['aut_rinnovo'])}" if p.get("aut_rinnovo") else "",
            f"valida fino al {data_it(scadenza)}" if scadenza else "") if v)),
        ("Schemi tipo utilizzati", p.get("schemi_tipo", "")),
        ("Altezza massima", _misura(altezza) or Manca("altezza massima", PONTEGGI)),
        ("Sviluppo in pianta", _misura(P.sviluppo(g))),
        ("Classe di carico degli impalcati", p["classe_carico"] or Manca("classe di carico", PONTEGGI, CONSIGLIATO)),
        ("Interpiano", _misura(g["interpiano"])),
        ("Mantovana parasassi", f"all'impalcato a {_misura(g['mantovana_livello'] * g['interpiano'])}: "
                                + ", ".join(l.nome for l in lati if l.mantovana) if any(l.mantovana for l in lati)
         else "non prevista"),
    ])
    stile.sezione(doc, "Tratti del ponteggio")
    stile.tabella_colorata(
        doc, ["Tratto", "Tipologia", "Facciata", "Campate", "Impalcati", "Larghezza", "Distanza", "Quota"],
        [[t.nome, t.tipo, _misura(t.lunghezza), f"{t.campate} × {_misura(t.campata)}",
          f"{t.livelli} (h {_misura(t.livelli * t.interpiano)})", _misura(t.larghezza), _misura(t.distanza) or "0 m",
          f"{t.quota:+.2f} m".replace(".", ",")] for t in lati], 8, larghezze=[3.2, 2.8, 1.9, 2.3, 2.4, 1.7, 1.6, 1.5])
    inseriti = g["elementi"]
    if inseriti:
        stile.sezione(doc, "Elementi inseriti e personalizzazioni")
        stile.tabella_colorata(doc, ["Elemento", "Posizione", "Quantità", "Note"],
                               [[E.voce(e["tipo"]).nome, E.descrizione(e, lati[e["tratto"]].nome),
                                 f"{E.quantita(e, lati[e['tratto']].campata, g['interpiano']):g}".replace(".", ","),
                                 e["note"]] for e in inseriti], 8, larghezze=[5.4, 5.6, 1.8, 4.6])
    stile.sezione(doc, "Elementi del ponteggio")
    stile.tabella_colorata(doc, ["Elemento", "Quantità indicativa"],
                           [[nome, f"{q:g} {u}".replace(".", ",")] for nome, q, u in P.elementi(p, g)], 8.5,
                           larghezze=[11.4, 6.0])
    stile.nota(doc, "Quantità stimate dalla geometria: gli elementi effettivi e il loro numero sono quelli degli schemi "
                    "del libretto del fabbricante.")

    stile.capitolo(doc, "Disegno esecutivo", "Allegato XXII, punto 5, e art. 134")
    doc.add_paragraph("Il disegno esecutivo riporta le generalità e la firma del progettista o, quando il calcolo non è "
                      "obbligatorio, della persona competente (art. 136, comma 1), i sovraccarichi massimi per metro "
                      "quadrato di impalcato, gli appoggi e gli ancoraggi.")
    a = P.ancoraggi(p, g)
    s = P.appoggio(p, g)
    stile.scheda(doc, [
        ("Sovraccarico massimo", f"{P._n(s.sovraccarico, 2)} kN/m² per impalcato" + (
            "" if P.sovraccarico(p["classe_carico"]) else " (da confermare con la classe di carico)")),
        ("Tipo di ancoraggio", g["tipo_ancoraggio"]),
        ("Descrizione degli ancoraggi", p["ancoraggi"] or Manca("descrizione degli ancoraggi", PONTEGGI)),
        ("Schema degli ancoraggi", f"{a.numero} ancoraggi, {a.maglia}; {P._n(a.area_per_ancoraggio, 1)} m² di "
                                   f"facciata per ancoraggio"),
        ("Piano di appoggio", p["piano_appoggio"] or Manca("piano di appoggio", PONTEGGI)),
        ("Verifica dell'appoggio", f"carico stimato sul montante più caricato ({s.tratto}) "
                                   f"{P._n(s.carico_montante, 2)} kN; pressione {P._n(s.pressione)} kPa su "
                                   f"{P._n(g['area_appoggio'], 2)} m² di ripartizione, portanza assunta "
                                   f"{P._n(s.portanza)} kPa: "
                                   + ("verificata" if s.verificato else
                                      f"non verificata, ripartizione minima {P._n(s.area_minima, 2)} m²")),
    ])
    _schemi(doc, p)

    stile.capitolo(doc, "Progetto del ponteggio", "Allegato XXII, punto 6, e artt. 132-133")
    if progetto_richiesto:
        doc.add_paragraph("Per il ponteggio è richiesto il progetto (art. 133), comprendente calcolo di resistenza "
                          "e stabilità e disegno esecutivo, firmato da un ingegnere o architetto abilitato e "
                          "allegato al presente piano.")
        stile.scheda(doc, [("Progettista", p["progettista"] or Manca("progettista abilitato", PONTEGGI))])
    else:
        doc.add_paragraph("Il ponteggio è montato secondo gli schemi tipo del libretto del fabbricante, entro i 20 m "
                          "di altezza: il progetto non è richiesto (art. 133).")

    stile.capitolo(doc, "Indicazioni generali per montaggio, trasformazione e smontaggio",
                   "Allegato XXII, punto 7 (piano di applicazione generalizzata)")
    lettere = [("stoccaggio", "a"), ("appoggio", "b"), ("tracciamento", "c"), ("dpi", "d"), ("sollevamento", "e"),
               ("linee_elettriche", "f"), ("ancoraggi", "g"), ("meteo", "h"), ("caduta_materiali", "i")]
    for chiave, lettera in lettere:
        stile.sezione(doc, f"{lettera}) {titoli[chiave]}")
        stile.testo(doc, testi[chiave], titoli[chiave], PONTEGGI, OBBLIGATORIO)
        if chiave == "linee_elettriche" and p.get("linee_tensione"):
            stile.scheda(doc, [("Linea elettrica aerea", p["linee_tensione"]),
                               ("Distanza dal ponteggio", _misura(p.get("linee_distanza") or 0) or "da rilevare"),
                               ("Distanza minima (Allegato IX)", _misura(pimus.distanza_minima(p["linee_tensione"])))])
    for chiave in ("istruzioni", "soccorso"):
        stile.sezione(doc, titoli[chiave])
        stile.testo(doc, testi[chiave], titoli[chiave], PONTEGGI, CONSIGLIATO)
    stile.scheda(doc, [("DPI specifici", p["dpi"]), ("Attrezzature di sollevamento", p["sollevamento"])],
                 titolo="Dotazioni")

    stile.capitolo(doc, "Modalità di montaggio, trasformazione e smontaggio", "Allegato XXII, punto 8")
    for chiave in ("montaggio", "trasformazione", "smontaggio"):
        stile.sezione(doc, titoli[chiave])
        stile.testo(doc, testi[chiave], titoli[chiave], PONTEGGI, OBBLIGATORIO)

    stile.capitolo(doc, "Regole da applicare durante l'uso", "Allegato XXII, punto 9")
    stile.testo(doc, testi["uso"], titoli["uso"], PONTEGGI, OBBLIGATORIO)

    stile.capitolo(doc, "Verifiche prima del montaggio e durante l'uso", "Allegato XXII, punto 10, e Allegato XIX")
    verifiche = repo.elenco("verifiche_ponteggio", ponteggio_id=ponteggio_id)
    if verifiche:
        t = stile.tabella_colorata(doc, ["Momento", "Verifica", "Esito", "Note"],
                                   [[v["momento"], v["voce"], v["esito"] or "Da eseguire", v["note"]]
                                    for v in verifiche], 8, larghezze=[3.0, 8.6, 2.4, 3.4])
        for riga, v in zip(t.rows[1:], verifiche):
            stile.colora_livello(riga.cells[2], 0 if v["esito"] in ("Conforme", "Non applicabile")
                                 else 3 if v["esito"] == "Non conforme" else 1)
    else:
        stile.testo(doc, "", "elenco delle verifiche dell'Allegato XIX", PONTEGGI, OBBLIGATORIO)

    p_data = doc.add_paragraph(f"{c['comune'] or ''}, {data_documento}".strip(", "))
    stile._spaziatura(p_data, 14, 8)
    stile.firme(doc, [("Il datore di lavoro dell'impresa che esegue il montaggio", impresa.get("datore_lavoro", "")),
                      ("Il preposto alle operazioni", preposto)])
    stile.nota(doc, "Il PiMUS è redatto da persona competente e messo a disposizione del preposto e dei lavoratori "
                    "addetti; una copia, con il disegno esecutivo e il libretto del fabbricante, è tenuta in "
                    "cantiere a disposizione dell'organo di vigilanza (art. 136, comma 1).")
    _allegati(doc, allegati)
    return salva(doc, destinazione)


def _schemi(doc, p) -> None:
    """Schema grafico generato dalla geometria: vista d'insieme, pianta, prospetti e sezione tipo."""
    from sicurcantiere import disegno_ponteggio

    try:
        tavole = disegno_ponteggio.tavole(p)
    except Exception:  # noqa: BLE001 - senza Qt il documento si genera lo stesso, senza disegni
        return
    stile.sezione(doc, "Schema grafico del ponteggio")
    stile.nota(doc, "Schema generato dai dati del ponteggio, con gli ancoraggi in rosso: va verificato sul libretto "
                    "del fabbricante e completato nel disegno esecutivo firmato dal responsabile del cantiere.")
    for tavola in tavole:
        stile.immagine_png(doc, tavola.png, stile.LARGHEZZA_UTILE if tavola.orizzontale else 11.5, tavola.titolo)


def _allegati(doc, allegati) -> None:
    if not allegati:
        return
    stile.capitolo(doc, "Allegati", "art. 134 e art. 136, comma 1", nuova_pagina=True)
    stile.tabella_colorata(doc, ["N.", "Tipo", "Titolo"], [[str(n), a["tipo"], a["titolo"]]
                                                          for n, a in enumerate(allegati, 1)], 8.5,
                           larghezze=[1.2, 6.0, 10.2])
    for n, a in enumerate(allegati, 1):
        stile.banda(doc, f"Allegato {n} · {a['tipo']}" + (f" · {a['titolo']}" if a["titolo"] else ""))
        stile.file_allegato(doc, a["file"], "nella pagina «Ponteggi e PiMUS», scheda «Allegati»")
