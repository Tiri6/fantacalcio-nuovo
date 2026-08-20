"""Test delle viste: le tabelle mostrate a schermo devono essere coerenti."""

import pytest

from fantacalcio.data import ArchivioSQLite
from fantacalcio.demo_data import GIORNATE_GIOCATE, NOMI_SQUADRE
from fantacalcio.scoring import RegoleLega
from fantacalcio.vista import (
    andamento_punti,
    calcola_fantavoto_riga,
    classifica,
    classifica_marcatori,
    migliori_per_media,
    tabellino_squadra,
)


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    return ArchivioSQLite(tmp_path_factory.mktemp("db") / "vista.db")


def test_classifica_ha_una_riga_per_squadra(archivio):
    tabella = classifica(archivio)
    assert len(tabella) == len(NOMI_SQUADRE)
    assert tabella["Pos"].tolist() == list(range(1, len(NOMI_SQUADRE) + 1))
    assert (tabella["PG"] == GIORNATE_GIOCATE).all()
    assert (tabella["V"] + tabella["N"] + tabella["P"] == tabella["PG"]).all()


def test_classifica_ordinata_per_punti(archivio):
    punti = classifica(archivio)["Punti"].tolist()
    assert punti == sorted(punti, reverse=True)


def test_andamento_una_riga_per_squadra_e_giornata(archivio):
    andamento = andamento_punti(archivio)
    assert len(andamento) == len(NOMI_SQUADRE) * GIORNATE_GIOCATE
    assert andamento.groupby("squadra")["giornata"].nunique().eq(GIORNATE_GIOCATE).all()
    assert andamento["punti"].gt(0).all()


def test_marcatori_ordinati_e_limitati(archivio):
    tabella = classifica_marcatori(archivio, quanti=10)
    assert len(tabella) == 10
    assert tabella["gol"].tolist() == sorted(tabella["gol"].tolist(), reverse=True)
    assert tabella["squadra"].notna().all()


def test_medie_rispettano_le_presenze_minime(archivio):
    tabella = migliori_per_media(archivio, presenze_minime=5, quanti=10)
    assert tabella["presenze"].ge(5).all()
    medie = tabella["media_fantavoto"].tolist()
    assert medie == sorted(medie, reverse=True)


def test_tabellino_ha_la_rosa_completa_e_totale_coerente(archivio):
    tabellino = tabellino_squadra(archivio, squadra_id=1, giornata=1)

    assert not tabellino.empty
    titolari_contati = tabellino[tabellino["Stato"] == "Titolare"]
    entrati = tabellino[tabellino["Stato"] == "Entrato"]
    non_sostituiti = tabellino[tabellino["Stato"] == "s.v."]

    assert len(titolari_contati) + len(entrati) + len(non_sostituiti) == 11
    assert len(entrati) <= RegoleLega().max_sostituzioni

    # I fantavoti sono formattati come testo per la resa a schermo.
    somma = sum(float(v) for v in tabellino["Fantavoto"] if v != "—")
    assert somma == pytest.approx(tabellino.attrs["totale"], abs=0.01)


def test_tabellino_celle_vuote_col_trattino(archivio):
    """I giocatori s.v. mostrano "—", non la stringa "None" di Streamlit."""
    tabellino = tabellino_squadra(archivio, squadra_id=1, giornata=1)

    valori = set(tabellino["Voto"]) | set(tabellino["Fantavoto"])
    assert "None" not in valori
    assert all(v == "—" or v.replace(".", "").isdigit() for v in valori)

    senza_voto = tabellino[tabellino["Stato"] == "s.v."]
    assert (senza_voto["Voto"] == "—").all()


def test_tabellino_giornata_inesistente(archivio):
    assert tabellino_squadra(archivio, squadra_id=1, giornata=99).empty


def test_calcola_fantavoto_riga():
    riga = {"giocatore_id": 1, "giocatore": "Tizio", "ruolo": "A", "voto": 7.0,
            "gol_segnati": 1, "assist": 1, "ammonizioni": 1}
    assert calcola_fantavoto_riga(riga) == 7.0 + 3.0 + 1.0 - 0.5
