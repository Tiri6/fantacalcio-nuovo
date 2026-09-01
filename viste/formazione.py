"""Formazione: schieri, salvi, e dal minuto prima non si tocca piu'.

La pagina si divide in due momenti che non si mescolano: finche' la giornata
e' aperta si compone la propria formazione; dal blocco in poi si guardano
quelle di tutti, disegnate sul campo.
"""

from datetime import datetime

import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.data import archivio, salva_formazione
from fantacalcio.formazioni import (
    TITOLARI,
    Formazione,
    formazione_suggerita,
    leggi_modulo,
    schieramento,
    stato_blocco,
    valida,
)

ui.barra_laterale()
schermate.mostra_messaggio()
st.markdown(tema.CSS_CAMPO, unsafe_allow_html=True)

utente = ui.utente_corrente()
lega = ui.lega_corrente()
opzioni = lega.opzioni

ui.intestazione(
    "Formazione",
    "📋",
    "Chi mandi in campo. Si chiude un minuto prima del calcio d'inizio.",
)

rose = ui.rose()
if not rose:
    st.info("Nessuna squadra iscritta.", icon="🫥")
    st.stop()

nomi_squadre = {id_: r.squadra.nome for id_, r in rose.items()}
nomi = ui.nomi_giocatori()
ruoli = ui.ruoli_per_giocatore()

# --- quale giornata ---------------------------------------------------------

riga = st.columns([1, 1, 2])
giornata = riga[0].number_input(
    "Giornata",
    min_value=1,
    max_value=max(opzioni.giornate_totali, 1),
    value=min(ui.giornate_disputate(ui.calendario()) + 1, opzioni.giornate_totali),
    step=1,
)
competizione = riga[1].selectbox(
    "Competizione",
    [c.name for c in opzioni.competizioni],
    format_func=lambda c: c.replace("_", " ").title(),
)

inizio = ui.inizio_giornata(int(giornata), competizione)
blocco = stato_blocco(inizio, datetime.now())

with riga[2]:
    if blocco.modificabile and blocco.mancano is not None:
        ore = int(blocco.mancano.total_seconds() // 3600)
        minuti = int(blocco.mancano.total_seconds() % 3600 // 60)
        st.markdown(
            tema.scheda(
                "Ancora aperta",
                f"Mancano {ore}h {minuti:02d}m alla chiusura. Si blocca un "
                f"minuto prima del calcio d'inizio.",
                icona="⏳",
            ),
            unsafe_allow_html=True,
        )
    elif blocco.modificabile:
        st.markdown(
            tema.scheda(
                "Nessun orario in calendario",
                "Questa giornata non ha un calcio d'inizio: finche' non c'e', "
                "le formazioni restano aperte.",
                icona="🗓️",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            tema.scheda("Formazioni chiuse", blocco.motivo, icona="🔒"),
            unsafe_allow_html=True,
        )

salvate = ui.formazioni(int(giornata), competizione)

st.divider()

# --- la mia formazione ------------------------------------------------------

mia_squadra = utente.squadra_id if utente.squadra_id in rose else None

if mia_squadra is None:
    st.info(
        "Non hai una squadra in questa lega: qui sotto puoi comunque vedere "
        "le formazioni degli altri.",
        icon="👀",
    )
elif not blocco.modificabile:
    st.info(
        "La giornata e' chiusa: la tua formazione e' quella che vedi qui "
        "sotto insieme alle altre.",
        icon="🔒",
    )
else:
    rosa = rose[mia_squadra]
    in_rosa = [c.giocatore_id for c in rosa.contratti]
    if not in_rosa:
        st.warning("La tua rosa e' vuota: prima si fa il draft.", icon="📭")
        st.stop()

    corrente = salvate.get(mia_squadra)
    moduli = list(opzioni.moduli_ammessi)
    modulo = st.selectbox(
        "Modulo",
        moduli,
        index=moduli.index(corrente.modulo)
        if corrente and corrente.modulo in moduli
        else 0,
    )

    # Cambiare modulo cambia i posti: la formazione salvata non vale piu' come
    # punto di partenza, e si riparte da una proposta valida.
    base = (
        corrente
        if corrente and corrente.modulo == modulo
        else formazione_suggerita(
            mia_squadra,
            int(giornata),
            modulo,
            in_rosa,
            ruoli,
            panchinari=opzioni.panchinari,
        )
    )

    schema = leggi_modulo(modulo)
    st.caption(
        f"{schema.difensori} difensori · {schema.centrocampisti} centrocampisti "
        f"· {schema.attaccanti} attaccanti. Un giocatore puo' occupare un "
        f"posto se ha un ruolo di quel reparto."
    )

    scelti: list[int] = []
    posizione = 0
    for reparto, quanti in schema.reparti:
        st.markdown(f"**{reparto.etichetta}**")
        colonne = st.columns(min(quanti, 5))
        for indice in range(quanti):
            candidati = [
                g
                for g in in_rosa
                if reparto.accetta(ruoli.get(g, ())) and (g not in scelti)
            ]
            precedente = (
                base.titolari[posizione] if posizione < len(base.titolari) else None
            )
            # Chi era gia' in quel posto resta selezionabile: toglierlo
            # dall'elenco farebbe saltare la scelta a ogni rerun.
            gia_li = (
                precedente is not None
                and precedente not in candidati
                and reparto.accetta(ruoli.get(precedente, ()))
            )
            if gia_li:
                candidati.insert(0, precedente)
            if not candidati:
                colonne[indice % len(colonne)].warning("Nessuno disponibile", icon="⚠️")
                posizione += 1
                continue
            scelta = colonne[indice % len(colonne)].selectbox(
                f"{reparto.etichetta} {indice + 1}",
                candidati,
                index=candidati.index(precedente) if precedente in candidati else 0,
                format_func=lambda g: f"{nomi.get(g, g)} ({'/'.join(ruoli.get(g, ()))})",
                key=f"_titolare_{giornata}_{competizione}_{posizione}",
                label_visibility="collapsed",
            )
            scelti.append(scelta)
            posizione += 1

    st.markdown("**Panchina** — l'ordine conta: entra il primo che puo' farlo")
    panchina = st.multiselect(
        "Panchina",
        [g for g in in_rosa if g not in scelti],
        # Il taglio non e' pignoleria: una panchina piu' lunga del massimo fa
        # alzare a Streamlit un errore che sostituisce l'intera pagina.
        default=[g for g in base.panchina if g in in_rosa and g not in scelti][
            : opzioni.panchinari
        ],
        format_func=lambda g: f"{nomi.get(g, g)} ({'/'.join(ruoli.get(g, ()))})",
        label_visibility="collapsed",
        max_selections=opzioni.panchinari,
    )

    proposta = Formazione(
        squadra_id=mia_squadra,
        giornata=int(giornata),
        modulo=modulo,
        titolari=tuple(scelti),
        panchina=tuple(panchina),
        competizione=competizione,
    )
    problemi = valida(proposta, ruoli, set(in_rosa))
    for problema in problemi:
        st.error(problema, icon="⛔")

    if st.button(
        "💾 Salva la formazione",
        type="primary",
        disabled=bool(problemi),
        use_container_width=True,
    ):
        try:
            salva_formazione(archivio(), proposta)
        except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
            st.error(f"Non riesco a salvare: {errore}", icon="⛔")
        else:
            ui.invalida_dati()
            st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                "success",
                f"Formazione salvata per la giornata {int(giornata)}.",
            )
            st.rerun()

st.divider()

# --- le formazioni di tutti -------------------------------------------------

st.subheader("Le formazioni della giornata")
if not salvate:
    st.caption("Nessuno ha ancora salvato la formazione per questa giornata.")
else:
    st.caption(
        f"{len(salvate)} squadre su {len(rose)} hanno schierato. "
        "Le formazioni sono visibili a tutti."
    )
    colonne = st.columns(2)
    for indice, (squadra_id, formazione) in enumerate(sorted(salvate.items())):
        with colonne[indice % 2]:
            st.markdown(f"**{nomi_squadre.get(squadra_id, '?')}** · {formazione.modulo}")
            reparti = [
                [
                    tema.maglia_in_campo(nomi.get(g, str(g)), "/".join(ruoli.get(g, ())))
                    for g in giocatori
                ]
                for _, giocatori in schieramento(formazione)
            ]
            st.markdown(tema.campo(reparti), unsafe_allow_html=True)
            if formazione.panchina:
                st.caption(
                    "Panchina: "
                    + ", ".join(nomi.get(g, str(g)) for g in formazione.panchina)
                )
            st.write("")

mancanti = [nomi_squadre[s] for s in rose if s not in salvate]
if mancanti:
    st.warning(
        f"Senza formazione: {', '.join(sorted(mancanti))}. "
        f"Chi non schiera prende {TITOLARI} posti vuoti, cioe' zero punti.",
        icon="⚠️",
    )
