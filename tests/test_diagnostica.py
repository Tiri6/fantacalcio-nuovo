"""La diagnostica dello schema: trovare cosa manca e dire come rimediare."""

import pandas as pd
import pytest

from fantacalcio.diagnostica import (
    ATTESO,
    Problema,
    riepilogo,
    sql_di_riparazione,
    verifica,
)


class ArchivioFinto:
    """Un archivio con lo schema che gli si dice di avere."""

    def __init__(self, tabelle: dict[str, pd.DataFrame]):
        self._tabelle = tabelle

    def tabella(self, nome: str) -> pd.DataFrame:
        if nome not in self._tabelle:
            raise RuntimeError(f'relation "{nome}" does not exist')
        return self._tabelle[nome]


def completo() -> dict[str, pd.DataFrame]:
    """Uno schema che ha tutto, con una riga per tabella."""
    return {
        nome: pd.DataFrame([dict.fromkeys(colonne)]) for nome, colonne in ATTESO.items()
    }


class TestVerifica:
    def test_schema_completo_nessun_problema(self):
        assert verifica(ArchivioFinto(completo())) == []

    def test_tabella_mancante(self):
        tabelle = completo()
        del tabelle["annunci"]
        problemi = verifica(ArchivioFinto(tabelle))
        assert len(problemi) == 1
        assert problemi[0].tabella == "annunci"
        assert problemi[0].tabella_mancante

    def test_colonna_mancante(self):
        tabelle = completo()
        tabelle["utenti"] = tabelle["utenti"].drop(columns=["cognome"])
        problemi = verifica(ArchivioFinto(tabelle))
        assert len(problemi) == 1
        assert problemi[0].colonne_mancanti == ("cognome",)

    def test_piu_colonne_mancanti_nella_stessa_tabella(self):
        tabelle = completo()
        tabelle["utenti"] = tabelle["utenti"].drop(columns=["cognome", "citta"])
        problemi = verifica(ArchivioFinto(tabelle))
        assert set(problemi[0].colonne_mancanti) == {"cognome", "citta"}

    def test_una_tabella_vuota_non_genera_falsi_allarmi(self):
        """Senza righe le colonne non si deducono: meglio tacere che sbagliare."""
        tabelle = completo()
        tabelle["annunci"] = pd.DataFrame()
        assert verifica(ArchivioFinto(tabelle)) == []

    def test_colonne_in_piu_non_sono_un_problema(self):
        tabelle = completo()
        tabelle["utenti"]["colonna_futura"] = None
        assert verifica(ArchivioFinto(tabelle)) == []


class TestRiparazione:
    def test_senza_problemi_nessuna_query(self):
        assert sql_di_riparazione([]) == ""

    def test_una_colonna_produce_il_suo_alter(self):
        sql = sql_di_riparazione([Problema("utenti", colonne_mancanti=("cognome",))])
        assert "alter table utenti add column if not exists cognome" in sql

    def test_il_tipo_e_quello_giusto_non_un_text_a_caso(self):
        sql = sql_di_riparazione(
            [
                Problema(
                    "utenti", colonne_mancanti=("data_nascita", "deve_cambiare_password")
                )
            ]
        )
        assert "data_nascita date" in sql
        assert "deve_cambiare_password boolean" in sql

    def test_una_colonna_sconosciuta_ricade_su_text(self):
        sql = sql_di_riparazione([Problema("utenti", colonne_mancanti=("misteriosa",))])
        assert "misteriosa text" in sql

    def test_una_tabella_mancante_rimanda_allo_schema_completo(self):
        sql = sql_di_riparazione([Problema("annunci", tabella_mancante=True)])
        assert "db/schema.sql" in sql
        assert "annunci" in sql

    def test_la_query_ricorda_i_privilegi(self):
        """Senza i GRANT la colonna esiste ma l'app continua a non scriverla."""
        sql = sql_di_riparazione([Problema("utenti", colonne_mancanti=("cognome",))])
        assert "service_role" in sql

    def test_gli_alter_sono_rieseguibili(self):
        sql = sql_di_riparazione([Problema("utenti", colonne_mancanti=("cognome",))])
        assert "if not exists" in sql


class TestMessaggi:
    def test_singolare_e_plurale(self):
        uno = Problema("utenti", colonne_mancanti=("cognome",))
        due = Problema("utenti", colonne_mancanti=("cognome", "citta"))
        assert "la colonna" in uno.messaggio
        assert "le colonne" in due.messaggio

    def test_tabella_mancante_lo_dice(self):
        assert "non esiste" in Problema("annunci", tabella_mancante=True).messaggio

    def test_riepilogo_quando_va_tutto_bene(self):
        assert "tutto quello che il sito si aspetta" in riepilogo([])

    def test_il_riepilogo_conta_i_problemi(self):
        assert riepilogo([Problema("utenti", colonne_mancanti=("x",))]).startswith(
            "1 problema"
        )


@pytest.mark.parametrize("tabella", sorted(ATTESO))
def test_ogni_tabella_attesa_esiste_davvero(tabella, tmp_path):
    """L'elenco atteso non deve scollarsi dallo schema vero."""
    from fantacalcio.data import ArchivioSQLite

    arch = ArchivioSQLite(tmp_path / "prova.db")
    arch.tabella(tabella)  # solleva se la tabella non c'e'
