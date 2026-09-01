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
    Reparto,
    adattamenti,
    formazione_suggerita,
    leggi_modulo,
    puo_occupare,
    schieramento,
    stato_blocco,
    valida,
)
from fantacalcio.leghe import ModalitaSostituzioni

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
    adattamento_ammesso = opzioni.modalita_sostituzioni is not ModalitaSostituzioni.EASY
    malus = ui.parametri_punteggio().malus_adattamento

    def etichetta_giocatore(giocatore: int, reparto: Reparto) -> str:
        """Nome, ruoli, e il prezzo se quel posto non e' il suo."""
        voce = f"{nomi.get(giocatore, giocatore)} ({'/'.join(ruoli.get(giocatore, ()))})"
        if not reparto.accetta(ruoli.get(giocatore, ())):
            voce += f" — adattato −{malus:g}"
        return voce

    st.caption(
        f"{schema.difensori} difensori · {schema.centrocampisti} centrocampisti "
        f"· {schema.attaccanti} attaccanti. "
        + (
            f"Chi occupa un posto che non e' del suo reparto gioca lo stesso, "
            f"con {malus:g} punto in meno "
            f"(modalita' {opzioni.modalita_sostituzioni.etichetta})."
            if adattamento_ammesso
            else "In modalita' Easy nessuno puo' giocare fuori posizione."
        )
    )

    # Le caselle si disegnano una dopo l'altra, e ognuna sa solo di quelle
    # gia' disegnate: mettere qui un giocatore che sta piu' avanti creerebbe
    # un doppione. Invece di lasciarlo da correggere a mano, le due caselle si
    # scambiano — che e' poi il gesto che si aveva in mente.
    chiavi = [f"_titolare_{giornata}_{competizione}_{i}" for i in range(TITOLARI)]
    reparto_di_posizione = [
        reparto for reparto, quanti in schema.reparti for _ in range(quanti)
    ]
    chiave_precedenti = f"_titolari_prima_{giornata}_{competizione}_{modulo}"

    def scambia_doppioni(posizione: int) -> None:
        """Chi entra qui lascia all'altra casella il giocatore che usciva."""
        prima = st.session_state.get(chiave_precedenti, {})
        entrato = st.session_state.get(chiavi[posizione])
        uscito = prima.get(posizione)
        if entrato is None or uscito is None or entrato == uscito:
            return
        for altra, chiave in enumerate(chiavi):
            if altra == posizione or st.session_state.get(chiave) != entrato:
                continue
            # Lo scambio vale solo se l'altra casella accetta chi esce: un
            # attaccante in difesa sarebbe peggio del doppione.
            ci_sta = altra < len(reparto_di_posizione) and (
                puo_occupare(reparto_di_posizione[altra], ruoli.get(uscito, ()))
                if adattamento_ammesso
                else reparto_di_posizione[altra].accetta(ruoli.get(uscito, ()))
            )
            if ci_sta:
                st.session_state[chiave] = uscito
            break

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
            # Fuori dalla modalita' Easy si puo' schierare chiunque, pagando
            # il malus — tranne che fra porta e movimento, dove il Mantra non
            # ammette adattamenti. Gli adattati stanno in fondo all'elenco e
            # lo dicono: la scelta resta possibile ma non capita per sbaglio.
            if adattamento_ammesso:
                candidati += [
                    g
                    for g in in_rosa
                    if g not in candidati
                    and g not in scelti
                    and puo_occupare(reparto, ruoli.get(g, ()))
                ]
            precedente = (
                base.titolari[posizione] if posizione < len(base.titolari) else None
            )
            # Chi era gia' in quel posto resta selezionabile: toglierlo
            # dall'elenco farebbe saltare la scelta a ogni rerun. Ma se nel
            # frattempo e' finito in una casella precedente non si ripropone,
            # altrimenti cambiando modulo lo stesso giocatore si ritrova
            # schierato due volte.
            gia_li = (
                precedente is not None
                and precedente not in candidati
                and precedente not in scelti
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
                format_func=lambda g, r=reparto: etichetta_giocatore(g, r),
                key=chiavi[posizione],
                label_visibility="collapsed",
                on_change=scambia_doppioni,
                args=(posizione,),
            )
            scelti.append(scelta)
            posizione += 1

    # Lo scambio ha bisogno di sapere chi c'era prima: il widget, quando la
    # richiamata parte, ha gia' il valore nuovo.
    st.session_state[chiave_precedenti] = dict(enumerate(scelti))

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
    problemi = valida(proposta, ruoli, set(in_rosa), opzioni.modalita_sostituzioni)
    for problema in problemi:
        st.error(problema, icon="⛔")

    # Gli adattamenti non sono errori: si salvano eccome. Ma il conto lo deve
    # sapere chi schiera, prima di premere il pulsante, non a giornata finita.
    fuori_posizione = adattamenti(proposta, ruoli)
    if fuori_posizione:
        costo = malus * len(fuori_posizione)
        st.warning(
            "Fuori posizione: "
            + ", ".join(
                f"{nomi.get(g, g)} in {r.etichetta.lower()}" for g, r in fuori_posizione
            )
            + f". Sono {len(fuori_posizione)} adattamenti: {costo:g} punti in meno.",
            icon="🔁",
        )

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
