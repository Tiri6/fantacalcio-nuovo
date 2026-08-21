"""Identita' delle squadre: presidente, motto, stadio, colori, maglia e logo."""

import streamlit as st

from fantacalcio import ui
from fantacalcio.data import archivio, prossimo_id, salva_squadra
from fantacalcio.identita import (
    ColoreNonValido,
    IdentitaSquadra,
    ImmagineNonValida,
    StileMaglia,
    immagine_a_data_uri,
)
from fantacalcio.modelli import Squadra

NUOVA = "➕ Crea una squadra nuova"

ui.intestazione(
    "Identita' delle squadre",
    "🎨",
    "Presidente, motto, stadio, citta', curva, colori sociali, maglia e logo.",
)
ui.barra_laterale()

# La conferma resta nel session_state finche' non se ne salva un'altra: cosi'
# sopravvive ai rerun che Streamlit fa dopo la scrittura.
if messaggio := st.session_state.get("esito_identita"):
    st.success(messaggio, icon="✅")

rose = ui.rose()
squadre = {rosa.squadra.nome: rosa.squadra for rosa in rose.values()}

galleria, scheda = st.tabs(["Galleria della lega", "Crea o modifica"])

with galleria:
    st.caption("Le maglie sono disegnate dai colori sociali di ogni squadra.")
    nomi = sorted(squadre)
    for inizio in range(0, len(nomi), 5):
        colonne = st.columns(5)
        for colonna, nome in zip(colonne, nomi[inizio : inizio + 5], strict=False):
            squadra = squadre[nome]
            with colonna:
                ui.mostra_maglia(squadra, larghezza=130)
                st.markdown(f"**{nome}**")
                if squadra.presidente:
                    st.caption(f"Presidente: {squadra.presidente}")
                if squadra.motto:
                    st.caption(f"_{squadra.motto}_")
                if squadra.stadio:
                    casa = squadra.stadio
                    if squadra.citta:
                        casa += f", {squadra.citta}"
                    st.caption(f"🏟️ {casa}")
                elif squadra.citta:
                    st.caption(f"📍 {squadra.citta}")
                if squadra.curva:
                    st.caption(f"📣 {squadra.curva}")

with scheda:
    scelta = st.selectbox("Squadra", [NUOVA, *sorted(squadre)])
    nuova = scelta == NUOVA
    squadra = None if nuova else squadre[scelta]
    identita = squadra.identita if squadra else IdentitaSquadra()

    modulo, anteprima = st.columns([3, 2])

    with modulo:
        nome = st.text_input(
            "Nome della squadra", value="" if nuova else squadra.nome, max_chars=60
        )
        presidente = st.text_input("Presidente", value=identita.presidente, max_chars=60)
        motto = st.text_input(
            "Motto",
            value=identita.motto,
            max_chars=120,
            placeholder="Chi non risica non rosica",
        )
        stadio = st.text_input(
            "Stadio", value=identita.stadio, max_chars=80, placeholder="Arena del Padel"
        )
        affiancate = st.columns(2)
        citta = affiancate[0].text_input(
            "Citta'", value=identita.citta, max_chars=60, placeholder="Ginevra"
        )
        curva = affiancate[1].text_input(
            "Curva",
            value=identita.curva,
            max_chars=60,
            placeholder="Curva Nord",
            help="Come si chiama il settore dei tuoi tifosi.",
        )
        anno = st.number_input(
            "Anno di fondazione",
            min_value=1900,
            max_value=2100,
            value=identita.anno_fondazione or 2026,
        )

        st.subheader("Colori sociali")
        colonna_primario, colonna_secondario = st.columns(2)
        primario = colonna_primario.color_picker(
            "Colore primario", value=identita.colore_primario
        )
        secondario = colonna_secondario.color_picker(
            "Colore secondario", value=identita.colore_secondario
        )
        stile = st.selectbox(
            "Disegno della maglia",
            options=list(StileMaglia),
            index=list(StileMaglia).index(identita.stile_maglia),
            format_func=lambda s: s.value,
        )

        st.subheader("Immagini (facoltative)")
        st.caption(
            "Il logo e' opzionale: senza, la squadra e' comunque riconoscibile "
            "dalla maglia. Massimo 512 KB per file."
        )
        file_logo = st.file_uploader(
            "Logo", type=["png", "jpg", "jpeg", "webp", "svg"], key="logo"
        )
        file_maglia = st.file_uploader(
            "Maglia personalizzata (sostituisce quella disegnata)",
            type=["png", "jpg", "jpeg", "webp", "svg"],
            key="maglia",
        )
        rimuovi_maglia = st.checkbox(
            "Torna alla maglia disegnata dai colori",
            value=False,
            disabled=not identita.maglia_caricata,
        )

    # --- anteprima dal vivo -------------------------------------------------
    errore_colori = None
    try:
        anteprima_identita = IdentitaSquadra(
            presidente=presidente,
            motto=motto,
            stadio=stadio,
            citta=citta,
            curva=curva,
            colore_primario=primario,
            colore_secondario=secondario,
            stile_maglia=stile,
            logo=identita.logo,
            maglia_caricata=None if rimuovi_maglia else identita.maglia_caricata,
            anno_fondazione=int(anno),
        )
    except ColoreNonValido as errore:
        anteprima_identita = None
        errore_colori = str(errore)

    with anteprima:
        st.subheader("Anteprima")
        if anteprima_identita is None:
            st.error(errore_colori)
        else:
            ui.mostra_maglia(anteprima_identita, larghezza=180)
            st.markdown(
                ui.pastiglia_colore(primario, "Primario")
                + "&nbsp;&nbsp;"
                + ui.pastiglia_colore(secondario, "Secondario"),
                unsafe_allow_html=True,
            )
            if not anteprima_identita.colori_distinguibili:
                st.warning(
                    "I due colori sono troppo simili: da lontano la maglia "
                    "sembrera' a tinta unita.",
                    icon="⚠️",
                )
            if identita.logo:
                ui.mostra_logo(identita)
            st.markdown(f"### {nome or 'Senza nome'}")
            if motto:
                st.caption(f"_{motto}_")

    # --- salvataggio --------------------------------------------------------
    st.divider()
    problemi = []
    if not nome.strip():
        problemi.append("Il nome della squadra e' obbligatorio.")
    if not presidente.strip():
        problemi.append("Il nome del presidente e' obbligatorio.")
    altri_nomi = {n.lower() for n in squadre if nuova or n != scelta}
    if nome.strip().lower() in altri_nomi:
        problemi.append(f"Esiste gia' una squadra chiamata «{nome.strip()}».")
    if errore_colori:
        problemi.append(errore_colori)

    for problema in problemi:
        st.error(problema, icon="⛔")

    if st.button(
        "Crea la squadra" if nuova else "Salva le modifiche",
        type="primary",
        disabled=bool(problemi),
    ):
        try:
            logo = identita.logo
            if file_logo is not None:
                logo = immagine_a_data_uri(file_logo.getvalue(), file_logo.type)

            maglia_caricata = None if rimuovi_maglia else identita.maglia_caricata
            if file_maglia is not None:
                maglia_caricata = immagine_a_data_uri(
                    file_maglia.getvalue(), file_maglia.type
                )

            definitiva = IdentitaSquadra(
                presidente=presidente.strip(),
                motto=motto.strip(),
                stadio=stadio.strip(),
                citta=citta.strip(),
                curva=curva.strip(),
                colore_primario=primario,
                colore_secondario=secondario,
                stile_maglia=stile,
                logo=logo,
                maglia_caricata=maglia_caricata,
                anno_fondazione=int(anno),
            )
            arch = archivio()
            identificativo = prossimo_id(arch, "squadre") if nuova else squadra.id
            salva_squadra(
                arch,
                Squadra(
                    id=identificativo,
                    nome=nome.strip(),
                    presidente=definitiva.presidente,
                    identita=definitiva,
                ),
            )
        except (ImmagineNonValida, ColoreNonValido) as errore:
            st.error(str(errore), icon="⛔")
        else:
            ui.invalida_dati()
            azione = "creata" if nuova else "salvata"
            # Il messaggio va nel session_state e si mostra al giro successivo:
            # st.rerun() scarta tutto cio' che e' stato disegnato in questo.
            st.session_state["esito_identita"] = (
                f"«{nome.strip()}» {azione}. La trovi nella galleria."
            )
            st.rerun()
