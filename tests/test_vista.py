"""Le tabelle mostrate a schermo devono essere coerenti con il dominio."""

import pytest

from fantacalcio.conformita import Momento
from fantacalcio.data import ArchivioSQLite, carica_rose
from fantacalcio.demo_data import DATA_DRAFT, GIORNATE_GIOCATE, SQUADRE
from fantacalcio.vista import (
    andamento_punti,
    classifica,
    contratti_in_scadenza,
    cruscotto_lega,
    rosa_dettagliata,
    stati_rose,
    violazioni_lega,
)


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    return ArchivioSQLite(tmp_path_factory.mktemp("db") / "vista.db")


@pytest.fixture(scope="module")
def rose(archivio):
    return carica_rose(archivio)


@pytest.fixture(scope="module")
def stati(rose):
    return stati_rose(rose, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)


class TestClassifica:
    def test_una_riga_per_squadra(self, archivio):
        tabella = classifica(archivio)
        assert len(tabella) == len(SQUADRE)
        assert tabella["Pos"].tolist() == list(range(1, len(SQUADRE) + 1))
        assert (tabella["PG"] == GIORNATE_GIOCATE).all()
        assert (tabella["V"] + tabella["N"] + tabella["P"] == tabella["PG"]).all()

    def test_ordinata_per_punti(self, archivio):
        punti = classifica(archivio)["Punti"].tolist()
        assert punti == sorted(punti, reverse=True)

    def test_andamento_una_riga_per_squadra_e_giornata(self, archivio):
        andamento = andamento_punti(archivio)
        assert len(andamento) == len(SQUADRE) * GIORNATE_GIOCATE
        assert andamento["punti"].gt(0).all()


class TestCruscotto:
    def test_una_riga_per_squadra(self, stati):
        tabella = cruscotto_lega(stati)
        assert len(tabella) == len(SQUADRE)
        assert set(tabella["Esito"]) == {"Conforme"}

    def test_le_colonne_economiche_sono_numeriche(self, stati):
        tabella = cruscotto_lega(stati)
        for colonna in ("Ingaggi", "Dead money", "Spesa", "Spazio cap"):
            assert tabella[colonna].dtype.kind == "f"

    def test_spesa_uguale_ingaggi_piu_dead_money(self, stati):
        tabella = cruscotto_lega(stati)
        atteso = tabella["Ingaggi"] + tabella["Dead money"]
        assert (tabella["Spesa"] - atteso).abs().max() < 0.01

    def test_nessuna_violazione_sulla_demo(self, stati):
        assert violazioni_lega(stati).empty


class TestRosaDettagliata:
    def test_una_riga_per_contratto(self, rose):
        rosa = rose[1]
        tabella = rosa_dettagliata(rosa, DATA_DRAFT)
        assert len(tabella) == rosa.dimensione

    def test_il_dead_money_e_meta_del_valore_residuo(self, rose):
        tabella = rosa_dettagliata(rose[1], DATA_DRAFT)
        atteso = tabella["Valore residuo"] * 0.5
        assert (tabella["Dead money se tagliato"] - atteso).abs().max() < 0.01

    def test_il_valore_residuo_e_ingaggio_per_anni(self, rose):
        tabella = rosa_dettagliata(rose[1], DATA_DRAFT)
        atteso = tabella["Ingaggio"] * tabella["Anni residui"]
        assert (tabella["Valore residuo"] - atteso).abs().max() < 0.01

    def test_le_scadenze_sono_marcate(self, rose):
        tabella = rosa_dettagliata(rose[1], DATA_DRAFT)
        scadenze = tabella[tabella["In scadenza"] == "Si"]
        assert (scadenze["Anni residui"] == 1).all()
        assert len(scadenze) == len(rose[1].contratti_annuali)

    def test_ordinata_per_scadenza(self, rose):
        anni = rosa_dettagliata(rose[1], DATA_DRAFT)["Anni residui"].tolist()
        assert anni == sorted(anni)


class TestDraftList:
    def test_contiene_solo_contratti_annuali(self, rose):
        scadenze = contratti_in_scadenza(rose, DATA_DRAFT)
        attesi = sum(len(r.contratti_annuali) for r in rose.values())
        assert len(scadenze) == attesi

    def test_ogni_squadra_e_rappresentata(self, rose):
        scadenze = contratti_in_scadenza(rose, DATA_DRAFT)
        assert set(scadenze["Squadra"]) == {r.squadra.nome for r in rose.values()}
