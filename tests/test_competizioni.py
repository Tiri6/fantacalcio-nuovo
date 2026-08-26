"""Competizioni: coppa, supercoppa, albo d'oro e calendario dei weekend."""

from datetime import date

import pytest

from fantacalcio.competizioni import (
    CompetizioneNonValida,
    CriterioSupercoppa,
    FormatoCoppa,
    RegoleCoppa,
    RegoleSupercoppa,
    TipoCompetizione,
    Titolo,
    bacheca_squadre,
    costruisci_weekend,
    crea_titolo,
    data_riferimento_u21,
    finaliste_supercoppa,
    ordina_albo,
    titolo_esistente,
)


class TestDataU21:
    @pytest.mark.parametrize(
        "stagione,atteso", [("2026/27", 2026), ("2030/31", 2030), ("1999/00", 1999)]
    )
    def test_si_ricava_l_anno_dalla_stagione(self, stagione, atteso):
        assert data_riferimento_u21(stagione) == date(atteso, 8, 31)

    @pytest.mark.parametrize("stagione", ["", None, "boh", 42])
    def test_stagione_illeggibile_non_esplode(self, stagione):
        """Una stagione scritta male non deve impedire di caricare una rosa."""
        assert data_riferimento_u21(stagione).month == 8

    def test_e_sempre_il_31_agosto(self):
        assert data_riferimento_u21("2026/27").day == 31


class TestRegoleCoppa:
    def test_turni_da_otto_squadre(self):
        assert RegoleCoppa(squadre_ammesse=8).turni == 3

    @pytest.mark.parametrize("quante,turni", [(2, 1), (4, 2), (8, 3), (16, 4)])
    def test_turni_per_dimensione(self, quante, turni):
        assert RegoleCoppa(squadre_ammesse=quante).turni == turni

    @pytest.mark.parametrize("quante", [3, 5, 6, 7, 10, 12])
    def test_solo_potenze_di_due(self, quante):
        """Con un numero diverso il tabellone non si chiude."""
        with pytest.raises(CompetizioneNonValida, match="potenza di due"):
            RegoleCoppa(squadre_ammesse=quante)

    def test_almeno_due_squadre(self):
        with pytest.raises(CompetizioneNonValida, match="due squadre"):
            RegoleCoppa(squadre_ammesse=1)

    def test_nomi_dei_turni(self):
        regole = RegoleCoppa(squadre_ammesse=8)
        assert regole.nome_turno(1) == "Quarti di finale"
        assert regole.nome_turno(2) == "Semifinali"
        assert regole.nome_turno(3) == "Finale"

    def test_a_sedici_si_parte_dagli_ottavi(self):
        assert RegoleCoppa(squadre_ammesse=16).nome_turno(1) == "Ottavi di finale"

    def test_giornate_dei_turni(self):
        regole = RegoleCoppa(squadre_ammesse=8, prima_giornata=5, ogni_quante_giornate=4)
        assert regole.giornate_dei_turni() == (5, 9, 13)

    @pytest.mark.parametrize("campo", ["prima_giornata", "ogni_quante_giornate"])
    def test_valori_non_positivi(self, campo):
        with pytest.raises(CompetizioneNonValida):
            RegoleCoppa(**{campo: 0})


class TestWeekend:
    def test_senza_coppa_le_numerazioni_restano_allineate(self):
        turni = costruisci_weekend(10, 27, None, prima_giornata_serie_a=1)
        assert turni[0].descrizione.endswith("1ª giornata")
        assert turni[4].descrizione.endswith("5ª giornata")

    def test_la_lega_parte_a_stagione_iniziata(self):
        turni = costruisci_weekend(10, 27, None, prima_giornata_serie_a=6)
        assert turni[0].giornata_serie_a == 6
        assert "1ª giornata" in turni[0].descrizione

    def test_il_turno_di_coppa_fa_slittare_il_campionato(self):
        """La giornata di campionato non sparisce: si sposta di un weekend."""
        regole = RegoleCoppa(squadre_ammesse=8, prima_giornata=5, ogni_quante_giornate=4)
        turni = costruisci_weekend(12, 27, regole, prima_giornata_serie_a=1)
        assert "4ª giornata" in turni[3].descrizione
        assert turni[4].impegni[0][0] is TipoCompetizione.COPPA_ITALIA
        # dopo la coppa il campionato riprende dalla quinta, non dalla sesta
        assert "5ª giornata" in turni[5].descrizione

    def test_nessuna_giornata_di_campionato_va_persa(self):
        regole = RegoleCoppa(squadre_ammesse=8, prima_giornata=3, ogni_quante_giornate=3)
        turni = costruisci_weekend(20, 10, regole, prima_giornata_serie_a=1)
        giocate = [
            e[1] for t in turni for e in t.impegni if e[0] is TipoCompetizione.CAMPIONATO
        ]
        assert giocate == [f"{n}ª giornata" for n in range(1, 11)]

    def test_finito_il_campionato_i_weekend_restano_liberi(self):
        turni = costruisci_weekend(10, 3, None)
        assert turni[3].libero
        assert turni[3].descrizione == "— nessun impegno —"


class TestAlbo:
    def titolo(self, id_, competizione, stagione, squadra):
        return crea_titolo(id_, 1, competizione, stagione, squadra)

    def test_un_titolo_senza_squadra_non_ha_senso(self):
        with pytest.raises(CompetizioneNonValida, match="squadra"):
            Titolo(1, 1, TipoCompetizione.CAMPIONATO, "2026/27", None, "  ")

    def test_un_titolo_senza_stagione_non_e_storicizzabile(self):
        with pytest.raises(CompetizioneNonValida, match="stagione"):
            Titolo(1, 1, TipoCompetizione.CAMPIONATO, "", None, "Tiri Team")

    def test_ordine_dalla_stagione_piu_recente(self):
        titoli = [
            self.titolo(1, TipoCompetizione.CAMPIONATO, "2024/25", "A"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "B"),
            self.titolo(3, TipoCompetizione.CAMPIONATO, "2025/26", "C"),
        ]
        assert [t.stagione for t in ordina_albo(titoli)] == [
            "2026/27",
            "2025/26",
            "2024/25",
        ]

    def test_nella_stessa_stagione_prima_il_campionato(self):
        titoli = [
            self.titolo(1, TipoCompetizione.SUPERCOPPA, "2026/27", "A"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "B"),
        ]
        assert ordina_albo(titoli)[0].competizione is TipoCompetizione.CAMPIONATO

    def test_conteggio_per_squadra(self):
        titoli = [
            self.titolo(1, TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "Tiri Team"),
            self.titolo(3, TipoCompetizione.COPPA_ITALIA, "2026/27", "Padel United"),
        ]
        conteggio = bacheca_squadre(titoli)
        assert conteggio["Tiri Team"][TipoCompetizione.CAMPIONATO] == 2
        assert conteggio["Padel United"][TipoCompetizione.COPPA_ITALIA] == 1

    def test_si_trova_il_titolo_di_una_stagione(self):
        titoli = [self.titolo(1, TipoCompetizione.CAMPIONATO, "2026/27", "A")]
        assert titolo_esistente(titoli, TipoCompetizione.CAMPIONATO, "2026/27")
        assert not titolo_esistente(titoli, TipoCompetizione.COPPA_ITALIA, "2026/27")
        assert not titolo_esistente(titoli, TipoCompetizione.CAMPIONATO, "2025/26")


class TestSupercoppa:
    def titolo(self, competizione, stagione, squadra):
        return crea_titolo(1, 1, competizione, stagione, squadra)

    def test_il_primo_anno_non_si_deduce_niente(self):
        """Albo vuoto: le due squadre le sceglie l'amministratore."""
        assert finaliste_supercoppa([], RegoleSupercoppa(), "2025/26") == (None, None)

    def test_dedotte_dall_albo(self):
        titoli = [
            self.titolo(TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team"),
            self.titolo(TipoCompetizione.COPPA_ITALIA, "2025/26", "Padel United"),
        ]
        assert finaliste_supercoppa(titoli, RegoleSupercoppa(), "2025/26") == (
            "Tiri Team",
            "Padel United",
        )

    def test_col_criterio_manuale_non_si_deduce_mai(self):
        titoli = [self.titolo(TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team")]
        regole = RegoleSupercoppa(criterio=CriterioSupercoppa.MANUALE)
        assert finaliste_supercoppa(titoli, regole, "2025/26") == (None, None)

    def test_manca_la_vincitrice_di_coppa(self):
        titoli = [self.titolo(TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team")]
        campione, sfidante = finaliste_supercoppa(titoli, RegoleSupercoppa(), "2025/26")
        assert campione == "Tiri Team"
        assert sfidante is None


def test_ogni_competizione_ha_icona_ed_etichetta():
    assert all(c.icona and c.etichetta for c in TipoCompetizione)


def test_ogni_formato_di_coppa_ha_un_etichetta():
    assert all(f.etichetta for f in FormatoCoppa)
