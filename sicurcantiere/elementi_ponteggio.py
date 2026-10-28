"""Catalogo degli elementi del ponteggio: quelli che compongono la struttura (calcolati dalla geometria) e
quelli che si inseriscono a mano sul disegno (mensole, travi carraie, teli, mantovane, scale, piazzole di
carico, integrazioni in tubi e giunti...).

Ogni elemento inserito è un dizionario salvato nella geometria del ponteggio:
    {"tipo", "tratto", "da", "a", "livello", "livello_a", "quantita", "posizione", "note"}
con le campate (da/a, contate da 0) e gli impalcati (livello/livello_a, contati da 1) che occupa; per gli
elementi a terra il livello è 0. «quantita» = 0 vuol dire calcolata dall'estensione; «posizione» è il punto
lungo la campata (da 0 a 1) degli elementi che non stanno su una stilata, come l'ancoraggio su tubo.

I nomi sono quelli d'uso comune nei cataloghi e nei libretti; le denominazioni esatte, le portate e le
condizioni d'impiego sono quelle del libretto del fabbricante del ponteggio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Voce:
    chiave: str
    nome: str
    categoria: str
    unita: str = "n."
    per: str = "campata"        # campata | stilata | pezzo | metro
    a_terra: bool = False       # si appoggia al terreno (livello 0)
    descrizione: str = ""
    avviso: str = ""            # obbligo o attenzione da riportare nel PiMUS quando l'elemento è presente


CATEGORIE = ["Struttura", "Ancoraggi", "Impalcati e parapetti", "Mensole e varchi", "Accessi",
             "Protezioni e schermature", "Sollevamento dei materiali", "Integrazioni", "Piccoli elementi",
             "Impianti e segnalazioni"]

CATALOGO: list[Voce] = [
    # struttura
    Voce("diagonale_facciata", "Diagonale di facciata aggiuntiva", "Struttura",
         descrizione="Controventatura sul piano dei montanti esterni, oltre a quelle dello schema"),
    Voce("diagonale_pianta", "Diagonale in pianta", "Struttura",
         descrizione="Controventatura orizzontale sotto l'impalcato, dove la richiede il libretto"),
    # ancoraggi fuori dallo schema
    Voce("ancoraggio_tubo", "Ancoraggio su tubo e giunto", "Ancoraggi", per="pezzo",
         descrizione="Tubo fissato con due giunti ortogonali tra le stilate (o tra i montanti del telaio) e "
                     "ancoraggio sul tubo, dove sul montante non c'è spazio o il punto di fissaggio è altrove",
         avviso="Ancoraggi su tubo e giunto: il tubo va collegato ai montanti con giunti ortogonali autorizzati e "
                "l'ancoraggio deve trasmettere lo sforzo previsto dal libretto; la disposizione va riportata nel "
                "disegno esecutivo."),
    Voce("ancoraggio_puntone", "Puntone di contrasto (sbadacchio) verso la facciata", "Ancoraggi", per="pezzo",
         descrizione="Tubo di contrasto contro la muratura, abbinato all'ancoraggio a trazione"),
    Voce("ancoraggio_doppio", "Ancoraggio a V (doppio, contro lo scorrimento laterale)", "Ancoraggi", per="pezzo"),
    Voce("telaio_passo_pedonale", "Telaio di partenza per passaggio pedonale", "Mensole e varchi", a_terra=True,
         descrizione="Telaio più largo alla base che lascia libero il marciapiede"),
    Voce("trave_carraia", "Trave per passo carraio", "Mensole e varchi", per="pezzo", a_terra=True,
         descrizione="Trave reticolare che sostiene le stilate interrotte alla base per lasciare un varco",
         avviso="Il varco con trave carraia va realizzato secondo lo schema del libretto; in caso contrario serve "
                "il progetto (art. 133)."),
    Voce("partenza_bocca_lupo", "Partenza su bocca di lupo, griglia o intercapedine", "Mensole e varchi",
         a_terra=True,
         descrizione="Traverso o trave di appoggio che scavalca la bocca di lupo e porta le basette su un appoggio "
                     "portante",
         avviso="Partenza su bocca di lupo o griglia: le basette appoggiano su travi o traversi verificati, mai sulla "
                "griglia; la soluzione va illustrata nel piano."),
    Voce("mensola_interna", "Mensola interna (allargamento verso la facciata)", "Mensole e varchi", per="stilata",
         descrizione="Riduce la distanza dalla facciata dove l'opera è rientrata (balconi, cornicioni)"),
    Voce("mensola_esterna", "Mensola esterna (sbalzo)", "Mensole e varchi", per="stilata",
         descrizione="Allarga l'impalcato verso l'esterno; con il puntone se previsto dal libretto"),
    Voce("disassamento", "Mensola per disassamento di stilata", "Mensole e varchi", per="stilata",
         descrizione="Sposta la stilata per superare un ostacolo (pensilina, aggetto)"),
    # impalcati e parapetti
    Voce("botola", "Impalcato con botola", "Impalcati e parapetti",
         descrizione="Piano di calpestio con botola apribile per il passaggio tra i livelli"),
    Voce("parapetto_interno", "Parapetto sul lato facciata", "Impalcati e parapetti",
         descrizione="Obbligatorio dove la distanza dalla facciata supera 20 cm (art. 138)"),
    Voce("parapetto_sommita", "Parapetto di sommità / protezione di gronda", "Impalcati e parapetti",
         descrizione="Montanti prolungati oltre la linea di gronda per la protezione dei lavori in copertura"),
    Voce("tavolato_legno", "Tavolato in legno", "Impalcati e parapetti",
         descrizione="Tavole accostate su traversi; spessore e appoggi secondo l'Allegato XVIII"),
    # accessi
    Voce("scala_interna", "Scala interna con botola", "Accessi",
         descrizione="Scala a rampa tra due impalcati, con botola richiudibile"),
    Voce("torre_scala", "Torre scala esterna", "Accessi", per="pezzo", a_terra=True,
         descrizione="Torre con rampe e pianerottoli affiancata al ponteggio"),
    # protezioni
    Voce("mantovana", "Mantovana parasassi", "Protezioni e schermature",
         descrizione="Intercetta la caduta di materiali verso le zone di passaggio"),
    Voce("telo", "Telo o rete di schermatura", "Protezioni e schermature", unita="m²",
         descrizione="Rete antipolvere o telo di facciata",
         avviso="Con teli, reti o graticci sulla facciata serve il calcolo per l'azione del vento e gli ancoraggi "
                "relativi (Allegato XIX)."),
    Voce("tabellone", "Tabellone pubblicitario", "Protezioni e schermature", unita="m²",
         avviso="Con tabelloni pubblicitari serve il calcolo per l'azione del vento (Allegato XIX)."),
    Voce("tunnel", "Passaggio pedonale protetto (tunnel)", "Protezioni e schermature", a_terra=True,
         descrizione="Copertura del percorso pedonale sotto il ponteggio"),
    Voce("protezione_varco", "Protezione del varco (parasassi sopra l'ingresso)", "Protezioni e schermature",
         a_terra=True),
    # sollevamento
    Voce("piazzola_carico", "Piazzola di carico", "Sollevamento dei materiali", per="pezzo",
         descrizione="Piano a sbalzo per il ricevimento dei materiali, con parapetto e cancelletto",
         avviso="La piazzola di carico va calcolata o realizzata secondo lo schema del libretto, con il carico "
                "ammesso esposto."),
    Voce("argano", "Argano a bandiera o carrucola", "Sollevamento dei materiali", per="pezzo",
         descrizione="Fissato ai montanti secondo le istruzioni del fabbricante; montanti raddoppiati e ancorati",
         avviso="Argano fissato al ponteggio: montanti di sostegno rinforzati e ancorati, secondo il libretto "
                "dell'argano e del ponteggio."),
    Voce("castello_carico", "Castello di carico (torre per il ricevimento dei materiali)", "Sollevamento dei materiali",
         per="pezzo", a_terra=True,
         descrizione="Torre costruita con elementi di ponteggio, affiancata, con piani di ricevimento e parapetti",
         avviso="Il castello di carico è costruito con elementi di ponteggio e rientra nel PiMUS: schema del libretto "
                "o progetto, carico ammesso esposto su ogni piano, ancoraggi propri."),
    Voce("montacarichi", "Montacarichi da cantiere", "Sollevamento dei materiali", per="pezzo", a_terra=True,
         descrizione="Elevatore affiancato al ponteggio, con il proprio libretto e i cancelli ai piani"),
    # integrazioni
    Voce("tubi_giunti", "Integrazione in tubi e giunti", "Integrazioni",
         descrizione="Raccordi, rinforzi o tratti in tubi e giunti dove la geometria non consente l'uso degli "
                     "elementi prefabbricati (strettoie, angoli, ostacoli)",
         avviso="Le integrazioni in tubi e giunti vanno realizzate con elementi autorizzati dello stesso "
                "fabbricante e secondo gli schemi del libretto; in caso contrario serve il progetto (art. 133)."),
    Voce("rinforzo_montante", "Rinforzo di montante (montante raddoppiato)", "Integrazioni", per="stilata"),
    # piccoli elementi (si contano a pezzi dove si aggiungono a quelli della struttura)
    Voce("giunto_ortogonale", "Giunto ortogonale", "Piccoli elementi", per="pezzo"),
    Voce("giunto_girevole", "Giunto girevole", "Piccoli elementi", per="pezzo"),
    Voce("giunto_testa", "Giunto di testa (manicotto)", "Piccoli elementi", per="pezzo"),
    Voce("tubo", "Tubo singolo", "Piccoli elementi", unita="m", per="pezzo"),
    Voce("spinotto", "Spinotto di collegamento", "Piccoli elementi", per="pezzo"),
    Voce("prolunga_basetta", "Basetta con prolunga (dislivelli)", "Piccoli elementi", per="pezzo", a_terra=True),
    Voce("basetta_snodata", "Basetta snodata (piani inclinati)", "Piccoli elementi", per="pezzo", a_terra=True),
    Voce("tavola_ripartizione", "Tavola o piastra di ripartizione sotto la basetta", "Piccoli elementi", per="pezzo",
         a_terra=True),
    Voce("corrente_aggiuntivo", "Corrente aggiuntivo", "Piccoli elementi"),
    Voce("fermapiede_aggiuntivo", "Tavola fermapiede aggiuntiva", "Piccoli elementi"),
    Voce("parapetto_testata", "Parapetto di testata aggiuntivo", "Piccoli elementi", per="pezzo"),
    # impianti
    Voce("messa_terra", "Dispersore di messa a terra", "Impianti e segnalazioni", per="pezzo", a_terra=True,
         descrizione="Collegamento contro le scariche atmosferiche, se il ponteggio non è autoprotetto"),
    Voce("segnalazione", "Luce di segnalazione notturna", "Impianti e segnalazioni", per="pezzo", a_terra=True),
    Voce("cartello", "Cartello con il carico ammesso", "Impianti e segnalazioni", per="pezzo", a_terra=True),
]

PER_CHIAVE = {v.chiave: v for v in CATALOGO}

# Tipi di ancoraggio alla costruzione.
TIPI_ANCORAGGIO = [
    "Tassello ad anello (golfare) e tubo con giunto",
    "Ancoraggio a cravatta attorno a pilastri o travi",
    "Ancoraggio a vitone nei vani delle finestre",
    "Piastra tassellata",
    "Tubo passante con puntone",
    "Ancoraggio a uncino",
]


def voce(chiave: str) -> Voce | None:
    return PER_CHIAVE.get(chiave)


def normalizza(e: dict[str, Any]) -> dict[str, Any] | None:
    """Elemento inserito con i valori ammessi; None se il tipo non è a catalogo."""
    v = voce(str(e.get("tipo", "")))
    if v is None:
        return None

    def intero(chiave: str, minimo: int) -> int:
        try:
            return max(minimo, int(e.get(chiave) or 0))
        except (TypeError, ValueError):
            return minimo

    da, a = intero("da", 0), intero("a", 0)
    livello_min = 0 if v.a_terra else 1
    livello, livello_a = intero("livello", livello_min), intero("livello_a", 0)
    try:
        quantita = max(0.0, float(e.get("quantita") or 0))
    except (TypeError, ValueError):
        quantita = 0.0
    try:
        posizione = min(1.0, max(0.0, float(e.get("posizione", 0.5))))
    except (TypeError, ValueError):
        posizione = 0.5
    return {"tipo": v.chiave, "tratto": intero("tratto", 0), "da": min(da, a) if a else da, "a": max(da, a),
            "livello": livello, "livello_a": max(livello, livello_a), "quantita": quantita,
            "posizione": posizione, "note": str(e.get("note") or "")}


def quantita(e: dict[str, Any], campata: float = 1.8, interpiano: float = 2.0) -> float:
    """Quantità dell'elemento: quella scritta o quella che deriva dalle campate e dai livelli occupati."""
    if e.get("quantita"):
        return float(e["quantita"])
    v = voce(e["tipo"])
    campate = e["a"] - e["da"] + 1
    livelli = e["livello_a"] - e["livello"] + 1
    if v is None or (v.per == "pezzo" and v.unita != "m"):
        return campate * livelli if v and v.chiave.startswith("ancoraggio_") else 1
    if v.unita == "m":
        return round(campate * campata, 1)
    if v.unita == "m²":
        return round(campate * campata * livelli * interpiano, 1)
    if v.per == "stilata":
        return (campate + 1) * livelli
    return campate * livelli


def descrizione(e: dict[str, Any], nome_tratto: str = "") -> str:
    """Posizione leggibile: «Nord, campate 3-5, impalcati 2-4»."""
    parti = [nome_tratto] if nome_tratto else []
    parti.append(f"campata {e['da'] + 1}" if e["da"] == e["a"] else f"campate {e['da'] + 1}-{e['a'] + 1}")
    if e["livello"] == 0 and e["livello_a"] == 0:
        parti.append("a terra")
    elif e["livello"] == e["livello_a"]:
        parti.append(f"impalcato {e['livello']}")
    else:
        parti.append(f"impalcati {e['livello']}-{e['livello_a']}")
    return ", ".join(parti)
