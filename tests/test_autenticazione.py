import pytest

from fantacalcio.autenticazione import (
    LUNGHEZZA_MINIMA_PASSWORD,
    Credenziali,
    PasswordNonValida,
    Ruolo,
    Utente,
    UtenteNonValido,
    autentica,
    cifra_password,
    con_nuova_password,
    controlla_password,
    crea_credenziali,
    normalizza_nome_utente,
    verifica_password,
)


class TestPassword:
    def test_hash_diverso_a_ogni_creazione(self):
        """Sali diversi: due utenti con la stessa password hanno hash diversi."""
        primo, _ = cifra_password("unapasswordlunga")
        secondo, _ = cifra_password("unapasswordlunga")
        assert primo != secondo

    def test_verifica_corretta(self):
        digest, sale = cifra_password("unapasswordlunga")
        assert verifica_password("unapasswordlunga", digest, sale)

    def test_verifica_fallisce_con_password_sbagliata(self):
        digest, sale = cifra_password("unapasswordlunga")
        assert not verifica_password("unapasswordlung", digest, sale)
        assert not verifica_password("", digest, sale)

    def test_verifica_non_esplode_su_dati_corrotti(self):
        assert not verifica_password("qualcosa", "non-esadecimale", "zz")

    @pytest.mark.parametrize("valore", ["", None, "corta"])
    def test_password_deboli_rifiutate(self, valore):
        with pytest.raises(PasswordNonValida):
            controlla_password(valore)

    def test_lunghezza_minima_rispettata(self):
        controlla_password("x" * LUNGHEZZA_MINIMA_PASSWORD)
        with pytest.raises(PasswordNonValida):
            controlla_password("x" * (LUNGHEZZA_MINIMA_PASSWORD - 1))


class TestNomeUtente:
    @pytest.mark.parametrize(
        "valore,atteso", [("Marco", "marco"), ("  LUCA ", "luca"), ("Giulia", "giulia")]
    )
    def test_normalizzazione(self, valore, atteso):
        assert normalizza_nome_utente(valore) == atteso

    @pytest.mark.parametrize("valore", ["", "  ", "ab", None])
    def test_valori_rifiutati(self, valore):
        with pytest.raises(UtenteNonValido):
            normalizza_nome_utente(valore)


class TestPermessi:
    def presidente(self) -> Utente:
        return Utente(1, "marco", "Marco", Ruolo.PRESIDENTE, squadra_id=1)

    def allenatore(self) -> Utente:
        return Utente(2, "luca", "Luca", Ruolo.FANTALLENATORE, squadra_id=2)

    def test_il_presidente_gestisce_tutte_le_squadre(self):
        presidente = self.presidente()
        assert presidente.puo_gestire(1)
        assert presidente.puo_gestire(7)
        assert presidente.puo_importare

    def test_il_fantallenatore_gestisce_solo_la_sua(self):
        allenatore = self.allenatore()
        assert allenatore.puo_gestire(2)
        assert not allenatore.puo_gestire(1)
        assert not allenatore.puo_importare

    def test_senza_squadra_non_gestisce_nulla(self):
        orfano = Utente(3, "tizio", "Tizio", Ruolo.FANTALLENATORE, squadra_id=None)
        assert not orfano.puo_gestire(None)
        assert not orfano.puo_gestire(1)

    def test_utente_disattivato_non_puo_nulla(self):
        spento = Utente(4, "caio", "Caio", Ruolo.PRESIDENTE, squadra_id=1, attivo=False)
        assert not spento.puo_gestire(1)
        assert not spento.puo_importare


class TestAutenticazione:
    @pytest.fixture
    def elenco(self) -> dict[str, Credenziali]:
        credenziali = crea_credenziali(
            1, "Marco", "Marco Tirinato", "unapasswordlunga", Ruolo.PRESIDENTE, 1
        )
        return {credenziali.utente.nome_utente: credenziali}

    def test_accesso_riuscito(self, elenco):
        utente = autentica(elenco, "marco", "unapasswordlunga")
        assert utente is not None
        assert utente.e_presidente

    def test_nome_utente_senza_maiuscole(self, elenco):
        assert autentica(elenco, "  MARCO  ", "unapasswordlunga") is not None

    def test_password_sbagliata(self, elenco):
        assert autentica(elenco, "marco", "sbagliata") is None

    def test_utente_inesistente(self, elenco):
        assert autentica(elenco, "nessuno", "unapasswordlunga") is None

    def test_nome_utente_malformato(self, elenco):
        assert autentica(elenco, "", "unapasswordlunga") is None

    def test_utente_disattivato_non_entra(self, elenco):
        from dataclasses import replace

        credenziali = elenco["marco"]
        spento = replace(credenziali, utente=replace(credenziali.utente, attivo=False))
        assert autentica({"marco": spento}, "marco", "unapasswordlunga") is None

    def test_cambio_password(self, elenco):
        aggiornate = con_nuova_password(elenco["marco"], "nuovapasswordlunga")
        assert aggiornate.corrisponde("nuovapasswordlunga")
        assert not aggiornate.corrisponde("unapasswordlunga")

    def test_crea_credenziali_valida_la_password(self):
        with pytest.raises(PasswordNonValida):
            crea_credenziali(1, "marco", "Marco", "corta")


class TestUtentiDelDatabaseDiDemo:
    def test_il_primo_utente_e_il_presidente(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite, carica_credenziali
        from fantacalcio.demo_data import PASSWORD_DEMO

        archivio = ArchivioSQLite(tmp_path / "utenti.db")
        credenziali = carica_credenziali(archivio)

        assert len(credenziali) == 10
        presidenti = [c.utente for c in credenziali.values() if c.utente.e_presidente]
        assert len(presidenti) == 1

        entrato = autentica(credenziali, presidenti[0].nome_utente, PASSWORD_DEMO)
        assert entrato is not None
        assert entrato.squadra_id == 1

    def test_ogni_utente_ha_la_sua_squadra(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite, carica_credenziali

        credenziali = carica_credenziali(ArchivioSQLite(tmp_path / "u2.db"))
        squadre = {c.utente.squadra_id for c in credenziali.values()}
        assert squadre == set(range(1, 11))

    def test_le_password_non_sono_in_chiaro(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite
        from fantacalcio.demo_data import PASSWORD_DEMO

        righe = ArchivioSQLite(tmp_path / "u3.db").tabella("utenti")
        assert PASSWORD_DEMO not in righe.to_string()
