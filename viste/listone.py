"""Listone giocatori: la fonte unica da cui pescano il draft e le rose.

Questa pagina non e' «Lista giocatori»: li' si guarda chi appartiene a chi,
qui si guarda **da dove arrivano i dati** e li si aggiorna. Un pulsante solo,
che va a prendere il listone ufficiale e gli stipendi e li mette insieme.
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

if utente.puo_importare:
    riga = st.columns([2, 1])
    with riga[0]:
        st.markdown(
            tema.scheda(
                "Da dove arriva",
                "Il listone ufficiale di Fantacalcio.it per nomi, squadre e "
                "ruoli Mantra; Capology per gli stipendi lordi e le "
                "nazionalita' (art. 4). Il pulsante scarica le due fonti e le "
                "mette insieme.",
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

    if aggiorna:
        with st.spinner("Scarico il listone e gli stipendi…"):
            esito = fonti_web.aggiorna_da_web(ingaggi_correnti=ui.ingaggi_noti())
            if esito.riuscito:
                try:
                    conteggio = fonti_web.applica(archivio(), esito.righe)
                except Exception as errore:  # noqa: BLE001 - i backend variano
                    st.session_state[CHIAVE_ESITO] = ("errore", str(errore), esito)
                else:
                    ui.invalida_dati()
                    st.session_state[CHIAVE_ESITO] = ("ok", conteggio, esito)
                    st.rerun()
            else:
                st.session_state[CHIAVE_ESITO] = ("giu", None, esito)

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
            "etichetta": "Con stipendio",
            "valore": str(con_stipendio),
            "nota": "fonte Capology",
            "stato": "ok" if con_stipendio else "avviso",
            "quota": con_stipendio / max(len(giocatori), 1),
        },
        {
            "etichetta": "Con data di nascita",
            "valore": str(con_nascita),
            "nota": "serve per l'Under 21",
            "stato": "ok" if con_nascita else "avviso",
            "quota": con_nascita / max(len(giocatori), 1),
        },
        {
            "etichetta": "Italiani",
            "valore": str(int(giocatori["Ita"].sum())),
            "nota": f"di cui {int(giocatori['U21'].sum())} Under 21",
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

st.caption(f"{len(filtrati)} giocatori su {len(giocatori)}")
st.dataframe(
    ui.in_milioni(filtrati.drop(columns=["Id"])),
    hide_index=True,
    use_container_width=True,
    height=520,
    column_config={
        **ui.COLONNE_EURO,
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

st.download_button(
    "⬇️ Scarica il listone consolidato (CSV)",
    filtrati.drop(columns=["Id"]).to_csv(index=False, sep=";").encode("utf-8"),
    file_name=f"listone-{stagione}.csv",
    mime="text/csv",
    help="Le righe che stai vedendo, filtri compresi.",
)

# --- quando la rete non basta ----------------------------------------------

if utente.puo_importare:
    st.divider()
    with st.expander("🛟 Se l'aggiornamento automatico non funziona"):
        st.markdown(
            f"""
Le due fonti sono pubbliche ma non sono nostre: cambiano indirizzo e formato
quando vogliono. Se il pulsante fallisce, il listone si carica a mano e il
sito funziona uguale.

1. scarica il file ufficiale da
   [{fonti_web.url_quotazioni(stagione)}]({fonti_web.url_quotazioni(stagione)})
   (oppure dalla pagina *Quotazioni* di Fantacalcio.it);
2. caricalo dalla pagina **Importa dati → Listone ufficiale**;
3. gli stipendi si caricano dallo stesso posto, con il CSV delle rose.

Gli indirizzi provati dal pulsante sono questi, e cambiano solo nella
stagione:
"""
        )
        st.code(
            f"{fonti_web.url_quotazioni(stagione)}\n{fonti_web.url_capology(stagione)}",
            language=None,
        )
