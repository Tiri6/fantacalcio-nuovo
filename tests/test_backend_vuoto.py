"""Un database senza righe non deve rompere niente.

I due backend rispondono in modo diverso al «non c'e' niente»: SQLite
restituisce una tabella vuota **con le sue colonne**, PostgREST una lista
vuota, da cui pandas costruisce un DataFrame **senza colonne**. Il codice che
fa `contratti["squadra_id"]` funziona sul primo e alza KeyError sul secondo.

E' successo davvero, in produzione, su ogni pagina: le squadre c'erano e i
contratti no. Provare in locale su SQLite non poteva scoprirlo — questi test
simulano la forma di PostgREST apposta.
"""

import pandas as pd
import pytest

from fantacalcio.data import (
    COLONNE_ATTESE,
    Archivio,
    calendario_dettagliato,
    carica_albo,
    carica_annunci,
    carica_credenziali,
    carica_giocatori,
    carica_leghe,
    carica_rose,
    carica_squadre,
    con_colonne,
)

# Il minimo perche' ci sia qualcosa da mettere in relazione: due squadre e
# nient'altro. E' lo stato di una lega appena creata.
SQUADRE = [
    {
        "id": 1,
        "nome": "Tiri Team",
        "presidente": "Marco",
        "motto": "",
        "stadio": "",
        "citta": "",
        "curva": "",
        "colore_primario": "#2e7d32",
        "colore_secondario": "#ffffff",
        "stile_maglia": "TINTA_UNITA",
        "logo": None,
        "maglia_caricata": None,
        "anno_fondazione": None,
        "lega_id": 1,
    },
    {
        "id": 2,
        "nome": "Padel United",
        "presidente": "Luca",
        "motto": "",
        "stadio": "",
        "citta": "",
        "curva": "",
        "colore_primario": "#1565c0",
        "colore_secondario": "#ffffff",
        "stile_maglia": "STRISCE",
        "logo": None,
        "maglia_caricata": None,
        "anno_fondazione": None,
        "lega_id": 1,
    },
]


class ArchivioComeSupabase(Archivio):
    """Risponde come PostgREST: senza righe, nessuna colonna.

    Non usa `con_colonne` di proposito: e' il backend grezzo, quello che il
    codice deve saper reggere.
    """

    nome = "finto PostgREST"

    def __init__(self, righe: dict[str, list[dict]] | None = None):
        self._righe = righe or {}

    def tabella(self, nome: str) -> pd.DataFrame:
        return pd.DataFrame(self._righe.get(nome, []))


class ArchivioNormalizzato(ArchivioComeSupabase):
    """Lo stesso backend, passato dal normalizzatore come quello vero."""

    def tabella(self, nome: str) -> pd.DataFrame:
        return con_colonne(nome, super().tabella(nome))


def test_il_finto_backend_riproduce_il_guasto():
    """Se questo smette di fallire, il test non prova piu' niente."""
    grezzo = ArchivioComeSupabase({"squadre": SQUADRE})
    assert list(grezzo.tabella("contratti").columns) == []
    with pytest.raises(KeyError):
        carica_rose(grezzo)


class TestDatabaseVuoto:
    @pytest.fixture
    def arch(self):
        return ArchivioNormalizzato()

    @pytest.fixture
    def con_squadre(self):
        return ArchivioNormalizzato({"squadre": SQUADRE})

    def test_rose_su_database_del_tutto_vuoto(self, arch):
        assert carica_rose(arch) == {}

    def test_rose_con_squadre_ma_senza_contratti(self, con_squadre):
        """Il caso vero: lega creata, draft non ancora fatto."""
        rose = carica_rose(con_squadre)
        assert len(rose) == 2
        assert all(not r.contratti for r in rose.values())
        assert rose[1].squadra.nome == "Tiri Team"

    def test_i_conti_di_una_rosa_vuota_sono_zero(self, con_squadre):
        rosa = carica_rose(con_squadre)[1]
        assert rosa.anni_impegnati == 0
        assert rosa.monte_ingaggi == 0
        assert rosa.dimensione == 0

    @pytest.mark.parametrize(
        "funzione",
        [
            carica_squadre,
            carica_giocatori,
            carica_leghe,
            carica_credenziali,
            carica_annunci,
            carica_albo,
            calendario_dettagliato,
        ],
    )
    def test_ogni_lettura_regge_il_vuoto(self, arch, funzione):
        risultato = funzione(arch)
        assert len(risultato) == 0

    def test_calendario_con_squadre_ma_senza_partite(self, con_squadre):
        assert calendario_dettagliato(con_squadre).empty


class TestNormalizzazione:
    def test_una_tabella_vuota_riceve_le_sue_colonne(self):
        normalizzata = con_colonne("contratti", pd.DataFrame([]))
        assert "squadra_id" in normalizzata.columns
        assert normalizzata.empty

    def test_una_tabella_piena_non_si_tocca(self):
        piena = pd.DataFrame([{"solo_questa": 1}])
        assert list(con_colonne("contratti", piena).columns) == ["solo_questa"]

    def test_una_tabella_sconosciuta_passa_com_e(self):
        vuota = pd.DataFrame([])
        assert con_colonne("tabella_mai_vista", vuota) is vuota

    @pytest.mark.parametrize("nome", sorted(COLONNE_ATTESE))
    def test_le_colonne_dichiarate_esistono_davvero(self, nome, tmp_path):
        """L'elenco non deve scollarsi dallo schema vero."""
        from fantacalcio.data import ArchivioSQLite

        reale = set(ArchivioSQLite(tmp_path / "prova.db").tabella(nome).columns)
        dichiarate = set(COLONNE_ATTESE[nome])
        assert dichiarate <= reale, f"in {nome} non esistono: {dichiarate - reale}"
