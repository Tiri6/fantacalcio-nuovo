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

# --- caricare il listone ----------------------------------------------------
#
# Un solo file, uno solo: il CSV con tutto dentro. C'e' stata una fase con due
# fonti da scaricare dal web e da mettere insieme, ma quei siti un server non
# li raggiunge, e due caselle di caricamento per una cosa sola confondevano e
# basta. Il lettore accetta anche l'.xlsx ufficiale, perche' riconoscerlo
# costa una riga e ogni tanto serve.

CHIAVE_ESITO = "_listone_esito"
CHIAVE_CONFERMA = "_listone_conferma_cancella"


def _salva(esito, sostituisci: bool) -> None:
    """Scrive in archivio quel che il file ha prodotto, e lo racconta."""
    if not esito.riuscito:
        st.session_state[CHIAVE_ESITO] = ("giu", None, esito)
        return
    try:
        conteggio = fonti_web.applica(archivio(), esito.righe, sostituisci=sostituisci)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.session_state[CHIAVE_ESITO] = ("errore", str(errore), esito)
        return
    ui.invalida_dati()
    st.session_state[CHIAVE_ESITO] = ("ok", conteggio, esito)
    st.rerun()


if utente.puo_importare:
    st.markdown(
        tema.scheda(
            "Come si carica",
            "Un file solo, con tutto dentro: id, nome, squadra, ruoli, data di "
            "nascita, nazionalita' e stipendio lordo. Le colonne si "
            "riconoscono dal nome, in qualsiasi ordine.",
            icona="📥",
        ),
        unsafe_allow_html=True,
    )

    # Nessun filtro sull'estensione, di proposito. Con `type=[...]` Streamlit
    # scarta il file **prima** di consegnarlo, e da fuori si vede solo un
    # pulsante che resta spento: un `.CSV` maiuscolo, un `.txt`, o quel che
    # produce il salvataggio da telefono bastavano a bloccare tutto senza
    # dire perche'. Il formato lo riconosciamo dal contenuto, che e' piu'
    # affidabile del nome, e se non lo capiamo lo diciamo.
    file_listone = st.file_uploader(
        "Il listone (.csv, oppure l'.xlsx ufficiale di Fantacalcio.it)",
        key="_file_listone",
    )

    # Cosa e' arrivato davvero: senza questa riga, «non funziona» non si puo'
    # distinguere da «non ho ancora scelto il file».
    if file_listone is None:
        st.caption("Nessun file ricevuto. Scegli il file qui sopra.")
    else:
        misura = len(file_listone.getvalue())
        st.caption(
            f"Ricevuto: **{file_listone.name}** ({misura / 1024:.1f} KB)."
            + ("  ⚠️ Il file e' vuoto." if not misura else "")
        )

    modo = st.radio(
        "Cosa fare con quello che c'e' gia'",
        options=[False, True],
        index=0,
        format_func=lambda sostituisci: (
            "Sostituisci il listone — chi non e' nel file viene cancellato, "
            "insieme al suo contratto"
            if sostituisci
            else "Aggiorna — unisce al listone esistente, non cancella nessuno"
        ),
        key="_listone_modo",
        disabled=giocatori.empty,
        help="Al primo caricamento non cambia niente: il listone e' vuoto.",
    )

    if modo and not giocatori.empty:
        tesserati = int((giocatori["Squadra"] != ui.SVINCOLATO).sum())
        st.warning(
            f"In sostituzione, i giocatori che non compaiono nel file vengono "
            f"cancellati. Oggi ce ne sono {len(giocatori)} in archivio, di cui "
            f"{tesserati} sotto contratto: se non sono nel file, perdono anche "
            f"il contratto.",
            icon="⚠️",
        )

    # Il pulsante resta acceso anche senza file: un pulsante spento non dice
    # perche' lo e', e chi lo guarda non ha modo di capire se il problema e'
    # suo o del sito.
    if st.button("📥 Consolida e carica", type="primary", use_container_width=True):
        if file_listone is None:
            st.error(
                "Non ho ricevuto nessun file. Scegli il listone qui sopra e "
                "aspetta che compaia il suo nome, poi premi di nuovo.",
                icon="📂",
            )
        else:
            with st.spinner("Leggo il file e lo metto in archivio…"):
                _salva(
                    fonti_web.aggiorna_da_file(
                        file_listone.getvalue(), ingaggi_correnti=ui.ingaggi_noti()
                    ),
                    sostituisci=bool(modo),
                )

    riga = st.columns([1, 1])
    riga[0].download_button(
        "⬇️ Scarica il modello del CSV",
        fonti_web.MODELLO_CSV_LISTONE.encode("utf-8"),
        file_name="listone-modello.csv",
        mime="text/csv",
        use_container_width=True,
    )
    if riga[1].button("↩︎ Nascondi il rapporto", use_container_width=True):
        st.session_state.pop(CHIAVE_ESITO, None)

    with st.expander("Che colonne deve avere il file"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Colonna": "id giocatore",
                        "Obbligatoria": True,
                        "Esempio": "2071",
                        "Nota": "L'id del listone ufficiale. E' quel che tiene "
                        "insieme le rose: i contratti puntano all'id, non al "
                        "nome, quindi correggere una grafia non scollega "
                        "nessuno.",
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
                        "Nota": "P, D, C o A. Non si ricava dal Mantra: un "
                        "esterno «E» in Classic puo' essere D o C.",
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
                        "Nota": "gg/mm/aaaa o aaaa-mm-gg. Senza, l'Under 21 "
                        "non si puo' determinare.",
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
                        "Nota": "In euro, fonte Capology (art. 4). Se la "
                        "casella e' vuota resta l'ingaggio gia' in archivio, "
                        "non diventa zero.",
                    },
                ]
            ),
            hide_index=True,
            use_container_width=True,
            column_config={"Obbligatoria": st.column_config.CheckboxColumn("Obbl.")},
        )
        st.caption(
            "L'ordine delle colonne non conta: si riconoscono dal nome. "
            "Separatore `;` o `,`; gli importi si possono scrivere "
            "`3.500.000`, `3,5M` o `€ 2.100.000`."
        )

memoria = st.session_state.get(CHIAVE_ESITO)
if memoria:
    stato, dettaglio, esito = memoria
    if stato == "ok":
        st.success(
            f"{dettaglio['totali']} giocatori nel listone "
            f"({dettaglio['nuovi']} nuovi"
            + (f", {dettaglio['rimossi']} cancellati" if dettaglio["rimossi"] else "")
            + f"), {dettaglio['con_stipendio']} con lo stipendio.",
            icon="✅",
        )
    elif stato == "errore":
        st.error(f"Letto, ma non salvato: {dettaglio}", icon="⛔")
    else:
        st.error(
            "Il file non si e' lasciato leggere: il listone e' rimasto quello "
            "di prima. Il dettaglio e' qui sotto.",
            icon="🚧",
        )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Fonte": f.nome,
                    "Esito": "✅" if f.ok else "⛔",
                    "Dettaglio": f.dettaglio,
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
                "Nel file la casella dello stipendio era vuota e in archivio "
                "non ce n'era uno da tenere. Restano a zero finche' non si "
                "ricarica il file completo: meglio di un ingaggio inventato."
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

# --- cancellare il listone --------------------------------------------------
#
# In fondo, dietro una conferma scritta a mano. E' l'unica azione del sito che
# porta via anche le rose: senza giocatori i contratti non hanno piu' un
# soggetto, e restare a puntare nel vuoto sarebbe peggio che sparire.

if utente.puo_importare and not giocatori.empty:
    st.divider()
    with st.expander("🗑️ Cancella tutto il listone"):
        tesserati = int((giocatori["Squadra"] != ui.SVINCOLATO).sum())
        st.warning(
            f"Cancella **tutti i {len(giocatori)} giocatori** e, con loro, "
            f"**i {tesserati} contratti** che li assegnano alle squadre. Le "
            f"squadre restano, ma le rose si svuotano. Non si torna indietro.",
            icon="⚠️",
        )
        st.caption(
            "Per ricaricare un listone sbagliato non serve cancellare: basta "
            "caricare il file giusto scegliendo «Sostituisci il listone»."
        )
        # «e premi Invio» non e' pedanteria: Streamlit consegna il testo solo
        # quando la casella perde il fuoco, quindi finche' non lo si fa il
        # pulsante resta spento e sembra rotto.
        conferma = st.text_input(
            "Scrivi CANCELLA e premi Invio per confermare",
            key=CHIAVE_CONFERMA,
            placeholder="CANCELLA",
        )
        if st.button(
            "🗑️ Cancella il listone e tutte le rose",
            type="primary",
            disabled=conferma.strip().upper() != "CANCELLA",
            use_container_width=True,
        ):
            from fantacalcio.data import svuota_listone

            try:
                andati = svuota_listone(archivio())
            except Exception as errore:  # noqa: BLE001 - i backend variano
                st.error(f"Non riesco a cancellare: {errore}", icon="⛔")
            else:
                ui.invalida_dati()
                st.session_state.pop(CHIAVE_ESITO, None)
                st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                    "warning",
                    f"Listone cancellato: {andati['giocatori']} giocatori e "
                    f"{andati['contratti']} contratti.",
                )
                st.rerun()
