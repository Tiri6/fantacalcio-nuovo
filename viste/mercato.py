"""Mercato: simulatore di scambi e calcolo del Dead Money da svincolo.

Il punto di questa pagina e' rispondere prima di agire: "questo scambio si puo'
fare?" e "quanto mi costa tagliarlo?".
"""

import streamlit as st

from fantacalcio import ui
from fantacalcio.mercato import (
    PropostaScambio,
    applica_scambio,
    calcola_dead_money,
    stato_mercato,
    svincola,
    valida_scambio,
)

STAGIONE = "2026/27"

ui.intestazione("Mercato", "🔁", "Scambi e svincoli verificati contro il regolamento.")
ui.barra_laterale()

rose = ui.rose()
nomi = {rosa.squadra.nome: id_ for id_, rosa in rose.items()}
giornate = ui.giornate_disputate(ui.calendario())
mercato = stato_mercato(giornate, ui.CALENDARIO)

st.caption(
    f"Giornate disputate: {giornate} · Finestre aperte: "
    + ", ".join(f.value for f in mercato.finestre_aperte)
)
if mercato.trade_deadline_superata:
    st.warning("Trade deadline superata: gli scambi non sono ratificabili.", icon="🔒")

scambi, svincoli = st.tabs(["Simula uno scambio", "Costo di uno svincolo"])

with scambi:
    colonna_a, colonna_b = st.columns(2)

    with colonna_a:
        nome_a = st.selectbox("Squadra A", sorted(nomi), index=0, key="squadra_a")
        rosa_a = rose[nomi[nome_a]]
        etichette_a = {
            f"{rosa_a.giocatore(c.giocatore_id).nome} · {c.anni_residui} anni · "
            f"{ui.milioni(rosa_a.giocatore(c.giocatore_id).ingaggio)}": c.giocatore_id
            for c in rosa_a.contratti
        }
        scelti_a = st.multiselect(
            "Cede",
            sorted(etichette_a),
            key="cede_a",
            placeholder="Scegli i giocatori",
        )

    with colonna_b:
        altre = [n for n in sorted(nomi) if n != nome_a]
        nome_b = st.selectbox("Squadra B", altre, key="squadra_b")
        rosa_b = rose[nomi[nome_b]]
        etichette_b = {
            f"{rosa_b.giocatore(c.giocatore_id).nome} · {c.anni_residui} anni · "
            f"{ui.milioni(rosa_b.giocatore(c.giocatore_id).ingaggio)}": c.giocatore_id
            for c in rosa_b.contratti
        }
        scelti_b = st.multiselect(
            "Cede",
            sorted(etichette_b),
            key="cede_b",
            placeholder="Scegli i giocatori",
        )

    da_a = tuple(etichette_a[e] for e in scelti_a)
    da_b = tuple(etichette_b[e] for e in scelti_b)

    prolungamenti: dict[int, int] = {}
    if da_a or da_b:
        st.subheader("Prolungamenti (facoltativi)")
        st.caption(
            "In sede di scambio il contratto puo' essere prolungato, restando nei "
            "66 anni. Lodo Bono: non si puo' accorciare. Lodo Corti: una sola volta "
            "per giocatore. Lodo Longoni: massimo 2 per squadra a stagione."
        )
        for giocatore_id, origine in [(g, rosa_a) for g in da_a] + [
            (g, rosa_b) for g in da_b
        ]:
            contratto = origine.contratto_di(giocatore_id)
            giocatore = origine.giocatore(giocatore_id)
            nuovi = st.slider(
                f"{giocatore.nome} — anni di contratto",
                min_value=1,
                max_value=ui.parametri().contratto_anni_massimo,
                value=contratto.anni_residui,
                key=f"anni_{giocatore_id}",
            )
            if nuovi != contratto.anni_residui:
                prolungamenti[giocatore_id] = nuovi

    if not da_a and not da_b:
        st.info("Scegli almeno un giocatore per simulare lo scambio.", icon="👆")
    else:
        proposta = PropostaScambio(
            da_squadra_a=da_a, da_squadra_b=da_b, prolungamenti=prolungamenti
        )
        violazioni = valida_scambio(rosa_a, rosa_b, proposta, STAGIONE, ui.parametri())
        bloccanti = [v for v in violazioni if v.bloccante]

        st.divider()
        if bloccanti:
            st.error(
                f"Scambio non ammesso: {len(bloccanti)} violazioni bloccanti.",
                icon="⛔",
            )
        else:
            st.success("Scambio ammesso dal regolamento.", icon="✅")
        ui.mostra_violazioni(violazioni)

        nuova_a, nuova_b = applica_scambio(rosa_a, rosa_b, proposta, STAGIONE)
        st.subheader("Effetto sulle due rose")
        confronto = st.columns(2)
        for colonna, prima, dopo in (
            (confronto[0], rosa_a, nuova_a),
            (confronto[1], rosa_b, nuova_b),
        ):
            with colonna:
                st.markdown(f"**{prima.squadra.nome}**")
                st.metric(
                    "Giocatori", dopo.dimensione, dopo.dimensione - prima.dimensione
                )
                st.metric(
                    "Anni impegnati",
                    dopo.anni_impegnati,
                    dopo.anni_impegnati - prima.anni_impegnati,
                    delta_color="inverse",
                )
                st.metric(
                    "Spesa salariale",
                    ui.milioni(dopo.spesa_salariale),
                    ui.milioni(dopo.spesa_salariale - prima.spesa_salariale),
                    delta_color="inverse",
                )

with svincoli:
    st.caption(
        "Lodo Origi: il taglio libera subito gli anni, ma il 50% del valore "
        "contrattuale residuo resta a carico del bilancio come Dead Money, "
        "addebitato alla prima sessione di mercato utile."
    )
    nome = st.selectbox("Squadra", sorted(nomi), key="squadra_svincolo")
    rosa = rose[nomi[nome]]

    etichette = {
        f"{rosa.giocatore(c.giocatore_id).nome} · {c.anni_residui} anni · "
        f"{ui.milioni(rosa.giocatore(c.giocatore_id).ingaggio)}": c.giocatore_id
        for c in rosa.contratti
    }
    scelto = st.selectbox("Giocatore da svincolare", sorted(etichette))
    giocatore_id = etichette[scelto]
    contratto = rosa.contratto_di(giocatore_id)
    giocatore = rosa.giocatore(giocatore_id)

    dead_money = calcola_dead_money(contratto, giocatore.ingaggio, ui.parametri())
    dopo, _ = svincola(rosa, giocatore_id, STAGIONE, ui.parametri())

    colonne = st.columns(4)
    colonne[0].metric(
        "Valore residuo", ui.milioni(contratto.valore_residuo(giocatore.ingaggio))
    )
    colonne[1].metric("Dead money", ui.milioni(dead_money))
    colonne[2].metric(
        "Anni liberati",
        contratto.anni_residui,
        f"da {rosa.anni_impegnati} a {dopo.anni_impegnati}",
    )
    colonne[3].metric(
        "Spesa salariale",
        ui.milioni(dopo.spesa_salariale),
        ui.milioni(dopo.spesa_salariale - rosa.spesa_salariale),
        delta_color="inverse",
    )

    risparmio = rosa.spesa_salariale - dopo.spesa_salariale
    st.info(
        f"Tagliando {giocatore.nome} risparmi {ui.milioni(risparmio)} sul monte "
        f"ingaggi e liberi {contratto.anni_residui} anni, ma ti restano "
        f"{ui.milioni(dead_money)} di Dead Money che non contano per il Salary Floor.",
        icon="💸",
    )
