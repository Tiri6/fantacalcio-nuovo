"""Draft: il tabellone delle chiamate, la Lottery e l'ordine dell'articolo 3.

La prima scheda e' quella che si usa mentre il draft si fa: di chi e' il
turno, chi si prende, per quanti anni, e come cambiano monte ingaggi e monte
anni subito dopo. Le altre servono a decidere l'ordine prima di cominciare.
"""

import random
from dataclasses import replace

import pandas as pd
import plotly.express as px
import streamlit as st

from fantacalcio import schermate, tema, ui, vista
from fantacalcio.data import archivio, assegna_contratto, salva_lega, svincola_giocatore
from fantacalcio.draft import (
    PESI_FASCIA,
    chiamata_numero,
    distribuzione_pick,
    griglia_chiamate,
    ordine_riparazione,
    sorteggia_lottery,
    tabellone_draft,
)

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
opzioni = lega.opzioni

ui.intestazione("Draft", "🎱", "Chi chiama, quando, e chi si porta a casa.")

rose = ui.rose()
if not rose:
    st.warning("Nessuna squadra iscritta: non c'e' nessuno da mettere in fila.")
    st.stop()

nomi_per_id = {id_: rosa.squadra.nome for id_, rosa in rose.items()}
id_per_nome = {nome: id_ for id_, nome in nomi_per_id.items()}
classifica = ui.classifica()
ordine_classifica = classifica["Squadra"].tolist() if not classifica.empty else []

# L'ordine salvato, ripulito: una squadra che se n'e' andata non deve lasciare
# un buco nel giro delle chiamate, e una appena iscritta va in fondo.
ordine_ids = [i for i in opzioni.ordine_draft if i in nomi_per_id]
ordine_ids += [
    i for i in sorted(nomi_per_id, key=lambda i: nomi_per_id[i]) if i not in ordine_ids
]
ordine_nomi = [nomi_per_id[i] for i in ordine_ids]
serpente = opzioni.draft_serpente

chiamate, lottery, articolo, riparazione = st.tabs(
    ["🎯 Chiamate", "🎲 Draft Lottery", "📜 Ordine art. 3", "🔧 Asta di riparazione"]
)


# --- il tabellone che si usa ------------------------------------------------

with chiamate:
    if utente.puo_importare:
        with st.expander(
            "⚙️ Ordine di chiamata e andamento", expanded=not opzioni.ordine_draft
        ):
            st.caption(
                "L'ordine e' quello in cui selezioni le squadre: togli tutto e "
                "rimettile nell'ordine giusto. Si salva una volta e resta."
            )
            scelte = st.multiselect(
                "Ordine di chiamata",
                options=sorted(nomi_per_id.values()),
                default=ordine_nomi,
                key="_draft_ordine",
            )
            andamento = st.radio(
                "Andamento dei round",
                options=[True, False],
                index=0 if serpente else 1,
                format_func=lambda s: (
                    "A serpente — il round pari va al contrario"
                    if s
                    else "In ordine — ogni round riparte dal primo"
                ),
                key="_draft_serpente",
            )

            riga = st.columns([1, 1])
            if riga[0].button(
                "💾 Salva l'ordine", type="primary", use_container_width=True
            ):
                if len(scelte) != len(nomi_per_id):
                    st.error(
                        f"Devi mettere in fila tutte e {len(nomi_per_id)} le "
                        f"squadre: ne hai scelte {len(scelte)}.",
                        icon="⛔",
                    )
                else:
                    nuove = replace(
                        opzioni,
                        ordine_draft=tuple(id_per_nome[n] for n in scelte),
                        draft_serpente=bool(andamento),
                    )
                    try:
                        salva_lega(archivio(), replace(lega, opzioni=nuove))
                    except Exception as errore:  # noqa: BLE001 - backend diversi
                        st.error(f"Non riesco a salvare: {errore}", icon="⛔")
                    else:
                        ui.invalida_dati()
                        st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                            "success",
                            "Ordine del draft salvato.",
                        )
                        st.rerun()

            if ordine_classifica and riga[1].button(
                "🎲 Prendi l'ordine dalla Lottery", use_container_width=True
            ):
                esito = sorteggia_lottery(ordine_classifica, random.Random(2026))
                st.session_state["_draft_ordine"] = list(esito.ordine)
                st.rerun()

    st.markdown(
        " ".join(
            tema.pastiglia(f"{posizione}. {nome}")
            for posizione, nome in enumerate(ordine_nomi, start=1)
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        (
            "Round pari al contrario (serpente)."
            if serpente
            else "Ordine fisso a ogni round."
        )
        + ("" if utente.puo_importare else " L'ordine lo imposta il presidente.")
    )

    # --- di chi e' il turno --------------------------------------------------
    #
    # Il progressivo si deduce da quanti contratti esistono: al primo draft
    # parte da zero e torna sempre giusto. Resta modificabile perche' con le
    # rose gia' caricate il conto non puo' saperlo.

    assegnati = sum(len(rosa.contratti) for rosa in rose.values())
    riga = st.columns([1, 3])
    numero = riga[0].number_input(
        "Chiamata numero",
        min_value=1,
        value=assegnati + 1,
        step=1,
        help="Si aggiorna da solo a ogni assegnazione. Cambialo se il draft e' "
        "cominciato prima o se stai recuperando a mano.",
    )
    turno = chiamata_numero(ordine_nomi, int(numero), serpente)
    prossime = [
        chiamata_numero(ordine_nomi, int(numero) + n, serpente) for n in range(1, 5)
    ]
    with riga[1]:
        st.markdown(
            tema.scheda(
                f"Tocca a {turno.squadra}",
                f"{turno.etichetta}. Poi: "
                + " → ".join(c.squadra for c in prossime)
                + ".",
                icona="📣",
            ),
            unsafe_allow_html=True,
        )

    st.divider()

    # --- assegnazione --------------------------------------------------------

    listone = ui.listone()
    tesserati = {
        contratto.giocatore_id for rosa in rose.values() for contratto in rosa.contratti
    }

    if listone.empty:
        st.info(
            "Il listone non e' ancora caricato: senza, non c'e' nessuno da "
            "chiamare. Si aggiorna dalla pagina «Listone giocatori».",
            icon="📋",
        )
    elif not utente.puo_importare:
        st.info(
            "Le chiamate le registra il presidente di lega (art. 1). Qui sotto "
            "vedi come stanno le squadre.",
            icon="🔒",
        )
    else:
        liberi = listone[~listone["Id"].isin(tesserati)]
        if liberi.empty:
            st.success("Tutti i giocatori del listone sono assegnati.", icon="✅")
        else:
            riga = st.columns([3, 1, 1])
            cerca = riga[0].text_input(
                "Filtra", placeholder="Nome, club o ruolo", key="_draft_cerca"
            )
            candidati = liberi
            if cerca.strip():
                testo = cerca.strip().lower()
                candidati = candidati[
                    candidati["Giocatore"].str.lower().str.contains(testo, na=False)
                    | candidati["Club"].str.lower().str.contains(testo, na=False)
                    | candidati["Ruoli"].str.lower().str.contains(testo, na=False)
                ]

            if candidati.empty:
                st.caption("Nessuno svincolato con questi criteri.")
            else:
                etichette = {
                    f"{r.Giocatore} · {r.Club} · {r.Ruoli}"
                    + (f" · {r.Ingaggio / 1_000_000:.1f}M" if r.Ingaggio else ""): r.Id
                    for r in candidati.head(300).itertuples()
                }
                scelto = riga[0].selectbox(
                    "Giocatore", list(etichette), key="_draft_giocatore"
                )
                anni = riga[1].number_input(
                    "Anni di contratto",
                    min_value=1,
                    max_value=opzioni.anni_contratto_massimi,
                    value=1,
                    key="_draft_anni",
                )
                # La chiave porta dentro il turno: cambiando chiamata il menu
                # riparte da chi tocca adesso invece di restare su chi ha appena
                # chiamato. Dentro lo stesso turno resta libero di cambiare.
                destinataria = riga[2].selectbox(
                    "Alla squadra",
                    ordine_nomi,
                    index=ordine_nomi.index(turno.squadra),
                    key=f"_draft_squadra_{turno.numero}",
                    help="Parte da chi e' di turno, ma si puo' cambiare.",
                )

                giocatore = listone[listone["Id"] == etichette[scelto]].iloc[0]
                rosa = rose[id_per_nome[destinataria]]
                ingaggio = float(giocatore["Ingaggio"])
                residuo = opzioni.budget_cap - rosa.monte_ingaggi - ingaggio
                anni_dopo = rosa.anni_impegnati + int(anni)
                monte_anni = ui.parametri().monte_anni

                ui.griglia_dati(
                    [
                        {
                            "etichetta": "Ingaggio",
                            "valore": (
                                f"{ingaggio / 1_000_000:.2f}M" if ingaggio else "—"
                            ),
                            "nota": giocatore["Nazionalita"] or "nazionalita' ignota",
                            "stato": "ok" if ingaggio else "avviso",
                        },
                        {
                            "etichetta": "Cap dopo la chiamata",
                            "valore": f"{residuo / 1_000_000:.1f}M",
                            "nota": f"su {opzioni.budget_cap_milioni:.0f}M",
                            "stato": "male" if residuo < 0 else "ok",
                        },
                        {
                            "etichetta": "Monte anni dopo",
                            "valore": f"{anni_dopo}/{monte_anni}",
                            "stato": "male" if anni_dopo > monte_anni else "ok",
                            "quota": anni_dopo / max(monte_anni, 1),
                        },
                        {
                            "etichetta": "Rosa dopo",
                            "valore": str(len(rosa.contratti) + 1),
                            "nota": (
                                f"su {opzioni.rosa_totale}"
                                if opzioni.rosa_totale
                                else "nessun limite"
                            ),
                        },
                    ]
                )

                if residuo < 0:
                    st.warning(
                        f"Sfora il budget cap di {abs(residuo) / 1_000_000:.2f}M.",
                        icon="⚠️",
                    )
                if anni_dopo > monte_anni:
                    st.warning(
                        f"Porta il monte anni a {anni_dopo}, oltre il tetto di "
                        f"{monte_anni}.",
                        icon="⚠️",
                    )

                azioni = st.columns([2, 1])
                if azioni[0].button(
                    f"✅ Assegna a {destinataria}",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        assegna_contratto(
                            archivio(),
                            giocatore_id=int(giocatore["Id"]),
                            squadra_id=id_per_nome[destinataria],
                            anni_residui=int(anni),
                        )
                    except Exception as errore:  # noqa: BLE001 - backend diversi
                        st.error(f"Non riesco a salvare: {errore}", icon="⛔")
                    else:
                        ui.invalida_dati()
                        st.session_state["_draft_ultima"] = (
                            int(giocatore["Id"]),
                            str(giocatore["Giocatore"]),
                            destinataria,
                        )
                        st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                            "success",
                            f"{giocatore['Giocatore']} a {destinataria}, "
                            f"{int(anni)} "
                            + ("anno" if int(anni) == 1 else "anni")
                            + f" · {turno.etichetta}.",
                        )
                        st.rerun()

                ultima = st.session_state.get("_draft_ultima")
                if ultima and azioni[1].button(
                    f"↩︎ Annulla {ultima[1]}", use_container_width=True
                ):
                    try:
                        svincola_giocatore(archivio(), ultima[0])
                    except Exception as errore:  # noqa: BLE001 - backend diversi
                        st.error(f"Non riesco ad annullare: {errore}", icon="⛔")
                    else:
                        ui.invalida_dati()
                        st.session_state.pop("_draft_ultima", None)
                        st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                            "warning",
                            f"{ultima[1]} tolto da {ultima[2]}: torna svincolato.",
                        )
                        st.rerun()

    # --- come stanno le squadre ----------------------------------------------

    st.divider()
    st.subheader("Monte ingaggi e monte anni")
    st.caption("Si aggiornano a ogni chiamata: e' il conto che decide il draft.")

    tetto_anni = ui.parametri().monte_anni
    situazione = pd.DataFrame(
        [
            {
                "Ordine": posizione,
                "Squadra": nome,
                "Turno": "📣" if nome == turno.squadra else "",
                "Giocatori": len(rose[id_per_nome[nome]].contratti),
                "Ingaggi": rose[id_per_nome[nome]].monte_ingaggi,
                "Spazio cap": opzioni.budget_cap - rose[id_per_nome[nome]].monte_ingaggi,
                "Anni": rose[id_per_nome[nome]].anni_impegnati,
                "Anni liberi": tetto_anni - rose[id_per_nome[nome]].anni_impegnati,
            }
            for posizione, nome in enumerate(ordine_nomi, start=1)
        ]
    )
    st.dataframe(
        ui.in_milioni(situazione),
        hide_index=True,
        use_container_width=True,
        column_config={
            **ui.COLONNE_EURO,
            "Turno": st.column_config.TextColumn("", width="small"),
            "Anni": st.column_config.ProgressColumn(
                "Monte anni", min_value=0, max_value=max(tetto_anni, 1), format="%d"
            ),
        },
    )

    with st.expander("Tabellone completo dei round"):
        quanti = st.slider("Round da mostrare", 1, 30, 6, key="_draft_round")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Round": numero_round,
                        **{f"{i}a": s for i, s in enumerate(giro, start=1)},
                    }
                    for numero_round, giro in griglia_chiamate(
                        ordine_nomi, quanti, serpente
                    )
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )


# --- la Lottery dell'articolo 3 ---------------------------------------------

with lottery:
    if not ordine_classifica:
        st.info(
            "La Lottery parte dalla classifica della stagione precedente: senza "
            "risultati non c'e' niente da sorteggiare. Per il primo draft "
            "l'ordine si mette a mano nella scheda «Chiamate».",
            icon="🗓️",
        )
    else:
        st.caption(
            "Due estrazioni distinte: le pick 1-5 tra la 10a e la 6a "
            f"classificata, le pick 6-10 tra la 5a e la 1a. Pesi: {PESI_FASCIA}."
        )
        seme = st.number_input(
            "Seme del sorteggio",
            min_value=0,
            value=2026,
            help="Stesso seme, stesso sorteggio: serve per rifare l'estrazione "
            "davanti a tutti.",
        )
        esito = sorteggia_lottery(ordine_classifica, random.Random(int(seme)))

        tabella = pd.DataFrame(
            {
                "Pick": range(1, len(esito.ordine) + 1),
                "Squadra": esito.ordine,
                "Posizione precedente": [
                    ordine_classifica.index(s) + 1 for s in esito.ordine
                ],
            }
        )
        tabella["Fascia"] = [
            "1-5 (dalla 10a alla 6a)" if p <= 5 else "6-10 (dalla 5a alla 1a)"
            for p in tabella["Pick"]
        ]
        st.dataframe(tabella, hide_index=True, use_container_width=True)

        st.subheader("Probabilita' di ogni pick")
        st.caption(
            "I pesi valgono per la prima estrazione di ciascuna fascia; le pick "
            "successive dipendono da chi e' gia' uscito, quindi si stimano per "
            "simulazione."
        )
        distribuzione = distribuzione_pick(ordine_classifica, simulazioni=4000)
        matrice = pd.DataFrame(distribuzione).T.fillna(0.0)
        matrice = matrice.reindex(ordine_classifica)
        figura = px.imshow(
            matrice,
            labels={"x": "Pick", "y": "", "color": "Probabilita'"},
            text_auto=".0%",
            aspect="auto",
            color_continuous_scale="Greens",
        )
        figura.update_layout(margin={"t": 20, "b": 10, "l": 10, "r": 10})
        st.plotly_chart(figura, use_container_width=True)


with articolo:
    st.caption(
        "L'ordine previsto dal regolamento della lega: round 1 e 2 a serpente "
        "sulla Lottery, i round multipli di 3 secondo l'ordine di arrivo della "
        "stagione precedente, gli altri di nuovo sulla Lottery."
    )
    if not ordine_classifica:
        st.info("Serve la classifica della stagione precedente.", icon="🗓️")
    else:
        round_totali = st.slider("Round da mostrare", 3, 12, 6, key="_art3_round")
        esito_tabellone = sorteggia_lottery(ordine_classifica, random.Random(2026))
        righe = []
        for numero_round, giro in tabellone_draft(
            round_totali, esito_tabellone.ordine, ordine_classifica
        ):
            criterio = (
                "Classifica precedente"
                if numero_round % 3 == 0
                else ("Lottery invertita" if numero_round == 2 else "Lottery")
            )
            righe.append(
                {
                    "Round": numero_round,
                    "Criterio": criterio,
                    **{f"{i}a": nome for i, nome in enumerate(giro, start=1)},
                }
            )
        st.dataframe(pd.DataFrame(righe), hide_index=True, use_container_width=True)


with riparazione:
    st.caption(
        "Nell'asta di riparazione tutti i turni seguono l'ordine inverso di "
        "classifica al momento dell'apertura della finestra."
    )
    if not ordine_classifica:
        st.info("Serve la classifica in corso.", icon="🗓️")
    else:
        ordine = ordine_riparazione(ordine_classifica)
        st.dataframe(
            pd.DataFrame({"Turno": range(1, len(ordine) + 1), "Squadra": ordine}),
            hide_index=True,
            use_container_width=True,
        )

    st.divider()
    st.subheader("Draft list: contratti in scadenza")
    st.caption("Chi arriva a scadenza naturale rientra nel draft della prossima asta.")
    scadenze = vista.contratti_in_scadenza(ui.rose(), ui.DATA_DRAFT)
    st.dataframe(
        ui.in_milioni(scadenze),
        hide_index=True,
        use_container_width=True,
        column_config=ui.COLONNE_EURO,
    )
