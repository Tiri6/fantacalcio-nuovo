"""Il backend di demo si costruisce e produce una lega conforme al regolamento."""

import pytest

from fantacalcio.conformita import Momento, verifica_rosa
from fantacalcio.data import ArchivioSQLite, calendario_dettagliato, carica_rose
from fantacalcio.demo_data import (
    DATA_DRAFT,
    GIORNATE_GIOCATE,
    SQUADRE,
    SQUADRE_CON_DEAD_MONEY,
)
from fantacalcio.regole import ParametriLega


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    return ArchivioSQLite(tmp_path_factory.mktemp("db") / "nuovo.db")


@pytest.fixture(scope="module")
def rose(archivio):
    return carica_rose(archivio)


def test_dieci_squadre(archivio):
    squadre = archivio.squadre()
    assert len(squadre) == len(SQUADRE) == 10
    assert squadre["nome"].is_unique


def test_ogni_squadra_ha_una_rosa_conforme(rose):
    """La demo deve essere un banco di prova valido, non una lega irregolare."""
    for rosa in rose.values():
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.conforme, f"{rosa.squadra.nome}: {stato.violazioni}"


def test_nessun_giocatore_in_due_rose(archivio):
    assert archivio.contratti()["giocatore_id"].is_unique


def test_i_contratti_stanno_nel_monte_anni(rose):
    parametri = ParametriLega()
    for rosa in rose.values():
        assert rosa.anni_impegnati <= parametri.monte_anni
        assert all(
            1 <= c.anni_residui <= parametri.contratto_anni_massimo
            for c in rosa.contratti
        )


def test_gli_ingaggi_stanno_nella_forbice(rose):
    parametri = ParametriLega()
    for rosa in rose.values():
        assert parametri.salary_floor <= rosa.monte_ingaggi <= parametri.salary_cap


def test_almeno_una_rosa_e_ampliata_dagli_under21(rose):
    parametri = ParametriLega()
    ampliate = [
        rosa for rosa in rose.values() if rosa.dimensione > parametri.rosa_massimo_base
    ]
    assert ampliate, "la demo deve mostrare l'espansione Under 21"
    for rosa in ampliate:
        slot = rosa.slot_u21(DATA_DRAFT, parametri)
        assert rosa.dimensione <= parametri.rosa_massimo(slot)


def test_il_dead_money_e_presente_dove_previsto(rose):
    con_dead_money = {id_ for id_, rosa in rose.items() if rosa.dead_money_totale > 0}
    assert con_dead_money == set(SQUADRE_CON_DEAD_MONEY)


def test_calendario_andata_e_ritorno(archivio):
    partite = calendario_dettagliato(archivio)
    assert partite["giornata"].max() == 18  # (10 - 1) * 2
    assert len(partite) == 90

    giocate = partite[partite["giornata"] <= GIORNATE_GIOCATE]
    assert giocate["gol_casa"].notna().all()
    assert giocate["punti_casa"].gt(0).all()

    future = partite[partite["giornata"] > GIORNATE_GIOCATE]
    assert future["gol_casa"].isna().all()


def test_db_non_viene_rigenerato_se_esiste(tmp_path):
    percorso = tmp_path / "lega.db"
    ArchivioSQLite(percorso)
    modificato = percorso.stat().st_mtime_ns
    ArchivioSQLite(percorso)
    assert percorso.stat().st_mtime_ns == modificato


def test_tabella_sconosciuta(archivio):
    with pytest.raises(ValueError, match="non prevista"):
        archivio.tabella("segreti_del_presidente")


def test_i_giocatori_hanno_ruoli_mantra(archivio):
    from fantacalcio.regole import RUOLI_MANTRA

    for ruoli in archivio.giocatori()["ruoli"]:
        assert all(r in RUOLI_MANTRA for r in ruoli.split(";"))
