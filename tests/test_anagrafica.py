"""Date all'italiana, sesso e squadra del cuore."""

from datetime import date

import pytest

from fantacalcio.anagrafica import (
    ALTRO_ESTERO,
    ALTRO_ITALIA,
    ETA_MASSIMA,
    ETA_MINIMA,
    NESSUNA,
    SERIE_A_PREDEFINITA,
    DataNonValida,
    Sesso,
    anni_compiuti,
    leggi_data_italiana,
    scrivi_data_italiana,
    squadra_valida,
    squadre_preferite,
)

OGGI = date(2026, 8, 25)


class TestDataItaliana:
    @pytest.mark.parametrize(
        "scritta",
        ["24/03/1991", "24-03-1991", "24.03.1991", "24 03 1991", " 24/03/1991 "],
    )
    def test_separatori_ammessi(self, scritta):
        assert leggi_data_italiana(scritta, OGGI) == date(1991, 3, 24)

    def test_zeri_non_obbligatori(self):
        assert leggi_data_italiana("4/3/1991", OGGI) == date(1991, 3, 4)

    @pytest.mark.parametrize("scritta,atteso", [("24/03/91", 1991), ("24/03/05", 2005)])
    def test_anno_a_due_cifre(self, scritta, atteso):
        """'91' vuol dire 1991, '05' vuol dire 2005: la soglia sta a meta'."""
        assert leggi_data_italiana(scritta, OGGI).year == atteso

    @pytest.mark.parametrize("scritta", ["", "   ", None])
    def test_vuota(self, scritta):
        with pytest.raises(DataNonValida, match="vuota"):
            leggi_data_italiana(scritta, OGGI)

    @pytest.mark.parametrize("scritta", ["24/03", "24/03/1991/12", "ieri"])
    def test_non_e_una_data(self, scritta):
        with pytest.raises(DataNonValida):
            leggi_data_italiana(scritta, OGGI)

    def test_il_messaggio_mostra_il_formato_atteso(self):
        with pytest.raises(DataNonValida, match="gg/mm/aaaa"):
            leggi_data_italiana("24/03", OGGI)

    @pytest.mark.parametrize("scritta", ["32/01/1991", "29/02/1991", "24/13/1991"])
    def test_giorni_inesistenti(self, scritta):
        with pytest.raises(DataNonValida, match="esistente"):
            leggi_data_italiana(scritta, OGGI)

    def test_il_29_febbraio_bisestile_esiste(self):
        assert leggi_data_italiana("29/02/1992", OGGI) == date(1992, 2, 29)

    def test_nel_futuro_rifiutata(self):
        with pytest.raises(DataNonValida, match="futuro"):
            leggi_data_italiana("01/01/2030", OGGI)

    def test_anno_digitato_male(self):
        """1066 invece di 1966 e' l'errore piu' comune: va intercettato."""
        with pytest.raises(DataNonValida, match="anno"):
            leggi_data_italiana("24/03/1066", OGGI)

    def test_troppo_giovane(self):
        with pytest.raises(DataNonValida, match=str(ETA_MINIMA)):
            leggi_data_italiana("01/01/2020", OGGI)

    def test_il_limite_massimo_e_coerente(self):
        assert ETA_MASSIMA > ETA_MINIMA

    def test_andata_e_ritorno(self):
        assert scrivi_data_italiana(date(1991, 3, 24)) == "24/03/1991"

    def test_scrivere_una_data_mancante(self):
        assert scrivi_data_italiana(None) == ""


class TestEta:
    def test_compleanno_non_ancora_passato(self):
        assert anni_compiuti(date(1991, 12, 31), OGGI) == 34

    def test_compleanno_gia_passato(self):
        assert anni_compiuti(date(1991, 1, 1), OGGI) == 35

    def test_proprio_oggi(self):
        assert anni_compiuti(date(1991, 8, 25), OGGI) == 35


class TestSquadraDelCuore:
    def test_l_elenco_contiene_le_voci_di_servizio(self):
        elenco = squadre_preferite()
        for voce in (ALTRO_ITALIA, ALTRO_ESTERO, NESSUNA):
            assert voce in elenco

    def test_le_voci_altro_stanno_in_fondo(self):
        """Devono restare le ultime: sono ripieghi, non squadre."""
        elenco = squadre_preferite()
        assert elenco[-3:] == [ALTRO_ITALIA, ALTRO_ESTERO, NESSUNA]

    def test_la_serie_a_arriva_dal_listone_quando_c_e(self):
        elenco = squadre_preferite(["Inter", "Milan", "Juventus"])
        assert elenco[:3] == ["Inter", "Juventus", "Milan"]

    def test_senza_listone_si_usa_l_elenco_predefinito(self):
        assert set(SERIE_A_PREDEFINITA) <= set(squadre_preferite())

    def test_nessun_duplicato_fra_a_e_b(self):
        elenco = squadre_preferite(["Monza", "Inter"])
        assert len(elenco) == len(set(elenco))

    def test_una_squadra_ammessa_resta_com_e(self):
        assert squadra_valida("Inter", ["Inter", ALTRO_ITALIA]) == "Inter"

    def test_una_squadra_sconosciuta_diventa_altro(self):
        assert squadra_valida("Pippo FC", ["Inter", ALTRO_ITALIA]) == ALTRO_ITALIA

    @pytest.mark.parametrize("scelta", ["", "   ", None])
    def test_scelta_vuota(self, scelta):
        assert squadra_valida(scelta) == NESSUNA


def test_ogni_sesso_ha_un_etichetta():
    assert all(s.etichetta for s in Sesso)
