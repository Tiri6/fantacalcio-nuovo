import random
from collections import Counter

import pytest

from fantacalcio.draft import (
    PESI_FASCIA,
    distribuzione_pick,
    ordine_riparazione,
    ordine_round,
    sorteggia_lottery,
    tabellone_draft,
)


class TestSorteggioLottery:
    def test_tutte_le_squadre_ricevono_una_pick(self, classifica):
        esito = sorteggia_lottery(classifica, random.Random(7))
        assert sorted(esito.ordine) == sorted(classifica)
        assert len(set(esito.ordine)) == 10

    def test_le_prime_cinque_pick_vanno_alla_fascia_bassa(self, classifica):
        """Articolo 3: le pick 1-5 si sorteggiano tra la 10a e la 6a."""
        fascia_bassa = set(classifica[5:])
        for seme in range(30):
            esito = sorteggia_lottery(classifica, random.Random(seme))
            assert set(esito.ordine[:5]) == fascia_bassa

    def test_le_ultime_cinque_pick_vanno_alla_fascia_alta(self, classifica):
        fascia_alta = set(classifica[:5])
        for seme in range(30):
            esito = sorteggia_lottery(classifica, random.Random(seme))
            assert set(esito.ordine[5:]) == fascia_alta

    def test_le_fasce_sono_ordinate_dalla_peggio_classificata(self, classifica):
        esito = sorteggia_lottery(classifica, random.Random(1))
        assert esito.fascia_bassa[0] == classifica[9]  # 10a
        assert esito.fascia_alta[0] == classifica[4]  # 5a

    def test_ultima_classificata_prende_la_prima_pick_circa_meta_delle_volte(
        self, classifica
    ):
        rng = random.Random(2024)
        prime = Counter(sorteggia_lottery(classifica, rng).ordine[0] for _ in range(4000))
        quota = prime[classifica[9]] / 4000
        assert 0.47 < quota < 0.53, f"la 10a ha preso la pick 1 nel {quota:.1%} dei casi"

    def test_quinta_classificata_domina_la_sesta_pick(self, classifica):
        rng = random.Random(99)
        seste = Counter(sorteggia_lottery(classifica, rng).ordine[5] for _ in range(4000))
        quota = seste[classifica[4]] / 4000
        assert 0.47 < quota < 0.53

    def test_prima_classificata_raramente_scavalca(self, classifica):
        """Alla 1a spetta il 5%: deve restare l'eccezione."""
        rng = random.Random(5)
        seste = Counter(sorteggia_lottery(classifica, rng).ordine[5] for _ in range(4000))
        assert seste[classifica[0]] / 4000 < 0.08

    def test_pesi_del_regolamento(self):
        assert PESI_FASCIA == (50, 20, 15, 10, 5)
        assert sum(PESI_FASCIA) == 100

    def test_numero_dispari_di_squadre(self):
        with pytest.raises(ValueError, match="due fasce"):
            sorteggia_lottery([f"S{i}" for i in range(9)])

    def test_squadre_duplicate(self):
        with pytest.raises(ValueError, match="duplicate"):
            sorteggia_lottery(["A", "B", "A", "B"])

    def test_pick_di(self, classifica):
        esito = sorteggia_lottery(classifica, random.Random(3))
        assert esito.pick_di(esito.ordine[0]) == 1
        assert esito.pick_di(esito.ordine[9]) == 10


class TestOrdineDeiRound:
    def test_primo_round_segue_la_lottery(self, classifica):
        lottery = list(reversed(classifica))
        assert ordine_round(1, lottery, classifica) == tuple(lottery)

    def test_secondo_round_e_a_serpente(self, classifica):
        lottery = list(reversed(classifica))
        assert ordine_round(2, lottery, classifica) == tuple(reversed(lottery))

    @pytest.mark.parametrize("numero", [3, 6, 9, 12])
    def test_i_multipli_di_tre_seguono_la_classifica(self, classifica, numero):
        """Articolo 3: in questi giri si chiama dalla 1a alla 10a classificata."""
        lottery = list(reversed(classifica))
        assert ordine_round(numero, lottery, classifica) == tuple(classifica)

    @pytest.mark.parametrize("numero", [4, 5, 7, 8, 10, 11])
    def test_gli_altri_round_seguono_la_lottery(self, classifica, numero):
        lottery = list(reversed(classifica))
        assert ordine_round(numero, lottery, classifica) == tuple(lottery)

    def test_round_zero_non_esiste(self, classifica):
        with pytest.raises(ValueError, match="partire da 1"):
            ordine_round(0, classifica, classifica)

    def test_tabellone_completo(self, classifica):
        lottery = list(reversed(classifica))
        tabellone = tabellone_draft(6, lottery, classifica)
        assert [n for n, _ in tabellone] == [1, 2, 3, 4, 5, 6]
        assert tabellone[2][1] == tuple(classifica)
        assert all(len(ordine) == 10 for _, ordine in tabellone)


class TestAstaDiRiparazione:
    def test_ordine_inverso_di_classifica(self, classifica):
        assert ordine_riparazione(classifica) == tuple(reversed(classifica))
        assert ordine_riparazione(classifica)[0] == classifica[-1]


class TestDistribuzionePick:
    def test_ogni_squadra_ha_una_distribuzione_completa(self, classifica):
        distribuzione = distribuzione_pick(classifica, simulazioni=500)
        assert set(distribuzione) == set(classifica)
        for probabilita in distribuzione.values():
            assert sum(probabilita.values()) == pytest.approx(1.0, abs=0.001)

    def test_la_fascia_alta_non_puo_prendere_le_prime_pick(self, classifica):
        distribuzione = distribuzione_pick(classifica, simulazioni=500)
        for squadra in classifica[:5]:
            assert all(pick > 5 for pick in distribuzione[squadra])
