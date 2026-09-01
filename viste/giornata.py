"""Giornata: gli scontri diretti, i due campi uno di fronte all'altro, il conto.

E' la pagina che si apre la domenica. Tre cose, in quest'ordine:

1. **le partite della giornata**, campionato o coppa, con il punteggio;
2. **le due formazioni disegnate**, con i punti di ogni giocatore appena i
   voti sono caricati — cosi' si vede la giornata mentre succede;
3. **il calcolo**, che spetta al presidente: carica i voti e scrive gol e
   fantapunti in calendario.

Il conto qui non si fa a mano: si chiama `fantacalcio.giornata`, che e' provato
dai test. Questa pagina mostra e scrive, non decide.
"""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.data import archivio, salva_risultato, salva_voti
from fantacalcio.formazioni import (
    Formazione,
    TabellinoSquadra,
    calcola_partita,
    schieramento,
)
from fantacalcio.giornata import (
    MODELLO_CSV_VOTI,
    VotiNonLeggibili,
    calcola_giornata,
    leggi_voti,
)

ui.barra_laterale()
schermate.mostra_messaggio()
st.markdown(tema.CSS_CAMPO, unsafe_allow_html=True)

utente = ui.utente_corrente()
lega = ui.lega_corrente()
opzioni = lega.opzioni

ui.intestazione(
    "Giornata",
    "⚔️",
    "Gli scontri diretti giornata per giornata, con le formazioni in campo.",
)

partite = ui.calendario()
if partite.empty:
    st.info(
        "Il calendario e' vuoto: prima si importano le partite dalla pagina "
        "«Importa dati», poi qui compaiono gli scontri diretti.",
        icon="🗓️",
    )
    st.stop()

nomi_squadre = ui.nomi_squadre()
nomi = ui.nomi_giocatori()
ruoli = ui.ruoli_per_giocatore()

# --- quale giornata ---------------------------------------------------------

riga = st.columns([1, 1, 2])
competizione = riga[0].selectbox(
    "Competizione",
    [c.name for c in opzioni.competizioni],
    format_func=lambda c: c.replace("_", " ").title(),
)

di_competizione = partite
if "competizione" in partite.columns:
    di_competizione = partite[partite["competizione"].astype(str) == competizione]

if di_competizione.empty:
    st.info(
        "Nessuna partita in calendario per questa competizione.",
        icon="🫥",
    )
    st.stop()

giornate = sorted({int(g) for g in di_competizione["giornata"].dropna()})
prossima = ui.giornate_disputate(di_competizione) + 1
# La chiave tiene ferma la giornata scelta quando la pagina si ricarica: dopo
# aver calcolato la 12 si resta sulla 12, invece di scivolare sulla 13 mentre
# il messaggio parla di un'altra giornata. Dipende dalla competizione perche'
# coppa e campionato non hanno le stesse giornate.
giornata = riga[1].selectbox(
    "Giornata",
    giornate,
    index=giornate.index(prossima) if prossima in giornate else len(giornate) - 1,
    key=f"_giornata_scelta_{competizione}",
)

del_turno = di_competizione[di_competizione["giornata"].astype("Int64") == int(giornata)]

formazioni = ui.formazioni(int(giornata), competizione)
voti = ui.voti(int(giornata))
parametri = ui.parametri_punteggio()
fasce = opzioni.fasce_difesa if opzioni.modificatore_difesa else ()
# Senza sostituzioni automatiche non entra nessuno: chi resta senza voto vale
# zero, ed e' una scelta della lega, non un caso limite.
sostituzioni_massime = (
    opzioni.sostituzioni_massime if opzioni.sostituzioni_automatiche else 0
)

with riga[2]:
    schierate = sum(
        1
        for _, p in del_turno.iterrows()
        for s in (int(p["casa_id"]), int(p["trasferta_id"]))
        if s in formazioni
    )
    st.markdown(
        tema.scheda(
            f"Giornata {int(giornata)}",
            f"{len(del_turno)} partite · "
            + (
                "una formazione salvata"
                if schierate == 1
                else f"{schierate} formazioni salvate"
            )
            + " · "
            + (f"{len(voti)} voti caricati" if voti else "voti non ancora caricati"),
            icona="📊",
        ),
        unsafe_allow_html=True,
    )

st.divider()

# --- le partite -------------------------------------------------------------


def campo_di(formazione: Formazione, tabellino: TabellinoSquadra | None) -> str:
    """Il campo di una squadra: i nomi, e i punti quando i voti ci sono.

    Quando c'e' il tabellino si disegna **chi ha davvero giocato**: al posto
    di chi e' rimasto senza voto compare il sostituto entrato, evidenziato.
    """
    if tabellino is None:
        return tema.campo(
            [
                [
                    tema.maglia_in_campo(nomi.get(g, str(g)), "/".join(ruoli.get(g, ())))
                    for g in giocatori
                ]
                for _, giocatori in schieramento(formazione)
            ]
        )

    entrati = {s.entrato for s in tabellino.sostituzioni}
    a_zero = set(tabellino.senza_voto)
    adattati = set(tabellino.adattati)
    scorrimento = iter(tabellino.schierati)
    reparti = []
    for _, giocatori in schieramento(formazione):
        riga_maglie = []
        for _ in giocatori:
            _, giocatore, punti = next(scorrimento)
            ruolo = "/".join(ruoli.get(giocatore, ()))
            if giocatore in adattati:
                ruolo = f"{ruolo} · adattato" if ruolo else "adattato"
            riga_maglie.append(
                tema.maglia_in_campo(
                    nomi.get(giocatore, str(giocatore)),
                    ruolo,
                    punti=punti,
                    entrato=giocatore in entrati,
                    senza_voto=giocatore in a_zero and giocatore not in entrati,
                )
            )
        reparti.append(riga_maglie)
    return tema.campo(reparti)


def mostra_partita(partita) -> None:
    """Una partita: intestazione col risultato e i due campi affiancati."""
    casa_id, trasferta_id = int(partita["casa_id"]), int(partita["trasferta_id"])
    casa = nomi_squadre.get(casa_id, str(casa_id))
    trasferta = nomi_squadre.get(trasferta_id, str(trasferta_id))

    scritto = not pd.isna(partita.get("gol_casa"))
    esito = None
    if casa_id in formazioni and trasferta_id in formazioni and voti:
        esito = calcola_partita(
            formazioni[casa_id],
            formazioni[trasferta_id],
            voti,
            ruoli,
            parametri,
            opzioni.bonus,
            fasce,
            sostituzioni_massime,
            opzioni.modalita_sostituzioni,
        )

    if scritto:
        titolo = (
            f"{casa} **{int(partita['gol_casa'])} - "
            f"{int(partita['gol_trasferta'])}** {trasferta}"
        )
        sotto = (
            f"{float(partita['punti_casa']):.1f} — "
            f"{float(partita['punti_trasferta']):.1f} fantapunti · risultato salvato"
        )
    elif esito is not None:
        titolo = f"{casa} **{esito.casa.gol} - {esito.trasferta.gol}** {trasferta}"
        sotto = (
            f"{esito.casa.totale:.1f} — {esito.trasferta.totale:.1f} fantapunti · "
            "provvisorio, non ancora salvato"
        )
    else:
        titolo = f"{casa} — {trasferta}"
        sotto = "da giocare"

    st.markdown(f"### {titolo}")
    st.caption(sotto)

    colonne = st.columns(2)
    for colonna, squadra_id, tabellino in (
        (colonne[0], casa_id, esito.casa if esito else None),
        (colonne[1], trasferta_id, esito.trasferta if esito else None),
    ):
        with colonna:
            st.markdown(f"**{nomi_squadre.get(squadra_id, squadra_id)}**")
            formazione = formazioni.get(squadra_id)
            if formazione is None:
                st.warning("Non ha schierato la formazione.", icon="⚠️")
                continue
            st.caption(formazione.modulo)
            st.markdown(campo_di(formazione, tabellino), unsafe_allow_html=True)
            if tabellino is not None:
                if tabellino.modificatore_difesa:
                    st.caption(
                        f"Modificatore difesa: {tabellino.modificatore_difesa:+.1f}"
                    )
                if tabellino.malus_adattamento:
                    quanti = len(tabellino.adattati)
                    st.caption(
                        f"Fuori posizione: {quanti} "
                        + ("giocatore" if quanti == 1 else "giocatori")
                        + f" ({tabellino.malus_adattamento:+.1f})"
                    )
                for sostituzione in tabellino.sostituzioni:
                    st.caption(
                        f"↔ {nomi.get(sostituzione.entrato, '?')} per "
                        f"{nomi.get(sostituzione.uscito, '?')}"
                        + (" · adattato" if sostituzione.adattato else "")
                    )
                rimasti = [
                    nomi.get(g, str(g))
                    for g in tabellino.senza_voto
                    if g not in {s.uscito for s in tabellino.sostituzioni}
                ]
                if rimasti:
                    st.caption(f"Senza voto e senza cambio: {', '.join(rimasti)}")
            elif formazione.panchina:
                st.caption(
                    "Panchina: "
                    + ", ".join(nomi.get(g, str(g)) for g in formazione.panchina)
                )


for indice, (_, partita) in enumerate(del_turno.iterrows()):
    if indice:
        st.divider()
    mostra_partita(partita)

# --- voti e calcolo, solo per il presidente ---------------------------------

st.divider()

if not utente.puo_importare:
    st.caption("I voti li carica il presidente di lega, che poi calcola la giornata.")
    st.stop()

st.subheader("Voti e calcolo della giornata")
st.caption(
    "Prima i voti, poi il calcolo: senza voti non si calcola niente. I voti "
    "si prendono da Fantacalcio o dall'app della lega e si incollano qui — "
    "il sito non riesce a scaricarli da solo (vedi «Punti aperti»)."
)

carica, calcola = st.tabs(["📥 Carica i voti", "⚡ Calcola"])

with carica:
    st.download_button(
        "📄 Scarica il modello dei voti",
        MODELLO_CSV_VOTI,
        file_name="voti-modello.csv",
        mime="text/csv",
    )
    st.caption(
        "Servono almeno «giocatore» (o «id» del listone) e «voto». Le altre "
        "colonne — gol, assist, ammonizioni, espulsioni, rigori, autogol, "
        "gol subiti, imbattuto — si aggiungono se ci sono. Un voto lasciato in "
        "bianco vuol dire **senza voto**, che non e' uno zero."
    )

    caricato = st.file_uploader("File dei voti (CSV o testo)", key="_voti_file")
    incollato = st.text_area(
        "…oppure incolla qui la tabella",
        height=160,
        placeholder="giocatore;voto;gol;assist\nDybala;7;1;1",
        key="_voti_incollati",
    )
    contenuto = caricato.getvalue() if caricato is not None else incollato

    if st.button("📥 Leggi e salva i voti", type="primary", use_container_width=True):
        if not contenuto:
            st.error("Non ho ne' un file ne' del testo da leggere.", icon="⛔")
        else:
            per_nome, per_id_ufficiale = ui.abbinamento_voti()
            try:
                esito_voti = leggi_voti(
                    contenuto, int(giornata), per_nome, per_id_ufficiale
                )
            except VotiNonLeggibili as errore:
                st.error(str(errore), icon="⛔")
            else:
                try:
                    quanti = salva_voti(archivio(), esito_voti.voti)
                except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
                    st.error(f"Non riesco a salvare i voti: {errore}", icon="⛔")
                else:
                    ui.invalida_dati()
                    messaggio = f"{quanti} voti salvati per la giornata {int(giornata)}."
                    if esito_voti.senza_voto:
                        messaggio += f" {esito_voti.senza_voto} senza voto."
                    if esito_voti.non_abbinati:
                        messaggio += (
                            f" Non abbinati ({len(esito_voti.non_abbinati)}): "
                            + ", ".join(esito_voti.non_abbinati[:10])
                            + ("…" if len(esito_voti.non_abbinati) > 10 else "")
                        )
                    st.session_state[schermate.CHIAVE_MESSAGGIO] = ("success", messaggio)
                    st.rerun()

with calcola:
    if not voti:
        st.warning(
            "Per questa giornata non ci sono voti: caricali nella scheda "
            "accanto, poi torna qui.",
            icon="📭",
        )
    senza_formazione = sorted(
        nomi_squadre.get(s, str(s))
        for _, p in del_turno.iterrows()
        for s in (int(p["casa_id"]), int(p["trasferta_id"]))
        if s not in formazioni
    )
    if senza_formazione:
        st.warning(
            "Queste squadre non hanno schierato: "
            f"{', '.join(senza_formazione)}. Le loro partite restano da "
            "calcolare finche' non c'e' una formazione.",
            icon="⚠️",
        )

    st.caption(
        "Il calcolo riscrive gol e fantapunti delle partite di questa "
        "giornata: si puo' rifare quando arrivano voti corretti."
    )
    if st.button(
        f"⚡ Calcola la giornata {int(giornata)}",
        type="primary",
        disabled=not voti,
        use_container_width=True,
    ):
        esito = calcola_giornata(
            int(giornata),
            [
                {
                    "id": int(p["id"]),
                    "casa_id": int(p["casa_id"]),
                    "trasferta_id": int(p["trasferta_id"]),
                }
                for _, p in del_turno.iterrows()
            ],
            formazioni,
            voti,
            ruoli,
            parametri,
            opzioni.bonus,
            fasce,
            sostituzioni_massime,
            opzioni.modalita_sostituzioni,
        )
        scritte = 0
        guasti: list[str] = []
        for risultato in esito.risultati:
            if not risultato.calcolata:
                continue
            try:
                salva_risultato(
                    archivio(),
                    risultato.partita_id,
                    risultato.esito.casa.gol,
                    risultato.esito.trasferta.gol,
                    risultato.esito.casa.totale,
                    risultato.esito.trasferta.totale,
                )
            except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
                guasti.append(f"partita {risultato.partita_id}: {errore}")
            else:
                scritte += 1

        for avviso in esito.avvisi:
            st.warning(avviso, icon="⚠️")
        for guasto in guasti:
            st.error(f"Non riesco a salvare {guasto}", icon="⛔")
        if scritte:
            ui.invalida_dati()
            saltate = len(esito.risultati) - esito.calcolate
            messaggio = f"Giornata {int(giornata)}: {scritte} partite calcolate."
            if saltate:
                messaggio += f" {saltate} saltate per formazione mancante."
            st.session_state[schermate.CHIAVE_MESSAGGIO] = ("success", messaggio)
            st.rerun()
        elif not guasti and not esito.avvisi:
            st.info("Non c'era niente da calcolare.", icon="🫥")
