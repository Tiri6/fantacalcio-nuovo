"""Squadre: identita', rosa completa e conti di una squadra alla volta.

Una pagina per squadra invece di una tabella di tutte: qui si guarda la
propria rosa giocatore per giocatore, con nazionalita', eta', status Under 21
e quanto pesa ciascuno sul budget.
"""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.competizioni import (
    TipoCompetizione,
    conta_per_competizione,
    titoli_di,
)

ui.barra_laterale()
schermate.mostra_messaggio()

rose = ui.rose()
if not rose:
    ui.intestazione("Squadre", "🛡️")
    st.info("Nessuna squadra ancora iscritta alla lega.", icon="🫥")
    st.stop()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
opzioni = lega.opzioni

per_nome = {rosa.squadra.nome: rosa for rosa in rose.values()}
nomi = sorted(per_nome)

# Se hai una squadra, la pagina si apre sulla tua.
mia = next((n for n, r in per_nome.items() if r.squadra.id == utente.squadra_id), nomi[0])
scelta = st.selectbox("Squadra", nomi, index=nomi.index(mia))
rosa = per_nome[scelta]
squadra = rosa.squadra
identita = squadra.identita

# --- identita' --------------------------------------------------------------
#
# Si modifica da dove la si guarda, con un pulsante in alto a destra: mandare
# a cercare un'altra pagina per correggere il nome dello stadio e' il modo per
# far credere che non si possa.
#
# Chi puo' farlo lo decide il dominio, non questa pagina: `puo_gestire` dice
# di si' al presidente per tutte le squadre e a ogni altro solo per la sua.

IN_MODIFICA = "squadra_in_modifica"

mia_da_gestire = utente.puo_gestire(squadra.id)
in_modifica = mia_da_gestire and st.session_state.get(IN_MODIFICA) == squadra.id
if not in_modifica:
    # Cambiare squadra dal menu chiude la modifica: altrimenti tornando
    # indietro la si ritroverebbe aperta senza averla riaperta.
    st.session_state.pop(IN_MODIFICA, None)

intestazione, maglia, azione = st.columns([5, 1, 2], vertical_alignment="center")
with intestazione:
    ui.intestazione(squadra.nome, "🛡️", identita.motto or "")
with maglia:
    ui.mostra_maglia(identita, larghezza=110)
with azione:
    if in_modifica:
        if st.button("Annulla", key="chiudi_modifica", use_container_width=True):
            st.session_state.pop(IN_MODIFICA, None)
            st.rerun()
    elif mia_da_gestire and st.button(
        "✏️ Modifica", key="apri_modifica", type="primary", use_container_width=True
    ):
        st.session_state[IN_MODIFICA] = squadra.id
        st.rerun()

if in_modifica:
    schermate.modulo_identita(
        squadra,
        lega,
        nomi_occupati={n.lower() for n in nomi if n != scelta},
        chiave=f"sq_{squadra.id}",
        compatto=True,
        etichetta_salva="💾 Salva",
        al_salvataggio=lambda: st.session_state.pop(IN_MODIFICA, None),
    )
else:
    dettagli = [
        ("Presidente", identita.presidente or "—"),
        ("Stadio", identita.stadio or "—"),
        ("Citta'", identita.citta or "—"),
        ("Curva", identita.curva or "—"),
    ]
    if identita.anno_fondazione:
        dettagli.append(("Fondata nel", str(identita.anno_fondazione)))

    colonne = st.columns(len(dettagli))
    for colonna, (etichetta, valore) in zip(colonne, dettagli, strict=True):
        colonna.markdown(f"**{etichetta}**  \n{valore}")

    st.markdown(
        tema.pastiglia_squadra(
            squadra.nome, identita.colore_primario, identita.colore_secondario
        ),
        unsafe_allow_html=True,
    )

# --- bacheca dei titoli -----------------------------------------------------
#
# Si popola da sola dall'albo d'oro: chi amministra registra il vincitore li',
# e la coppa compare qui. Nessun dato da tenere allineato a mano.

titoli = titoli_di(ui.albo(), squadra.id, squadra.nome)

st.divider()
st.subheader("🏆 Bacheca")

if not titoli:
    st.caption(
        "Ancora nessun titolo. La bacheca si riempie da sola quando chi "
        "amministra registra un vincitore nell'albo d'oro."
    )
else:
    conteggio = conta_per_competizione(titoli)
    ui.griglia_dati(
        [
            {
                "etichetta": tipo.etichetta,
                "valore": str(quanti),
                "nota": tipo.icona * min(quanti, 5) if quanti else "—",
                "stato": "ok" if quanti else "avviso",
            }
            for tipo, quanti in conteggio.items()
        ]
    )

    st.markdown(
        " ".join(
            tema.pastiglia(
                f"{t.competizione.icona} {t.stagione}",
                tema.AMBRA
                if t.competizione is TipoCompetizione.CAMPIONATO
                else tema.VERDE,
            )
            for t in titoli
        ),
        unsafe_allow_html=True,
    )
    with st.expander(f"Tutti i {len(titoli)} titoli"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Competizione": (
                            f"{t.competizione.icona} {t.competizione.etichetta}"
                        ),
                        "Stagione": t.stagione,
                        "Nota": t.note,
                    }
                    for t in titoli
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )

st.divider()

# --- conti ------------------------------------------------------------------

parametri = ui.parametri()
riferimento = ui.data_u21()
stato = ui.stati()[squadra.id]

ingaggi = rosa.monte_ingaggi
residuo = opzioni.budget_cap - ingaggi
italiani = sum(1 for g in rosa.giocatori if g.italiano)
u21 = sum(1 for g in rosa.giocatori if g.under_21(riferimento, parametri))

ui.griglia_dati(
    [
        {
            "etichetta": "Rosa",
            "valore": str(len(rosa.contratti)),
            "nota": (
                f"su {opzioni.rosa_totale}"
                if opzioni.rosa_totale
                else "nessun limite di ruolo"
            ),
        },
        {
            "etichetta": "Anni di contratto",
            "valore": f"{rosa.anni_impegnati}/{parametri.monte_anni}",
            "nota": f"{parametri.monte_anni - rosa.anni_impegnati} liberi",
            "stato": "male" if rosa.anni_impegnati > parametri.monte_anni else "ok",
            "quota": rosa.anni_impegnati / max(parametri.monte_anni, 1),
        },
        {
            "etichetta": "Budget cap residuo",
            "valore": f"{residuo / 1_000_000:.1f}M",
            "nota": f"su {opzioni.budget_cap_milioni:.0f}M",
            "stato": "male" if residuo < 0 else "ok",
            "quota": ingaggi / max(opzioni.budget_cap, 1),
        },
        {
            "etichetta": "Italiani",
            "valore": str(italiani),
            "nota": f"di cui {u21} Under 21",
            "stato": (
                "male"
                if opzioni.minimo_italiani and italiani < opzioni.minimo_italiani
                else "ok"
            ),
        },
    ]
)

if opzioni.minimo_italiani and italiani < opzioni.minimo_italiani:
    st.error(
        f"La lega chiede almeno {opzioni.minimo_italiani} italiani in rosa: "
        f"qui sono {italiani}.",
        icon="⛔",
    )
if opzioni.minimo_u21_italiani and u21 < opzioni.minimo_u21_italiani:
    st.error(
        f"La lega chiede almeno {opzioni.minimo_u21_italiani} Under 21 "
        f"italiani: qui sono {u21}.",
        icon="⛔",
    )

st.divider()

# --- rosa -------------------------------------------------------------------

st.subheader("Rosa")

if not rosa.contratti:
    st.info("Rosa vuota. I giocatori si assegnano dalla pagina «Draft».", icon="📭")
else:
    righe = []
    for contratto in sorted(rosa.contratti, key=lambda c: -c.anni_residui):
        try:
            giocatore = rosa.giocatore(contratto.giocatore_id)
        except KeyError:
            # Un contratto che punta a un giocatore non in anagrafica: si
            # salta invece di far esplodere l'intera rosa.
            continue
        righe.append(
            {
                "Giocatore": giocatore.nome,
                "Club": giocatore.club,
                "Ruoli": "/".join(giocatore.ruoli),
                "Nazionalita": giocatore.nazionalita,
                "Nato": (
                    giocatore.data_nascita.strftime("%d/%m/%Y")
                    if giocatore.data_nascita
                    else ""
                ),
                "Eta": giocatore.eta_al(riferimento) or 0,
                "Ita": giocatore.italiano,
                "U21": giocatore.under_21(riferimento, parametri),
                "Anni": contratto.anni_residui,
                "Ingaggio": giocatore.ingaggio,
                "Prolungato": contratto.prolungato,
            }
        )

    tabella = pd.DataFrame(righe)
    st.dataframe(
        ui.in_milioni(tabella),
        hide_index=True,
        use_container_width=True,
        column_config={
            **ui.COLONNE_EURO,
            "Ita": st.column_config.CheckboxColumn("🇮🇹", help="Italiano"),
            "U21": st.column_config.CheckboxColumn(
                "U21", help=f"Under 21 al {riferimento.strftime('%d/%m/%Y')}"
            ),
            "Anni": st.column_config.NumberColumn(
                "Anni", help="Anni di contratto residui"
            ),
            "Prolungato": st.column_config.CheckboxColumn(
                "Lodo Corti",
                help="Ha gia' usato il prolungamento da scambio: non se ne fanno altri.",
            ),
        },
    )
    st.caption(
        f"Under 21 valutati al {riferimento.strftime('%d/%m/%Y')} · "
        f"ingaggi dalla fonte Capology"
    )

st.divider()
st.subheader("Conformita' al regolamento")
ui.mostra_violazioni(stato.violazioni)
