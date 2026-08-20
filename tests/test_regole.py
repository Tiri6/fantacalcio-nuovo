import pytest

from fantacalcio.regole import ParametriLega, fasce_gol, parametri_da_dict


class TestEspansioneU21:
    @pytest.mark.parametrize("u21,atteso", [(0, 33), (1, 34), (2, 35), (3, 36)])
    def test_un_posto_per_ogni_u21(self, parametri, u21, atteso):
        assert parametri.rosa_massimo(u21) == atteso

    def test_oltre_tre_u21_non_amplia_ulteriormente(self, parametri):
        assert parametri.rosa_massimo(5) == 36

    def test_valori_negativi_ignorati(self, parametri):
        assert parametri.rosa_massimo(-2) == 33


class TestRegolaUnTerzo:
    @pytest.mark.parametrize(
        "dimensione,minimo",
        [(30, 10), (31, 11), (32, 11), (33, 11), (34, 12), (35, 12), (36, 12)],
    )
    def test_soglie_del_regolamento(self, parametri, dimensione, minimo):
        assert parametri.minimo_annuali(dimensione) == minimo

    def test_fuori_fascia_usa_la_fascia_piu_vicina(self, parametri):
        assert parametri.minimo_annuali(25) == 10
        assert parametri.minimo_annuali(40) == 12


class TestFasceGol:
    @pytest.mark.parametrize(
        "punti,gol", [(59, 0), (65.5, 0), (66, 1), (71.5, 1), (72, 2), (90, 5)]
    )
    def test_di_sei_in_sei(self, parametri, punti, gol):
        assert fasce_gol(punti, parametri) == gol

    def test_soglia_alternativa_a_sessanta(self):
        """Se la lega votasse il primo gol a 60, basta cambiare il parametro."""
        parametri = ParametriLega(soglia_primo_gol=60.0)
        assert fasce_gol(59.9, parametri) == 0
        assert fasce_gol(60, parametri) == 1
        assert fasce_gol(66, parametri) == 2


class TestParametriDaDict:
    def test_sovrascrive_solo_le_chiavi_note(self):
        parametri = parametri_da_dict({"salary_cap": 120_000_000, "inventata": 1})
        assert parametri.salary_cap == 120_000_000
        assert parametri.monte_anni == ParametriLega().monte_anni
