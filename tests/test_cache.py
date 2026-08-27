"""Le cache di Streamlit non devono contenere oggetti di dominio.

Streamlit ricarica i sorgenti senza riavviare il processo: dopo un
aggiornamento la cache puo' contenere oggetti costruiti dalla classe vecchia,
e il primo accesso a un campo aggiunto di recente alza un AttributeError che
uccide l'intera app. E' successo davvero, con `opzioni.coppa_italia`.

Un DataFrame di tipi elementari non porta con se' una classe che puo' cambiare
forma. Questa e' la prova che la regola resti.
"""

import ast
import pathlib
import pickle

import pytest

UI = pathlib.Path(__file__).resolve().parents[1] / "fantacalcio" / "ui.py"

# Cio' che una funzione in cache puo' restituire: dati, non oggetti nostri.
RITORNI_AMMESSI = {"pd.DataFrame", "dict", "int", "float", "str", "bool", "list[str]"}


def funzioni_in_cache() -> list[tuple[str, str | None]]:
    """Nome e tipo di ritorno di ogni funzione decorata con @st.cache_*."""
    albero = ast.parse(UI.read_text(encoding="utf-8"))
    trovate = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        for decoratore in nodo.decorator_list:
            testo = ast.unparse(decoratore)
            if "cache_data" in testo or "cache_resource" in testo:
                ritorno = ast.unparse(nodo.returns) if nodo.returns else None
                trovate.append((nodo.name, ritorno))
    return trovate


def test_ci_sono_funzioni_in_cache_da_controllare():
    """Se questo fallisce il test non sta piu' guardando niente."""
    assert funzioni_in_cache()


@pytest.mark.parametrize("nome,ritorno", funzioni_in_cache())
def test_ogni_funzione_in_cache_restituisce_dati(nome, ritorno):
    assert ritorno is not None, (
        f"`{nome}` e' in cache ma non dichiara cosa restituisce: senza "
        f"annotazione non si puo' garantire che non sia un oggetto di dominio."
    )
    assert ritorno in RITORNI_AMMESSI, (
        f"`{nome}` mette in cache un `{ritorno}`. Le cache devono contenere "
        f"solo dati elementari: dopo un aggiornamento del codice un oggetto "
        f"in cache conserva la forma vecchia e rompe l'app. Metti in cache la "
        f"tabella grezza e ricostruisci l'oggetto a ogni giro."
    )


class OpzioniPrima:
    """La forma che la classe aveva prima dell'aggiornamento."""

    def __init__(self):
        self.partecipanti = 10


class OpzioniDopo:
    """La stessa classe dopo aver guadagnato un campo."""

    def __init__(self):
        self.partecipanti = 10
        self.coppa_italia = False


def test_il_guasto_che_ha_originato_la_regola():
    """Un oggetto messo via prima dell'aggiornamento non ha i campi nuovi.

    E' cio' che accade quando Streamlit ricarica i sorgenti tenendo vive le
    cache: l'istanza conservata resta quella di prima, e il codice nuovo le
    chiede un campo che lei non ha mai avuto.
    """
    conservato = pickle.dumps(OpzioniPrima())
    riletto = pickle.loads(conservato)

    # il codice nuovo si aspetta questo...
    assert hasattr(OpzioniDopo(), "coppa_italia")
    # ...ma l'oggetto in cache viene da prima
    assert not hasattr(riletto, "coppa_italia")
    with pytest.raises(AttributeError):
        _ = riletto.coppa_italia
