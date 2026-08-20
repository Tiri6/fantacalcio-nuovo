from dataclasses import replace

from conftest import DATA_DRAFT, costruisci_rosa

from fantacalcio.conformita import Gravita, Momento, verifica_rosa
from fantacalcio.modelli import VoceDeadMoney


def codici(stato) -> set[str]:
    return {v.codice for v in stato.violazioni}


class TestRosaConforme:
    def test_nessuna_violazione(self, rosa):
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.violazioni == ()
        assert stato.conforme

    def test_fotografia_coerente(self, rosa):
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.dimensione == 30
        assert stato.anni_impegnati == 10 * 1 + 20 * 2
        assert stato.anni_disponibili == 66 - stato.anni_impegnati
        assert stato.monte_ingaggi == 90_000_000
        assert stato.spazio_salariale == 10_000_000


class TestDimensioneRosa:
    def test_sotto_il_minimo_blocca_a_fine_mercato(self):
        rosa = costruisci_rosa(dimensione=29)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.RIPARAZIONE)
        assert "rosa_minima" in codici(stato)
        assert not stato.conforme

    def test_sotto_il_minimo_in_stagione_e_solo_avviso(self):
        rosa = costruisci_rosa(dimensione=29)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        violazione = next(v for v in stato.violazioni if v.codice == "rosa_minima")
        assert violazione.gravita is Gravita.AVVISO
        assert stato.conforme

    def test_sopra_il_massimo_senza_u21(self):
        rosa = costruisci_rosa(dimensione=34, annuali=12)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert "rosa_massima" in codici(stato)

    def test_un_u21_amplia_il_limite_di_un_posto(self):
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 1
        assert stato.limite_dimensione == 34
        assert "rosa_massima" not in codici(stato)

    def test_tre_u21_portano_a_trentasei(self):
        rosa = costruisci_rosa(dimensione=36, annuali=12, u21=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.limite_dimensione == 36
        assert "rosa_massima" not in codici(stato)

    def test_u21_straniero_non_da_diritto_al_posto(self):
        """Articolo 2: il posto extra spetta solo all'Under 21 italiano."""
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        u21 = min(rosa._indice.values(), key=lambda g: g.id)
        rosa._indice[u21.id] = replace(u21, nazionalita="Francia")

        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 0
        assert "rosa_massima" in codici(stato)

    def test_ventunenne_al_draft_non_e_piu_u21(self):
        """Chi compie 21 anni prima del draft perde lo status per la stagione."""
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        u21 = min(rosa._indice.values(), key=lambda g: g.id)
        from datetime import date

        rosa._indice[u21.id] = replace(u21, data_nascita=date(2005, 1, 1))

        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 0


class TestPortieri:
    def test_quattro_portieri_bloccano(self):
        stato = verifica_rosa(costruisci_rosa(portieri=4), DATA_DRAFT)
        assert "portieri" in codici(stato)

    def test_meno_di_tre_portieri_e_consentito(self):
        """La V2.1 ha sostituito "3 portieri obbligatori" con "massimo 3"."""
        stato = verifica_rosa(costruisci_rosa(portieri=2), DATA_DRAFT)
        assert "portieri" not in codici(stato)


class TestMonteAnni:
    def test_oltre_sessantasei_anni_blocca(self):
        # 30 giocatori: 5 annuali + 25 da 3 anni = 80 anni.
        rosa = costruisci_rosa(annuali=5, anni_altri=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.anni_impegnati == 80
        assert "monte_anni" in codici(stato)

    def test_esattamente_sessantasei_e_ammesso(self):
        # 30 giocatori: 24 annuali + 6 da 7... serve una combinazione valida:
        # 12 annuali + 18 da 3 anni = 66.
        rosa = costruisci_rosa(annuali=12, anni_altri=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.anni_impegnati == 66
        assert "monte_anni" not in codici(stato)

    def test_contratto_oltre_cinque_anni_blocca(self):
        rosa = costruisci_rosa(dimensione=30, annuali=29, anni_altri=6)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert "durata_contratto" in codici(stato)


class TestRegolaUnTerzo:
    def test_annuali_insufficienti_bloccano_a_fine_mercato(self):
        rosa = costruisci_rosa(dimensione=30, annuali=9)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        violazione = next(v for v in stato.violazioni if v.codice == "regola_un_terzo")
        assert violazione.valore == 9
        assert violazione.limite == 10
        assert not stato.conforme

    def test_in_stagione_e_solo_avviso(self):
        rosa = costruisci_rosa(dimensione=30, annuali=9)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        assert stato.conforme

    def test_rosa_ampliata_alza_la_soglia(self):
        """34 giocatori richiedono 12 annuali, non piu' 10."""
        rosa = costruisci_rosa(dimensione=34, annuali=11, u21=1)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.annuali_richiesti == 12
        assert "regola_un_terzo" in codici(stato)


class TestEconomia:
    def test_sopra_il_cap_blocca_a_fine_asta(self):
        rosa = costruisci_rosa(ingaggio=3_500_000)  # 105M
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert "salary_cap" in codici(stato)
        assert not stato.conforme

    def test_sopra_il_cap_in_stagione_e_solo_avviso(self):
        """Articolo 8b: lo sforamento da scambio si sana prima dell'asta."""
        rosa = costruisci_rosa(ingaggio=3_500_000)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        violazione = next(v for v in stato.violazioni if v.codice == "salary_cap")
        assert violazione.gravita is Gravita.AVVISO
        assert stato.conforme

    def test_sotto_il_floor_blocca_a_fine_asta(self):
        rosa = costruisci_rosa(ingaggio=2_000_000)  # 60M
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.RIPARAZIONE)
        assert "salary_floor" in codici(stato)

    def test_il_floor_non_si_verifica_in_stagione(self):
        rosa = costruisci_rosa(ingaggio=2_000_000)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        assert "salary_floor" not in codici(stato)


class TestDeadMoney:
    def test_pesa_sul_cap(self):
        rosa = costruisci_rosa(ingaggio=3_200_000)  # 96M di ingaggi
        rosa.dead_money = [VoceDeadMoney(1, "Tagliato", 6_000_000, "2026/27")]

        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.spesa_salariale == 102_000_000
        assert "salary_cap" in codici(stato)

    def test_non_conta_per_il_floor(self):
        """Articolo 4: la soglia minima va raggiunta con gli ingaggi in rosa."""
        rosa = costruisci_rosa(ingaggio=2_500_000)  # 75M, sotto gli 80M
        rosa.dead_money = [VoceDeadMoney(1, "Tagliato", 20_000_000, "2026/27")]

        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.monte_ingaggi == 75_000_000
        assert "salary_floor" in codici(stato)

    def test_gia_addebitato_non_pesa_piu(self):
        rosa = costruisci_rosa()
        rosa.dead_money = [
            VoceDeadMoney(1, "Tagliato", 9_000_000, "2025/26", addebitato=True)
        ]
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.dead_money == 0
        assert stato.spesa_salariale == 90_000_000
