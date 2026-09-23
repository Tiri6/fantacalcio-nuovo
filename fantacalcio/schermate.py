"""Le schermate che precedono l'app vera: accesso, lega, squadra.

Sono i tre cancelli che un partecipante attraversa una volta sola:

    registrati / accedi  ->  crea o unisciti a una lega  ->  crea la squadra

Stanno qui e non in `viste/` perche' girano *prima* di `st.navigation`: non
sono pagine del menu, sono le condizioni per vederlo.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from . import tema
from .anagrafica import (
    NESSUNA,
    DataNonValida,
    Sesso,
    leggi_data_italiana,
    squadra_valida,
    squadre_preferite,
)
from .autenticazione import (
    LUNGHEZZA_MINIMA_PASSWORD,
    Credenziali,
    EmailGiaUsata,
    NomeUtenteOccupato,
    PasswordNonValida,
    PermessoNegato,
    Ruolo,
    StatoRichiesta,
    Utente,
    UtenteNonValido,
    apri_richiesta_password,
    assegna_squadra,
    cambia_password,
    chiudi_richiesta,
    con_codice_recupero,
    entra_in_lega,
    normalizza_nome_utente,
    recupera_con_codice,
    registra,
    reimposta_password,
)
from .competizioni import (
    CompetizioneNonValida,
    CriterioSupercoppa,
    FormatoCoppa,
    RegoleCoppa,
    RegoleSupercoppa,
)
from .data import (
    archivio,
    carica_credenziali,
    carica_inviti,
    carica_leghe,
    carica_richieste_password,
    carica_squadre,
    prossimo_id,
    salva_credenziali,
    salva_invito,
    salva_lega,
    salva_richiesta_password,
    salva_squadra,
)
from .identita import ColoreNonValido, IdentitaSquadra, StileMaglia
from .leghe import (
    EmailNonValida,
    FormatoCampionato,
    Lega,
    LegaNonValida,
    Modalita,
    ModalitaSostituzioni,
    OpzioniLega,
    RegoleNonModificabili,
    StatoInvito,
    TipoAsta,
    aggiorna_opzioni,
    crea_invito,
    crea_lega,
    differenze,
    invito_per_email,
    moduli_disponibili,
    puo_modificare_regole,
    trova_per_codice,
)
from .modelli import Squadra

CHIAVE_MESSAGGIO = "_messaggio"


def _ricorda(testo: str, tipo: str = "success") -> None:
    """Messaggi mostrati dopo un rerun.

    Un `st.success()` seguito da `st.rerun()` non si vede: la pagina riparte
    prima che il browser lo disegni. Si conserva e si mostra al giro dopo.
    """
    st.session_state[CHIAVE_MESSAGGIO] = (tipo, testo)


def _dati_cambiati() -> None:
    """Da chiamare dopo ogni scrittura, prima del rerun.

    Le cache sono indicizzate su un numero di versione: senza questa, dopo
    esserti registrato la schermata ti direbbe ancora che non esisti.
    """
    from .ui import invalida_dati

    invalida_dati()


def mostra_messaggio() -> None:
    coppia = st.session_state.pop(CHIAVE_MESSAGGIO, None)
    if not coppia:
        return
    tipo, testo = coppia
    {"success": st.success, "info": st.info, "warning": st.warning}.get(tipo, st.success)(
        testo, icon="✅" if tipo == "success" else "ℹ️"
    )


# ===========================================================================
# 1. Accesso e registrazione
# ===========================================================================


def _club_dal_listone() -> list[str]:
    """I club di Serie A dal listone caricato, se c'e'.

    Meglio della lista cablata: quando il listone ufficiale e' importato,
    l'elenco e' quello vero della stagione in corso e nessuno deve ricordarsi
    di aggiornarlo a settembre.
    """
    try:
        giocatori = archivio().giocatori()
    except Exception:  # noqa: BLE001 - senza database si usa l'elenco predefinito
        return []
    if giocatori.empty or "club" not in giocatori.columns:
        return []
    return sorted({str(c).strip() for c in giocatori["club"] if str(c).strip()})


def modulo_recupero(credenziali: dict[str, Credenziali]) -> None:
    """Le due strade per rientrare quando la password non si ricorda piu'.

    Non parte nessuna mail — il sito non ne manda, e dirlo e' piu' onesto che
    far aspettare un messaggio che non arrivera'. Restano:

    1. il **codice di recupero**, che chi se l'e' salvato usa da solo;
    2. la **richiesta al presidente**, che resta scritta nel sito invece di
       vivere in una chat.
    """
    col_codice, col_richiesta = st.tabs(
        ["🔑 Ho un codice di recupero", "🙋 Chiedi al presidente"]
    )

    with col_codice:
        _recupero_con_codice(credenziali)

    with col_richiesta:
        _richiesta_al_presidente(credenziali)


def _recupero_con_codice(credenziali: dict[str, Credenziali]) -> None:
    st.caption(
        "E' il codice che hai salvato dal tuo profilo, tipo «H7KP-2MQX-9TBW». "
        "Vale una volta sola: dopo averlo usato scegli la password nuova e, se "
        "vuoi, te ne generi un altro."
    )
    with st.form("recupero_codice"):
        nome_utente = st.text_input("Nome utente")
        codice = st.text_input("Codice di recupero")
        nuova = st.text_input(
            "Password nuova",
            type="password",
            help=f"Almeno {LUNGHEZZA_MINIMA_PASSWORD} caratteri.",
        )
        conferma = st.text_input("Ripeti la password nuova", type="password")
        inviato = st.form_submit_button("Rientra", type="primary")

    if not inviato:
        return

    try:
        trovato = credenziali.get(normalizza_nome_utente(nome_utente))
    except UtenteNonValido:
        trovato = None

    try:
        if trovato is None:
            # Stesso messaggio che per un codice sbagliato: dire «quel nome non
            # esiste» sarebbe un modo comodo per scoprire chi e' iscritto.
            raise PasswordNonValida("Il codice di recupero non e' corretto")
        aggiornate = recupera_con_codice(trovato, codice, nuova, conferma)
    except PasswordNonValida as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_credenziali(archivio(), aggiornate)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare la password: {errore}", icon="⛔")
        return

    _dati_cambiati()
    st.session_state[CHIAVE_MESSAGGIO] = (
        "success",
        "Password cambiata: ora puoi entrare. Il codice che hai usato non vale "
        "piu', se ne vuoi un altro lo generi dal tuo profilo.",
    )
    st.rerun()


def _richiesta_al_presidente(credenziali: dict[str, Credenziali]) -> None:
    st.caption(
        "Il presidente vede la richiesta nel sito e ti manda una password "
        "temporanea, che al primo accesso dovrai sostituire."
    )
    with st.form("richiesta_password"):
        nome_utente = st.text_input("Nome utente")
        inviato = st.form_submit_button("Avvisa il presidente", type="primary")

    if not inviato:
        return

    if not nome_utente.strip():
        st.error("Scrivi il tuo nome utente.", icon="⛔")
        return

    arch = archivio()
    try:
        aperte = carica_richieste_password(arch)
        richiesta = apri_richiesta_password(
            credenziali,
            nome_utente,
            aperte=aperte,
            quando=_adesso(),
            prossimo_id=prossimo_id(arch, "richieste_password"),
        )
        if richiesta is not None:
            salva_richiesta_password(arch, richiesta)
            _dati_cambiati()
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a registrare la richiesta: {errore}", icon="⛔")
        return

    # Stessa risposta in tutti i casi — nome inesistente, richiesta gia'
    # aperta, richiesta nuova. Da fuori non si deve capire la differenza.
    st.success(
        "Fatto. Se quel nome utente esiste, il presidente vedra' la richiesta "
        "e ti fara' avere una password temporanea.",
        icon="📨",
    )


def _adesso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def modulo_registrazione(credenziali: dict[str, Credenziali], primo_utente: bool) -> None:
    """Registrazione autonoma: chi arriva si crea l'account da solo.

    Il primo che si registra diventa presidente: senza, un database vuoto non
    avrebbe nessuno che possa amministrare.
    """
    if primo_utente:
        st.info(
            "Sei il primo ad arrivare: il tuo account sara' quello del "
            "**presidente di lega**, l'unico che puo' creare la lega, invitare "
            "gli altri e ratificare gli scambi.",
            icon="👑",
        )

    squadre_del_cuore = squadre_preferite(_club_dal_listone())

    with st.form("registrazione"):
        st.markdown("**Chi sei**")
        riga = st.columns(2)
        nome = riga[0].text_input("Nome", placeholder="Marco")
        cognome = riga[1].text_input("Cognome", placeholder="Tirinato")

        riga = st.columns(2)
        nascita = riga[0].text_input(
            "Data di nascita",
            placeholder="gg/mm/aaaa",
            help="Per esempio 24/03/1991.",
        )
        sesso = riga[1].selectbox("Sesso", list(Sesso), format_func=lambda x: x.etichetta)

        riga = st.columns(2)
        citta = riga[0].text_input("Citta' di provenienza", placeholder="Ginevra")
        squadra_cuore = riga[1].selectbox(
            "Squadra preferita",
            squadre_del_cuore,
            index=squadre_del_cuore.index(NESSUNA),
            help="Serie A e B. Se tifi altrove, scegli una delle voci «Altro».",
        )

        st.divider()
        st.markdown("**Come entri**")
        riga = st.columns(2)
        nome_utente = riga[0].text_input(
            "Nome utente",
            placeholder="marco",
            help="Almeno 3 caratteri. E' quello che userai per entrare.",
        )
        email = riga[1].text_input(
            "Email",
            placeholder="marco@esempio.it",
            help="Serve a farti trovare se qualcuno ti ha gia' invitato a una "
            "lega. Il sito non ti scrive: non ha un server di posta.",
        )

        riga = st.columns(2)
        password = riga[0].text_input(
            "Password",
            type="password",
            help=f"Almeno {LUNGHEZZA_MINIMA_PASSWORD} caratteri.",
        )
        conferma = riga[1].text_input("Ripeti la password", type="password")
        # La regola sta scritta prima di premere, non nell'errore dopo: e' il
        # motivo per cui una registrazione fallisce senza lasciare traccia.
        st.caption(
            f"La password deve avere almeno **{LUNGHEZZA_MINIMA_PASSWORD} "
            f"caratteri**. Tutti i campi sono obbligatori."
        )

        inviato = st.form_submit_button("Crea l'account", type="primary")

    if not inviato:
        return

    mancanti = [
        etichetta
        for etichetta, valore in (
            ("Nome", nome),
            ("Cognome", cognome),
            ("Data di nascita", nascita),
            ("Citta' di provenienza", citta),
            ("Nome utente", nome_utente),
            ("Email", email),
        )
        if not (valore or "").strip()
    ]
    if mancanti:
        st.error(f"Manca: {', '.join(mancanti)}.", icon="⛔")
        return

    try:
        data_nascita = leggi_data_italiana(nascita)
    except DataNonValida as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        nuove = registra(
            credenziali_esistenti=credenziali,
            id_=prossimo_id(archivio(), "utenti"),
            nome_utente=nome_utente,
            nome=nome,
            cognome=cognome,
            password=password,
            conferma=conferma,
            email=email,
            data_nascita=data_nascita,
            sesso=sesso,
            citta=citta,
            squadra_preferita=squadra_valida(squadra_cuore, squadre_del_cuore),
            ruolo=Ruolo.PRESIDENTE if primo_utente else Ruolo.FANTALLENATORE,
        )
    except (
        NomeUtenteOccupato,
        EmailGiaUsata,
        UtenteNonValido,
        PasswordNonValida,
        EmailNonValida,
    ) as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_credenziali(archivio(), nuove)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(
            f"Non riesco a scrivere sul database: {errore}\n\n"
            "Con la chiave `anon` le scritture sono bloccate dalla RLS: nei "
            "secret serve la chiave `service_role`.",
            icon="⛔",
        )
        return

    _dati_cambiati()
    _ricorda(
        f"Account «{nuove.utente.nome_utente}» creato. Ora entra con quelle credenziali."
    )
    st.rerun()


# ===========================================================================
# 2. Crea o unisciti a una lega
# ===========================================================================


def _riassunto_opzioni(opzioni: OpzioniLega) -> str:
    rosa = (
        f"rosa da {opzioni.rosa_totale}"
        if opzioni.rosa_totale is not None
        else "rosa senza limiti di ruolo"
    )
    return (
        f"{opzioni.modalita.etichetta} · {opzioni.partecipanti} squadre · "
        f"{rosa} · primo gol a {opzioni.soglia_primo_gol:g}"
    )


def _limite_di_ruolo(colonna, etichetta: str, massimo: int, valore: int | None):
    """Una casella «quanti ne puoi tesserare», dove 0 vuol dire «quanti vuoi».

    Serve uno zero e non un interruttore separato perche' i quattro limiti
    sono indipendenti davvero: un interruttore solo non saprebbe rappresentare
    una lega che limita i portieri e lascia liberi gli altri, e riaprendo le
    regole gliene inventerebbe tre che nessuno aveva chiesto.
    """
    scelto = colonna.number_input(etichetta, 0, massimo, valore or 0)
    return int(scelto) if scelto else None


def _modulo_opzioni(
    iniziali: OpzioniLega | None = None, stagione_iniziale: str = ""
) -> tuple[OpzioniLega | None, str]:
    """Tutte le caselle delle regole di lega. `None` se qualcosa non torna.

    Lo usano in due: la creazione, che parte dai valori predefiniti, e la
    modifica, che parte da quelli della lega. E' lo stesso modulo apposta —
    due moduli separati divergerebbero alla prima opzione aggiunta, e
    l'aggiunta finirebbe solo in uno dei due.

    Le opzioni stanno fuori da `st.form` di proposito: cambiando modalita' i
    moduli ammessi cambiano, e dentro un form non si aggiornerebbero finche'
    non premi invio.
    """
    base = iniziali or OpzioniLega()
    st.markdown("#### Impostazioni generali")
    riga = st.columns(3)
    modalita = riga[0].radio(
        "Modalita'",
        list(Modalita),
        # Mantra e' il default: e' la modalita' in cui gioca questa lega, e
        # partire dall'altra vuol dire che chi non guarda crea la lega sbagliata.
        index=list(Modalita).index(base.modalita),
        format_func=lambda m: m.etichetta,
        horizontal=True,
        help="Mantra usa i ruoli specifici (Dc, E, W, T...). Classic usa P/D/C/A.",
    )
    partecipanti = riga[1].number_input(
        "Partecipanti", min_value=2, max_value=20, value=base.partecipanti, step=1
    )
    formato = riga[2].selectbox(
        "Formato",
        list(FormatoCampionato),
        index=list(FormatoCampionato).index(base.formato),
        format_func=lambda f: f.etichetta,
    )

    riga = st.columns(3)
    giornate = riga[0].number_input(
        "Giornate totali",
        min_value=1,
        max_value=76,
        value=base.giornate_totali,
        step=1,
    )
    punti_vittoria = riga[1].number_input(
        "Punti per vittoria",
        min_value=1,
        max_value=5,
        value=base.punti_vittoria,
        step=1,
    )
    punti_pareggio = riga[2].number_input(
        "Punti per pareggio",
        min_value=0,
        max_value=3,
        value=base.punti_pareggio,
        step=1,
    )

    st.markdown("#### Rosa e mercato")
    riga = st.columns(3)
    tipo_asta = riga[0].selectbox(
        "Come si assegnano i giocatori",
        list(TipoAsta),
        index=list(TipoAsta).index(base.tipo_asta),
        format_func=lambda t: t.etichetta,
        help="«Draft» significa che l'assegnazione avviene fuori dalla "
        "piattaforma e i risultati si caricano via CSV.",
    )
    anni_contratto = riga[1].number_input(
        "Anni di contratto (massimo)",
        min_value=1,
        max_value=10,
        value=base.anni_contratto_massimi,
        step=1,
        help="Durata massima di un contratto. E' la leva del fantacalcio "
        "manageriale: quanto a lungo puoi legare a te un giocatore.",
    )
    budget_milioni = riga[2].number_input(
        "Budget cap annuale (milioni)",
        min_value=0.0,
        max_value=1_000.0,
        value=base.budget_cap / 1_000_000,
        step=5.0,
        help="Tetto agli ingaggi di una squadra in una stagione. Fonte degli "
        "stipendi: Capology.",
    )
    stagione = st.text_input("Stagione", value=stagione_iniziale or "2026/27")

    st.markdown("**Limite di giocatori per ruolo**")
    st.caption(
        "**0 = nessun limite** per quel ruolo. Si mettono uno per uno perche' "
        "una lega puo' benissimo limitare i portieri e lasciare liberi gli "
        "altri — ed e' esattamente quello che fa questa."
    )
    riga = st.columns(4)
    portieri = _limite_di_ruolo(riga[0], "Portieri", 6, base.rosa_portieri)
    difensori = _limite_di_ruolo(riga[1], "Difensori", 15, base.rosa_difensori)
    centrocampisti = _limite_di_ruolo(
        riga[2], "Centrocampisti", 15, base.rosa_centrocampisti
    )
    attaccanti = _limite_di_ruolo(riga[3], "Attaccanti", 12, base.rosa_attaccanti)

    messi = [v for v in (portieri, difensori, centrocampisti, attaccanti) if v]
    if len(messi) == 4:
        st.caption(f"Rosa complessiva: **{sum(messi)}** giocatori")
    elif messi:
        st.caption("Limite solo su alcuni ruoli: per gli altri conta il monte anni.")
    else:
        st.caption("Nessun tetto per ruolo: la rosa la limita il monte anni.")

    st.markdown("**Vincoli di rosa e di mercato**")
    riga = st.columns(3)
    minimo_italiani = riga[0].number_input(
        "Minimo giocatori italiani",
        min_value=0,
        max_value=40,
        value=base.minimo_italiani,
        step=1,
        help="0 = nessun vincolo.",
    )
    minimo_u21 = riga[1].number_input(
        "Minimo Under 21 italiani",
        min_value=0,
        max_value=20,
        value=base.minimo_u21_italiani,
        step=1,
        help="Sottoinsieme del vincolo qui accanto: un Under 21 italiano "
        "conta anche come italiano. 0 = nessun vincolo.",
    )
    scambi_stagione = riga[2].number_input(
        "Scambi permessi a stagione",
        min_value=0,
        max_value=50,
        value=base.scambi_per_stagione,
        step=1,
        help="Per squadra, nell'arco della stagione. 0 = illimitati.",
    )

    st.markdown("#### Competizioni")
    st.caption(
        "Il campionato c'e' sempre. Le altre compaiono nel menu solo se le accendi qui."
    )
    riga = st.columns(2)
    coppa = riga[0].toggle("Coppa Italia", value=base.coppa_italia)
    supercoppa = riga[1].toggle("Supercoppa", value=base.supercoppa)

    regole_coppa = base.regole_coppa
    if coppa:
        with st.expander("Regole della Coppa Italia", expanded=True):
            riga = st.columns(3)
            formato_coppa = riga[0].selectbox(
                "Formato",
                list(FormatoCoppa),
                index=list(FormatoCoppa).index(base.regole_coppa.formato),
                format_func=lambda f: f.etichetta,
            )
            ammesse = riga[1].selectbox(
                "Squadre ammesse",
                [2, 4, 8, 16],
                index=(
                    [2, 4, 8, 16].index(base.regole_coppa.squadre_ammesse)
                    if base.regole_coppa.squadre_ammesse in (2, 4, 8, 16)
                    else 2
                ),
                help="Una potenza di due: altrimenti il tabellone non si chiude.",
            )
            teste = riga[2].toggle(
                "Teste di serie dalla classifica",
                value=base.regole_coppa.teste_di_serie,
            )

            riga = st.columns(3)
            prima = riga[0].number_input(
                "Primo turno alla giornata", 1, 40, base.regole_coppa.prima_giornata
            )
            passo = riga[1].number_input(
                "Un turno ogni quante giornate",
                1,
                10,
                base.regole_coppa.ogni_quante_giornate,
            )
            spareggio = riga[2].toggle(
                "Parita': passa chi ha piu' fantapunti",
                value=base.regole_coppa.spareggio_ai_fantapunti,
                help="Senza, una coppa a gara secca non saprebbe chi far passare.",
            )
            try:
                regole_coppa = RegoleCoppa(
                    formato=formato_coppa,
                    squadre_ammesse=int(ammesse),
                    prima_giornata=int(prima),
                    ogni_quante_giornate=int(passo),
                    teste_di_serie=bool(teste),
                    spareggio_ai_fantapunti=bool(spareggio),
                )
            except CompetizioneNonValida as errore:
                st.error(str(errore), icon="⛔")
            else:
                turni = ", ".join(
                    f"{regole_coppa.nome_turno(n + 1)} (G{g})"
                    for n, g in enumerate(regole_coppa.giornate_dei_turni())
                )
                st.caption(f"Tabellone: {turni}")

    regole_supercoppa = base.regole_supercoppa
    if supercoppa:
        with st.expander("Regole della Supercoppa", expanded=True):
            criterio = st.selectbox(
                "Chi si affronta",
                list(CriterioSupercoppa),
                index=list(CriterioSupercoppa).index(base.regole_supercoppa.criterio),
                format_func=lambda c: c.etichetta,
                help="Il primo anno l'albo d'oro e' vuoto: le due squadre le "
                "scegli a mano. Dall'anno dopo si ricavano da sole.",
            )
            prima_stagione = st.toggle(
                "Si gioca prima dell'inizio del campionato",
                value=base.regole_supercoppa.prima_della_stagione,
            )
            regole_supercoppa = RegoleSupercoppa(
                criterio=criterio, prima_della_stagione=bool(prima_stagione)
            )

    st.markdown("#### Formazione")
    disponibili = moduli_disponibili(modalita)
    moduli = st.multiselect(
        "Moduli ammessi",
        disponibili,
        # Cambiando modalita' i moduli della lega non esistono piu': si
        # riparte da tutti quelli disponibili invece che da un elenco vuoto.
        default=[m for m in base.moduli_ammessi if m in disponibili] or list(disponibili),
        help="Chi schiera la formazione potra' scegliere solo fra questi.",
    )
    riga = st.columns(3)
    panchinari = riga[0].number_input("Panchinari", 0, 20, base.panchinari)
    sostituzioni = riga[1].toggle(
        "Sostituzioni automatiche", value=base.sostituzioni_automatiche
    )
    capitano = riga[2].toggle("Capitano", value=base.capitano)

    riga = st.columns([2, 1])
    modalita_sostituzioni = riga[0].selectbox(
        "Modalita' delle sostituzioni",
        list(ModalitaSostituzioni),
        index=list(ModalitaSostituzioni).index(base.modalita_sostituzioni),
        format_func=lambda m: m.etichetta,
        disabled=not sostituzioni,
        help="Sono le tre modalita' del Mantra. Cambiano chi entra al posto "
        "di chi resta senza voto, non quante sostituzioni si possono fare.",
    )
    sostituzioni_massime = riga[1].number_input(
        "Sostituzioni per giornata",
        min_value=0,
        max_value=11,
        value=base.sostituzioni_massime,
        disabled=not sostituzioni,
        help="Il portiere di riserva che subentra ne consuma una.",
    )
    st.caption(modalita_sostituzioni.spiegazione)

    st.markdown("#### Punteggio e fasce di gol")
    riga = st.columns(3)
    soglia = riga[0].number_input(
        "Punti per il primo gol",
        min_value=50.0,
        max_value=80.0,
        value=base.soglia_primo_gol,
        step=0.5,
        help="Sotto questa soglia il risultato e' 0 gol.",
    )
    passo = riga[1].number_input(
        "Punti per ogni gol successivo",
        min_value=1.0,
        max_value=12.0,
        value=base.passo_gol,
        step=0.5,
    )
    senza_voto = riga[2].number_input(
        "Voto d'ufficio a chi non gioca",
        min_value=0.0,
        max_value=6.0,
        value=base.voto_minimo_senza_voto,
        step=0.5,
    )

    anteprima = ", ".join(f"{int(soglia + passo * n)}→{n + 1}" for n in range(4))
    st.caption(f"Fasce risultanti: {anteprima}, e cosi' via")

    st.markdown("#### Modificatori di reparto")
    riga = st.columns(3)
    mod_difesa = riga[0].toggle("Modificatore difesa", value=base.modificatore_difesa)
    mod_centrocampo = riga[1].toggle(
        "Modificatore centrocampo", value=base.modificatore_centrocampo
    )
    mod_attacco = riga[2].toggle("Modificatore attacco", value=base.modificatore_attacco)
    st.caption(
        "Le soglie esatte di ogni modificatore sono parametri: si cambiano "
        "senza toccare il codice. Quelle di partenza sono in PUNTI_APERTI.md, "
        "da confermare con la lega."
    )

    with st.expander("Bonus e malus"):
        riga = st.columns(3)
        gol = riga[0].number_input("Gol segnato", 0.0, 10.0, base.bonus.gol_segnato, 0.5)
        gol_subito = riga[1].number_input(
            "Gol subito", -5.0, 0.0, base.bonus.gol_subito, 0.5
        )
        assist = riga[2].number_input("Assist", 0.0, 5.0, base.bonus.assist, 0.5)
        riga = st.columns(3)
        rigore_parato = riga[0].number_input(
            "Rigore parato", 0.0, 6.0, base.bonus.rigore_parato, 0.5
        )
        rigore_sbagliato = riga[1].number_input(
            "Rigore sbagliato", -6.0, 0.0, base.bonus.rigore_sbagliato, 0.5
        )
        autogol = riga[2].number_input("Autogol", -6.0, 0.0, base.bonus.autogol, 0.5)
        riga = st.columns(3)
        ammonizione = riga[0].number_input(
            "Ammonizione", -3.0, 0.0, base.bonus.ammonizione, 0.5
        )
        espulsione = riga[1].number_input(
            "Espulsione", -5.0, 0.0, base.bonus.espulsione, 0.5
        )
        imbattuto = riga[2].number_input(
            "Portiere imbattuto", 0.0, 3.0, base.bonus.portiere_imbattuto, 0.5
        )

    from .leghe import Bonus

    try:
        return OpzioniLega(
            modalita=modalita,
            partecipanti=int(partecipanti),
            formato=formato,
            giornate_totali=int(giornate),
            tipo_asta=tipo_asta,
            anni_contratto_massimi=int(anni_contratto),
            budget_cap=float(budget_milioni) * 1_000_000,
            coppa_italia=bool(coppa),
            supercoppa=bool(supercoppa),
            regole_coppa=regole_coppa,
            regole_supercoppa=regole_supercoppa,
            rosa_portieri=portieri,
            rosa_difensori=difensori,
            rosa_centrocampisti=centrocampisti,
            rosa_attaccanti=attaccanti,
            minimo_italiani=int(minimo_italiani),
            minimo_u21_italiani=int(minimo_u21),
            scambi_per_stagione=int(scambi_stagione),
            moduli_ammessi=tuple(moduli),
            panchinari=int(panchinari),
            sostituzioni_automatiche=bool(sostituzioni),
            modalita_sostituzioni=modalita_sostituzioni,
            sostituzioni_massime=int(sostituzioni_massime),
            capitano=bool(capitano),
            punti_vittoria=int(punti_vittoria),
            punti_pareggio=int(punti_pareggio),
            soglia_primo_gol=float(soglia),
            passo_gol=float(passo),
            voto_minimo_senza_voto=float(senza_voto),
            modificatore_difesa=bool(mod_difesa),
            modificatore_centrocampo=bool(mod_centrocampo),
            modificatore_attacco=bool(mod_attacco),
            bonus=Bonus(
                gol_segnato=float(gol),
                gol_subito=float(gol_subito),
                assist=float(assist),
                rigore_parato=float(rigore_parato),
                rigore_sbagliato=float(rigore_sbagliato),
                autogol=float(autogol),
                ammonizione=float(ammonizione),
                espulsione=float(espulsione),
                portiere_imbattuto=float(imbattuto),
            ),
        ), stagione
    except LegaNonValida as errore:
        st.error(str(errore), icon="⛔")
        return None, stagione


def _crea_la_lega(utente: Utente, credenziali: Credenziali) -> None:
    nome = st.text_input(
        "Nome della lega", placeholder="Fantacalcio NuoVo", key="_nome_lega"
    )
    st.divider()

    esito = _modulo_opzioni()
    opzioni, stagione = esito if esito else (None, "2026/27")

    st.divider()
    if not st.button("🏆 Crea la lega", type="primary", use_container_width=True):
        return

    if opzioni is None:
        return

    try:
        lega = crea_lega(
            id_=prossimo_id(archivio(), "leghe"),
            nome=nome,
            admin_id=utente.id,
            opzioni=opzioni,
            stagione=stagione,
        )
    except LegaNonValida as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_lega(archivio(), lega)
        salva_credenziali(
            archivio(), entra_in_lega(credenziali, lega.id, Ruolo.PRESIDENTE)
        )
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare la lega: {errore}", icon="⛔")
        return

    st.session_state["_lega_appena_creata"] = lega.codice_invito
    _dati_cambiati()
    _ricorda(f"Lega «{lega.nome}» creata.")
    st.rerun()


def _unisciti_a_una_lega(utente: Utente, credenziali: Credenziali) -> None:
    leghe = carica_leghe(archivio())

    if not leghe:
        st.warning(
            "Non esiste ancora nessuna lega. Creane una tu, oppure aspetta il "
            "codice da chi la sta creando.",
            icon="🕰️",
        )
        return

    # Se qualcuno ti ha gia' invitato con la tua email, ti si apre la strada.
    if utente.email:
        for lega in leghe.values():
            invito = invito_per_email(
                carica_inviti(archivio(), lega.id), lega.id, utente.email
            )
            if invito is None:
                continue
            st.success(
                f"Sei stato invitato alla lega **{lega.nome}**.",
                icon="✉️",
            )
            if st.button(
                f"Entra in «{lega.nome}»", type="primary", use_container_width=True
            ):
                _entra(credenziali, lega, invito_id=invito.id)
            st.divider()
            break

    codice = st.text_input(
        "Codice d'invito",
        placeholder="ABCD-2345",
        help="Otto caratteri. Te lo passa chi ha creato la lega.",
    )

    if not st.button("Entra nella lega", use_container_width=True):
        return

    lega = trova_per_codice(leghe, codice)
    if lega is None:
        st.error(
            "Nessuna lega con questo codice. Controlla di averlo copiato per "
            "intero: sono otto caratteri.",
            icon="⛔",
        )
        return
    _entra(credenziali, lega)


def _entra(credenziali: Credenziali, lega: Lega, invito_id: int | None = None) -> None:
    """Associa l'utente alla lega e marca l'eventuale invito come accettato."""
    try:
        salva_credenziali(archivio(), entra_in_lega(credenziali, lega.id))
        if invito_id is not None:
            for invito in carica_inviti(archivio(), lega.id):
                if invito.id == invito_id:
                    from dataclasses import replace

                    salva_invito(archivio(), replace(invito, stato=StatoInvito.ACCETTATO))
                    break
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a registrare l'ingresso: {errore}", icon="⛔")
        return
    _dati_cambiati()
    _ricorda(f"Benvenuto nella lega «{lega.nome}».")
    st.rerun()


def festeggia_lega_nuova() -> None:
    """Mostra il codice d'invito subito dopo la creazione, una volta sola.

    Va chiamata da *ogni* schermata che possa venire dopo la creazione: appena
    la lega esiste il cancello successivo scatta, quindi mostrarla solo qui
    dentro `scegli_lega` significherebbe non mostrarla mai.
    """
    codice = st.session_state.pop("_lega_appena_creata", None)
    if not codice:
        return
    st.balloons()
    st.markdown("### 🎉 La lega e' aperta")
    st.write(
        "Questo e' il **codice d'invito**. Girarlo ai tuoi amici e' tutto "
        "quello che serve perche' possano entrare:"
    )
    st.markdown(tema.codice_invito(codice), unsafe_allow_html=True)
    st.caption("Lo ritrovi sempre nella barra laterale e nella pagina «La lega».")
    st.divider()


def scegli_lega(utente: Utente, credenziali: Credenziali) -> None:
    """Il bivio: crei la lega o ti unisci a una che esiste gia'."""
    festeggia_lega_nuova()

    st.markdown(
        tema.testata(
            "Non sei ancora in una lega",
            "Crea la tua lega e invita gli amici, oppure entra in una che "
            "esiste gia' con il codice che ti hanno passato.",
            occhiello=f"Ciao {utente.nome}",
        ),
        unsafe_allow_html=True,
    )

    crea, unisci = st.tabs(["🏆 Crea una lega", "🔑 Unisciti a una lega"])
    with crea:
        _crea_la_lega(utente, credenziali)
    with unisci:
        _unisciti_a_una_lega(utente, credenziali)


# ===========================================================================
# 3. Crea la squadra
# ===========================================================================

STILI = list(StileMaglia)


def crea_squadra(utente: Utente, credenziali: Credenziali, lega: Lega) -> None:
    """Nome, citta', stadio, curva e colori: l'identita' della squadra.

    I colori stanno fuori da un form perche' l'anteprima della maglia si deve
    aggiornare mentre li scegli, non dopo aver premuto invio.
    """
    festeggia_lega_nuova()

    st.markdown(
        tema.testata(
            "Fonda la tua squadra",
            "Nome, casa e colori. Si potra' cambiare tutto dalla pagina "
            "«Identita' squadre», ma il nome e' quello con cui ti vedranno gli altri.",
            occhiello=lega.nome,
        ),
        unsafe_allow_html=True,
    )

    sinistra, destra = st.columns([3, 2], gap="large")

    with sinistra:
        nome = st.text_input("Nome della squadra", placeholder="Real Sporcaccioni")
        riga = st.columns(2)
        citta = riga[0].text_input("Citta'", placeholder="Ginevra")
        stadio = riga[1].text_input("Stadio", placeholder="Arena del NuoVo")
        curva = st.text_input(
            "Nome della curva",
            placeholder="Curva Nord",
            help="Come si chiama il settore dei tuoi tifosi.",
        )
        motto = st.text_input("Motto", placeholder="Chi non salta un pari e'")

        st.markdown("**Colori sociali**")
        riga = st.columns(3)
        primario = riga[0].color_picker("Primario", "#2e7d32")
        secondario = riga[1].color_picker("Secondario", "#ffffff")
        stile = riga[2].selectbox("Stile maglia", STILI, format_func=lambda s: s.value)

    try:
        identita = IdentitaSquadra(
            presidente=utente.nome_completo,
            motto=motto,
            stadio=stadio,
            citta=citta,
            curva=curva,
            colore_primario=primario,
            colore_secondario=secondario,
            stile_maglia=stile,
        )
    except ColoreNonValido as errore:
        st.error(str(errore), icon="⛔")
        return

    with destra:
        st.markdown("**Anteprima**")
        from .ui import mostra_maglia

        mostra_maglia(identita, larghezza=170)
        st.markdown(
            tema.pastiglia_squadra(nome or "La tua squadra", primario, secondario),
            unsafe_allow_html=True,
        )
        if not identita.colori_distinguibili:
            st.warning(
                "I due colori sono troppo simili: da lontano la maglia si "
                "legge male. Prova ad allontanarli.",
                icon="🎨",
            )

    st.divider()
    azioni = st.columns([2, 1])

    if azioni[0].button("⚽ Fonda la squadra", type="primary", use_container_width=True):
        _salva_nuova_squadra(utente, credenziali, lega, nome, identita)

    if azioni[1].button("Lo faccio dopo", use_container_width=True):
        st.session_state["_salta_squadra"] = True
        st.rerun()


def _salva_nuova_squadra(
    utente: Utente,
    credenziali: Credenziali,
    lega: Lega,
    nome: str,
    identita: IdentitaSquadra,
) -> None:
    pulito = (nome or "").strip()
    if len(pulito) < 3:
        st.error("Il nome della squadra deve avere almeno 3 caratteri.", icon="⛔")
        return

    esistenti = archivio().squadre()
    if not esistenti.empty and pulito.lower() in {
        str(n).strip().lower() for n in esistenti["nome"]
    }:
        st.error(
            f"«{pulito}» esiste gia' in questa lega. Scegli un altro nome.",
            icon="⛔",
        )
        return

    squadra = Squadra(
        id=prossimo_id(archivio(), "squadre"),
        nome=pulito,
        presidente=utente.nome_completo,
        identita=identita,
        lega_id=lega.id,
    )

    try:
        salva_squadra(archivio(), squadra)
        salva_credenziali(archivio(), assegna_squadra(credenziali, squadra.id))
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare la squadra: {errore}", icon="⛔")
        return

    _dati_cambiati()
    _ricorda(f"«{squadra.nome}» e' nata. Benvenuto in {lega.nome}.")
    st.rerun()


# ===========================================================================
# Inviti per email (usati dalla pagina Lega)
# ===========================================================================


def modulo_invito(lega: Lega, utente: Utente) -> None:
    """L'admin riserva un posto a un indirizzo email.

    Non parte nessuna mail: l'app non ha un server di posta, e montarne uno
    per dieci persone non si giustifica. L'invito registra chi e' atteso, cosi'
    quando quella persona si registra con quell'email trova il posto pronto.
    """
    with st.form("invito"):
        email = st.text_input("Email di chi vuoi invitare")
        inviato = st.form_submit_button("Riserva il posto", type="primary")

    if not inviato:
        return

    try:
        invito = crea_invito(
            id_=prossimo_id(archivio(), "inviti"),
            lega=lega,
            email=email,
            creato_da=utente.id,
        )
    except EmailNonValida as errore:
        st.error(str(errore), icon="⛔")
        return

    esistenti = carica_inviti(archivio(), lega.id)
    if any(i.email == invito.email for i in esistenti):
        st.warning(f"{invito.email} e' gia' nella lista degli invitati.", icon="ℹ️")
        return

    try:
        salva_invito(archivio(), invito)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare l'invito: {errore}", icon="⛔")
        return

    _dati_cambiati()
    _ricorda(
        f"Posto riservato per {invito.email}. Mandagli il codice "
        f"{lega.codice_invito} e potra' entrare."
    )
    st.rerun()


# ===========================================================================
# 4. Password
# ===========================================================================


def modulo_cambio_password(credenziali: Credenziali, obbligatorio: bool = False) -> None:
    """Cambio autonomo della password. Serve conoscere quella attuale.

    `obbligatorio` e' il caso di chi arriva da una reimpostazione: la password
    che ha in mano l'ha scelta qualcun altro, e finche' non la sostituisce non
    entra.
    """
    if obbligatorio:
        st.warning(
            "La tua password e' stata reimpostata da chi amministra la lega. "
            "Scegline una tua per continuare.",
            icon="🔐",
        )

    with st.form("cambio_password"):
        attuale = st.text_input(
            "Password attuale",
            type="password",
            help="Quella che hai usato per entrare adesso.",
        )
        nuova = st.text_input("Password nuova", type="password")
        conferma = st.text_input("Ripeti la password nuova", type="password")
        inviato = st.form_submit_button("Cambia password", type="primary")

    if not inviato:
        return

    try:
        aggiornate = cambia_password(credenziali, attuale, nuova, conferma)
    except PasswordNonValida as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_credenziali(archivio(), aggiornate)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare la password: {errore}", icon="⛔")
        return

    _dati_cambiati()
    _ricorda("Password cambiata.")
    st.rerun()


def modulo_reimposta_password(utente: Utente, lega: Lega) -> None:
    """Il presidente genera una password temporanea per un partecipante.

    Non parte nessuna mail: la password compare a schermo una volta sola e va
    consegnata a voce o su un canale privato. Al primo accesso chi la riceve e'
    obbligato a sostituirla.
    """
    tutte = carica_credenziali(archivio())
    altri = {
        c.utente.nome_utente: c
        for c in tutte.values()
        if c.utente.lega_id == lega.id and c.utente.id != utente.id
    }

    if not altri:
        st.info("Non c'e' nessun altro partecipante in questa lega.", icon="👤")
        return

    if fatto := st.session_state.pop("_password_generata", None):
        nome, temporanea = fatto
        st.success(f"Password nuova per **{nome}**:", icon="🔑")
        st.code(temporanea, language=None)
        st.caption(
            "Compare **una volta sola**: copiala adesso e passagliela a voce o "
            "in privato. Al primo accesso dovra' sceglierne una sua."
        )
        st.divider()

    scelto = st.selectbox(
        "Partecipante",
        sorted(altri),
        format_func=lambda n: f"{altri[n].utente.nome_completo} ({n})",
    )

    if not st.button("Genera una password temporanea", use_container_width=True):
        return

    try:
        aggiornate, temporanea = reimposta_password(altri[scelto], utente)
    except (PermessoNegato, PasswordNonValida) as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_credenziali(archivio(), aggiornate)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare la password: {errore}", icon="⛔")
        return

    _dati_cambiati()
    st.session_state["_password_generata"] = (
        aggiornate.utente.nome_completo,
        temporanea,
    )
    st.rerun()


def modulo_codice_recupero(credenziali: Credenziali) -> None:
    """Genera il codice con cui si rientra da soli, senza chiedere a nessuno.

    Compare una volta sola, come una password temporanea: da li' in poi il
    sito ne conserva solo l'impronta. Vale finche' non lo si usa o non se ne
    genera un altro.
    """
    if nuovo := st.session_state.pop("_codice_recupero", None):
        st.success("Ecco il tuo codice di recupero:", icon="🔑")
        st.code(nuovo, language=None)
        st.caption(
            "**Salvalo adesso**: non ricomparira'. Tienilo dove terresti una "
            "chiave di scorta — nelle note del telefono, in un gestore di "
            "password, su un foglio. Vale una volta sola."
        )
        st.divider()

    if credenziali.ha_codice_recupero:
        st.info(
            "Hai gia' un codice di recupero. Se ne generi un altro, quello di "
            "prima smette di funzionare.",
            icon="✅",
        )
        etichetta = "Genera un codice nuovo"
    else:
        st.warning(
            "Non hai un codice di recupero: se dimentichi la password dovrai "
            "passare dal presidente. Generarne uno costa un secondo.",
            icon="⚠️",
        )
        etichetta = "Genera il codice di recupero"

    if not st.button(etichetta, use_container_width=True):
        return

    try:
        aggiornate, codice = con_codice_recupero(credenziali)
        salva_credenziali(archivio(), aggiornate)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a generare il codice: {errore}", icon="⛔")
        return

    _dati_cambiati()
    st.session_state["_codice_recupero"] = codice
    st.rerun()


def modulo_richieste_password(utente: Utente, lega: Lega) -> None:
    """Chi ha chiesto aiuto dalla schermata di accesso, e cosa farci.

    Sta accanto al pulsante che reimposta le password perche' le due cose si
    fanno insieme: si guarda chi ha chiesto, gli si genera la password, e si
    segna la richiesta come evasa.
    """
    try:
        richieste = [
            r for r in carica_richieste_password(archivio(), lega.id) if r.aperta
        ]
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.caption(f"Richieste non leggibili: {errore}")
        return

    if not richieste:
        return

    quante = len(richieste)
    st.warning(
        f"{quante} "
        + ("richiesta" if quante == 1 else "richieste")
        + " di aiuto sulla password: "
        + ", ".join(f"**{r.nome_utente}**" for r in richieste[:5])
        + ("…" if quante > 5 else "")
        + ". Generagli una password temporanea qui sotto, poi segna la "
        "richiesta come evasa.",
        icon="🙋",
    )

    for richiesta in richieste:
        riga = st.columns([3, 1, 1])
        quando = richiesta.chiesta_il.replace("T", " ")[:16]
        riga[0].markdown(f"**{richiesta.nome_utente}** · {quando or 'senza data'}")
        if riga[1].button("Evasa", key=f"_evasa_{richiesta.id}"):
            _chiudi_richiesta(richiesta, utente, StatoRichiesta.EVASA)
        if riga[2].button("Annulla", key=f"_annulla_{richiesta.id}"):
            _chiudi_richiesta(richiesta, utente, StatoRichiesta.ANNULLATA)
    st.divider()


def _chiudi_richiesta(richiesta, utente: Utente, stato) -> None:
    try:
        salva_richiesta_password(
            archivio(), chiudi_richiesta(richiesta, utente, stato, quando=_adesso())
        )
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a chiudere la richiesta: {errore}", icon="⛔")
        return
    _dati_cambiati()
    st.session_state[CHIAVE_MESSAGGIO] = (
        "success",
        f"Richiesta di {richiesta.nome_utente} segnata come {stato.etichetta.lower()}.",
    )
    st.rerun()


def modulo_modifica_regole(utente: Utente, lega: Lega) -> None:
    """Il presidente cambia le regole di una lega gia' avviata.

    E' lo stesso modulo della creazione, riempito con quel che la lega ha
    adesso: cosi' non si scrivono due volte le stesse caselle, e un'opzione
    aggiunta domani compare in tutti e due i posti senza fare niente.

    Prima di salvare si legge **cosa cambia**. Una regola toccata per sbaglio
    la scoprirebbero dieci persone a giornata in corso, e rileggere tre righe
    costa meno di rimediare.
    """
    if not puo_modificare_regole(utente, lega):
        st.info("Le regole le cambia chi ha creato la lega.", icon="🔒")
        return

    squadre = carica_squadre(archivio())
    iscritte = sum(1 for s in squadre.values() if s.lega_id == lega.id)

    st.caption(
        "Le caselle partono da come sta la lega adesso: cambia quel che serve "
        "e salva. Rose, calendario e albo restano dove sono — e' il motivo per "
        "cui questa pagina esiste invece di doverne creare una nuova."
    )

    esito = _modulo_opzioni(lega.opzioni, lega.stagione)
    nuove, stagione = esito if esito else (None, lega.stagione)

    st.divider()
    if nuove is None:
        return

    cambiate = differenze(lega.opzioni, nuove)
    cambia_stagione = stagione.strip() and stagione.strip() != lega.stagione
    if cambia_stagione:
        cambiate = [f"Stagione: {lega.stagione} → {stagione.strip()}", *cambiate]

    if not cambiate:
        st.caption("Per ora non hai cambiato niente.")
        return

    st.markdown("**Cosa cambia**")
    for riga in cambiate:
        st.markdown(f"- {riga}")
    _avvisi_sulle_regole(lega, nuove, iscritte)

    if not st.button(
        "💾 Salva le regole nuove", type="primary", use_container_width=True
    ):
        return

    try:
        aggiornata = aggiorna_opzioni(
            lega, nuove, utente, squadre_iscritte=iscritte, stagione=stagione
        )
    except (RegoleNonModificabili, LegaNonValida) as errore:
        st.error(str(errore), icon="⛔")
        return

    try:
        salva_lega(archivio(), aggiornata)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare le regole: {errore}", icon="⛔")
        return

    _dati_cambiati()
    quante = len(cambiate)
    _ricorda(
        f"Regole aggiornate: {quante} "
        + ("modifica salvata." if quante == 1 else "modifiche salvate.")
    )
    st.rerun()


def _avvisi_sulle_regole(lega: Lega, nuove: OpzioniLega, iscritte: int) -> None:
    """Le conseguenze che il salvataggio non rifiuta ma che conviene sapere.

    Non sono errori: sono cambiamenti legittimi che pero' toccano roba gia'
    salvata, e vale la pena dirli prima invece di lasciarli scoprire.
    """
    avvisi: list[str] = []

    if iscritte > nuove.partecipanti:
        avvisi.append(
            f"La lega ha **{iscritte} squadre** iscritte e staresti mettendo "
            f"il tetto a {nuove.partecipanti}: il salvataggio lo rifiutera'."
        )

    tolti = [m for m in lega.opzioni.moduli_ammessi if m not in nuove.moduli_ammessi]
    if tolti:
        avvisi.append(
            "Moduli tolti: **"
            + ", ".join(tolti)
            + "**. Chi li aveva gia' usati trovera' la formazione da rifare."
        )

    if nuove.panchinari < lega.opzioni.panchinari:
        avvisi.append(
            f"La panchina passa da {lega.opzioni.panchinari} a "
            f"**{nuove.panchinari}**: le formazioni salvate con piu' panchinari "
            f"vanno risistemate."
        )

    if (
        nuove.soglia_primo_gol != lega.opzioni.soglia_primo_gol
        or nuove.passo_gol != lega.opzioni.passo_gol
    ):
        avvisi.append(
            "Cambiano le fasce di gol: le giornate **gia' calcolate** restano "
            "come sono, le prossime useranno le fasce nuove. Se vuoi "
            "riallineare anche il passato, ricalcola quelle giornate."
        )

    if nuove.modalita is not lega.opzioni.modalita:
        avvisi.append(
            f"Stai passando a **{nuove.modalita.etichetta}**: cambiano i ruoli "
            f"con cui si schiera, e i moduli con loro."
        )

    for avviso in avvisi:
        st.warning(avviso, icon="⚠️")


def modulo_ruoli(utente: Utente, lega: Lega) -> None:
    """Il presidente promuove qualcuno a editor, o lo riporta fantallenatore.

    L'editor scrive in bacheca e basta: non ratifica scambi e non importa
    dati. E' una delega stretta, non una seconda presidenza.
    """
    tutte = carica_credenziali(archivio())
    altri = {
        c.utente.nome_utente: c
        for c in tutte.values()
        if c.utente.lega_id == lega.id and c.utente.id != utente.id
    }
    if not altri:
        st.info("Non c'e' nessun altro partecipante in questa lega.", icon="👤")
        return

    riga = st.columns([3, 2, 2])
    scelto = riga[0].selectbox(
        "Partecipante",
        sorted(altri),
        format_func=lambda n: f"{altri[n].utente.nome_completo} ({n})",
        key="_ruolo_chi",
    )
    attuale = altri[scelto].utente.ruolo
    assegnabili = [Ruolo.FANTALLENATORE, Ruolo.EDITOR]
    nuovo = riga[1].selectbox(
        "Ruolo",
        assegnabili,
        index=assegnabili.index(attuale) if attuale in assegnabili else 0,
        format_func=lambda r: r.etichetta,
        key="_ruolo_quale",
    )
    riga[2].markdown(f"**Adesso e'**  \n{attuale.etichetta}")

    if attuale is Ruolo.PRESIDENTE:
        st.warning(
            "E' il presidente della lega: il ruolo non si cambia da qui.", icon="👑"
        )
        return

    if nuovo is attuale:
        st.caption("Ha gia' questo ruolo.")
        return

    if st.button(f"Assegna «{nuovo.etichetta}»", use_container_width=True):
        from dataclasses import replace as _replace

        credenziali = altri[scelto]
        aggiornate = _replace(
            credenziali, utente=_replace(credenziali.utente, ruolo=nuovo)
        )
        try:
            salva_credenziali(archivio(), aggiornate)
        except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
            st.error(f"Non riesco a salvare il ruolo: {errore}", icon="⛔")
            return
        _dati_cambiati()
        _ricorda(f"{aggiornate.utente.nome_completo} ora e' {nuovo.etichetta}.")
        st.rerun()


# ===========================================================================
# 5. Identita' della squadra, sempre modificabile
# ===========================================================================


def modulo_identita(
    squadra: Squadra | None,
    lega: Lega,
    nomi_occupati: set[str],
    chiave: str = "identita",
    compatto: bool = False,
    etichetta_salva: str | None = None,
    al_salvataggio: Callable[[], None] | None = None,
) -> bool:
    """Crea o modifica l'identita' di una squadra. Vero se ha salvato.

    Vive qui e non in una vista perche' serve in due posti: la pagina
    «Identita' squadre», che le mostra tutte, e la pagina «Squadre», dove
    guardi la tua e vuoi correggerla senza andare a cercarla altrove.

    `compatto` toglie logo, maglia caricata e anteprima: accanto alla rosa
    servono i campi, non una seconda vetrina.

    `al_salvataggio` viene chiamato appena il salvataggio e' andato a buon
    fine, prima del rerun: serve a chi tiene aperta una modalita' modifica e
    la deve richiudere. Il valore di ritorno non basta, perche' `st.rerun()`
    interrompe la funzione prima che possa restituirlo.
    """
    from .identita import (
        ColoreNonValido,
        ImmagineNonValida,
        StileMaglia,
        immagine_a_data_uri,
    )
    from .ui import invalida_dati, mostra_logo, mostra_maglia, pastiglia_colore

    nuova = squadra is None
    identita = squadra.identita if squadra else IdentitaSquadra()

    colonne = [st.container()] if compatto else st.columns([3, 2])
    modulo = colonne[0]

    with modulo:
        nome = st.text_input(
            "Nome della squadra",
            value="" if nuova else squadra.nome,
            max_chars=60,
            key=f"{chiave}_nome",
        )
        riga = st.columns(2)
        presidente = riga[0].text_input(
            "Presidente", value=identita.presidente, max_chars=60, key=f"{chiave}_pres"
        )
        anno = riga[1].number_input(
            "Anno di fondazione",
            min_value=1900,
            max_value=2100,
            value=identita.anno_fondazione or 2026,
            key=f"{chiave}_anno",
        )
        motto = st.text_input(
            "Motto",
            value=identita.motto,
            max_chars=120,
            placeholder="Chi non risica non rosica",
            key=f"{chiave}_motto",
        )
        riga = st.columns(3)
        stadio = riga[0].text_input(
            "Stadio",
            value=identita.stadio,
            max_chars=80,
            placeholder="Arena del Padel",
            key=f"{chiave}_stadio",
        )
        citta = riga[1].text_input(
            "Citta'",
            value=identita.citta,
            max_chars=60,
            placeholder="Ginevra",
            key=f"{chiave}_citta",
        )
        curva = riga[2].text_input(
            "Curva",
            value=identita.curva,
            max_chars=60,
            placeholder="Curva Nord",
            help="Come si chiama il settore dei tuoi tifosi.",
            key=f"{chiave}_curva",
        )

        st.markdown("**Colori sociali**")
        riga = st.columns(3)
        primario = riga[0].color_picker(
            "Primario", value=identita.colore_primario, key=f"{chiave}_prim"
        )
        secondario = riga[1].color_picker(
            "Secondario", value=identita.colore_secondario, key=f"{chiave}_sec"
        )
        stile = riga[2].selectbox(
            "Disegno della maglia",
            options=list(StileMaglia),
            index=list(StileMaglia).index(identita.stile_maglia),
            format_func=lambda s: s.value,
            key=f"{chiave}_stile",
        )

        file_logo = file_maglia = None
        rimuovi_maglia = False
        if not compatto:
            st.markdown("**Immagini (facoltative)**")
            st.caption(
                "Il logo e' opzionale: senza, la squadra e' comunque "
                "riconoscibile dalla maglia. Massimo 512 KB per file."
            )
            file_logo = st.file_uploader(
                "Logo",
                type=["png", "jpg", "jpeg", "webp", "svg"],
                key=f"{chiave}_logo",
            )
            file_maglia = st.file_uploader(
                "Maglia personalizzata (sostituisce quella disegnata)",
                type=["png", "jpg", "jpeg", "webp", "svg"],
                key=f"{chiave}_maglia",
            )
            rimuovi_maglia = st.checkbox(
                "Torna alla maglia disegnata dai colori",
                value=False,
                disabled=not identita.maglia_caricata,
                key=f"{chiave}_rimuovi",
            )

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

    if not compatto:
        with colonne[1]:
            st.subheader("Anteprima")
            if anteprima_identita is None:
                st.error(errore_colori)
            else:
                mostra_maglia(anteprima_identita, larghezza=180)
                st.markdown(
                    pastiglia_colore(primario, "Primario")
                    + "&nbsp;&nbsp;"
                    + pastiglia_colore(secondario, "Secondario"),
                    unsafe_allow_html=True,
                )
                if not anteprima_identita.colori_distinguibili:
                    st.warning(
                        "I due colori sono troppo simili: da lontano la maglia "
                        "sembrera' a tinta unita.",
                        icon="⚠️",
                    )
                if identita.logo:
                    mostra_logo(identita)
                st.markdown(f"### {nome or 'Senza nome'}")
                if motto:
                    st.caption(f"_{motto}_")

    st.divider()
    problemi = []
    if not nome.strip():
        problemi.append("Il nome della squadra e' obbligatorio.")
    if not presidente.strip():
        problemi.append("Il nome del presidente e' obbligatorio.")
    if nome.strip().lower() in nomi_occupati:
        problemi.append(f"Esiste gia' una squadra chiamata «{nome.strip()}».")
    if errore_colori:
        problemi.append(errore_colori)

    for problema in problemi:
        st.error(problema, icon="⛔")

    if not st.button(
        etichetta_salva or ("Crea la squadra" if nuova else "Salva le modifiche"),
        type="primary",
        disabled=bool(problemi),
        key=f"{chiave}_salva",
        use_container_width=compatto,
    ):
        return False

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
        salva_squadra(
            archivio(),
            Squadra(
                id=prossimo_id(archivio(), "squadre") if nuova else squadra.id,
                nome=nome.strip(),
                presidente=definitiva.presidente,
                identita=definitiva,
                # Va riportato a mano: ricostruendo la Squadra senza, il
                # salvataggio scollegherebbe la squadra dalla sua lega.
                lega_id=lega.id if nuova else (squadra.lega_id or lega.id),
            ),
        )
    except (ImmagineNonValida, ColoreNonValido) as errore:
        st.error(str(errore), icon="⛔")
        return False
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        st.error(f"Non riesco a salvare: {errore}", icon="⛔")
        return False

    invalida_dati()
    if al_salvataggio is not None:
        al_salvataggio()
    _ricorda(f"«{nome.strip()}» {'creata' if nuova else 'aggiornata'}.")
    st.rerun()
    return True
