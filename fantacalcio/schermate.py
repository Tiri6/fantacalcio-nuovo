"""Le schermate che precedono l'app vera: accesso, lega, squadra.

Sono i tre cancelli che un partecipante attraversa una volta sola:

    registrati / accedi  ->  crea o unisciti a una lega  ->  crea la squadra

Stanno qui e non in `viste/` perche' girano *prima* di `st.navigation`: non
sono pagine del menu, sono le condizioni per vederlo.
"""

from __future__ import annotations

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
    Utente,
    UtenteNonValido,
    assegna_squadra,
    cambia_password,
    entra_in_lega,
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
    prossimo_id,
    salva_credenziali,
    salva_invito,
    salva_lega,
    salva_squadra,
)
from .identita import ColoreNonValido, IdentitaSquadra, StileMaglia
from .leghe import (
    EmailNonValida,
    FormatoCampionato,
    Lega,
    LegaNonValida,
    Modalita,
    OpzioniLega,
    StatoInvito,
    TipoAsta,
    crea_invito,
    crea_lega,
    invito_per_email,
    moduli_disponibili,
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


def _modulo_opzioni() -> OpzioniLega | None:
    """Tutte le caselle della creazione lega. None se qualcosa non torna.

    Le opzioni stanno fuori da `st.form` di proposito: cambiando modalita' i
    moduli ammessi cambiano, e dentro un form non si aggiornerebbero finche'
    non premi invio.
    """
    st.markdown("#### Impostazioni generali")
    riga = st.columns(3)
    modalita = riga[0].radio(
        "Modalita'",
        list(Modalita),
        # Mantra e' il default: e' la modalita' in cui gioca questa lega, e
        # partire dall'altra vuol dire che chi non guarda crea la lega sbagliata.
        index=list(Modalita).index(Modalita.MANTRA),
        format_func=lambda m: m.etichetta,
        horizontal=True,
        help="Mantra usa i ruoli specifici (Dc, E, W, T...). Classic usa P/D/C/A.",
    )
    partecipanti = riga[1].number_input(
        "Partecipanti", min_value=2, max_value=20, value=10, step=1
    )
    formato = riga[2].selectbox(
        "Formato", list(FormatoCampionato), format_func=lambda f: f.etichetta
    )

    riga = st.columns(3)
    giornate = riga[0].number_input(
        "Giornate totali", min_value=1, max_value=76, value=27, step=1
    )
    punti_vittoria = riga[1].number_input(
        "Punti per vittoria", min_value=1, max_value=5, value=3, step=1
    )
    punti_pareggio = riga[2].number_input(
        "Punti per pareggio", min_value=0, max_value=3, value=1, step=1
    )

    st.markdown("#### Rosa e mercato")
    riga = st.columns(3)
    tipo_asta = riga[0].selectbox(
        "Come si assegnano i giocatori",
        list(TipoAsta),
        index=list(TipoAsta).index(TipoAsta.DRAFT),
        format_func=lambda t: t.etichetta,
        help="«Draft» significa che l'assegnazione avviene fuori dalla "
        "piattaforma e i risultati si caricano via CSV.",
    )
    anni_contratto = riga[1].number_input(
        "Anni di contratto (massimo)",
        min_value=1,
        max_value=10,
        value=5,
        step=1,
        help="Durata massima di un contratto. E' la leva del fantacalcio "
        "manageriale: quanto a lungo puoi legare a te un giocatore.",
    )
    budget_milioni = riga[2].number_input(
        "Budget cap annuale (milioni)",
        min_value=0.0,
        max_value=1_000.0,
        value=100.0,
        step=5.0,
        help="Tetto agli ingaggi di una squadra in una stagione. Fonte degli "
        "stipendi: Capology.",
    )
    stagione = st.text_input("Stagione", value="2026/27")

    st.markdown("**Limite di giocatori per ruolo**")
    con_limiti = st.radio(
        "Limite di giocatori per ruolo",
        [True, False],
        format_func=lambda x: "Imposta un limite per ruolo" if x else "Nessun limite",
        horizontal=True,
        label_visibility="collapsed",
        help="Senza limiti conta solo il monte anni: puoi tesserare i ruoli "
        "che vuoi, nelle proporzioni che vuoi.",
    )

    if con_limiti:
        riga = st.columns(4)
        portieri = riga[0].number_input("Portieri", 1, 6, 3)
        difensori = riga[1].number_input("Difensori", 3, 15, 8)
        centrocampisti = riga[2].number_input("Centrocampisti", 3, 15, 8)
        attaccanti = riga[3].number_input("Attaccanti", 2, 12, 6)
        totale_rosa = portieri + difensori + centrocampisti + attaccanti
        st.caption(f"Rosa complessiva: **{totale_rosa}** giocatori")
    else:
        portieri = difensori = centrocampisti = attaccanti = None
        totale_rosa = None
        st.caption("Nessun tetto per ruolo: la rosa la limita il monte anni.")

    st.markdown("**Vincoli di rosa e di mercato**")
    riga = st.columns(3)
    minimo_italiani = riga[0].number_input(
        "Minimo giocatori italiani",
        min_value=0,
        max_value=40,
        value=0,
        step=1,
        help="0 = nessun vincolo.",
    )
    minimo_u21 = riga[1].number_input(
        "Minimo Under 21 italiani",
        min_value=0,
        max_value=20,
        value=0,
        step=1,
        help="Sottoinsieme del vincolo qui accanto: un Under 21 italiano "
        "conta anche come italiano. 0 = nessun vincolo.",
    )
    scambi_stagione = riga[2].number_input(
        "Scambi permessi a stagione",
        min_value=0,
        max_value=50,
        value=0,
        step=1,
        help="Per squadra, nell'arco della stagione. 0 = illimitati.",
    )

    st.markdown("#### Competizioni")
    st.caption(
        "Il campionato c'e' sempre. Le altre compaiono nel menu solo se le accendi qui."
    )
    riga = st.columns(2)
    coppa = riga[0].toggle("Coppa Italia", value=False)
    supercoppa = riga[1].toggle("Supercoppa", value=False)

    regole_coppa = RegoleCoppa()
    if coppa:
        with st.expander("Regole della Coppa Italia", expanded=True):
            riga = st.columns(3)
            formato_coppa = riga[0].selectbox(
                "Formato", list(FormatoCoppa), format_func=lambda f: f.etichetta
            )
            ammesse = riga[1].selectbox(
                "Squadre ammesse",
                [2, 4, 8, 16],
                index=2,
                help="Una potenza di due: altrimenti il tabellone non si chiude.",
            )
            teste = riga[2].toggle("Teste di serie dalla classifica", value=True)

            riga = st.columns(3)
            prima = riga[0].number_input("Primo turno alla giornata", 1, 40, 5)
            passo = riga[1].number_input("Un turno ogni quante giornate", 1, 10, 4)
            spareggio = riga[2].toggle(
                "Parita': passa chi ha piu' fantapunti",
                value=True,
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

    regole_supercoppa = RegoleSupercoppa()
    if supercoppa:
        with st.expander("Regole della Supercoppa", expanded=True):
            criterio = st.selectbox(
                "Chi si affronta",
                list(CriterioSupercoppa),
                format_func=lambda c: c.etichetta,
                help="Il primo anno l'albo d'oro e' vuoto: le due squadre le "
                "scegli a mano. Dall'anno dopo si ricavano da sole.",
            )
            prima_stagione = st.toggle(
                "Si gioca prima dell'inizio del campionato", value=True
            )
            regole_supercoppa = RegoleSupercoppa(
                criterio=criterio, prima_della_stagione=bool(prima_stagione)
            )

    st.markdown("#### Formazione")
    disponibili = moduli_disponibili(modalita)
    moduli = st.multiselect(
        "Moduli ammessi",
        disponibili,
        default=list(disponibili),
        help="Chi schiera la formazione potra' scegliere solo fra questi.",
    )
    riga = st.columns(3)
    panchinari = riga[0].number_input("Panchinari", 0, 20, 12)
    sostituzioni = riga[1].toggle("Sostituzioni automatiche", value=True)
    capitano = riga[2].toggle("Capitano", value=True)

    st.markdown("#### Punteggio e fasce di gol")
    riga = st.columns(3)
    soglia = riga[0].number_input(
        "Punti per il primo gol",
        min_value=50.0,
        max_value=80.0,
        value=66.0,
        step=0.5,
        help="Sotto questa soglia il risultato e' 0 gol.",
    )
    passo = riga[1].number_input(
        "Punti per ogni gol successivo",
        min_value=1.0,
        max_value=12.0,
        value=6.0,
        step=0.5,
    )
    senza_voto = riga[2].number_input(
        "Voto d'ufficio a chi non gioca",
        min_value=0.0,
        max_value=6.0,
        value=6.0,
        step=0.5,
    )

    anteprima = ", ".join(f"{int(soglia + passo * n)}→{n + 1}" for n in range(4))
    st.caption(f"Fasce risultanti: {anteprima}, e cosi' via")

    st.markdown("#### Modificatori di reparto")
    riga = st.columns(3)
    mod_difesa = riga[0].toggle("Modificatore difesa", value=True)
    mod_centrocampo = riga[1].toggle("Modificatore centrocampo", value=False)
    mod_attacco = riga[2].toggle("Modificatore attacco", value=False)
    st.caption(
        "Le soglie esatte di ogni modificatore sono parametri: si cambiano "
        "senza toccare il codice. Quelle di partenza sono in PUNTI_APERTI.md, "
        "da confermare con la lega."
    )

    with st.expander("Bonus e malus"):
        riga = st.columns(3)
        gol = riga[0].number_input("Gol segnato", 0.0, 10.0, 3.0, 0.5)
        gol_subito = riga[1].number_input("Gol subito", -5.0, 0.0, -1.0, 0.5)
        assist = riga[2].number_input("Assist", 0.0, 5.0, 1.0, 0.5)
        riga = st.columns(3)
        rigore_parato = riga[0].number_input("Rigore parato", 0.0, 6.0, 3.0, 0.5)
        rigore_sbagliato = riga[1].number_input("Rigore sbagliato", -6.0, 0.0, -3.0, 0.5)
        autogol = riga[2].number_input("Autogol", -6.0, 0.0, -2.0, 0.5)
        riga = st.columns(3)
        ammonizione = riga[0].number_input("Ammonizione", -3.0, 0.0, -0.5, 0.5)
        espulsione = riga[1].number_input("Espulsione", -5.0, 0.0, -1.0, 0.5)
        imbattuto = riga[2].number_input("Portiere imbattuto", 0.0, 3.0, 1.0, 0.5)

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
            rosa_portieri=None if portieri is None else int(portieri),
            rosa_difensori=None if difensori is None else int(difensori),
            rosa_centrocampisti=(None if centrocampisti is None else int(centrocampisti)),
            rosa_attaccanti=None if attaccanti is None else int(attaccanti),
            minimo_italiani=int(minimo_italiani),
            minimo_u21_italiani=int(minimo_u21),
            scambi_per_stagione=int(scambi_stagione),
            moduli_ammessi=tuple(moduli),
            panchinari=int(panchinari),
            sostituzioni_automatiche=bool(sostituzioni),
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
        ), st.session_state.get("_stagione_lega", stagione)
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
