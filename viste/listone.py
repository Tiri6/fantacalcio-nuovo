"""Listone giocatori: l'unica tabella dei giocatori, e da dove arriva.

Qui c'e' tutto quel che si sa di un calciatore — ruoli, nazionalita', eta',
stipendio, e la squadra della lega che lo possiede — e da qui lo si aggiorna.

Era diviso in due pagine, «Lista giocatori» e questa: dicevano quasi le
stesse cose in due posti, e chi cercava un giocatore doveva indovinare quale
delle due guardare.
"""

import pandas as pd
import streamlit as st

from fantacalcio import fonti_web, schermate, tema, ui
from fantacalcio.data import archivio
from fantacalcio.regole import ETICHETTE_RUOLO

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()

stagione = fonti_web.stagione()
ui.intestazione(
    "Listone giocatori",
    "📋",
    f"Serie A {fonti_web.etichetta_stagione(stagione)}: ruoli Mantra, "
    "nazionalita' e stipendi lordi in un file solo.",
)

giocatori = ui.listone()

# --- l'aggiornamento --------------------------------------------------------
#
# Il risultato dell'ultimo aggiornamento resta a schermo finche' non si cambia
# pagina: dice quante righe sono arrivate da dove, ed e' l'unico modo per
# accorgersi che una delle due fonti ha cambiato formato.

CHIAVE_ESITO = "_listone_esito"


def _salva(esito) -> None:
    """Scrive in archivio quel che l'aggiornamento ha prodotto, e lo racconta."""
    if not esito.riuscito:
        st.session_state[CHIAVE_ESITO] = ("giu", None, esito)
        return
    try:
        conteggio = fonti_web.applica(archivio(), esito.righe)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.session_state[CHIAVE_ESITO] = ("errore", str(errore), esito)
        return
    ui.invalida_dati()
    st.session_state[CHIAVE_ESITO] = ("ok", conteggio, esito)
    st.rerun()


if utente.puo_importare:
    dal_web, dal_file = st.tabs(["🌐 Dal web", "📁 Dai file scaricati a mano"])

    with dal_web:
        riga = st.columns([2, 1])
        with riga[0]:
            st.markdown(
                tema.scheda(
                    "Da dove arriva",
                    "Il listone ufficiale di Fantacalcio.it per nomi, squadre "
                    "e ruoli Mantra; Capology per gli stipendi lordi e le "
                    "nazionalita' (art. 4). Il pulsante scarica le due fonti e "
                    "le mette insieme.",
                    icona="🌐",
                ),
                unsafe_allow_html=True,
            )
        with riga[1]:
            aggiorna = st.button(
                "🔄 Aggiorna listone",
                type="primary",
                use_container_width=True,
                help="Scarica dal web e riscrive il catalogo. Le rose non si "
                "toccano: i contratti restano dove sono.",
            )
            if st.button("↩︎ Nascondi il rapporto", use_container_width=True):
                st.session_state.pop(CHIAVE_ESITO, None)

        with st.expander("Indirizzi alternativi"):
            st.caption(
                "Se una delle due fonti risponde 403 o cambia posto, qui si "
                "punta altrove senza aspettare una modifica al codice. "
                "Vuoti = gli indirizzi soliti."
            )
            alt_listone = st.text_input(
                "Indirizzo del listone (.xlsx)",
                placeholder=fonti_web.url_quotazioni(stagione),
                key="_alt_listone",
            )
            alt_stipendi = st.text_input(
                "Indirizzo degli stipendi",
                placeholder=fonti_web.url_capology(stagione),
                key="_alt_stipendi",
            )

        if aggiorna:
            with st.spinner("Scarico il listone e gli stipendi…"):
                _salva(
                    fonti_web.aggiorna_da_web(
                        ingaggi_correnti=ui.ingaggi_noti(),
                        url_listone=alt_listone,
                        url_stipendi=alt_stipendi,
                    )
                )

    # Il browser, sulle stesse pagine, entra sempre: ha i cookie e una
    # provenienza. Un server no, e contro un CDN che lo rifiuta non c'e'
    # niente da fare dal nostro lato. Questa via non passa dalla rete.
    with dal_file:
        st.caption(
            "Scarica i due file dal tuo browser e caricali qui: e' la via che "
            "funziona sempre, anche quando il sito viene rifiutato dal CDN."
        )
        file_listone = st.file_uploader(
            "Listone: l'.xlsx ufficiale, oppure un .csv con tutto dentro",
            type=["xlsx", "csv"],
            key="_file_listone",
            help=f"L'xlsx si scarica da {fonti_web.url_quotazioni(stagione)}. "
            "Il CSV lo prepari tu: le colonne sono elencate qui sotto.",
        )
        file_stipendi = st.file_uploader(
            "Stipendi (.csv, facoltativo)",
            type=["csv", "txt"],
            key="_file_stipendi",
            help="Colonne riconosciute dal nome: giocatore, squadra, lordo, "
            "nazionalita, nascita. Senza questo file gli ingaggi restano "
            "quelli che sono gia' in archivio.",
        )

        # Capology non offre l'esportazione, ma la tabella si seleziona e si
        # copia: incollata qui arriva separata da tabulazioni, e va bene
        # uguale. E' la strada piu' corta fra una pagina web e il sito.
        incollati = st.text_area(
            "…oppure incolla qui la tabella degli stipendi",
            height=140,
            key="_incolla_stipendi",
            placeholder=(
                "Seleziona la tabella nel browser, Ctrl+C, e incolla qui.\n"
                "Giocatore\tSquadra\tLordo annuale\n"
                "Paulo Dybala\tRoma\t€ 6.000.000"
            ),
            help="Accetta il copia-incolla da una pagina (colonne separate da "
            "tabulazione), il CSV di un foglio di calcolo, o l'HTML della "
            "tabella. La prima riga deve essere l'intestazione.",
        )
        modelli = st.columns(2)
        modelli[0].download_button(
            "⬇️ Modello del listone in CSV",
            fonti_web.MODELLO_CSV_LISTONE.encode("utf-8"),
            file_name="listone.csv",
            mime="text/csv",
            use_container_width=True,
        )
        modelli[1].download_button(
            "⬇️ Modello del file stipendi",
            fonti_web.MODELLO_CSV_STIPENDI.encode("utf-8"),
            file_name="stipendi.csv",
            mime="text/csv",
            use_container_width=True,
        )

        with st.expander("Che colonne deve avere il CSV del listone"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Colonna": "id giocatore",
                            "Obbligatoria": True,
                            "Esempio": "2071",
                            "Nota": "L'id del listone ufficiale. E' quel che "
                            "tiene insieme le rose: i contratti puntano "
                            "all'id, non al nome.",
                        },
                        {
                            "Colonna": "nome giocatore",
                            "Obbligatoria": True,
                            "Esempio": "Paulo",
                            "Nota": "Basta anche solo il cognome.",
                        },
                        {
                            "Colonna": "cognome giocatore",
                            "Obbligatoria": False,
                            "Esempio": "Dybala",
                            "Nota": "Se c'e', viene unito al nome.",
                        },
                        {
                            "Colonna": "squadra di provenienza",
                            "Obbligatoria": False,
                            "Esempio": "Roma",
                            "Nota": "La squadra di Serie A.",
                        },
                        {
                            "Colonna": "ruolo classic",
                            "Obbligatoria": False,
                            "Esempio": "A",
                            "Nota": "P, D, C o A. Non si ricava dal Mantra: "
                            "un esterno «E» in Classic puo' essere D o C.",
                        },
                        {
                            "Colonna": "ruolo mantra",
                            "Obbligatoria": True,
                            "Esempio": "A/Pc",
                            "Nota": "Piu' ruoli separati da / o da ;",
                        },
                        {
                            "Colonna": "data di nascita",
                            "Obbligatoria": False,
                            "Esempio": "15/11/1993",
                            "Nota": "gg/mm/aaaa o aaaa-mm-gg. Senza, l'Under "
                            "21 non si puo' determinare.",
                        },
                        {
                            "Colonna": "nazionalita",
                            "Obbligatoria": False,
                            "Esempio": "Argentina",
                            "Nota": "Serve al minimo italiani in rosa.",
                        },
                        {
                            "Colonna": "stipendio lordo",
                            "Obbligatoria": False,
                            "Esempio": "6000000",
                            "Nota": "In euro, fonte Capology (art. 4). Se "
                            "manca resta quello gia' in archivio.",
                        },
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                column_config={"Obbligatoria": st.column_config.CheckboxColumn("Obbl.")},
            )
            st.caption(
                "L'ordine delle colonne non conta: si riconoscono dal nome. "
                "Separatore punto e virgola o virgola, come esce da Excel."
            )

        if st.button(
            "📥 Consolida e salva",
            type="primary",
            disabled=file_listone is None,
            use_container_width=True,
        ):
            with st.spinner("Leggo i file e li metto insieme…"):
                _salva(
                    fonti_web.aggiorna_da_file(
                        file_listone.getvalue(),
                        stipendi_csv=(
                            file_stipendi.getvalue()
                            if file_stipendi
                            else (incollati.strip() or None)
                        ),
                        ingaggi_correnti=ui.ingaggi_noti(),
                    )
                )

memoria = st.session_state.get(CHIAVE_ESITO)
if memoria:
    stato, dettaglio, esito = memoria
    if stato == "ok":
        st.success(
            f"{dettaglio['totali']} giocatori nel listone "
            f"({dettaglio['nuovi']} nuovi), "
            f"{dettaglio['con_stipendio']} con lo stipendio.",
            icon="✅",
        )
    elif stato == "errore":
        st.error(f"Scaricato, ma non salvato: {dettaglio}", icon="⛔")
    else:
        st.error(
            "Il listone non e' arrivato: il catalogo e' rimasto quello di "
            "prima. Sotto c'e' il dettaglio, e piu' in basso il modo manuale.",
            icon="🚧",
        )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Fonte": f.nome,
                    "Esito": "✅" if f.ok else "⛔",
                    "Dettaglio": f.dettaglio,
                    "Indirizzo": f.url,
                }
                for f in esito.fonti
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    if esito.senza_stipendio:
        with st.expander(f"{len(esito.senza_stipendio)} giocatori senza stipendio"):
            st.caption(
                "Capology li scrive con un nome che non ho saputo abbinare, "
                "oppure non li ha proprio. Restano a zero finche' non si "
                "correggono a mano: meglio di un ingaggio inventato."
            )
            st.write(", ".join(esito.senza_stipendio))

st.divider()

# --- cosa c'e' adesso -------------------------------------------------------

if giocatori.empty:
    st.info(
        "Il listone e' vuoto. Se sei il presidente, premi «Aggiorna listone» "
        "qui sopra; in alternativa si carica il file a mano dalla pagina "
        "«Importa dati».",
        icon="📭",
    )
    st.stop()

svincolati = int((giocatori["Squadra"] == ui.SVINCOLATO).sum())
con_stipendio = int((giocatori["Ingaggio"] > 0).sum())
con_nascita = int((giocatori["Nato"] != "").sum())
ui.griglia_dati(
    [
        {
            "etichetta": "Giocatori",
            "valore": str(len(giocatori)),
            "nota": f"{giocatori['Club'].nunique()} squadre di Serie A",
        },
        {
            "etichetta": "Svincolati",
            "valore": str(svincolati),
            "nota": f"tesserati {len(giocatori) - svincolati}",
            "stato": "avviso" if svincolati else "ok",
            "quota": 1 - svincolati / max(len(giocatori), 1),
        },
        {
            "etichetta": "Con stipendio",
            "valore": str(con_stipendio),
            "nota": "fonte Capology",
            "stato": "ok" if con_stipendio else "avviso",
            "quota": con_stipendio / max(len(giocatori), 1),
        },
        {
            "etichetta": "Con data di nascita",
            "valore": str(con_nascita),
            "nota": f"{int(giocatori['U21'].sum())} Under 21",
            "stato": "ok" if con_nascita else "avviso",
            "quota": con_nascita / max(len(giocatori), 1),
        },
    ]
)

st.divider()

# --- filtri e tabella -------------------------------------------------------

riga = st.columns([2, 2, 2, 2])
cerca = riga[0].text_input("Cerca", placeholder="Nome o club")
club_scelti = riga[1].multiselect(
    "Squadra di Serie A", sorted(giocatori["Club"].unique()), placeholder="Tutte"
)
ruoli_scelti = riga[2].multiselect(
    "Ruolo Mantra",
    sorted({r for elenco in giocatori["Ruoli"] for r in elenco.split("/")}),
    placeholder="Tutti",
    format_func=lambda r: f"{r} — {ETICHETTE_RUOLO.get(r, r)}",
)
nazioni = riga[3].multiselect(
    "Nazionalita'",
    sorted(n for n in giocatori["Nazionalita"].unique() if n),
    placeholder="Tutte",
)

riga = st.columns([3, 1, 1])
squadre_scelte = riga[0].multiselect(
    "Squadra della lega",
    sorted(giocatori["Squadra"].unique()),
    placeholder="Tutte, svincolati compresi",
)
solo_italiani = riga[1].toggle("Solo Ita")
solo_u21 = riga[2].toggle("Solo U21")

filtrati = giocatori
if cerca.strip():
    testo = cerca.strip().lower()
    filtrati = filtrati[
        filtrati["Giocatore"].str.lower().str.contains(testo, na=False)
        | filtrati["Club"].str.lower().str.contains(testo, na=False)
    ]
if club_scelti:
    filtrati = filtrati[filtrati["Club"].isin(club_scelti)]
if ruoli_scelti:
    filtrati = filtrati[
        filtrati["Ruoli"].apply(lambda r: any(x in r.split("/") for x in ruoli_scelti))
    ]
if nazioni:
    filtrati = filtrati[filtrati["Nazionalita"].isin(nazioni)]
if squadre_scelte:
    filtrati = filtrati[filtrati["Squadra"].isin(squadre_scelte)]
if solo_italiani:
    filtrati = filtrati[filtrati["Ita"]]
if solo_u21:
    filtrati = filtrati[filtrati["U21"]]

st.caption(f"{len(filtrati)} giocatori su {len(giocatori)}")
st.dataframe(
    ui.in_milioni(filtrati.drop(columns=["Id"])),
    hide_index=True,
    use_container_width=True,
    height=520,
    column_config={
        **ui.COLONNE_EURO,
        "R": st.column_config.TextColumn("R", help="Ruolo Classic", width="small"),
        "Squadra": st.column_config.TextColumn("Squadra", help="Chi lo possiede"),
        "Anni": st.column_config.NumberColumn("Anni", help="Anni di contratto residui"),
        "Quotazione": st.column_config.NumberColumn(
            "Qt.", help="Quotazione Mantra all'asta"
        ),
        "FVM": st.column_config.NumberColumn(
            "FVM", help="Fanta Valore di Mercato Mantra"
        ),
        "Ita": st.column_config.CheckboxColumn("🇮🇹", help="Italiano"),
        "U21": st.column_config.CheckboxColumn(
            "U21", help=f"Under 21 al {ui.data_u21().strftime('%d/%m/%Y')}"
        ),
    },
)

st.caption(
    f"Lo status Under 21 si valuta al **{ui.data_u21().strftime('%d/%m/%Y')}**: "
    "chi compie 21 anni dopo resta Under per tutta la stagione."
)

scarichi = st.columns(2)
scarichi[0].download_button(
    "⬇️ Scarica il listone consolidato (CSV)",
    filtrati.drop(columns=["Id"]).to_csv(index=False, sep=";").encode("utf-8"),
    file_name=f"listone-{stagione}.csv",
    mime="text/csv",
    help="Le righe che stai vedendo, filtri compresi.",
    use_container_width=True,
)
# Il giro completo: si scarica quel che c'e', si riempiono le tre colonne che
# mancano e si ricarica dalla scheda «Dai file». Gli id non cambiano, quindi
# le rose non si scollegano.
scarichi[1].download_button(
    "📝 Scarica da completare (stipendi, nascita, nazionalita')",
    ui.listone_da_completare().encode("utf-8"),
    file_name=f"listone-{stagione}-da-completare.csv",
    mime="text/csv",
    help="Tutti i giocatori in archivio, con le colonne da riempire vuote. "
    "Si compila in Excel e si ricarica da «Dai file scaricati a mano».",
    use_container_width=True,
)

with st.expander("Legenda dei ruoli Mantra"):
    st.markdown(
        " ".join(
            tema.pastiglia(f"{sigla} · {nome}") for sigla, nome in ETICHETTE_RUOLO.items()
        ),
        unsafe_allow_html=True,
    )

# --- quando la rete non basta ----------------------------------------------

if utente.puo_importare:
    st.divider()
    with st.expander("🛟 Se l'aggiornamento dal web risponde 403"):
        st.markdown(
            f"""
Le due fonti sono pubbliche ma non sono nostre, e i loro file stanno dietro a
un CDN che difende gli statici. **403 Forbidden vuol dire che la richiesta e'
arrivata e che il server l'ha rifiutata**: non e' un indirizzo sbagliato, e'
che una richiesta fatta da un server non somiglia a un visitatore. Il sito ci
prova presentandosi come un browser — User-Agent, lingua, e la pagina delle
quotazioni come provenienza — ma se il filtro guarda l'indirizzo IP di chi
chiama, dal nostro lato non c'e' altro da fare.

**La via che funziona sempre** e' la scheda «Dai file scaricati a mano»:

1. apri
   [{fonti_web.url_quotazioni(stagione)}]({fonti_web.url_quotazioni(stagione)})
   nel tuo browser (dal browser scende: ha i cookie e la cronologia del sito);
2. torna qui, scheda **📁 Dai file scaricati a mano**, e caricalo;
3. gli stipendi, se li hai, si caricano nello stesso posto come CSV — il
   modello si scarica da li'. Senza, nomi e ruoli si aggiornano lo stesso e
   gli ingaggi restano quelli che sono gia' in archivio.

Gli indirizzi che il pulsante prova sono questi, e cambiano solo nella
stagione:
"""
        )
        st.code(
            f"{fonti_web.url_quotazioni(stagione)}\n{fonti_web.url_capology(stagione)}",
            language=None,
        )
        st.caption(
            "Da un computer con la rete aperta si puo' anche usare "
            "`python scripts/aggiorna_listone.py --csv listone.csv`, che "
            "produce lo stesso file consolidato."
        )
