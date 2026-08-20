"""Test del backend di demo: il DB si costruisce e le viste sono coerenti."""

import pandas as pd
import pytest

from fantacalcio.data import (
    ArchivioSQLite,
    calendario_dettagliato,
    prestazioni_dettagliate,
    rose_dettagliate,
)
from fantacalcio.demo_data import GIORNATE_GIOCATE, NOMI_SQUADRE, ROSA


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    percorso = tmp_path_factory.mktemp("db") / "lega_test.db"
    return ArchivioSQLite(percorso)


def test_squadre_create(archivio):
    squadre = archivio.squadre()
    assert len(squadre) == len(NOMI_SQUADRE)
    assert squadre["nome"].is_unique


def test_ogni_squadra_ha_la_rosa_completa(archivio):
    rose = rose_dettagliate(archivio)
    per_squadra = rose.groupby("squadra")["giocatore_id"].count()
    assert set(per_squadra) == {sum(ROSA.values())}

    composizione = rose.groupby(["squadra", "ruolo"])["giocatore_id"].count().unstack()
    for ruolo, quanti in ROSA.items():
        assert (composizione[ruolo] == quanti).all()


def test_nessun_giocatore_in_due_rose(archivio):
    rose = archivio.rose()
    assert rose["giocatore_id"].is_unique


def test_calendario_completo_e_parzialmente_giocato(archivio):
    partite = calendario_dettagliato(archivio)
    assert partite["giornata"].max() == (len(NOMI_SQUADRE) - 1) * 2

    giocate = partite[partite["giornata"] <= GIORNATE_GIOCATE]
    assert giocate["gol_casa"].notna().all()
    assert giocate["punti_casa"].gt(0).all()

    future = partite[partite["giornata"] > GIORNATE_GIOCATE]
    assert future["gol_casa"].isna().all()


def test_prestazioni_hanno_squadra_e_qualche_sv(archivio):
    prestazioni = prestazioni_dettagliate(archivio)
    assert prestazioni["squadra"].notna().all()
    assert prestazioni["voto"].isna().any(), "servono degli s.v. per testare i cambi"
    voti = prestazioni["voto"].dropna()
    assert voti.between(4.0, 10.0).all()


def test_db_non_viene_rigenerato_se_esiste(tmp_path):
    percorso = tmp_path / "lega.db"
    ArchivioSQLite(percorso)
    modificato = percorso.stat().st_mtime_ns
    ArchivioSQLite(percorso)
    assert percorso.stat().st_mtime_ns == modificato


def test_tabella_sconosciuta(archivio):
    with pytest.raises(ValueError, match="non prevista"):
        archivio.tabella("classifica_segreta")


def test_classifica_demo_torna_con_le_partite(archivio):
    """I punti in classifica devono corrispondere ai risultati del calendario."""
    from fantacalcio.standings import Partita, calcola_classifica

    partite_df = calendario_dettagliato(archivio)
    partite = [
        Partita(
            giornata=int(r.giornata),
            casa=r.casa,
            trasferta=r.trasferta,
            gol_casa=None if pd.isna(r.gol_casa) else int(r.gol_casa),
            gol_trasferta=None if pd.isna(r.gol_trasferta) else int(r.gol_trasferta),
            punti_casa=None if pd.isna(r.punti_casa) else float(r.punti_casa),
            punti_trasferta=(
                None if pd.isna(r.punti_trasferta) else float(r.punti_trasferta)
            ),
        )
        for r in partite_df.itertuples()
    ]
    classifica = calcola_classifica(archivio.squadre()["nome"].tolist(), partite)

    assert all(r.giocate == GIORNATE_GIOCATE for r in classifica)
    totale_punti = sum(r.punti for r in classifica)
    partite_giocate = sum(1 for p in partite if p.giocata)
    # Ogni partita distribuisce 3 punti (vittoria) o 2 (pareggio).
    assert 2 * partite_giocate <= totale_punti <= 3 * partite_giocate
