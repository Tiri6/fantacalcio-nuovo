"""Impostazioni della lega: codice d'invito, partecipanti, regole di gioco.

E' la pagina che risponde alla domanda "come si entra qui dentro?" e "con che
regole giochiamo?". Le opzioni sono in sola lettura per chi non amministra.
"""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.data import archivio, carica_inviti
from fantacalcio.leghe import moduli_disponibili

ui.barra_laterale()
schermate.mostra_messaggio()
# Se la lega e' appena nata e chi l'ha creata e' arrivato qui saltando la
# squadra, il codice non l'ha ancora visto in grande: glielo si mostra qui.
schermate.festeggia_lega_nuova()

utente = ui.utente_corrente()
lega = ui.lega_corrente()

ui.intestazione(
    lega.nome,
    icona="🏆",
    sottotitolo=f"Stagione {lega.stagione} — {lega.opzioni.modalita.etichetta}",
)

opzioni = lega.opzioni
amministra = utente.id == lega.admin_id or utente.puo_importare

# --- come si entra ----------------------------------------------------------

st.subheader("Come si entra")

sinistra, destra = st.columns([2, 3], gap="large")

with sinistra:
    st.markdown(tema.codice_invito(lega.codice_invito), unsafe_allow_html=True)
    st.caption(
        "Chi ha questo codice puo' unirsi alla lega dalla schermata iniziale, "
        "scheda «Unisciti a una lega»."
    )

with destra:
    iscritti = [c.utente for c in ui.tutte_le_credenziali().values()]
    dentro = [u for u in iscritti if u.lega_id == lega.id]
    con_squadra = [u for u in dentro if u.ha_squadra]

    ui.griglia_dati(
        [
            {
                "etichetta": "Partecipanti",
                "valore": f"{len(dentro)}/{opzioni.partecipanti}",
                "nota": "iscritti sui posti previsti",
                "stato": "ok" if len(dentro) <= opzioni.partecipanti else "avviso",
                "quota": len(dentro) / max(opzioni.partecipanti, 1),
            },
            {
                "etichetta": "Squadre fondate",
                "valore": str(len(con_squadra)),
                "nota": f"{len(dentro) - len(con_squadra)} ancora senza squadra",
                "stato": "ok" if len(con_squadra) == len(dentro) else "avviso",
            },
        ]
    )

if amministra:
    with st.expander("✉️ Invita qualcuno per email"):
        st.caption(
            "Riservare un posto non manda nessuna mail: l'app non ha un server "
            "di posta. Registra chi e' atteso, cosi' quando quella persona si "
            "iscrive con quell'indirizzo trova la lega gia' pronta. Il codice "
            "va comunque girato a mano."
        )
        schermate.modulo_invito(lega, utente)

        inviti = carica_inviti(archivio(), lega.id)
        if inviti:
            st.dataframe(
                pd.DataFrame(
                    [{"Email": i.email, "Stato": i.stato.etichetta} for i in inviti]
                ),
                hide_index=True,
                use_container_width=True,
            )

st.divider()

# --- chi c'e' ---------------------------------------------------------------

st.subheader("Chi c'e'")

squadre = ui.squadre()
nomi_squadra = (
    {int(r["id"]): str(r["nome"]) for _, r in squadre.iterrows()}
    if not squadre.empty
    else {}
)

if dentro:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Partecipante": u.nome,
                    "Utente": u.nome_utente,
                    "Ruolo": u.ruolo.etichetta,
                    "Squadra": nomi_squadra.get(u.squadra_id, "— nessuna —"),
                }
                for u in sorted(dentro, key=lambda u: u.nome.lower())
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("Nessun iscritto ancora.", icon="🫥")

st.divider()

# --- con che regole ---------------------------------------------------------

st.subheader("Con che regole si gioca")

generali, formazione, punteggio = st.tabs(["Generali", "Rosa e formazione", "Punteggio"])

with generali:
    ui.griglia_dati(
        [
            {"etichetta": "Modalita'", "valore": opzioni.modalita.etichetta},
            {"etichetta": "Formato", "valore": opzioni.formato.etichetta},
            {"etichetta": "Giornate", "valore": str(opzioni.giornate_totali)},
            {"etichetta": "Assegnazione", "valore": opzioni.tipo_asta.etichetta},
        ]
    )
    st.caption(
        f"Vittoria {opzioni.punti_vittoria} punti · pareggio "
        f"{opzioni.punti_pareggio} · crediti iniziali {opzioni.crediti_iniziali}"
    )

with formazione:
    ui.griglia_dati(
        [
            {
                "etichetta": "Rosa",
                "valore": str(opzioni.rosa_totale),
                "nota": (
                    f"{opzioni.rosa_portieri} Por · {opzioni.rosa_difensori} Dif · "
                    f"{opzioni.rosa_centrocampisti} Cen · {opzioni.rosa_attaccanti} Att"
                ),
            },
            {"etichetta": "Panchinari", "valore": str(opzioni.panchinari)},
            {
                "etichetta": "Moduli ammessi",
                "valore": f"{len(opzioni.moduli_ammessi)}",
                "nota": f"su {len(moduli_disponibili(opzioni.modalita))} possibili",
            },
        ]
    )
    st.markdown(
        " ".join(tema.pastiglia(m) for m in opzioni.moduli_ammessi),
        unsafe_allow_html=True,
    )
    st.caption(
        ("Sostituzioni automatiche attive. " if opzioni.sostituzioni_automatiche else "")
        + ("Capitano attivo." if opzioni.capitano else "Nessun capitano.")
    )

with punteggio:
    st.markdown("**Fasce di gol**")
    fasce = pd.DataFrame(
        [
            {
                "Fantapunti": f"{opzioni.soglia_primo_gol + opzioni.passo_gol * n:g}+",
                "Gol": n + 1,
            }
            for n in range(6)
        ]
    )
    st.dataframe(fasce, hide_index=True, use_container_width=False)

    attivi = [
        nome
        for nome, acceso in (
            ("Difesa", opzioni.modificatore_difesa),
            ("Centrocampo", opzioni.modificatore_centrocampo),
            ("Attacco", opzioni.modificatore_attacco),
        )
        if acceso
    ]
    st.markdown("**Modificatori attivi**")
    st.markdown(
        " ".join(tema.pastiglia(n) for n in attivi) if attivi else "_Nessuno_",
        unsafe_allow_html=True,
    )

    st.markdown("**Bonus e malus**")
    bonus = opzioni.bonus
    st.dataframe(
        pd.DataFrame(
            [
                {"Evento": "Gol segnato", "Valore": bonus.gol_segnato},
                {"Evento": "Gol subito", "Valore": bonus.gol_subito},
                {"Evento": "Assist", "Valore": bonus.assist},
                {"Evento": "Rigore parato", "Valore": bonus.rigore_parato},
                {"Evento": "Rigore sbagliato", "Valore": bonus.rigore_sbagliato},
                {"Evento": "Autogol", "Valore": bonus.autogol},
                {"Evento": "Ammonizione", "Valore": bonus.ammonizione},
                {"Evento": "Espulsione", "Valore": bonus.espulsione},
                {"Evento": "Portiere imbattuto", "Valore": bonus.portiere_imbattuto},
            ]
        ),
        hide_index=True,
        use_container_width=False,
    )

if not amministra:
    st.caption("Solo chi amministra la lega puo' cambiare queste impostazioni.")
