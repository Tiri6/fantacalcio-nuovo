"""Bacheca della lega: notizie, comunicazioni e recap di giornata.

E' la pagina d'ingresso: la prima cosa che vede chi entra e' cosa e' successo,
non una tabella di contratti. Scrive chi amministra, leggono tutti.

Il testo degli annunci si rende con `st.markdown` **senza**
`unsafe_allow_html`: Streamlit scuda l'HTML, quindi un annuncio non puo'
iniettare markup nella pagina di chi legge.
"""

import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.bacheca import (
    TESTO_MASSIMO,
    Annuncio,
    AnnuncioNonValido,
    NonAutorizzato,
    TipoAnnuncio,
    crea_annuncio,
    filtra_per_tipo,
    modifica,
    puo_pubblicare,
    visibili_per,
)
from fantacalcio.data import archivio, elimina_annuncio, prossimo_id, salva_annuncio

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
amministra = puo_pubblicare(utente, lega)

ui.intestazione(
    "Bacheca",
    "📣",
    f"Cosa succede in {lega.nome}: notizie, comunicazioni e recap di giornata.",
)

annunci = visibili_per(ui.annunci(), utente, lega)


# --- scrittura --------------------------------------------------------------


def _salva(nuovo: Annuncio, messaggio: str) -> None:
    try:
        salva_annuncio(archivio(), nuovo)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare l'annuncio: {errore}", icon="⛔")
        return
    ui.invalida_dati()
    st.session_state[schermate.CHIAVE_MESSAGGIO] = ("success", messaggio)
    st.rerun()


def modulo_scrittura() -> None:
    """Editor dell'annuncio. Fuori da un form: l'anteprima si aggiorna sola."""
    tipo = st.selectbox(
        "Tipo",
        list(TipoAnnuncio),
        format_func=lambda t: f"{t.icona} {t.etichetta}",
        key="_nuovo_tipo",
    )
    titolo = st.text_input(
        "Titolo", key="_nuovo_titolo", placeholder="La giornata in tre righe"
    )
    testo = st.text_area(
        "Testo",
        key="_nuovo_testo",
        height=220,
        max_chars=TESTO_MASSIMO,
        placeholder=(
            "Si scrive in Markdown:\n\n"
            "**grassetto**, *corsivo*, - elenchi, [link](https://...)"
        ),
    )

    riga = st.columns(3)
    giornata = riga[0].number_input(
        "Giornata di riferimento",
        min_value=0,
        max_value=76,
        value=0,
        step=1,
        help="Zero se l'annuncio non riguarda una giornata in particolare.",
    )
    evidenza = riga[1].toggle("Metti in evidenza", help="Resta in cima alla bacheca.")
    bozza = riga[2].toggle(
        "Salva come bozza", help="La vedi solo tu, finche' non la pubblichi."
    )

    if testo.strip():
        with st.expander("Anteprima", expanded=True):
            st.markdown(f"#### {titolo or '(senza titolo)'}")
            st.markdown(testo)

    if not st.button("Pubblica", type="primary", use_container_width=True):
        return

    try:
        nuovo = crea_annuncio(
            id_=prossimo_id(archivio(), "annunci"),
            lega=lega,
            utente=utente,
            titolo=titolo,
            testo=testo,
            tipo=tipo,
            giornata=int(giornata) or None,
            pubblicato=not bozza,
            in_evidenza=bool(evidenza),
        )
    except (AnnuncioNonValido, NonAutorizzato) as errore:
        st.error(str(errore), icon="⛔")
        return

    for chiave in ("_nuovo_titolo", "_nuovo_testo"):
        st.session_state.pop(chiave, None)
    _salva(nuovo, "Bozza salvata." if bozza else f"«{nuovo.titolo}» pubblicato.")


if amministra:
    with st.expander("✍️ Scrivi un annuncio", expanded=not annunci):
        modulo_scrittura()
else:
    st.caption("Solo chi amministra la lega puo' scrivere in bacheca.")


# --- lettura ----------------------------------------------------------------

st.divider()

if not annunci:
    st.info(
        "La bacheca e' vuota. Il primo annuncio lo scrive chi amministra la lega.",
        icon="📭",
    )
    st.stop()

presenti = [t for t in TipoAnnuncio if any(a.tipo is t for a in annunci)]
if len(presenti) > 1:
    scelta = st.radio(
        "Filtra",
        [None, *presenti],
        format_func=lambda t: "Tutto" if t is None else f"{t.icona} {t.etichetta}",
        horizontal=True,
        label_visibility="collapsed",
    )
    annunci = filtra_per_tipo(annunci, scelta)


def intestazione_annuncio(a: Annuncio) -> None:
    etichette = [tema.pastiglia(f"{a.tipo.icona} {a.tipo.etichetta}")]
    if a.in_evidenza:
        etichette.append(tema.pastiglia("📌 In evidenza", tema.AMBRA))
    if a.e_bozza:
        etichette.append(tema.pastiglia("Bozza", tema.ROSSO))
    if a.giornata:
        etichette.append(tema.pastiglia(f"Giornata {a.giornata}", tema.AZZURRO))
    st.markdown(" ".join(etichette), unsafe_allow_html=True)
    st.markdown(f"### {a.titolo}")
    firma = a.autore_nome or "chi amministra"
    st.caption(f"{firma} · {a.data_leggibile}")


for annuncio in annunci:
    with st.container(border=True):
        intestazione_annuncio(annuncio)
        # Niente unsafe_allow_html: il testo lo scrive una persona.
        st.markdown(annuncio.testo)

        if not amministra:
            continue

        azioni = st.columns([1, 1, 1, 3])
        chiave = f"_ann_{annuncio.id}"

        etichetta = "Togli evidenza" if annuncio.in_evidenza else "Metti in evidenza"
        if azioni[0].button(etichetta, key=f"{chiave}_ev"):
            _salva(
                modifica(annuncio, utente, lega, in_evidenza=not annuncio.in_evidenza),
                "Evidenza aggiornata.",
            )

        etichetta = "Pubblica" if annuncio.e_bozza else "Riporta a bozza"
        if azioni[1].button(etichetta, key=f"{chiave}_pub"):
            _salva(
                modifica(annuncio, utente, lega, pubblicato=annuncio.e_bozza),
                "Pubblicato." if annuncio.e_bozza else "Riportato a bozza.",
            )

        # Due passaggi: un annuncio cancellato non si recupera.
        if azioni[2].button("Elimina", key=f"{chiave}_del"):
            st.session_state[f"{chiave}_conferma"] = True

        if st.session_state.get(f"{chiave}_conferma"):
            st.warning(f"Eliminare «{annuncio.titolo}»? Non si torna indietro.", icon="⚠️")
            conferma = st.columns([1, 1, 4])
            if conferma[0].button("Sì, elimina", key=f"{chiave}_si", type="primary"):
                try:
                    elimina_annuncio(archivio(), annuncio.id)
                except Exception as errore:  # noqa: BLE001 - backend diversi
                    st.error(f"Non riesco a eliminare: {errore}", icon="⛔")
                else:
                    st.session_state.pop(f"{chiave}_conferma", None)
                    ui.invalida_dati()
                    st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                        "success",
                        f"«{annuncio.titolo}» eliminato.",
                    )
                    st.rerun()
            if conferma[1].button("Annulla", key=f"{chiave}_no"):
                st.session_state.pop(f"{chiave}_conferma", None)
                st.rerun()
