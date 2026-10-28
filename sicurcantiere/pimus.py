"""Contenuti del Piano di Montaggio, Uso e Smontaggio dei ponteggi (art. 136 e Allegato XXII).

I testi base sono una traccia scritta per SicurCantiere: vanno adattati al
ponteggio specifico e al libretto del fabbricante.
"""

from __future__ import annotations

from typing import Any

from sicurcantiere.ponteggio import TIPI_PONTEGGIO  # noqa: F401 - usato dalle pagine

ALTEZZA_SENZA_PROGETTO = 20.0  # m, art. 133: oltre serve il progetto

# (chiave, titolo, testo base)
SEZIONI: list[tuple[str, str, str]] = [
    ("stoccaggio", "Zone di stoccaggio e di montaggio",
     "Gli elementi del ponteggio sono depositati in un'area delimitata, piana e compatta, vicina "
     "alla zona di montaggio ma fuori dai percorsi dei mezzi. I materiali sono accatastati in modo "
     "stabile, separati per tipologia, senza superare l'altezza di [indicare] m. La zona sottostante "
     "il montaggio è interdetta al passaggio con transenne e segnaletica per tutta la durata delle "
     "operazioni."),
    ("appoggio", "Verifica del piano di appoggio",
     "Prima del montaggio il preposto verifica che il piano di appoggio sia in grado di sostenere i "
     "carichi trasmessi dalle basette: su terreno naturale si interpongono tavole o piastre di "
     "ripartizione; su pavimentazioni si verifica l'assenza di cavità, pozzetti e sottoservizi. Le "
     "basette regolabili sono usate entro l'estensione massima indicata dal fabbricante."),
    ("tracciamento", "Tracciamento e allineamento",
     "Il ponteggio è tracciato a partire dagli spigoli dell'edificio, mantenendo la distanza dalla "
     "facciata non superiore a 20 cm o, se maggiore, prevedendo il parapetto anche sul lato interno. "
     "Il primo impalcato viene messo in bolla e in squadro prima di proseguire in elevazione."),
    ("dpi", "DPI utilizzati e punti di ancoraggio",
     "Gli addetti utilizzano casco con sottogola, scarpe antinfortunistiche, guanti e imbracatura "
     "anticaduta con doppio cordino e assorbitore di energia. Durante il montaggio il cordino è "
     "agganciato ai punti indicati dal fabbricante (montanti, correnti o dispositivi dedicati), "
     "sempre al di sopra del piano di lavoro, mantenendo almeno un aggancio in ogni momento."),
    ("sollevamento", "Attrezzature per il sollevamento dei materiali",
     "Il sollevamento degli elementi avviene con [carrucola / argano a bandiera / gru], installata "
     "secondo le istruzioni del fabbricante e verificata prima dell'uso. I carichi sono imbracati "
     "con ganci dotati di chiusura di sicurezza; nessuno sosta sotto il carico sospeso."),
    ("linee_elettriche", "Misure in presenza di linee elettriche aeree",
     "Prima del montaggio si verifica la presenza di linee elettriche aeree nude in tensione nel raggio "
     "d'azione del ponteggio e delle attrezzature di sollevamento. Se presenti, il montaggio avviene "
     "mantenendo le distanze di sicurezza dell'Allegato IX (3 m fino a 1 kV, 3,5 m fino a 30 kV, 5 m fino "
     "a 132 kV, 7 m oltre) da qualsiasi parte del ponteggio, degli elementi movimentati e dei lavoratori; "
     "dove non è possibile si chiede all'ente gestore la messa fuori tensione o la protezione della linea "
     "(art. 117)."),
    ("ancoraggi", "Tipo e modalità di realizzazione degli ancoraggi",
     "Gli ancoraggi alla costruzione sono realizzati secondo lo schema del libretto, in numero e "
     "posizione non inferiori a quelli previsti, con [tasselli / anelli / tubi a cravatta]. Ogni "
     "ancoraggio viene posato man mano che si sale e prima di caricare l'impalcato superiore; i "
     "tasselli sono di tipo idoneo al supporto e verificati a trazione a campione."),
    ("meteo", "Misure in caso di condizioni meteorologiche avverse",
     "Il montaggio, la trasformazione e lo smontaggio sono sospesi con vento forte, pioggia intensa, "
     "neve, ghiaccio o scarsa visibilità. Prima della ripresa il preposto verifica il ponteggio, "
     "con particolare attenzione ad ancoraggi, appoggi e teli o reti eventualmente applicati."),
    ("caduta_materiali", "Misure contro la caduta di materiali e oggetti",
     "Durante il montaggio e lo smontaggio l'area sottostante è delimitata e interdetta. Gli impalcati "
     "sono completi di tavole fermapiede; dove sotto il ponteggio passano persone o veicoli si installano "
     "la mantovana parasassi, le reti o i teli e, sopra gli ingressi, la protezione del varco. Gli attrezzi "
     "sono assicurati contro la caduta e i materiali non vengono depositati sui bordi degli impalcati."),
    ("soccorso", "Procedure di emergenza e soccorso",
     "Per il soccorso di un addetto rimasto sospeso all'imbracatura, la squadra dispone dei mezzi indicati "
     "nel piano di soccorso (dispositivo di recupero, scala o piattaforma) e interviene senza attendere i "
     "soccorsi esterni, perché la sospensione inerte prolungata è pericolosa. Il preposto chiama il 112 "
     "e indica il percorso di accesso al cantiere."),
    ("istruzioni", "Istruzioni per gli addetti",
     "Le operazioni sono eseguite da lavoratori formati ai sensi dell'Allegato XXI, sotto la "
     "diretta sorveglianza del preposto. Il personale conosce il presente piano e il libretto del "
     "fabbricante, che sono disponibili in cantiere."),
    ("montaggio", "Sequenza di montaggio passo dopo passo",
     "1. Delimitazione dell'area e posa delle basette sul piano di ripartizione.\n"
     "2. Posa della prima campata di base, messa in bolla e in squadro.\n"
     "3. Posa dei correnti, delle diagonali e degli impalcati del primo livello.\n"
     "4. Salita al livello superiore con la protezione del parapetto provvisorio o con il cordino agganciato.\n"
     "5. Posa degli ancoraggi prima di procedere al livello successivo.\n"
     "6. Ripetizione fino alla quota finale; posa di parapetti, fermapiede e mantovana.\n"
     "7. Verifica finale del preposto e consegna del ponteggio per l'uso."),
    ("trasformazione", "Trasformazione del ponteggio",
     "Qualsiasi modifica rispetto alla configurazione iniziale è eseguita dagli addetti formati "
     "sotto la sorveglianza del preposto, dopo aver interdetto l'uso del tratto interessato e "
     "verificato che la nuova configurazione rientri negli schemi del libretto o nel progetto."),
    ("smontaggio", "Sequenza di smontaggio",
     "Lo smontaggio procede dall'alto verso il basso, nell'ordine inverso al montaggio. Gli "
     "ancoraggi si rimuovono solo quando si smonta il livello corrispondente. Gli elementi sono "
     "calati con l'attrezzatura di sollevamento, mai lanciati."),
    ("uso", "Regole durante l'uso del ponteggio",
     "È vietato modificare il ponteggio, rimuovere ancoraggi, parapetti o tavole fermapiede, "
     "depositare materiali oltre il carico ammesso per la classe del ponteggio e salire o scendere "
     "lungo i montanti. L'accesso agli impalcati avviene dalle scale interne o dalle botole. Ogni "
     "anomalia è segnalata immediatamente al preposto."),
]

# Voci di verifica (momento, descrizione, tipologie a cui si applicano; vuoto = tutte), sugli argomenti
# dell'Allegato XIX: prima di ogni montaggio per elemento e per tipologia, poi durante l'uso.
TELAI, TUBI, MULTI = "Telai prefabbricati", "Tubi e giunti", "Multidirezionale"
VERIFICHE_TIPOLOGIA: list[tuple[str, str, tuple[str, ...]]] = [
    ("Prima del montaggio", "Presenza in cantiere della copia dell'autorizzazione ministeriale e del libretto", ()),
    ("Prima del montaggio", "Marchio del fabbricante rilevabile su ogni elemento e conforme al libretto (elementi "
                            "senza marchio o difformi: scartati)", ()),
    ("Prima del montaggio", "Stato della protezione contro la corrosione degli elementi", ()),
    ("Prima del montaggio", "Telai: verticalità dei montanti e orizzontalità del traverso", (TELAI,)),
    ("Prima del montaggio", "Telai: spinotto di collegamento tra i montanti efficiente", (TELAI,)),
    ("Prima del montaggio", "Telai: attacchi delle controventature (perni e boccole) efficienti", (TELAI,)),
    ("Prima del montaggio", "Montanti e traversi prefabbricati: linearità e collegamenti efficienti",
     ("Montanti e traversi prefabbricati",)),
    ("Prima del montaggio", "Montanti multidirezionali: rosette integre e non deformate, cunei efficienti", (MULTI,)),
    ("Prima del montaggio", "Correnti, diagonali e traversi: linearità e collegamenti al telaio o ai nodi", ()),
    ("Prima del montaggio", "Tubi: linearità, assenza di schiacciamenti, estremità tagliate a squadra", (TUBI,)),
    ("Prima del montaggio", "Giunti: bulloni completi di dadi, filettature in buono stato, assenza di deformazioni",
     (TUBI,)),
    ("Prima del montaggio", "Tubi e giunti eventualmente usati di tipo autorizzato e di un unico fabbricante", ()),
    ("Prima del montaggio", "Impalcati prefabbricati: piani di calpestio orizzontali, appoggi al traverso non "
                            "deformati, sistemi di collegamento efficienti", ()),
    ("Prima del montaggio", "Tavole in legno: integre, senza nodi passanti, spessore adeguato", (TUBI,)),
    ("Prima del montaggio", "Basette: piastra e vite di regolazione integre", ()),
    ("Prima del montaggio", "Piano di appoggio verificato e tavole di ripartizione predisposte", ()),
    ("Durante l'uso", "Disegno esecutivo conforme allo schema tipo del fabbricante e firmato dalla persona "
                      "competente (art. 136)", ()),
    ("Durante l'uso", "Progetto firmato da ingegnere o architetto abilitato per altezza oltre 20 m o schemi non "
                      "conformi (art. 133)", ()),
    ("Durante l'uso", "Documentazione dell'ultima verifica eseguita dal preposto", ()),
    ("Durante l'uso", "Calcolo per l'azione del vento in presenza di teli, reti, graticci o tabelloni", ()),
    ("Durante l'uso", "Ancoraggi presenti nel numero e nelle posizioni previste, efficienti e serrati", ()),
    ("Durante l'uso", "Verticalità dei montanti e assenza di cedimenti degli appoggi", ()),
    ("Durante l'uso", "Giunti serrati correttamente", (TUBI,)),
    ("Durante l'uso", "Controventature (diagonali di facciata e in pianta) presenti e collegate", ()),
    ("Durante l'uso", "Parapetti, correnti intermedi e tavole fermapiede completi su tutti i lati aperti", ()),
    ("Durante l'uso", "Impalcati completi, con i dispositivi di blocco in opera e senza vuoti tra gli elementi", ()),
    ("Durante l'uso", "Distanza dalla facciata non superiore a 20 cm o parapetto sul lato interno", ()),
    ("Durante l'uso", "Mantovana parasassi e protezioni dei passaggi presenti dove richieste", ()),
    ("Durante l'uso", "Scale di accesso interne e botole funzionanti", ()),
    ("Durante l'uso", "Carichi sugli impalcati entro i limiti della classe del ponteggio, cartello esposto", ()),
    ("Durante l'uso", "Verifica dopo violente perturbazioni atmosferiche o prolungata interruzione dei lavori "
                      "(art. 137)", ()),
    ("Durante l'uso", "Messa a terra contro le scariche atmosferiche, se il ponteggio non è autoprotetto", ()),
]
# compatibilità: elenco (momento, voce) di tutte le verifiche
VERIFICHE: list[tuple[str, str]] = [(m, v) for m, v, _ in VERIFICHE_TIPOLOGIA]


def verifiche_per(tipologie: list[str]) -> list[tuple[str, str]]:
    """Verifiche che riguardano le tipologie presenti nel ponteggio."""
    return [(m, v) for m, v, tipi in VERIFICHE_TIPOLOGIA if not tipi or any(t in tipologie for t in tipi)]


ESITI = ["", "Conforme", "Non conforme", "Non applicabile"]


def chiave_testo(ponteggio_id: int, sezione: str) -> str:
    return f"pimus:{ponteggio_id}:{sezione}"


def avvisi(ponteggio: dict[str, Any], addetti: list[dict[str, Any]] | None = None) -> list[str]:
    """Obblighi e incongruenze del ponteggio da segnalare all'utente e nel documento. Con la squadra
    (`addetti`) si controllano anche il preposto e la formazione di ciascuno."""
    from sicurcantiere import ponteggio as P

    messaggi = []
    altezza = max(float(ponteggio.get("altezza") or 0), P.altezza_massima(ponteggio))
    if altezza > ALTEZZA_SENZA_PROGETTO or not ponteggio.get("conforme_schemi", 1):
        motivo = (f"altezza superiore a {ALTEZZA_SENZA_PROGETTO:g} m" if altezza > ALTEZZA_SENZA_PROGETTO
                  else "configurazione non conforme agli schemi tipo del libretto")
        messaggi.append(f"Progetto del ponteggio obbligatorio ({motivo}, art. 133): acquisire il "
                        "calcolo di resistenza e stabilità e il disegno esecutivo firmati da un ingegnere o "
                        "architetto abilitato.")
        if not str(ponteggio.get("progettista", "")).strip():
            messaggi.append("Indicare il progettista del ponteggio.")
    if not str(ponteggio.get("autorizzazione", "")).strip():
        messaggi.append("Indicare gli estremi dell'autorizzazione ministeriale del ponteggio (art. 131).")
    else:
        messaggi += avvisi_autorizzazione(ponteggio)
    messaggi += avvisi_linee(ponteggio)
    if addetti:
        messaggi += P.avvisi_squadra(addetti)
    elif not str(ponteggio.get("preposto", "")).strip():
        messaggi.append("Indicare il preposto alle operazioni di montaggio e smontaggio (art. 136, comma 6).")
    if not ponteggio.get("impresa_id"):
        messaggi.append("Indicare l'impresa che esegue il montaggio.")
    if "geometria" in ponteggio:
        messaggi += P.avvisi_geometria(ponteggio)
    return messaggi


# Distanze minime dalle linee elettriche aeree nude in tensione (Allegato IX, tabella 1): (fino a kV, metri).
DISTANZE_LINEE: list[tuple[float, float, str]] = [
    (1, 3.0, "fino a 1 kV"),
    (30, 3.5, "da 1 a 30 kV"),
    (132, 5.0, "da 30 a 132 kV"),
    (float("inf"), 7.0, "oltre 132 kV"),
]
TENSIONI = ["", *[d[2] for d in DISTANZE_LINEE]]
ANNI_AUTORIZZAZIONE = 10  # art. 131: l'autorizzazione è soggetta a rinnovo ogni dieci anni


def distanza_minima(tensione: str) -> float:
    return next((d for _, d, nome in DISTANZE_LINEE if nome == tensione), 0.0)


def avvisi_linee(ponteggio: dict[str, Any]) -> list[str]:
    tensione = ponteggio.get("linee_tensione") or ""
    if not tensione:
        return []
    minima = _m(distanza_minima(tensione))
    distanza = float(ponteggio.get("linee_distanza") or 0)
    if not distanza:
        return [f"Linea elettrica aerea {tensione}: indicare la distanza dal ponteggio (minimo {minima} m, "
                "Allegato IX)."]
    if distanza < distanza_minima(tensione):
        return [f"Linea elettrica aerea {tensione} a {_m(distanza)} m dal ponteggio, meno dei {minima} m "
                "dell'Allegato IX: chiedere all'ente gestore la messa fuori tensione o la protezione della linea "
                "(art. 117)."]
    return []


def _m(valore: float) -> str:
    return f"{valore:g}".replace(".", ",")


def scadenza_autorizzazione(ponteggio: dict[str, Any]):
    """Fine della validità: dieci anni dalla data dell'autorizzazione o dell'ultimo rinnovo."""
    from datetime import date

    ultima = None
    for chiave in ("aut_data", "aut_rinnovo"):
        try:
            d = date.fromisoformat(str(ponteggio.get(chiave) or ""))
        except ValueError:
            continue
        ultima = max(ultima, d) if ultima else d
    if ultima is None:
        return None
    try:
        return ultima.replace(year=ultima.year + ANNI_AUTORIZZAZIONE)
    except ValueError:
        return ultima.replace(year=ultima.year + ANNI_AUTORIZZAZIONE, day=28)


def avvisi_autorizzazione(ponteggio: dict[str, Any], oggi=None) -> list[str]:
    from datetime import date

    if "aut_data" not in ponteggio:
        return []
    scadenza = scadenza_autorizzazione(ponteggio)
    if scadenza is None:
        return ["Indicare la data dell'autorizzazione ministeriale (rinnovo ogni dieci anni, art. 131)."]
    if scadenza < (oggi or date.today()):
        return [f"Autorizzazione ministeriale scaduta il {scadenza.strftime('%d/%m/%Y')}: indicare la data del "
                "rinnovo (ogni dieci anni, art. 131) o usare un sistema con autorizzazione valida."]
    return []


def avvisi_ponteggio(repo, ponteggio: dict[str, Any]) -> list[str]:
    return avvisi(ponteggio, repo.elenco("addetti_ponteggio", ponteggio_id=ponteggio["id"]))


TIPI_ALLEGATO = [
    "Disegno esecutivo",
    "Progetto (calcolo e disegno)",
    "Libretto del fabbricante",
    "Autorizzazione ministeriale",
    "Schema degli ancoraggi",
    "Prove di tenuta degli ancoraggi",
    "Attestati di formazione",
    "Foto",
    "Altro",
]
