"""Helper condivisi dalle pagine Streamlit: setup, cache e formattazioni."""

from __future__ import annotations

import base64
from datetime import date

import pandas as pd
import streamlit as st

from . import tema, vista
from .autenticazione import Credenziali, Utente, autentica
from .config import carica_impostazioni
from .conformita import Momento
from .data import (
    archivio,
    calendario_dettagliato,
    carica_credenziali,
    carica_leghe,
    carica_rose,
)
from .leghe import Lega
from .regole import CalendarioStagione, ParametriLega

TTL = 300  # secondi: la lega cambia al massimo una volta a giornata

DATA_DRAFT = date(2026, 9, 15)
CALENDARIO = CalendarioStagione(data_draft_settembre=DATA_DRAFT)


def parametri() -> ParametriLega:
    return ParametriLega()


def configura_app() -> None:
    """set_page_config va chiamata una volta sola, dal router in app.py."""
    st.set_page_config(
        page_title=carica_impostazioni().nome_lega, page_icon="⚽", layout="wide"
    )
    st.markdown(tema.CSS, unsafe_allow_html=True)


def intestazione(titolo: str, icona: str = "⚽", sottotitolo: str = "") -> None:
    """Testata di pagina: fascia scura, occhiello e sottotitolo."""
    st.markdown(
        tema.testata(f"{icona} {titolo}".strip(), sottotitolo), unsafe_allow_html=True
    )


def griglia_dati(voci: list[dict]) -> None:
    """Fila di riquadri numerici. Ogni voce: etichetta, valore, nota, stato, quota."""
    if not voci:
        return
    for colonna, voce in zip(st.columns(len(voci)), voci, strict=True):
        colonna.markdown(
            tema.dato(
                voce.get("etichetta", ""),
                voce.get("valore", ""),
                voce.get("nota", ""),
                voce.get("stato", "ok"),
                voce.get("quota"),
            ),
            unsafe_allow_html=True,
        )


CHIAVE_UTENTE = "_utente"
CHIAVE_TENTATIVI = "_tentativi_login"
MASSIMI_TENTATIVI = 5


# I dati della sessione sono il *nome utente*, non l'oggetto Utente: appena
# entri in una lega o fondi la squadra la riga cambia, e un oggetto congelato
# al momento del login mostrerebbe ancora lo stato vecchio.


@st.cache_data(ttl=TTL)
def _credenziali(versione: int) -> dict:
    return carica_credenziali(archivio())


def tutte_le_credenziali() -> dict[str, Credenziali]:
    return _credenziali(versione_dati())


def credenziali_correnti() -> Credenziali | None:
    nome = st.session_state.get(CHIAVE_UTENTE)
    return tutte_le_credenziali().get(nome) if nome else None


def utente_corrente() -> Utente | None:
    trovate = credenziali_correnti()
    return trovate.utente if trovate else None


def esci() -> None:
    for chiave in (CHIAVE_UTENTE, "_salta_squadra"):
        st.session_state.pop(chiave, None)


@st.cache_data(ttl=TTL)
def _leghe(versione: int) -> dict:
    return carica_leghe(archivio())


def leghe() -> dict[int, Lega]:
    return _leghe(versione_dati())


def lega_corrente() -> Lega | None:
    utente = utente_corrente()
    if utente is None or utente.lega_id is None:
        return None
    return leghe().get(utente.lega_id)


def _leggi_credenziali_o_spiega():
    """Carica gli utenti, traducendo i guasti del database in messaggi chiari."""
    try:
        return tutte_le_credenziali(), None
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        testo = str(errore)
        if "utenti" in testo and (
            "does not exist" in testo or "not find" in testo or "schema cache" in testo
        ):
            return None, (
                "Il database e' raggiungibile ma non ha le tabelle. Apri il SQL "
                "Editor di Supabase e incolla il contenuto di `db/schema.sql`."
            )
        if "leghe" in testo or "inviti" in testo:
            return None, (
                "Il database ha le tabelle vecchie ma non `leghe` e `inviti`. "
                "Rilancia `db/schema.sql` nel SQL Editor di Supabase: e' "
                "rieseguibile, non cancella niente."
            )
        return None, (
            f"Non riesco a leggere gli utenti dal database: {testo}\n\n"
            "Controlla SUPABASE_URL e SUPABASE_KEY nei secret. Per scrivere "
            "serve la chiave `service_role`, non la `anon`."
        )


def richiedi_login() -> Utente:
    """Mostra accesso e registrazione, e ferma la pagina finche' non sei entrato."""
    utente = utente_corrente()
    if utente is not None:
        return utente

    from . import schermate

    impostazioni = carica_impostazioni()
    st.markdown(
        tema.testata(
            impostazioni.nome_lega,
            "Il gestionale della lega: contratti, monte anni, Salary Cap, "
            "draft e scambi.",
            occhiello="Fantacalcio manageriale",
        ),
        unsafe_allow_html=True,
    )

    credenziali, guasto = _leggi_credenziali_o_spiega()
    if guasto:
        st.error(guasto, icon="⛔")
        st.stop()

    schermate.mostra_messaggio()

    primo_utente = not credenziali
    if primo_utente:
        # Database vuoto: c'e' solo una cosa sensata da fare, registrarsi.
        schermate.modulo_registrazione(credenziali, primo_utente=True)
        st.stop()

    accedi, registrati = st.tabs(["🔓 Accedi", "✍️ Registrati"])

    with registrati:
        schermate.modulo_registrazione(credenziali, primo_utente=False)

    with accedi:
        _modulo_accesso(credenziali)

    if not impostazioni.usa_supabase:
        from .demo_data import PASSWORD_DEMO

        st.info(
            f"**Modalita' demo.** Utenti di prova: `marco` (presidente), `luca`, "
            f"`giulia`... — password `{PASSWORD_DEMO}` per tutti. Con i dati veri "
            f"su Supabase questi utenti non esistono.",
            icon="🧪",
        )

    st.stop()


def _modulo_accesso(credenziali: dict[str, Credenziali]) -> None:
    tentativi = st.session_state.get(CHIAVE_TENTATIVI, 0)
    if tentativi >= MASSIMI_TENTATIVI:
        st.error(
            "Troppi tentativi falliti. Ricarica la pagina per riprovare.",
            icon="🚫",
        )
        return

    with st.form("accesso"):
        nome_utente = st.text_input("Nome utente")
        password = st.text_input("Password", type="password")
        inviato = st.form_submit_button("Entra", type="primary")

    if not inviato:
        return

    trovato = autentica(credenziali, nome_utente, password)
    if trovato is None:
        # Messaggio volutamente generico: non deve rivelare quali nomi
        # utente esistono.
        st.session_state[CHIAVE_TENTATIVI] = tentativi + 1
        st.error("Nome utente o password non corretti.", icon="⛔")
        return

    st.session_state[CHIAVE_UTENTE] = trovato.nome_utente
    st.session_state[CHIAVE_TENTATIVI] = 0
    st.rerun()


def richiedi_lega(utente: Utente) -> Lega:
    """Secondo cancello: senza una lega non c'e' niente da amministrare."""
    from . import schermate

    lega = lega_corrente()
    if lega is not None:
        return lega

    credenziali = credenziali_correnti()
    if credenziali is None:  # pragma: no cover - la sessione e' appena caduta
        esci()
        st.rerun()

    barra_laterale()
    schermate.mostra_messaggio()
    schermate.scegli_lega(utente, credenziali)
    st.stop()


def richiedi_squadra(utente: Utente, lega: Lega) -> None:
    """Terzo cancello: si puo' rimandare, ma senza squadra il sito e' vuoto.

    Rimandabile di proposito: chi amministra e basta non e' obbligato ad avere
    una squadra, e obbligarlo lo bloccherebbe fuori dal proprio gestionale.
    """
    from . import schermate

    if utente.ha_squadra or st.session_state.get("_salta_squadra"):
        return

    credenziali = credenziali_correnti()
    if credenziali is None:  # pragma: no cover - la sessione e' appena caduta
        esci()
        st.rerun()

    barra_laterale()
    schermate.mostra_messaggio()
    schermate.crea_squadra(utente, credenziali, lega)
    st.stop()


def solo_presidente(
    messaggio: str = "Questa pagina e' riservata al presidente.",
) -> Utente:
    """Blocca la pagina se chi guarda non e' il presidente di lega."""
    utente = richiedi_login()
    if not utente.puo_importare:
        st.warning(messaggio, icon="🔒")
        st.stop()
    return utente


def barra_laterale() -> None:
    """Utente, lega, backend attivo e ricarica dei dati."""
    impostazioni = carica_impostazioni()
    utente = utente_corrente()
    lega = lega_corrente()
    with st.sidebar:
        if utente is not None:
            st.markdown(f"**{utente.nome}**")
            st.caption(utente.ruolo.etichetta)
            if st.button("Esci", use_container_width=True):
                esci()
                st.rerun()
            st.divider()
        if lega is not None:
            st.markdown(f"🏆 **{lega.nome}**")
            st.caption(
                f"{lega.stagione} · {lega.opzioni.modalita.etichetta} · "
                f"{lega.opzioni.partecipanti} squadre"
            )
            st.code(lega.codice_invito, language=None)
            st.caption("Codice d'invito: giralo a chi deve entrare.")
            st.divider()
        st.caption(impostazioni.nome_lega)
        if impostazioni.usa_supabase:
            st.success("Dati live da Supabase", icon="🟢")
        else:
            st.info(
                "Modalita' demo: lega generata in locale. Aggiungi SUPABASE_URL e "
                "SUPABASE_KEY nei secret per i dati veri.",
                icon="🧪",
            )
        if st.button("Ricarica dati", use_container_width=True):
            invalida_dati()
            st.rerun()


def milioni(importo: float) -> str:
    return f"{importo / 1_000_000:.2f}M"


COLONNE_EURO = {
    nome: st.column_config.NumberColumn(format="%.2f M")
    for nome in (
        "Ingaggi",
        "Dead money",
        "Spesa",
        "Spazio cap",
        "Ingaggio",
        "Valore residuo",
        "Dead money se tagliato",
    )
}


def in_milioni(tabella: pd.DataFrame) -> pd.DataFrame:
    """Riscala le colonne in euro a milioni, per leggerle senza contare gli zeri."""
    copia = tabella.copy()
    for colonna in COLONNE_EURO:
        if colonna in copia.columns:
            copia[colonna] = copia[colonna] / 1_000_000
    return copia


# --- caricamenti in cache ---------------------------------------------------
#
# Le cache sono indicizzate su un numero di versione invece di essere svuotate
# con `cache_data.clear()`: svuotare una cache provoca un rerun immediato, che
# cancellerebbe il messaggio di conferma appena mostrato dopo un salvataggio.


@st.cache_resource
def _contatore_versione() -> dict:
    """Contatore condiviso da tutte le sessioni del server.

    Deve essere globale, non nel session_state: le cache di Streamlit sono
    comuni a tutti gli utenti collegati, quindi se il numero di versione fosse
    per sessione chi entra dopo leggerebbe la fotografia vecchia — per esempio
    senza lo scambio appena proposto da un altro.
    """
    return {"versione": 0}


def versione_dati() -> int:
    return _contatore_versione()["versione"]


def invalida_dati() -> None:
    """Da chiamare dopo ogni scrittura: tutte le sessioni ricaricano."""
    _contatore_versione()["versione"] += 1


@st.cache_data(ttl=TTL)
def _squadre(versione: int) -> pd.DataFrame:
    return archivio().squadre()


def squadre() -> pd.DataFrame:
    return _squadre(versione_dati())


@st.cache_resource(ttl=TTL)
def _rose(versione: int):
    """Le rose sono oggetti di dominio, non dati serializzabili: cache_resource."""
    return carica_rose(archivio())


def rose():
    return _rose(versione_dati())


@st.cache_data(ttl=TTL)
def _classifica(versione: int) -> pd.DataFrame:
    return vista.classifica(archivio())


def classifica() -> pd.DataFrame:
    return _classifica(versione_dati())


@st.cache_data(ttl=TTL)
def _calendario(versione: int) -> pd.DataFrame:
    return calendario_dettagliato(archivio())


def calendario() -> pd.DataFrame:
    return _calendario(versione_dati())


@st.cache_data(ttl=TTL)
def _andamento_punti(versione: int) -> pd.DataFrame:
    return vista.andamento_punti(archivio())


def andamento_punti() -> pd.DataFrame:
    return _andamento_punti(versione_dati())


def stati(momento: Momento = Momento.STAGIONE):
    return vista.stati_rose(rose(), DATA_DRAFT, parametri(), momento)


def giornate_disputate(partite: pd.DataFrame) -> int:
    giocate = partite[partite["gol_casa"].notna()]
    return int(giocate["giornata"].max()) if not giocate.empty else 0


def formatta_partita(riga) -> str:
    if pd.isna(riga.gol_casa):
        return f"{riga.casa} — {riga.trasferta}"
    return (
        f"{riga.casa} {int(riga.gol_casa)} - {int(riga.gol_trasferta)} {riga.trasferta}"
    )


def badge_esito(conforme: bool) -> str:
    return "🟢 Conforme" if conforme else "🔴 Da sistemare"


def mostra_violazioni(violazioni) -> None:
    """Elenca le violazioni distinguendo blocchi e avvisi."""
    if not violazioni:
        st.success("Nessuna violazione: rosa conforme al regolamento.", icon="✅")
        return
    for v in violazioni:
        testo = f"**{v.articolo}** — {v.messaggio}"
        if v.bloccante:
            st.error(testo, icon="⛔")
        else:
            st.warning(testo, icon="⚠️")


def mostra_maglia(squadra_o_identita, larghezza: int = 160, didascalia: str = "") -> None:
    """Disegna la maglia. Se e' stata caricata un'immagine, mostra quella.

    Si passa sempre da un data URI: `st.html` non renderizza l'SVG inline, e
    cosi' maglia disegnata e maglia caricata seguono la stessa strada.
    """
    identita = getattr(squadra_o_identita, "identita", squadra_o_identita)
    contenuto = identita.maglia(larghezza)

    if not contenuto.startswith("data:"):
        codificato = base64.b64encode(contenuto.encode("utf-8")).decode("ascii")
        contenuto = f"data:image/svg+xml;base64,{codificato}"

    st.image(contenuto, width=larghezza, caption=didascalia or None)


def mostra_logo(identita, larghezza: int = 96) -> None:
    if identita.logo:
        st.image(identita.logo, width=larghezza)


def pastiglia_colore(colore: str, etichetta: str = "") -> str:
    """Quadratino colorato da mettere in linea con il testo."""
    return (
        f'<span style="display:inline-block;width:14px;height:14px;'
        f"border-radius:3px;background:{colore};border:1px solid #8884;"
        f'vertical-align:-2px;margin-right:6px"></span>{etichetta}'
    )


def scambi():
    """Registro degli scambi, ricaricato quando i dati cambiano."""
    return _scambi(versione_dati())


@st.cache_resource(ttl=TTL)
def _scambi(versione: int):
    from .scambi import carica_scambi

    return carica_scambi(archivio())


def nomi_squadre() -> dict[int, str]:
    return {id_: rosa.squadra.nome for id_, rosa in rose().items()}


def nomi_utenti() -> dict[int, str]:
    from .data import carica_credenziali

    return {c.utente.id: c.utente.nome for c in carica_credenziali(archivio()).values()}
