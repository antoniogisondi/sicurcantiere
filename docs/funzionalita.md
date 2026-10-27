# SicurCantiere: funzionalità, scelte e prossimi passi

Documento di riferimento del prodotto, da tenere aggiornato a ogni versione. Serve per il sito
di vendita, per le presentazioni ai clienti e per non perdere le decisioni prese. Il dettaglio
tecnico è nel [README](../README.md).

*Ultimo aggiornamento: versione 0.24.0 (PiMUS con disegno del ponteggio in 3D e 2D, squadra con formazione, ancoraggi, carichi, elementi e allegati), ottobre 2026.*

## Lo scopo

SicurCantiere è una suite di programmi per il **consulente della sicurezza**, cioè il
coordinatore, l'RSPP o il tecnico che redige POS, PSC e PiMUS (e in futuro DVR) per conto delle
imprese.

Rispetto agli altri software del settore punta su:
- **meno lavoro per il consulente**: ogni dato si inserisce una volta sola e si ritrova in tutti i
  documenti e in tutti i cantieri;
- **precisione**: controlli di completezza in base alla norma, valutazioni con metodi normati e
  documenti che seguono l'ordine dell'Allegato XV;
- **adattamento al singolo cantiere**: niente documenti generici, perché ogni lavorazione,
  macchina, figura e valutazione è quella del caso reale;
- **leggerezza**: un installatore piccolo, il programma che si aggiorna da solo, file di cantiere
  singoli e portabili.

È scritto da zero a partire dalla normativa e non contiene codice o contenuti di altri software.

## I programmi

| Programma | Per chi | Documenti | File |
| --- | --- | --- | --- |
| **SicurCantiere POS** | Impresa esecutrice o il suo consulente | POS, valutazioni dei rischi specifici, sostanze pericolose, consegna DPI, tesserini, schede dei lavoratori | `.spo` |
| **SicurCantiere PSC** | Coordinatore (CSP/CSE) | PSC, fascicolo dell'opera, notifica preliminare | `.scs` |
| **SicurCantiere PiMUS** | Impresa che monta i ponteggi | PiMUS con verifiche | `.spm` |
| **SicurCantiere DVR** | *in programma* | Documento di valutazione dei rischi aziendale | — |

I programmi condividono gli archivi, il motore dei documenti, l'assistente AI e la licenza. Ogni
programma apre anche i file degli altri: per esempio il POS può partire dal file del PSC.

## Funzionalità

### Dati del cantiere e soggetti
- Dati generali con verifica automatica degli obblighi: PSC e coordinatori (art. 90), notifica
  preliminare (art. 99), picco di lavoratori presenti.
- Committente, responsabile dei lavori (anche coincidente con il committente), CSP, CSE,
  progettisti, direzione lavori, con qualifica, PEC e partita IVA.
- Foto del cantiere nel documento.

### Imprese, figure e lavoratori
- **Anagrafica completa dell'impresa**: posizioni INAIL, INPS e Cassa edile, CCNL, DURC con
  scadenza, DVR, SOA, certificazioni, lavori affidati, impresa affidataria e subappalti, incaricato
  dell'art. 97, logo nel frontespizio.
- **Figure della sicurezza adattate alla realtà dell'impresa**:
  - il datore di lavoro può svolgere di persona i compiti di RSPP, primo soccorso e antincendio
    (art. 34, con avviso oltre 5 lavoratori), direttore tecnico, capocantiere e preposto;
  - le figure che l'impresa non ha (direttore tecnico, capocantiere, medico competente) si
    dichiarano non presenti con il motivo, e il POS lo spiega;
  - una persona può avere più ruoli;
  - i ruoli scritti a mano vengono riconosciuti;
  - preposto obbligatorio (D.L. 146/2021).
- **Maestranze e lavoratori autonomi**:
  - foto, idoneità sanitaria, formazione ricevuta, DPI consegnati scelti da un elenco per parte
    del corpo;
  - mansioni, cioè le lavorazioni svolte e le macchine usate da ciascuno;
  - tesserini di riconoscimento e schede dei lavoratori.
- **Archivio anagrafiche personale**: persone e imprese, con figure e maestranze, si salvano una
  volta e si riprendono in ogni cantiere e in ogni programma.
- **Idoneità e patente** (scheda delle imprese, in PSC e POS):
  - patente a crediti (art. 27): situazione, numero, crediti (minimo 15), data di verifica sul
    portale INL; esenzione per le imprese con SOA dalla III classe;
  - DURC di congruità della manodopera (D.M. 143/2021);
  - documenti dell'Allegato XVII (punto 1 per le imprese, punto 2 per i lavoratori autonomi) con
    esito e note, e verbale di verifica dell'idoneità tecnico-professionale da stampare;
  - controlli che segnalano patente mancante o insufficiente e documentazione incompleta; la
    patente compare anche nelle tabelle delle imprese del PSC e dei subappalti del POS.

### Lavorazioni, rischi e attrezzature
- **Archivio**:
  - 268 fasi di lavoro in 99 lavorazioni e 18 categorie, filtrabili per tipo di intervento;
  - 116 macchine, attrezzi e opere provvisionali con rischi e scheda d'uso (prima, durante e
    dopo l'uso, DPI dell'operatore);
  - lavorazioni personalizzate dall'utente, riutilizzabili negli altri cantieri.
- **Per ogni fase**:
  - descrizione, addetto, modalità organizzative, turni e procedure richieste dal PSC;
  - rischi con probabilità × danno e livello colorato, misure e DPI;
  - rischi dichiarati "non presenti" con la motivazione;
  - vista Struttura con lavoratori, attrezzi, macchine, rischi, misure e DPI.
- **Codici delle fasi automatici**: non si inseriscono a mano. Le fasi dell'archivio tengono il
  loro codice; quelle create da zero prendono la sigla della lavorazione (per esempio ST.xx per le
  strutture), oppure UT.xx finché la lavorazione non viene indicata.
- **Valutazioni specifiche automatiche**: le valutazioni necessarie nascono da sole dai rischi
  delle lavorazioni e delle macchine, e restano "da eseguire" finché non si inseriscono i dati.

### Valutazioni dei rischi specifici con metodi normati
- Sollevamento: NIOSH, compito semplice e composto (UNI ISO 11228-1).
- Traino e spinta: tavole di Snook e Ciriello (UNI ISO 11228-2).
- Trasporto manuale: masse cumulate e tavole (UNI ISO 11228-1).
- Movimenti ripetitivi: indice OCRA (UNI ISO 11228-3).
- Rumore: LEX,8h, picco, valori dell'art. 189 e attenuazione dei protettori (metodo SNR).
- Vibrazioni mano-braccio e corpo intero: A(8), valori dell'art. 201 e tempi d'uso che portano
  al valore d'azione.
- Risultato in tempo reale, misure suggerite in base ai fattori peggiori, relazione Word e
  inclusione automatica nel POS.

### Sostanze pericolose
- Importazione dalla scheda di sicurezza in PDF: frasi H, avvertenza e data della scheda.
- Pittogrammi e categorie di pericolo ricavati dalle frasi H, con le misure.
- Capitolo del POS ed elenco stampabile.

### Coordinamento (PSC)
- Gantt interattivo con colori per impresa, barre trascinabili e scala giorni, settimane o mesi.
- Gantt analitico: uomini-giorno, durata, grafici di affollamento e pericolosità.
- Interferenze tra imprese nella stessa zona, ordinate per gravità, con le prescrizioni del
  coordinatore.
- Costi della sicurezza, fascicolo dell'opera e notifica preliminare.
- **Il PSC è uno per tutto il cantiere**: lo redige il CSP su incarico del committente (art. 90,
  commi 3-4, e art. 91) e riguarda tutte le imprese esecutrici e tutti i lavoratori autonomi, che
  devono attuarlo insieme ai rispettivi POS (art. 100, comma 3). Per questo nel PSC non si sceglie
  mai un'impresa: la pagina Documenti ha solo PSC, fascicolo e notifica. Il verbale di verifica
  dell'idoneità (art. 90, comma 9, e Allegato XVII), che è invece uno per impresa o lavoratore
  autonomo, si genera con «Genera il verbale...» nella scheda «Idoneità e patente» di ciascuna.

### Il documento finale (PSC, fascicolo, notifica)
- **Stessa impaginazione del POS**, nei colori arancioni del programma PSC: copertina con
  committente, firme, logo e dati dello studio del coordinatore, indice, revisioni, capitoli
  numerati con il riferimento di legge.
- **Tutti i contenuti dell'Allegato XV** (punti 2.1.2, 2.1.3, 2.1.4, 2.2, 2.3 e 4), in quattro parti:
  - *l'opera e i soggetti*: dati generali (imprese, lavoratori, uomini-giorno, durata), contesto
    dell'area con foto e mappe, descrizione dell'opera, soggetti con la data di incarico, imprese
    con datori di lavoro e subappalti, **organigramma disegnato automaticamente**, documentazione da
    tenere in cantiere;
  - *area, organizzazione e lavorazioni*: metodo con le scale di probabilità e danno e la matrice
    colorata, area di cantiere nelle tre voci del punto 2.2.1, caratteristiche idrogeologiche,
    **organizzazione del cantiere nelle voci a)-n) del punto 2.2.2**, segnaletica, scelte
    progettuali, lavorazioni con i rischi per fase, **riepilogo per rischio**, schede di macchine
    e attrezzature con la **potenza sonora** (art. 190), **lavori a rischio particolare (Allegato
    XI)** e **valutazione del rischio da ordigni bellici** (art. 91, comma 2-bis);
  - *coordinamento*: interferenze con gravità e prescrizioni, modalità di verifica del CSE,
    **procedure complementari da sviluppare nei POS** (punto 2.1.3), uso comune, cooperazione,
    emergenze con i numeri nazionali e le strutture del territorio;
  - *tempi e costi*: programma dei lavori, **diagramma di Gantt** su pagine orizzontali (barre per
    impresa, zone, interferenze in rosso, affollamento e pericolosità), **costi della sicurezza per
    categoria del punto 4.1.1** con subtotali e prezzario di riferimento.
- **Tavole allegate** (punto 2.1.4): planimetria, tavola degli scavi, profilo altimetrico, come
  immagini o **PDF inseriti pagina per pagina** nel documento.
- Firme del coordinatore, del committente o responsabile dei lavori, del CSE e, per accettazione,
  dei datori di lavoro delle imprese.
- Nella pagina «Relazione del PSC» ogni voce ha la sua guida alla compilazione e la bozza con l'AI;
  i controlli segnalano voci obbligatorie vuote, Allegato XI non verificato, scavi senza valutazione
  degli ordigni, planimetria mancante, costi senza categoria.
- **Dati da completare** come nel POS.
- **Fascicolo dell'opera** con le schede dell'Allegato XVI e **notifica preliminare** con le voci
  dell'Allegato XII, con la stessa grafica e i dati mancanti evidenziati.

### Dal PSC al POS
- **PSC fatto con SicurCantiere PSC**: nella pagina Imprese, «Prepara il POS dell'impresa...» crea il
  file `.spo` dell'impresa. Contiene cantiere, soggetti, l'impresa, le sue lavorazioni con rischi,
  macchine, valutazioni e sostanze, e per ogni fase le interferenze con le altre imprese e le
  prescrizioni del coordinatore. Non serve l'AI.
- **PSC fatto con qualsiasi altro programma** (PDF o Word): in SicurCantiere POS, «Nuovo POS da un
  PSC...».
  - **Lettura**: l'assistente AI legge il PSC una volta sola e trova cantiere, soggetti, imprese,
    fasi con rischi e prescrizioni, interferenze e procedure richieste ai POS.
  - **Scelta**: si spuntano le imprese di cui preparare il POS e, se il PSC non le assegna, le fasi
    che ciascuna svolge.
  - **Risultato**: per ogni impresa nasce un file `.spo` da completare. Le fasi riconosciute
    nell'archivio portano con sé macchine, attrezzi, rischi e misure; le altre riportano i rischi
    del PSC da valutare.
  - **Consumo contenuto**: il testo viene ripulito in locale prima dell'invio (intestazioni,
    numeri di pagina, indice). Prima dell'invio il programma mostra la stima dei token e chiede
    conferma. Per esempio, un PSC di 126 pagine richiede circa 65 mila token in 6 richieste.
  - **Verifiche future**: la lettura del PSC resta salvata nel file del POS, per controllare in
    seguito che il POS risponda a ogni richiesta del PSC.
- In entrambi i casi il POS non si genera subito: prima si completa il file in SicurCantiere POS.

### PiMUS
- Dati del ponteggio, testi base per tutte le sezioni e verifiche prima del montaggio e durante
  l'uso.
- Avviso automatico quando serve il progetto (art. 133), anche quando un solo lato supera i 20 m.
- **Disegno del ponteggio** (scheda «Disegno»): il ponteggio si crea da zero e si modifica con i
  dati. Si inseriscono:
  - la tipologia (telai prefabbricati, tubi e giunti, montanti e traversi, multidirezionale);
  - la forma: lati in sequenza (facciata, a L, a U) oppure perimetro chiuso;
  - per ogni lato la lunghezza, l'altezza se diversa e la mantovana sì/no;
  - campata, larghezza degli impalcati, interpiano e distanza dalla facciata;
  - la maglia degli ancoraggi (ogni N campate e N livelli, a rombo o allineati), la mantovana e i
    teli.

  Lo schema si aggiorna mentre si scrive:
  - vista **3D** che si ruota trascinando, si ingrandisce con la rotellina e si sposta con il tasto
    destro;
  - **pianta**;
  - **prospetto** di ogni lato, dove un clic su un nodo aggiunge o toglie un ancoraggio;
  - **sezione tipo**.

  Disegnato con Qt, senza librerie CAD da installare.
- **Calcoli e quantità** (stime, prevalgono il libretto e il progetto):
  - numero di ancoraggi e m² di facciata per ancoraggio, con avviso oltre i 22 m²;
  - carico sul montante più caricato (peso proprio, più la classe di carico UNI EN 12811-1 su un
    impalcato pieno e su quello adiacente al 50%) e pressione sul terreno, confrontate con la
    portanza; se la pressione supera la portanza, l'avviso indica la ripartizione minima;
  - elenco indicativo degli elementi per tipologia.
- **Squadra di montaggio** con la formazione di ciascuno: corso da 28 ore e aggiornamento ogni 4
  anni (Allegato XXI e Accordo Stato-Regioni del 17/04/2025). Gli avvisi segnalano corso mancante,
  aggiornamento scaduto, preposto o addetti mancanti. I nomi si possono prendere dai lavoratori
  dell'impresa.
- **Allegati** (disegno esecutivo, progetto, libretto, autorizzazione, schema e prove degli
  ancoraggi, attestati, foto): immagini e PDF entrano in coda al documento.
- Documento nella stessa impaginazione di PSC e POS, in verde:
  - copertina con le firme e capitoli dell'Allegato XXII;
  - tabella della squadra con la scadenza della formazione;
  - geometria, elementi, schema degli ancoraggi e verifica dell'appoggio;
  - schema grafico (vista d'insieme, pianta, prospetti, sezione) e allegati;
  - dati mancanti evidenziati ed esiti delle verifiche colorati.

### Documenti brevi
- Verbale di consegna dei DPI, tesserini di riconoscimento (a tessera, con barra colorata e
  linea di taglio), schede dei lavoratori, elenco delle sostanze pericolose e relazione delle
  valutazioni specifiche hanno la grafica del POS (testata con riferimento di legge, schede a
  righe sottili, tabelle colorate, riquadri delle firme). Anche i capitoli sostanze e valutazioni
  dentro il POS usano la stessa grafica.

### Il documento finale (POS)
- **Capitoli nell'ordine dell'Allegato XV 3.2.1**, in tre parti:
  - il cantiere e l'impresa;
  - attività e valutazione dei rischi;
  - misure, protezione ed emergenze.
- **Impaginazione propria**:
  - copertina con dati e firme;
  - capitoli numerati con il riferimento di legge e indice automatico;
  - intestazione con impresa e revisione, "Pagina X di Y";
  - tabelle leggere con l'intestazione ripetuta a ogni pagina e il livello di rischio colorato;
  - lavorazioni e fasi in riquadri.
- **Tutto quello che si compila finisce nel documento**, compresi i testi scritti con l'AI:
  - le voci vuote non stampano righe vuote;
  - le firme finali portano i nomi del datore di lavoro, dell'RSPP, del medico competente e
    dell'RLS o RLST.
- **Contenuti generati in automatico**:
  - cartelli di sicurezza scelti in base ai rischi;
  - icone dei DPI;
  - numeri di emergenza;
  - documenti da tenere in cantiere;
  - allegati riportati solo se pertinenti.
- Tabella delle revisioni, con la data del documento presa dall'ultima revisione.

### Documenti composti: bozza, emissione, consegna (POS e PSC)
- **Il documento resta salvato nel cantiere**, con lo storico delle revisioni. Per ognuna si
  vedono stato, data, descrizione e dati mancanti.
- **Stati**:
  - *bozza*: si ricompone quante volte serve, con la filigrana BOZZA;
  - *emessa*: versione definitiva bloccata; per cambiarla si compone la revisione successiva;
  - *consegnata*: con destinatario e data;
  - *annullata*: resta nello storico ma non vale più.
- **Revisioni automatiche**: ogni composizione scrive la sua riga nella tabella delle revisioni del
  documento (numero, data, motivo).
- **Modifica in Word senza perdere il collegamento**: la bozza si apre in Word, si modifica e si
  riprende nel cantiere; le revisioni emesse si aprono in sola lettura.
- **Capitoli su misura che restano quando si ricompone** (dove gli altri programmi perdono le
  modifiche):
  - togliere un capitolo;
  - aggiungere un testo in fondo al capitolo;
  - sostituirne il contenuto (titolo e riferimento di legge restano);
  - se poi cambiano i dati da cui il capitolo era composto, il programma avvisa di ricontrollare
    il testo scritto a mano.
- **Confronto tra due revisioni**, capitolo per capitolo: capitoli aggiunti, tolti e righe
  cambiate.
- Esportazione in Word della revisione scelta.

### Dati da completare (al posto dei campi tra simboli degli altri programmi)
- Ogni dato mancante è classificato:
  - *obbligatorio per legge* (contenuti minimi dell'Allegato XV);
  - *consigliato*;
  - *facoltativo*: non si stampa, compare solo nell'elenco.
- **Nella bozza**:
  - il dato mancante è evidenziato in giallo con un testo chiaro, per esempio
    "[Da compilare: nominativo RSPP]";
  - un commento di Word accanto dice in quale pagina del programma si compila;
  - prima dell'indice c'è la pagina "Dati da completare" con tutti i mancanti, divisi per livello,
    con capitolo e pagina del programma.
- **Nel programma**: l'elenco "Dati da completare" della bozza; con un doppio clic si va alla
  pagina in cui il dato si compila.
- **All'emissione**:
  - spariscono filigrana, riepilogo ed evidenziazioni;
  - i dati rimasti vuoti diventano righe da compilare a mano;
  - con dati obbligatori mancanti serve una conferma esplicita con il motivo, che resta registrata
    con la revisione.

### Controlli prima della stampa
- Errori e avvisi per ogni pagina, ciascuno con il collegamento alla pagina da correggere. Per
  esempio: DURC o idoneità scaduti, figure obbligatorie mancanti, rischi senza misure,
  valutazioni da eseguire, sostanze senza scheda.

### Assistente AI (incluso nella licenza, spento all'inizio)
- **Incluso nella licenza**: "SicurCantiere AI" funziona senza chiavi API, passando dal server ponte
  dell'ufficio.
  - **Quota mensile per piano**: 1,5 milioni di crediti per i singoli, 3 milioni per il Completo,
    8 milioni per lo Studio.
  - **Limiti**: tetto giornaliero del 30% e ricariche acquistabili.
  - **Motori**: Standard (DeepSeek, oggi su Scaleway in UE) per tutti; Avanzato (Claude) nel piano Studio, a 8 crediti per
    token.
  - **Credito**: si verifica in *Strumenti > Impostazioni assistente AI*.
- **Solo con licenza**: durante la prova gratuita, o con la licenza scaduta, l'assistente non è
  disponibile e i suoi pulsanti non compaiono. Nel programma non ci sono chiavi API: quelle delle
  versioni precedenti vengono cancellate dal PC.
- **Cosa fa**: suggerisce rischi, misure e DPI di fasi, macchine e attrezzature, scrive bozze dei
  testi, compila i parametri delle valutazioni dichiarando le ipotesi e completa le schede delle
  sostanze.
- **Riservatezza**: non invia nomi di persone. Il programma dice dove ciascun fornitore tratta i
  dati.

### Programma
- **Aggiornamento automatico**: il programma avvisa della nuova versione, la installa e si riapre
  da solo.
- **Interfaccia**: tema chiaro e scuro, colore per programma, barra laterale con i problemi di
  ogni pagina, guida rapida (F1).
- **Chiusura con modifiche non salvate**: il programma chiede "Salva / Non salvare / Annulla".
  "Non salvare" riporta il cantiere all'ultimo salvataggio (o all'apertura).
- **Tutto in italiano**, compresi i pulsanti e i menu standard (Sì/No/Annulla, Copia/Incolla).
- **Sicurezza dei dati**: salvataggio automatico a ogni modifica e copie di sicurezza all'apertura.
  I file dei progetti vecchi si aggiornano da soli.
- **Annulla e ripeti** (Ctrl+Z / Ctrl+Y, menu Modifica e barra degli strumenti) su tutto il cantiere:
  annulla anche eliminazioni, importazioni dall'archivio e modifiche nelle tabelle (fino a 40 passi,
  tenuti in memoria finché il cantiere è aperto). Nei campi di testo Ctrl+Z annulla prima la
  scrittura nel campo.
- **Cerca nel cantiere** (Ctrl+F): fasi, rischi, attrezzature, imprese, lavoratori, soggetti, costi
  e testi della relazione; doppio clic per andare alla pagina.
- **Modelli di cantiere**: «File > Salva come modello» conserva il cantiere (senza documenti
  composti e revisioni) come punto di partenza; «Nuovo da un modello» ne crea uno nuovo. I modelli
  stanno nella cartella dei dati del programma, separati per PSC, POS e PiMUS.
- **Anteprima ed esportazione in PDF**: per i documenti composti (pulsante «Anteprima» e «Altro >
  Esporta in PDF») e, dopo la creazione, per tutti gli altri documenti. La conversione usa Word
  (sempre presente negli studi) o LibreOffice.
- **Icone dei programmi**: logo della suite intero con sotto un'etichetta nel colore del programma
  (PSC arancio, POS blu, PiMUS verde); i file dei cantieri e l'installatore hanno il logo semplice.
- **Panoramica al primo avvio** in quattro schermate, da rivedere in «Aiuto > Panoramica del
  programma».
- **Schermi da portatile (1366×768)**: la finestra ci sta sempre; sotto i 1350 pixel la pagina dei
  documenti si dispone in verticale, i moduli vanno su una o due colonne secondo lo spazio e le
  schede lunghe scorrono.
- **Revisione UX/UI (ottobre 2026)**, dalle revisioni di PSC e POS:
  - *elenco e dettaglio*: Soggetti, figure dell'impresa, Costi, Fascicolo, Macchine e Rischi e misure hanno
    un elenco compatto e il pannello di modifica a destra; «Aggiungi» apre il pannello sul primo campo;
  - *Rischi e misure*: filtri «Tutti», «Alti e molto alti», «Da valutare»; DPI come etichette scelte
    dall'elenco per parte del corpo;
  - *Fasi e cronoprogramma (PSC)*: due viste, «Elenco» e «Cronoprogramma»; il Gantt a tutta altezza con
    fase e impresa su due righe, «oggi» nella riga delle date, affollamento nel colore del programma, e il
    dettaglio della fase a destra con i collegamenti a descrizione, rischi, macchine e interferenze;
    importo, manodopera, squadra e zona si modificano nel dettaglio;
  - *Interferenze*: elenco con gravità colorata e stato della prescrizione (da scrivere, generica,
    scritta); la prescrizione si scrive a destra, con «Usa la generica» o l'assistente AI; zona mancante
    segnalata con il collegamento a Fasi;
  - *Documenti e controlli*: in testa lo stato («Il POS non è ancora pronto: 1 errore»), poi l'elenco da
    sistemare con «Vai alla pagina», un solo pulsante «Componi la bozza», lo storico e gli altri
    documenti; nel PSC non si sceglie mai un'impresa (il PSC comprende tutte le imprese e i lavoratori
    autonomi del cantiere: il verbale di idoneità si genera dalla scheda «Idoneità e patente» di
    ciascuna, con «Genera il verbale...»); la notifica è segnata
    «non obbligatoria» quando non serve; l'avvertenza legale compare all'emissione (coordinatore per il
    PSC, datore di lavoro per il POS);
  - *esiti solo con i dati*: «Da determinare» finché mancano imprese e fasi; Costi, Fascicolo e Sostanze
    non sono verdi se vuoti (per Fascicolo e Sostanze c'è la dichiarazione esplicita); avviso con i costi
    a 0,00 €; campi numerici vuoti invece di 0; costo uomo-giorno come suggerimento (250 € tipico);
  - *pagina iniziale*: cantieri recenti in elenco con impresa o committente, stato del documento, dati
    obbligatori mancanti e ricerca; nel POS «Nuovo POS da un PSC» è la prima azione; barra laterale e
    pulsanti nascosti senza cantiere; i tre passi si possono chiudere;
  - *regole comuni*: riga selezionata con barra laterale e grassetto (non si confonde con gli avvisi),
    frecce delle tendine solo sulla riga selezionata, date vuote con «gg/mm/aaaa», celle obbligatorie
    vuote evidenziate («da assegnare»), spazi da riempire «____» evidenziati in giallo e contati negli
    avvisi, numeri della barra laterale spiegati al passaggio del mouse, nome del file in basso con il
    percorso nel suggerimento, «Cantiere senza nome», un solo pulsante pieno per pagina;
  - *altro*: Relazione con «2 di 5» per scheda, «Non pertinente...» con il motivo e riquadri che si
    allungano; costi con totale in alto, subtotali per categoria e prezzari recenti; Macchine con un solo
    «Aggiungi dall'archivio...» con ricerca e le azioni AI in un menu; «Prepara il POS dell'impresa» come
    pulsante principale nelle Imprese del PSC; ruoli obbligatori mancanti aggiungibili con un clic;
    Struttura con il livello e la valutazione in riquadri colorati; anteprima delle immagini nei moduli;
    stato vuoto al centro in Sostanze.
  - *rimandate*: comune con CAP e provincia da elenco ISTAT, correttore ortografico, elenco dei codici
    ATECO, proposta delle schede II del fascicolo dalle lavorazioni, ipotesi dell'AI accanto ai
    parametri delle valutazioni.
- **Testi rivisti** in tutto il programma, nei documenti, nell'archivio e nel gestionale delle
  licenze: tono professionale e uniforme, riferimenti normativi nella forma «art. 90, comma 9»,
  nessun riferimento ad altri software del settore.

## Licenze

- **Codice offline**: il codice `SC1-…` è firmato e il programma lo verifica senza collegarsi a
  internet. Non è legato al PC.
- **Piani**:
  - POS, PSC o PiMUS singoli;
  - Completo (tutti e tre);
  - Studio (tutti e tre, più postazioni).
- **Prova gratuita**: 30 giorni con un solo cantiere. I documenti stampati in prova riportano
  "versione di prova".
- **Alla scadenza** il programma continua a funzionare, ma non riceve più gli aggiornamenti
  pubblicati dopo la scadenza né l'assistenza.
- **Programmi non inclusi** nel piano: compare la pagina "Non incluso nella tua licenza".
- **Codice nascosto**: il codice di licenza è nascosto come una password in *Aiuto > Licenza*, con
  la spunta "Mostra il codice" per controllarlo.
- **Titolare in vista**: il nome compare nella barra del programma, in *Aiuto > Licenza* e in
  piccolo a piè di pagina di ogni documento generato, oltre che nelle proprietà del file. Passare
  il codice ad altri significa stampare documenti con il nome di un altro studio.
- **Gestionale web** sul server dell'ufficio ([licenze/README.md](../licenze/README.md)):
  - clienti, emissione, rinnovo, pagamenti ed esportazione CSV;
  - promemoria delle scadenze a 30, 60 o 90 giorni;
  - email di consegna e di rinnovo pronte;
  - registro dei codici consegnati e dei promemoria inviati;
  - accesso con verifica in due passaggi.

### Licenze per PC (in sviluppo, ottobre 2026)

Decisione di ottobre 2026: le licenze diventano **legate ai PC**, con attivazione online sul server
dell'ufficio (opzione «server proprio», scelta al posto dei servizi esterni come Keygen,
LicenseSpring o Cryptolens, che costerebbero 600-3.600 € l'anno). Il server gira sulla VM del NAS
insieme al ponte AI (stesso indirizzo pubblico con Tailscale Funnel); passerà al server Proxmox
copiando la cartella dei dati.

Fatto (non ancora nei programmi pubblicati):
- **Modulo comune `sicur_license`** (passo 1), usato da tutti i programmi della suite e dal server:
  - *impronta del PC*: codice di Windows, scheda madre e nome del PC, trasformati in hash con un
    sale assegnato dal server per ogni licenza; al server non arriva nessun dato in chiaro. Lo
    stesso PC è riconosciuto se coincidono 2 elementi su 3 (cambio di disco, di nome o
    reinstallazione di Windows non consumano un posto);
  - *certificato firmato* valido 14 giorni e legato al PC, rinnovato in sottofondo a ogni avvio;
    firme a due livelli: la chiave delle licenze (radice, già nota ai programmi) autorizza ogni 6
    mesi una chiave di servizio, con cui il server firma i certificati;
  - *custodia cifrata* con DPAPI di Windows (copiata su un altro PC non si legge) e ultima ora vista,
    contro l'orologio spostato indietro;
  - *sola lettura* invece del blocco: se la licenza non è valida si aprono, si stampano e si
    esportano in PDF i documenti già fatti, sempre con il motivo e cosa fare (non attivato, altro
    PC, orologio, revocata, scaduta, programma non incluso, aggiornamenti finiti, 14 giorni senza
    internet, con avviso 3 giorni prima);
  - *attivazione offline* con file di richiesta e file di attivazione valido 90 giorni.
- **Server delle attivazioni** (passo 2, `licenze/attivazioni.py`), nello stesso servizio pubblico del
  ponte AI e sullo stesso database del gestionale:
  - una licenza per N postazioni si attiva su N PC: **il PC in più rispetto alla licenza** (con 1
    postazione il secondo, con 3 il quarto) è rifiutato con «La licenza è già attiva su N PC su N»,
    l'elenco dei PC (nome e ultimo uso) e la possibilità di liberarne uno; il rifiuto va nel registro;
  - riattivare lo stesso PC non consuma posti;
  - trasferimenti: liberare un PC è sempre possibile, ma in 30 giorni si attivano al massimo N PC nuovi
    più 2; oltre serve l'assistenza;
  - i rinnovi restano la stessa licenza: i PC attivati non vanno riattivati;
  - la licenza annullata nel gestionale si blocca davvero al primo collegamento (sola lettura);
  - limiti contro i tentativi (10 codici sbagliati in un'ora per indirizzo, 30 richieste l'ora per
    licenza), segnalazione delle macchine virtuali copiate, registro conservato un anno, errori
    senza dettagli tecnici;
  - comandi sulla VM: PC attivi di una licenza, file di attivazione offline, nuova chiave di servizio.
- **Gestionale** (passo 3): nella pagina della licenza i PC attivati («2 su 3») con nome, ultimo uso,
  programma e versione; disattivazione di un PC con il motivo; posti in più venduti a parte; «Sblocca i
  trasferimenti»; file di attivazione offline da caricare e scaricare; registro della licenza.
  «Annulla la licenza» la blocca davvero (con «Riattiva»). Nel cruscotto «Da guardare»: licenze con PC
  rifiutati nel mese e PC sospetti di copia; pagina «Attivazioni» con il registro di tutte le licenze.
  Nella scheda del cliente, per ogni licenza, i PC attivati su quelli disponibili.
- **Nei programmi** (passo 4):
  - *attivazione*: in «Aiuto > Licenza...» si incolla il codice e «Attiva la licenza» attiva questo PC sul
    server; con i posti finiti si apre l'elenco dei PC della licenza (nome, attivazione, ultimo uso) con
    «Disattiva» per liberarne uno, e l'attivazione riprova da sola; «PC della licenza...», «Disattiva questo
    PC» e «Attivazione senza internet» (file di richiesta da mandare all'assistenza, file `.sclic` da
    caricare);
  - *chi ha già il codice*: al primo avvio della nuova versione il PC si attiva da solo in sottofondo; senza
    internet il programma funziona 14 giorni con l'avviso nella barra, poi passa in sola lettura;
  - *a ogni avvio* il certificato si rinnova in sottofondo; se la licenza diventa non valida (annullata,
    scaduta, PC liberato da un altro PC...) il cantiere aperto si riapre in sola lettura, e torna
    modificabile appena la licenza è di nuovo valida;
  - *sola lettura*: il cantiere si apre da una copia temporanea (il file del cliente non cambia mai), con
    una fascia in alto che dice il motivo e cosa fare; i campi non sono modificabili, Salva, Genera,
    Annulla e i nuovi cantieri sono disattivati; restano la navigazione, la ricerca, i controlli e, per i
    documenti già composti, «Apri in Word», l'anteprima e l'esportazione in PDF;
  - dopo un rifiuto del server o «Disattiva questo PC» il programma non si riattiva da solo (niente
    tentativi ripetuti nel registro, niente posti spostati avanti e indietro): si riattiva da «Licenza...»;
  - anche la prova gratuita finita e i cantieri oltre il primo durante la prova si aprono in sola lettura,
    invece di essere bloccati;
  - email del gestionale aggiornate: la consegna spiega l'attivazione sul PC e come spostarla, il promemoria
    dice che senza rinnovo il programma passa in sola lettura.
- I codici `SC1-…` già venduti valgono anche con le attivazioni: nessun codice nuovo da mandare.
- **Programma compilato e controlli di sicurezza** (passo 6): il programma si compila con Nuitka (codice C,
  niente sorgente Python nell'eseguibile); i tre programmi sono copie dello stesso eseguibile in un'unica
  cartella (installazione più piccola, una sola copia di Qt; l'aggiornamento toglie le cartelle PSC, POS e
  PiMUS delle versioni precedenti). A ogni build: analisi del codice (bandit), librerie con falle note
  (pip-audit), SBOM CycloneDX allegato alla versione pubblicata, librerie installate solo alle versioni
  esatte con impronta (`requisiti/`). L'installatore si prova anche sopra l'ultima versione pubblicata.
- **Assistente AI con il certificato del PC** (passo 5): il programma manda il certificato e le impronte del
  PC; il server accetta solo PC attivi sulla licenza e certificati non copiati. Il solo codice vale finché
  la licenza non ha PC attivati (clienti con la versione precedente), poi non basta più; in sola lettura
  l'assistente non è disponibile.
- **Aggiornamenti firmati** (passo 5): ogni versione pubblicata ha la firma (versione, dimensione, SHA-256)
  fatta con la chiave degli aggiornamenti, segreta su GitHub; il programma verifica firma e file prima di
  installare e scarta un installatore modificato o una firma di un'altra versione. Si attiva creando la
  chiave sulla VM (`python -m licenze chiave-aggiornamenti`), mettendo la segreta su GitHub e la pubblica nel
  programma (vedi licenze/README.md).

Regole scelte (modificabili): abbonamento scaduto → sola lettura; licenza perpetua → funzionano le
versioni uscite entro la fine degli aggiornamenti inclusi, le successive si aprono in sola lettura.

## Decisioni prese

- Fino alla versione 0.22: licenze offline, senza vincolo al PC; alla scadenza il programma continua a
  funzionare. Da ottobre 2026 (in sviluppo): licenze legate ai PC con attivazione online sul server
  proprio, sola lettura quando la licenza non è valida, mai blocco dei dati.
- La chiave privata delle licenze resta solo sul server; nel programma c'è la chiave pubblica.
- AI spenta finché il cliente non la attiva con la sua chiave; nessun nome di persona viene inviato.
- Si pubblica una nuova versione solo quando lo decide il titolare.
- Grafica dei documenti propria, diversa da quella degli altri software del settore.

## Prossimi passi

1. **Licenze per PC, passi successivi** (fatti i passi 1-6, vedi sopra):
   - da decidere: codici nuovi casuali al posto di `SC1-…` per le licenze nuove; prova gratuita legata al PC
     sul server (oggi riparte reinstallando il programma);
   - passo 7: checklist GDPR (informativa, registro dei trattamenti, backup cifrati con password) e Cyber
     Resilience Act (segnalazione delle vulnerabilità sfruttate già obbligatoria dall'11 settembre 2026,
     requisiti completi dall'11 dicembre 2027);
   - ultimo passo prima del rilascio ufficiale (deciso a ottobre 2026): firma del programma con un
     certificato di firma del codice (OV, circa 120 €/anno, o Azure Artifact Signing).
1. **Server ponte AI**: da ottobre 2026 il motore Standard è DeepSeek V4.1 Flash su **Scaleway**
   (Parigi, dati trattati nell'UE). Il programma mostra ai clienti la sede comunicata dal server (riga
   SEDE di `ai.env`), quindi cambiando fornitore non serve una nuova versione. All'arrivo dei primi
   clienti si valuta se restare o passare a:
   - AI in locale (Ollama o vLLM su un server con GPU da circa 24 GB): i dati non escono dal server;
   - modello aperto su un server con GPU noleggiato in Europa;
   - DeepSeek V4 Pro presso un altro fornitore UE (più preciso di Flash), oppure Mistral.
   In tutti i casi basta cambiare indirizzo, modello, chiave e sede in `ai.env`, senza toccare il
   programma. Prima di passare, provare su uno o due PSC veri quante imprese e fasi trova e quanto
   tempo impiega rispetto a DeepSeek.
2. **Sito di vendita**: presentazione, prezzi, acquisto della licenza e download.
3. **SicurCantiere DVR.**
3. **SicurCantiere Formazione** (quarto programma della suite, idea approvata da sviluppare):
   - stesso archivio di aziende e lavoratori degli altri programmi;
   - struttura clienti → aziende → lavoratori → attestati;
   - corsi richiesti per ogni mansione, con chi è scoperto o in scadenza;
   - scadenzario con le scadenze già impostate per i corsi più comuni (lavoratori, preposto,
     antincendio, primo soccorso, attrezzature, ponteggi), da ricontrollare sul nuovo Accordo
     Stato-Regioni del 2025;
   - email di promemoria ai clienti con l'elenco di chi scade;
   - calendario dei corsi, registro presenze, test di verifica, attestati numerati;
   - lettura degli attestati in PDF con l'AI (corso, data, ore);
   - collegamento al POS: formazione dei lavoratori stampata in automatico e avviso se un corso è
     scaduto nelle date del cantiere.
3. **Documenti composti, prossimi passi**: allegati in PDF uniti in coda con la numerazione,
   composizione salvata anche per il PiMUS.
3. **Strumenti del CSE durante i lavori**: verbali di sopralluogo e di riunione di coordinamento,
   verifica dei POS ricevuti (art. 92), registro delle prescrizioni e delle sospensioni, avviso ai condomini o ai terzi.
4. **Idee per distinguersi**, da scegliere:
   - verifica automatica, punto per punto, che il POS risponda alle richieste del PSC letto (la
     lettura è già salvata nel file);
   - verifica dei POS ricevuti da parte del coordinatore (art. 92), con il verbale di verifica;
   - più documenti dagli stessi dati: nomine, richiesta della documentazione dell'Allegato XVII,
     verbali di coordinamento, informativa ai lavoratori;
   - scadenzario di tutti i cantieri (DURC, idoneità, formazione, verifiche) con le email di
     sollecito;
   - modelli di cantiere tipo che si arricchiscono con l'uso;
   - sopralluogo dal telefono con il verbale;
   - importazione dei vecchi documenti per chi arriva da altri programmi;
   - assistente AI che cita l'articolo di legge di ogni suggerimento.
