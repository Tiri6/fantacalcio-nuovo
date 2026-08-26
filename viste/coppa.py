"""Coppa Italia: tabellone, turni e regole. Compare solo se la lega la gioca."""

import pandas as pd
import streamlit as st

from fantacalcio import tema, ui

ui.barra_laterale()

lega = ui.lega_corrente()
regole = lega.opzioni.regole_coppa

ui.intestazione(
    "Coppa Italia",
    "🥇",
    f"{regole.formato.etichetta} · {regole.squadre_ammesse} squadre ammesse.",
)

partite = ui.calendario()
classifica = ui.classifica()
disputate = ui.giornate_disputate(partite) if not partite.empty else 0

giornate_turni = regole.giornate_dei_turni()

ui.griglia_dati(
    [
        {"etichetta": "Squadre ammesse", "valore": str(regole.squadre_ammesse)},
        {
            "etichetta": "Turni",
            "valore": str(regole.turni),
            "nota": f"dal {regole.nome_turno(1).lower()} alla finale",
        },
        {
            "etichetta": "Primo turno",
            "valore": f"G{regole.prima_giornata}",
            "nota": f"poi ogni {regole.ogni_quante_giornate} giornate",
        },
    ]
)

st.divider()

# --- tabellone --------------------------------------------------------------

st.subheader("Tabellone")

turni = []
for numero, giornata in enumerate(giornate_turni, start=1):
    turni.append(
        {
            "Turno": regole.nome_turno(numero),
            "Giornata": f"G{giornata}",
            "Stato": "Disputato" if disputate >= giornata else "Da giocare",
        }
    )
st.dataframe(pd.DataFrame(turni), hide_index=True, use_container_width=True)

# --- ammesse ----------------------------------------------------------------

st.subheader("Chi si qualifica")

if regole.teste_di_serie and not classifica.empty:
    ammesse = classifica.head(regole.squadre_ammesse)
    st.caption(
        f"Teste di serie dalla classifica: passano le prime "
        f"{regole.squadre_ammesse}. Ecco come sarebbero oggi."
    )
    st.dataframe(
        ammesse[["Squadra"]].assign(Testa=range(1, len(ammesse) + 1)),
        hide_index=True,
        use_container_width=False,
    )

    if len(ammesse) == regole.squadre_ammesse:
        st.markdown(f"**Accoppiamenti del {regole.nome_turno(1).lower()}**")
        nomi = list(ammesse["Squadra"])
        # Tabellone classico: la prima incontra l'ultima ammessa, e cosi' via.
        for alta, bassa in zip(nomi, reversed(nomi), strict=True):
            if nomi.index(alta) >= len(nomi) // 2:
                break
            st.markdown(
                f"{tema.pastiglia(alta)} contro {tema.pastiglia(bassa, tema.AZZURRO)}",
                unsafe_allow_html=True,
            )
elif regole.teste_di_serie:
    st.info(
        "Le teste di serie si assegnano dalla classifica: compariranno dopo "
        "le prime giornate.",
        icon="🏁",
    )
else:
    st.info("Sorteggio libero: gli accoppiamenti li fa chi amministra.", icon="🎲")

st.divider()

# --- regole -----------------------------------------------------------------

st.subheader("Le regole di questa coppa")
st.markdown(
    f"""
- **Formato**: {regole.formato.etichetta}
- **Squadre ammesse**: {regole.squadre_ammesse}
- **Teste di serie**: {
        "dalla classifica" if regole.teste_di_serie else "no, sorteggio libero"
    }
- **In caso di parita'**: {
        "passa chi ha totalizzato piu' fantapunti"
        if regole.spareggio_ai_fantapunti
        else "si ripete la sfida"
    }
- **Calendario**: primo turno alla {regole.prima_giornata}ª giornata, poi uno
  ogni {regole.ogni_quante_giornate}
"""
)

st.caption(
    "I risultati della coppa si importano come quelli di campionato, dalla "
    "pagina «Importa dati»: il gestionale non calcola i punteggi."
)
