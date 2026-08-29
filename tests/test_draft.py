import random
from collections import Counter

import pytest

from fantacalcio.draft import (
    PESI_FASCIA,
    chiamata_numero,
    distribuzione_pick,
    griglia_chiamate,
    ordine_riparazione,
    ordine_round,
    sorteggia_lottery,
    tabellone_draft,
    turni_di_chiamata,
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


class TestTabelloneChiamate:
    """Ordine di chiamata: serpente o fisso, e di chi e' il turno adesso."""

    SQUADRE = ("Tiri Team", "Padel United", "Nuovo Cuneo FC", "Real Bisalta")

    def test_il_primo_round_segue_l_ordine(self):
        chiamate = turni_di_chiamata(self.SQUADRE, round_totali=1)
        assert [c.squadra for c in chiamate] == list(self.SQUADRE)
        assert [c.numero for c in chiamate] == [1, 2, 3, 4]
        assert all(c.round == 1 for c in chiamate)

    def test_a_serpente_i_round_pari_vanno_al_contrario(self):
        chiamate = turni_di_chiamata(self.SQUADRE, round_totali=2, serpente=True)
        assert [c.squadra for c in chiamate] == [
            *self.SQUADRE,
            *reversed(self.SQUADRE),
        ]
        # Chi chiude un round dispari riapre il successivo: due di fila.
        assert chiamate[3].squadra == chiamate[4].squadra

    def test_a_ordine_fisso_ogni_round_ricomincia_da_capo(self):
        chiamate = turni_di_chiamata(self.SQUADRE, round_totali=3, serpente=False)
        assert [c.squadra for c in chiamate[:4]] == list(self.SQUADRE)
        assert [c.squadra for c in chiamate[4:8]] == list(self.SQUADRE)
        assert [c.squadra for c in chiamate[8:]] == list(self.SQUADRE)

    def test_il_terzo_round_a_serpente_torna_all_ordine_di_partenza(self):
        chiamate = turni_di_chiamata(self.SQUADRE, round_totali=3, serpente=True)
        assert [c.squadra for c in chiamate[8:]] == list(self.SQUADRE)

    def test_chiamata_singola_senza_costruire_tutto(self):
        # La numero 5 e' la prima del secondo round: a serpente e' l'ultima
        # squadra dell'ordine, che ha appena chiamato.
        chiamata = chiamata_numero(self.SQUADRE, 5, serpente=True)
        assert chiamata.round == 2
        assert chiamata.posizione == 1
        assert chiamata.squadra == "Real Bisalta"
        assert chiamata.etichetta == "Round 2 · pick 1"

        assert chiamata_numero(self.SQUADRE, 5, serpente=False).squadra == "Tiri Team"

    def test_coerenza_fra_il_singolo_e_il_tabellone(self):
        chiamate = turni_di_chiamata(self.SQUADRE, round_totali=5)
        for chiamata in chiamate:
            assert chiamata_numero(self.SQUADRE, chiamata.numero) == chiamata

    def test_la_griglia_raggruppa_per_round(self):
        griglia = griglia_chiamate(self.SQUADRE, round_totali=2)
        assert [numero for numero, _ in griglia] == [1, 2]
        assert griglia[1][1] == tuple(reversed(self.SQUADRE))

    def test_numeri_impossibili(self):
        with pytest.raises(ValueError, match="partono da 1"):
            chiamata_numero(self.SQUADRE, 0)
        with pytest.raises(ValueError, match="almeno una squadra"):
            chiamata_numero((), 1)
        with pytest.raises(ValueError, match="almeno un round"):
            turni_di_chiamata(self.SQUADRE, 0)


class TestAssegnazioneContratti:
    """Assegnare e svincolare un giocatore alla volta."""

    def archivio_con_giocatori(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite

        arch = ArchivioSQLite(tmp_path / "draft.db")
        arch.svuota("contratti")
        arch.scrivi(
            "giocatori",
            [
                {
                    "id": 1,
                    "id_ufficiale": 2071,
                    "nome": "Dybala",
                    "club": "Roma",
                    "ruoli": "A;Pc",
                    "ingaggio": 6_000_000,
                    "nazionalita": "Argentina",
                    "data_nascita": None,
                    "quotazione": 24,
                    "fvm": 70,
                }
            ],
            chiave="id",
        )
        return arch

    def test_assegna_e_poi_svincola(self, tmp_path):
        from fantacalcio.data import assegna_contratto, svincola_giocatore

        arch = self.archivio_con_giocatori(tmp_path)
        assegna_contratto(arch, giocatore_id=1, squadra_id=2, anni_residui=3)
        contratti = arch.contratti()
        assert len(contratti) == 1
        assert int(contratti.iloc[0]["squadra_id"]) == 2
        assert int(contratti.iloc[0]["anni_residui"]) == 3

        svincola_giocatore(arch, 1)
        assert arch.contratti().empty

    def test_riassegnare_sposta_invece_di_duplicare(self, tmp_path):
        from fantacalcio.data import assegna_contratto

        arch = self.archivio_con_giocatori(tmp_path)
        assegna_contratto(arch, 1, squadra_id=2, anni_residui=3)
        assegna_contratto(arch, 1, squadra_id=5, anni_residui=1)
        contratti = arch.contratti()
        assert len(contratti) == 1
        assert int(contratti.iloc[0]["squadra_id"]) == 5

    def test_svincolare_chi_non_ha_contratto_non_esplode(self, tmp_path):
        from fantacalcio.data import svincola_giocatore

        arch = self.archivio_con_giocatori(tmp_path)
        svincola_giocatore(arch, 999)
        assert arch.contratti().empty
