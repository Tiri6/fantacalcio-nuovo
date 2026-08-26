"""Ciclo di vita di uno scambio: proposta, accettazione, ratifica."""

from datetime import datetime, timedelta

import pytest
from conftest import STAGIONE, costruisci_rosa

from fantacalcio.autenticazione import Ruolo, Utente
from fantacalcio.data import ArchivioSQLite
from fantacalcio.mercato import PropostaScambio
from fantacalcio.scambi import (
    StatoScambio,
    TransizioneNonAmmessa,
    accetta,
    annulla,
    applica_alle_rose,
    carica_scambi,
    conta_conclusi,
    giornata_di_efficacia,
    proponi,
    ratifica,
    rifiuta,
    salva_scambio,
    scambi_residui,
)

PRESIDENTE = Utente(1, "marco", "Marco", Ruolo.PRESIDENTE, squadra_id=1)
ALLENATORE_A = Utente(2, "anna", "Anna", Ruolo.FANTALLENATORE, squadra_id=1)
ALLENATORE_B = Utente(3, "bruno", "Bruno", Ruolo.FANTALLENATORE, squadra_id=2)


@pytest.fixture
def rose():
    return (
        costruisci_rosa(squadra_id=1, nome="Tiri Team"),
        costruisci_rosa(squadra_id=2, nome="Padel United"),
    )


@pytest.fixture
def proposta():
    return PropostaScambio(da_squadra_a=(1029,), da_squadra_b=(2029,))


@pytest.fixture
def scambio(rose, proposta):
    creato, _ = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)
    return creato


class TestProposta:
    def test_registra_i_movimenti(self, rose, proposta):
        creato, violazioni = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)

        assert violazioni == []
        assert creato.stato is StatoScambio.PROPOSTO
        assert len(creato.movimenti) == 2
        assert {m.da_squadra_id for m in creato.movimenti} == {1, 2}
        assert all(not m.prolungato for m in creato.movimenti)

    def test_registra_il_prolungamento(self, rose):
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 4})
        creato, _ = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)

        movimento = creato.movimenti[0]
        assert movimento.prolungato
        assert movimento.anni_dopo == 4

    def test_non_si_propone_per_una_squadra_altrui(self, rose, proposta):
        with pytest.raises(TransizioneNonAmmessa, match="non puo' proporre"):
            proponi(1, *rose, proposta, ALLENATORE_B, STAGIONE)

    def test_il_presidente_puo_proporre_per_chiunque(self, rose, proposta):
        creato, _ = proponi(1, *rose, proposta, PRESIDENTE, STAGIONE)
        assert creato.stato is StatoScambio.PROPOSTO

    def test_le_violazioni_arrivano_ma_non_bloccano_la_bozza(self, rose):
        # Lodo Bono: la durata non puo' scendere.
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 1})
        creato, violazioni = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)

        assert creato is not None
        assert "lodo_bono" in {v.codice for v in violazioni}

    def test_giocatore_non_in_rosa(self, rose):
        proposta = PropostaScambio(da_squadra_a=(999_999,))
        with pytest.raises(ValueError, match="non ha in rosa"):
            proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)

    def test_riconversione_in_proposta(self, scambio, proposta):
        ricostruita = scambio.a_proposta()
        assert ricostruita.da_squadra_a == proposta.da_squadra_a
        assert ricostruita.da_squadra_b == proposta.da_squadra_b


class TestAccettazioneERifiuto:
    def test_accetta_chi_riceve(self, scambio):
        accettato = accetta(scambio, ALLENATORE_B)
        assert accettato.stato is StatoScambio.ACCETTATO
        assert accettato.deciso_da == ALLENATORE_B.id

    def test_il_proponente_non_puo_accettare_da_solo(self, scambio):
        with pytest.raises(TransizioneNonAmmessa, match="ha ricevuto la proposta"):
            accetta(scambio, ALLENATORE_A)

    def test_rifiuto(self, scambio):
        assert rifiuta(scambio, ALLENATORE_B).stato is StatoScambio.RIFIUTATO

    def test_il_proponente_ritira(self, scambio):
        assert annulla(scambio, ALLENATORE_A).stato is StatoScambio.ANNULLATO

    def test_chi_riceve_non_ritira(self, scambio):
        with pytest.raises(TransizioneNonAmmessa, match="ha proposto"):
            annulla(scambio, ALLENATORE_B)

    def test_non_si_accetta_due_volte(self, scambio):
        accettato = accetta(scambio, ALLENATORE_B)
        with pytest.raises(TransizioneNonAmmessa, match="Accettato"):
            accetta(accettato, ALLENATORE_B)

    def test_uno_scambio_ritirato_e_chiuso(self, scambio):
        ritirato = annulla(scambio, ALLENATORE_A)
        assert not ritirato.stato.aperto
        with pytest.raises(TransizioneNonAmmessa):
            accetta(ritirato, ALLENATORE_B)


class TestRatifica:
    def test_solo_il_presidente_ratifica(self, scambio, rose):
        accettato = accetta(scambio, ALLENATORE_B)
        with pytest.raises(TransizioneNonAmmessa, match="presidente"):
            ratifica(accettato, *rose, ALLENATORE_A, STAGIONE)

    def test_non_si_ratifica_una_proposta_non_accettata(self, scambio, rose):
        with pytest.raises(TransizioneNonAmmessa, match="Proposto"):
            ratifica(scambio, *rose, PRESIDENTE, STAGIONE)

    def test_ratifica_sposta_i_giocatori(self, scambio, rose):
        accettato = accetta(scambio, ALLENATORE_B)
        ratificato, nuova_a, nuova_b = ratifica(
            accettato, *rose, PRESIDENTE, STAGIONE, giornata_efficacia=5
        )

        assert ratificato.stato is StatoScambio.RATIFICATO
        assert ratificato.ratificato_da == PRESIDENTE.id
        assert ratificato.giornata_efficacia == 5
        assert nuova_a.contratto_di(2029) is not None
        assert nuova_a.contratto_di(1029) is None
        assert nuova_b.contratto_di(1029) is not None

    def test_ratifica_rifiutata_se_lo_scambio_non_e_piu_valido(self, rose):
        """Tra proposta e ratifica le rose cambiano: si ricontrolla sempre."""
        rosa_a, rosa_b = rose
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 5})
        creato, _ = proponi(1, rosa_a, rosa_b, proposta, ALLENATORE_A, STAGIONE)
        accettato = accetta(creato, ALLENATORE_B)

        # Nel frattempo B riempie il monte anni e non puo' piu' assorbire nulla.
        rosa_b_piena = costruisci_rosa(
            squadra_id=2, nome="Padel United", annuali=12, anni_altri=3
        )
        with pytest.raises(TransizioneNonAmmessa, match="non e' piu' valido"):
            ratifica(accettato, rosa_a, rosa_b_piena, PRESIDENTE, STAGIONE)


class TestGiornataDiEfficacia:
    def test_con_almeno_24_ore_vale_subito(self, scambio):
        inizio = scambio.creato_il + timedelta(hours=30)
        assert giornata_di_efficacia(scambio, 5, inizio) == 5

    def test_oltre_il_termine_vale_dalla_successiva(self, scambio):
        inizio = scambio.creato_il + timedelta(hours=10)
        assert giornata_di_efficacia(scambio, 5, inizio) == 6

    def test_al_limite_esatto_vale_subito(self, scambio):
        inizio = scambio.creato_il + timedelta(hours=24)
        assert giornata_di_efficacia(scambio, 5, inizio) == 5

    def test_senza_orario_non_si_sposta(self, scambio):
        assert giornata_di_efficacia(scambio, 5, None) == 5


class TestPersistenza:
    def test_salva_e_rilegge(self, tmp_path, rose, proposta):
        archivio = ArchivioSQLite(tmp_path / "scambi.db")
        creato, _ = proponi(
            1,
            *rose,
            proposta,
            ALLENATORE_A,
            STAGIONE,
            quando=datetime(2026, 10, 1, 18, 30),
            note="Scambio alla pari",
        )
        salva_scambio(archivio, creato)

        riletti = carica_scambi(archivio)
        assert len(riletti) == 1
        riletto = riletti[0]
        assert riletto.id == creato.id
        assert riletto.stato is StatoScambio.PROPOSTO
        assert riletto.note == "Scambio alla pari"
        assert riletto.creato_il == datetime(2026, 10, 1, 18, 30)
        assert len(riletto.movimenti) == 2

    def test_aggiornare_lo_stato_non_duplica(self, tmp_path, rose, proposta):
        archivio = ArchivioSQLite(tmp_path / "scambi2.db")
        creato, _ = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)
        salva_scambio(archivio, creato)
        salva_scambio(archivio, accetta(creato, ALLENATORE_B))

        riletti = carica_scambi(archivio)
        assert len(riletti) == 1
        assert riletti[0].stato is StatoScambio.ACCETTATO

    def test_archivio_vuoto(self, tmp_path):
        assert carica_scambi(ArchivioSQLite(tmp_path / "vuoto.db")) == []

    def test_applica_alle_rose_scrive_i_contratti(self, tmp_path, rose, proposta):
        archivio = ArchivioSQLite(tmp_path / "applica.db")
        creato, _ = proponi(1, *rose, proposta, ALLENATORE_A, STAGIONE)
        _, nuova_a, nuova_b = ratifica(
            accetta(creato, ALLENATORE_B), *rose, PRESIDENTE, STAGIONE
        )
        applica_alle_rose(archivio, nuova_a, nuova_b)

        contratti = archivio.contratti()
        assert (
            int(contratti[contratti["giocatore_id"] == 1029]["squadra_id"].iloc[0]) == 2
        )
        assert (
            int(contratti[contratti["giocatore_id"] == 2029]["squadra_id"].iloc[0]) == 1
        )


class TestLimiteScambiStagionale:
    """Il limite di scambi per stagione conta solo quelli andati a buon fine."""

    def scambio(self, id_, stato, squadra_a=1, squadra_b=2, creato="2026-10-01T10:00:00"):
        from fantacalcio.scambi import Scambio

        return Scambio(
            id=id_,
            squadra_a_id=squadra_a,
            squadra_b_id=squadra_b,
            proposto_da=1,
            stato=stato,
            movimenti=[],
            creato_il=creato,
        )

    def test_solo_i_ratificati_contano(self):
        """Una proposta in attesa non ha spostato nessuno: non deve pesare."""
        registro = [
            self.scambio(1, StatoScambio.RATIFICATO),
            self.scambio(2, StatoScambio.PROPOSTO),
            self.scambio(3, StatoScambio.ACCETTATO),
            self.scambio(4, StatoScambio.RIFIUTATO),
            self.scambio(5, StatoScambio.ANNULLATO),
        ]
        assert conta_conclusi(registro, 1) == 1

    def test_conta_da_entrambi_i_lati(self):
        registro = [
            self.scambio(1, StatoScambio.RATIFICATO, squadra_a=1, squadra_b=2),
            self.scambio(2, StatoScambio.RATIFICATO, squadra_a=3, squadra_b=1),
        ]
        assert conta_conclusi(registro, 1) == 2
        assert conta_conclusi(registro, 3) == 1

    def test_gli_scambi_di_altri_non_contano(self):
        registro = [self.scambio(1, StatoScambio.RATIFICATO, squadra_a=2, squadra_b=3)]
        assert conta_conclusi(registro, 1) == 0

    def test_limite_zero_significa_illimitati(self):
        registro = [self.scambio(n, StatoScambio.RATIFICATO) for n in range(1, 20)]
        assert scambi_residui(registro, 1, limite=0) is None

    def test_i_residui_scalano(self):
        registro = [self.scambio(1, StatoScambio.RATIFICATO)]
        assert scambi_residui(registro, 1, limite=5) == 4

    def test_i_residui_non_diventano_negativi(self):
        registro = [self.scambio(n, StatoScambio.RATIFICATO) for n in range(1, 8)]
        assert scambi_residui(registro, 1, limite=3) == 0

    def test_filtro_per_stagione(self):
        registro = [
            self.scambio(1, StatoScambio.RATIFICATO, creato="2026-10-01T10:00:00"),
            self.scambio(2, StatoScambio.RATIFICATO, creato="2025-10-01T10:00:00"),
        ]
        assert conta_conclusi(registro, 1, stagione="2026/27") == 1
