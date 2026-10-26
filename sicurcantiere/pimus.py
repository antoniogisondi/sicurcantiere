"""Contenuti del Piano di Montaggio, Uso e Smontaggio dei ponteggi (art. 136 e Allegato XXII).

I testi base sono una traccia scritta per SicurCantiere: vanno adattati al
ponteggio specifico e al libretto del fabbricante.
"""

from __future__ import annotations

from typing import Any

TIPI_PONTEGGIO = [
    "Telai prefabbricati",
    "Tubi e giunti",
    "Montanti e traversi prefabbricati",
    "Multidirezionale",
]

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
    ("ancoraggi", "Tipo e modalità di realizzazione degli ancoraggi",
     "Gli ancoraggi alla costruzione sono realizzati secondo lo schema del libretto, in numero e "
     "posizione non inferiori a quelli previsti, con [tasselli / anelli / tubi a cravatta]. Ogni "
     "ancoraggio viene posato man mano che si sale e prima di caricare l'impalcato superiore; i "
     "tasselli sono di tipo idoneo al supporto e verificati a trazione a campione."),
    ("meteo", "Misure in caso di condizioni meteorologiche avverse",
     "Il montaggio, la trasformazione e lo smontaggio sono sospesi con vento forte, pioggia intensa, "
     "neve, ghiaccio o scarsa visibilità. Prima della ripresa il preposto verifica il ponteggio, "
     "con particolare attenzione ad ancoraggi, appoggi e teli o reti eventualmente applicati."),
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

# Voci di verifica (momento, descrizione), in linea con gli argomenti dell'Allegato XIX.
VERIFICHE: list[tuple[str, str]] = [
    ("Prima del montaggio", "Presenza della copia dell'autorizzazione ministeriale e del libretto del fabbricante"),
    ("Prima del montaggio", "Marchio del fabbricante leggibile sugli elementi"),
    ("Prima del montaggio", "Telai, montanti e traversi privi di deformazioni, corrosioni o saldature non originali"),
    ("Prima del montaggio", "Correnti e diagonali integri, con dispositivi di collegamento funzionanti"),
    ("Prima del montaggio", "Basette regolabili con vite e piastra integre"),
    ("Prima del montaggio", "Giunti e spinotti efficienti, senza deformazioni o filettature danneggiate"),
    ("Prima del montaggio", "Impalcati metallici o tavole senza deformazioni, rotture o nodi passanti"),
    ("Prima del montaggio", "Piano di appoggio verificato e tavole di ripartizione predisposte"),
    ("Durante l'uso", "Ancoraggi presenti nel numero e nelle posizioni previste e ben serrati"),
    ("Durante l'uso", "Verticalità dei montanti e assenza di cedimenti degli appoggi"),
    ("Durante l'uso", "Parapetti, correnti intermedi e tavole fermapiede completi su tutti i lati aperti"),
    ("Durante l'uso", "Impalcati completi e fissati, senza vuoti tra tavola e tavola"),
    ("Durante l'uso", "Distanza dalla facciata non superiore a 20 cm o parapetto interno"),
    ("Durante l'uso", "Mantovana parasassi presente dove richiesta"),
    ("Durante l'uso", "Scale di accesso interne e botole funzionanti"),
    ("Durante l'uso", "Carichi sugli impalcati entro i limiti della classe del ponteggio"),
    ("Durante l'uso", "Verifica dopo eventi meteorologici avversi o lunghe interruzioni"),
    ("Durante l'uso", "Messa a terra contro le scariche atmosferiche, se necessaria"),
]

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
    if addetti:
        messaggi += P.avvisi_squadra(addetti)
    elif not str(ponteggio.get("preposto", "")).strip():
        messaggi.append("Indicare il preposto alle operazioni di montaggio e smontaggio (art. 136, comma 6).")
    if not ponteggio.get("impresa_id"):
        messaggi.append("Indicare l'impresa che esegue il montaggio.")
    if "geometria" in ponteggio:
        messaggi += P.avvisi_geometria(ponteggio)
    return messaggi


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
