"""Registro degli scambi: proposte ricevute, inviate e storico (art. 8)."""

from datetime import datetime

import pandas as pd
import streamlit as st

from fantacalcio import ui
from fantacalcio.data import archivio
from fantacalcio.mercato import valida_scambio
from fantacalcio.scambi import (
    StatoScambio,
    TransizioneNonAmmessa,
    accetta,
    annulla,
    applica_alle_rose,
    conta_conclusi,
    giornata_di_efficacia,
    ratifica,
    rifiuta,
    salva_scambio,
    scambi_residui,
)

STAGIONE = "2026/27"  # usata dalle transizioni; la lega ha la sua in `lega.stagione`

utente = ui.richiedi_login()
ui.intestazione(
    "Scambi",
    "🤝",
    "Ogni scambio ha una storia: chi l'ha proposto, chi l'ha accettato, "
    "chi l'ha ratificato.",
)
ui.barra_laterale()

if messaggio := st.session_state.get("esito_scambi"):
    st.success(messaggio, icon="✅")

rose = ui.rose()
nomi = ui.nomi_squadre()
utenti = ui.nomi_utenti()
registro = ui.scambi()
giornate = ui.giornate_disputate(ui.calendario())

lega = ui.lega_corrente()
opzioni = lega.opzioni

# --- quanti scambi ho ancora -----------------------------------------------

if utente.squadra_id is not None:
    mia_rosa = rose.get(utente.squadra_id)
    fatti = conta_conclusi(registro, utente.squadra_id, lega.stagione)
    residui = scambi_residui(
        registro, utente.squadra_id, opzioni.scambi_per_stagione, lega.stagione
    )
    prolungati = mia_rosa.prolungamenti_stagione(lega.stagione) if mia_rosa else 0
    massimi = ui.parametri().prolungamenti_per_squadra_a_stagione

    ui.griglia_dati(
        [
            {
                "etichetta": "Scambi conclusi",
                "valore": str(fatti),
                "nota": (
                    "senza limite" if residui is None else f"{residui} ancora disponibili"
                ),
                "stato": "male" if residui == 0 else "ok",
                "quota": (
                    None
                    if residui is None
                    else fatti / max(opzioni.scambi_per_stagione, 1)
                ),
            },
            {
                "etichetta": "Prolungamenti usati",
                "valore": f"{prolungati}/{massimi}",
                "nota": "Lodo Longoni, per stagione",
                "stato": "avviso" if prolungati >= massimi else "ok",
            },
        ]
    )

    if residui == 0:
        st.warning(
            f"Hai esaurito i {opzioni.scambi_per_stagione} scambi previsti per "
            f"questa stagione. Le proposte in corso restano valide.",
            icon="🔒",
        )

    with st.expander("Come funzionano i prolungamenti negli scambi"):
        st.markdown(
            f"""
**Lodo Longoni** — scambiando un giocatore, chi lo riceve puo' **allungargli
il contratto**, se ha anni liberi nel monte anni. Dybala arriva con 1 anno
residuo e puoi portarlo a 3: i due anni in piu' si scalano dal tuo monte.
Il prolungamento si compone dalla pagina «Componi scambio», insieme allo
scambio stesso. Massimo **{massimi} per squadra a stagione**.

**Lodo Corti** — ogni giocatore puo' beneficiarne **una volta sola** nell'arco
della vita residua del suo contratto. Chi e' gia' stato prolungato ha la
spunta nella colonna «Lodo Corti» della pagina Squadre, e un secondo
prolungamento viene rifiutato.

**Lodo Bono** — il contratto non si puo' accorciare in sede di scambio.
"""
        )

    st.divider()


def descrivi(scambio) -> str:
    a = nomi.get(scambio.squadra_a_id, "?")
    b = nomi.get(scambio.squadra_b_id, "?")
    return f"{a} ⇄ {b}"


def tabella_movimenti(scambio) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Giocatore": m.nome_giocatore,
                "Da": nomi.get(m.da_squadra_id, "?"),
                "A": nomi.get(m.a_squadra_id, "?"),
                "Anni": (
                    f"{m.anni_prima} → {m.anni_dopo}"
                    if m.prolungato
                    else str(m.anni_prima)
                ),
                "Prolungato": "Si" if m.prolungato else "",
            }
            for m in scambio.movimenti
        ]
    )


def registra(scambio, esito: str) -> None:
    salva_scambio(archivio(), scambio)
    ui.invalida_dati()
    st.session_state["esito_scambi"] = esito
    st.rerun()


def scheda(scambio, azioni: bool) -> None:
    stato = scambio.stato
    icona = {
        StatoScambio.PROPOSTO: "🕓",
        StatoScambio.ACCETTATO: "🤝",
        StatoScambio.RATIFICATO: "✅",
        StatoScambio.RIFIUTATO: "🚫",
        StatoScambio.ANNULLATO: "↩️",
    }[stato]

    with st.expander(
        f"{icona} {descrivi(scambio)} · {stato.etichetta} · "
        f"{scambio.creato_il:%d/%m %H:%M}",
        expanded=azioni and stato.aperto,
    ):
        st.caption(
            f"Proposto da {utenti.get(scambio.proposto_da, 'ignoto')}"
            + (f" · Nota: {scambio.note}" if scambio.note else "")
        )
        if not scambio.movimenti:
            st.caption("Nessun movimento registrato.")
        else:
            st.dataframe(
                tabella_movimenti(scambio), hide_index=True, use_container_width=True
            )

        if scambio.giornata_efficacia:
            st.caption(f"Efficace dalla {scambio.giornata_efficacia}ª giornata.")

        if not azioni or not stato.aperto:
            return

        rosa_a = rose.get(scambio.squadra_a_id)
        rosa_b = rose.get(scambio.squadra_b_id)
        if rosa_a is None or rosa_b is None:
            st.error("Una delle due squadre non esiste piu'.", icon="⛔")
            return

        # Le rose possono essere cambiate dopo la proposta: si ricontrolla.
        violazioni = valida_scambio(
            rosa_a, rosa_b, scambio.a_proposta(), STAGIONE, ui.parametri()
        )
        ui.mostra_violazioni(violazioni)
        bloccato = any(v.bloccante for v in violazioni)

        colonne = st.columns(3)

        if stato is StatoScambio.PROPOSTO and (
            utente.puo_gestire(scambio.squadra_b_id) or utente.e_presidente
        ):
            if colonne[0].button(
                "Accetta", key=f"acc{scambio.id}", type="primary", disabled=bloccato
            ):
                registra(accetta(scambio, utente), "Scambio accettato.")
            if colonne[1].button("Rifiuta", key=f"rif{scambio.id}"):
                registra(rifiuta(scambio, utente), "Scambio rifiutato.")

        puo_ritirare = utente.puo_gestire(scambio.squadra_a_id) or utente.e_presidente
        if puo_ritirare and colonne[2].button("Ritira", key=f"ann{scambio.id}"):
            registra(annulla(scambio, utente), "Proposta ritirata.")

        if stato is StatoScambio.ACCETTATO and utente.puo_importare:
            st.divider()
            st.markdown("**Ratifica (presidente)**")
            st.caption(
                "Art. 8: lo scambio va comunicato almeno 24 ore prima dell'inizio "
                "della giornata. Se il termine e' scaduto vale da quella successiva."
            )
            usa_orario = st.checkbox(
                "Conosco l'orario di inizio della prossima giornata",
                key=f"orario{scambio.id}",
            )
            inizio = None
            if usa_orario:
                giorno = st.date_input("Data", key=f"data{scambio.id}")
                ora = st.time_input("Ora", key=f"ora{scambio.id}")
                inizio = datetime.combine(giorno, ora)

            efficacia = giornata_di_efficacia(
                scambio, giornate + 1, inizio, ui.parametri()
            )
            st.caption(f"Avrebbe effetto dalla {efficacia}ª giornata.")

            if st.button(
                "Ratifica lo scambio",
                key=f"rat{scambio.id}",
                type="primary",
                disabled=bloccato,
            ):
                try:
                    ratificato, nuova_a, nuova_b = ratifica(
                        scambio,
                        rosa_a,
                        rosa_b,
                        utente,
                        STAGIONE,
                        giornata_efficacia=efficacia,
                        parametri=ui.parametri(),
                    )
                except TransizioneNonAmmessa as errore:
                    st.error(str(errore), icon="⛔")
                else:
                    applica_alle_rose(archivio(), nuova_a, nuova_b)
                    registra(
                        ratificato,
                        f"Scambio ratificato: efficace dalla {efficacia}ª giornata.",
                    )


mia = utente.squadra_id
ricevute = [
    s for s in registro if s.stato is StatoScambio.PROPOSTO and s.squadra_b_id == mia
]
inviate = [s for s in registro if s.stato.aperto and s.squadra_a_id == mia]
da_ratificare = [s for s in registro if s.stato is StatoScambio.ACCETTATO]
storico = [s for s in registro if not s.stato.aperto]

etichette = [
    f"Ricevute ({len(ricevute)})",
    f"Inviate ({len(inviate)})",
    f"Storico ({len(storico)})",
]
if utente.puo_importare:
    etichette.insert(2, f"Da ratificare ({len(da_ratificare)})")

schede = st.tabs(etichette)
indice = 0

with schede[indice]:
    if not ricevute:
        st.info("Nessuna proposta in attesa di una tua risposta.", icon="📭")
    for scambio in ricevute:
        scheda(scambio, azioni=True)
indice += 1

with schede[indice]:
    if not inviate:
        st.info("Non hai proposte aperte.", icon="📭")
    for scambio in inviate:
        scheda(scambio, azioni=True)
indice += 1

if utente.puo_importare:
    with schede[indice]:
        if not da_ratificare:
            st.info("Nessuno scambio in attesa di ratifica.", icon="📭")
        for scambio in da_ratificare:
            scheda(scambio, azioni=True)
    indice += 1

with schede[indice]:
    if not storico:
        st.caption("Lo storico si riempie quando gli scambi vengono chiusi.")
    for scambio in storico:
        scheda(scambio, azioni=False)
