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
def test_ogni_tabella_attesa_esiste_davvero(tabella, archivio_demo):
    """L'elenco atteso non deve scollarsi dallo schema vero."""
    archivio_demo.tabella(tabella)  # solleva se la tabella non c'e'


class TestNienteRestaFuoriControllo:
    """La diagnostica deve guardare **tutte** le tabelle che l'app usa.

    E' il difetto che ha lasciato Marco davanti a una pagina rotta: mancava la
    tabella `formazioni`, ma `ATTESO` non la elencava, quindi la pagina che
    dice «il database non e' aggiornato» giurava che fosse tutto a posto.
    """

    def test_ogni_tabella_dell_app_e_controllata(self):
        from fantacalcio.data import TABELLE
        from fantacalcio.diagnostica import ATTESO

        fuori = sorted(set(TABELLE) - set(ATTESO))
        assert fuori == [], (
            f"Queste tabelle non verrebbero mai controllate: {fuori}. "
            f"Aggiungile ad ATTESO, altrimenti chi non lancia la migrazione "
            f"vede una pagina rotta e una diagnostica che dice «tutto bene»."
        )

    def test_ogni_colonna_attesa_esiste_davvero(self):
        """Difendersi anche dal contrario: controllare colonne inventate."""
        from fantacalcio.data import COLONNE_ATTESE
        from fantacalcio.diagnostica import ATTESO

        for tabella, colonne in ATTESO.items():
            note = set(COLONNE_ATTESE.get(tabella, ()))
            if not note:
                continue
            inventate = sorted(set(colonne) - note)
            assert inventate == [], f"{tabella}: colonne che non esistono {inventate}"


class TestQualeFileEseguire:
    def test_una_tabella_mancante_dice_il_suo_file(self):
        from fantacalcio.diagnostica import Problema

        problema = Problema("formazioni", tabella_mancante=True)
        assert "aggiornamento_giornata.sql" in problema.messaggio

    def test_la_query_di_riparazione_nomina_i_file(self):
        from fantacalcio.diagnostica import Problema, sql_di_riparazione

        sql = sql_di_riparazione(
            [
                Problema("formazioni", tabella_mancante=True),
                Problema("voti", tabella_mancante=True),
            ]
        )
        assert "db/aggiornamento_giornata.sql" in sql

    def test_una_tabella_senza_file_noto_non_inventa_niente(self):
        from fantacalcio.diagnostica import Problema, migrazione_per

        assert migrazione_per("squadre") == ""
        assert "db/" not in Problema("squadre", tabella_mancante=True).messaggio


class TestTabellaAssenteSenzaErrore:
    """La degradazione non deve rendere cieca la diagnostica.

    Da quando una tabella mancante si legge vuota invece di alzare un errore,
    `verifica` non poteva piu' distinguerla da una tabella senza righe: la
    pagina «Impostazioni lega» diceva che andava tutto bene mentre Formazione
    e Giornata erano inutilizzabili. E' successo, ed e' questo test.
    """

    def test_la_segnala_lo_stesso(self, archivio_demo, db_demo):
        import sqlite3

        from fantacalcio.diagnostica import verifica

        arch = archivio_demo
        with sqlite3.connect(db_demo) as conn:
            conn.execute("drop table formazioni")

        problemi = verifica(arch)
        assenti = [p.tabella for p in problemi if p.tabella_mancante]
        assert "formazioni" in assenti

    def test_una_tabella_vuota_ma_esistente_non_e_un_problema(self, archivio_demo):
        from fantacalcio.diagnostica import verifica

        arch = archivio_demo
        assert [p.tabella for p in verifica(arch) if p.tabella_mancante] == []
