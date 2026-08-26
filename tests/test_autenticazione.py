from dataclasses import replace

import pytest

from fantacalcio.autenticazione import (
    LUNGHEZZA_MINIMA_PASSWORD,
    Credenziali,
    NomeUtenteOccupato,
    PasswordNonValida,
    PermessoNegato,
    Ruolo,
    Utente,
    UtenteNonValido,
    assegna_squadra,
    autentica,
    cambia_password,
    cifra_password,
    con_nuova_password,
    controlla_password,
    crea_credenziali,
    entra_in_lega,
    genera_password_temporanea,
    normalizza_nome_utente,
    puo_reimpostare,
    registra,
    reimposta_password,
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


class TestRegistrazione:
    """Chi arriva si crea l'account da solo: il presidente non lo crea a mano."""

    def test_crea_un_utente_nuovo(self):
        nuove = registra({}, 1, "luca", "Luca Rossi", "password1", "password1")
        assert nuove.utente.nome_utente == "luca"
        assert nuove.utente.ruolo is Ruolo.FANTALLENATORE
        assert nuove.corrisponde("password1")

    def test_il_nome_utente_si_normalizza(self):
        assert (
            registra({}, 1, "  LuCa  ", "Luca", "password1").utente.nome_utente == "luca"
        )

    def test_nome_gia_preso(self):
        esistenti = {"luca": registra({}, 1, "luca", "Luca", "password1")}
        with pytest.raises(NomeUtenteOccupato, match="luca"):
            registra(esistenti, 2, "LUCA", "Luca Bis", "password2")

    def test_il_conflitto_si_dice_apertamente(self):
        """Al contrario del login: qui tacere lascerebbe l'utente bloccato."""
        esistenti = {"luca": registra({}, 1, "luca", "Luca", "password1")}
        with pytest.raises(NomeUtenteOccupato) as errore:
            registra(esistenti, 2, "luca", "Altro", "password2")
        assert "gia' preso" in str(errore.value)

    def test_password_non_coincidenti(self):
        with pytest.raises(PasswordNonValida, match="non coincidono"):
            registra({}, 1, "luca", "Luca", "password1", "password2")

    def test_senza_conferma_non_si_controlla(self):
        assert registra({}, 1, "luca", "Luca", "password1") is not None

    def test_password_troppo_corta(self):
        with pytest.raises(PasswordNonValida):
            registra({}, 1, "luca", "Luca", "corta", "corta")

    def test_email_conservata(self):
        nuove = registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")
        assert nuove.utente.email == "luca@esempio.it"

    def test_chi_si_registra_non_ha_ne_lega_ne_squadra(self):
        utente = registra({}, 1, "luca", "Luca", "password1").utente
        assert not utente.ha_lega
        assert not utente.ha_squadra


class TestIngressoInLega:
    def test_entrare_assegna_la_lega(self):
        credenziali = registra({}, 1, "luca", "Luca", "password1")
        dentro = entra_in_lega(credenziali, lega_id=7)
        assert dentro.utente.lega_id == 7
        assert dentro.utente.ha_lega

    def test_si_puo_entrare_come_presidente(self):
        credenziali = registra({}, 1, "marco", "Marco", "password1")
        dentro = entra_in_lega(credenziali, 7, Ruolo.PRESIDENTE)
        assert dentro.utente.e_presidente
        assert dentro.utente.puo_importare

    def test_il_ruolo_resta_quello_se_non_lo_cambi(self):
        credenziali = registra({}, 1, "luca", "Luca", "password1")
        assert entra_in_lega(credenziali, 7).utente.ruolo is Ruolo.FANTALLENATORE

    def test_entrare_non_tocca_la_password(self):
        credenziali = registra({}, 1, "luca", "Luca", "password1")
        assert entra_in_lega(credenziali, 7).corrisponde("password1")

    def test_assegnare_la_squadra(self):
        credenziali = registra({}, 1, "luca", "Luca", "password1")
        con_squadra = assegna_squadra(entra_in_lega(credenziali, 7), squadra_id=3)
        assert con_squadra.utente.squadra_id == 3
        assert con_squadra.utente.ha_squadra
        assert con_squadra.utente.lega_id == 7
        assert con_squadra.utente.puo_gestire(3)
        assert not con_squadra.utente.puo_gestire(4)

    def test_l_originale_non_cambia(self):
        """Le credenziali sono immutabili: chi le tiene in mano non se le vede mutare."""
        credenziali = registra({}, 1, "luca", "Luca", "password1")
        entra_in_lega(credenziali, 7)
        assert credenziali.utente.lega_id is None


class TestCambioPassword:
    def credenziali(self):
        return registra({}, 1, "luca", "Luca", "password1")

    def test_cambio_riuscito(self):
        nuove = cambia_password(self.credenziali(), "password1", "password2", "password2")
        assert nuove.corrisponde("password2")
        assert not nuove.corrisponde("password1")

    def test_serve_la_password_attuale(self):
        """Senza, chi trovasse una sessione aperta si prenderebbe l'account."""
        with pytest.raises(PasswordNonValida, match="attuale"):
            cambia_password(self.credenziali(), "sbagliata", "password2", "password2")

    def test_le_due_nuove_devono_coincidere(self):
        with pytest.raises(PasswordNonValida, match="coincidono"):
            cambia_password(self.credenziali(), "password1", "password2", "password3")

    def test_la_nuova_deve_essere_robusta(self):
        with pytest.raises(PasswordNonValida):
            cambia_password(self.credenziali(), "password1", "corta", "corta")

    def test_non_si_puo_rimettere_la_stessa(self):
        with pytest.raises(PasswordNonValida, match="uguale"):
            cambia_password(self.credenziali(), "password1", "password1", "password1")

    def test_il_sale_cambia_a_ogni_cambio(self):
        """Due password uguali non devono produrre lo stesso hash."""
        prime = self.credenziali()
        seconde = cambia_password(prime, "password1", "password2", "password2")
        terze = cambia_password(seconde, "password2", "password1", "password1")
        assert terze.sale != prime.sale
        assert terze.hash_password != prime.hash_password

    def test_cambiare_spegne_l_obbligo(self):
        """Il senso del flag: si spegne solo quando la password la scegli tu."""
        di_lega = replace(
            self.credenziali(),
            utente=replace(self.credenziali().utente, lega_id=1),
        )
        temporanee, temporanea = reimposta_password(di_lega, PRESIDENTE_DI_LEGA)
        assert temporanee.utente.deve_cambiare_password

        nuove = cambia_password(temporanee, temporanea, "password3", "password3")
        assert not nuove.utente.deve_cambiare_password
        assert nuove.corrisponde("password3")

    def test_l_originale_non_cambia(self):
        prime = self.credenziali()
        cambia_password(prime, "password1", "password2", "password2")
        assert prime.corrisponde("password1")


class TestReimpostazione:
    def bersaglio(self):
        """Un partecipante della lega 1, con password nota."""
        credenziali = registra({}, 2, "luca", "Luca", "password1")
        return replace(credenziali, utente=replace(credenziali.utente, lega_id=1))

    def test_genera_una_password_usabile(self):
        nuove, temporanea = reimposta_password(self.bersaglio(), PRESIDENTE_DI_LEGA)
        assert len(temporanea) >= LUNGHEZZA_MINIMA_PASSWORD
        assert nuove.corrisponde(temporanea)
        assert nuove.utente.deve_cambiare_password

    def test_la_temporanea_non_contiene_caratteri_confondibili(self):
        """Viene dettata a voce: O/0 e I/1 sono il modo classico di sbagliarla."""
        insieme = "".join(genera_password_temporanea() for _ in range(100))
        assert not set(insieme) & set("OIl01")

    def test_due_password_temporanee_sono_diverse(self):
        assert len({genera_password_temporanea() for _ in range(50)}) > 45

    def test_un_fantallenatore_non_reimposta(self):
        estraneo = replace(
            registra({}, 3, "mario", "Mario", "password1").utente, lega_id=1
        )
        with pytest.raises(PermessoNegato):
            reimposta_password(self.bersaglio(), estraneo)

    def test_il_presidente_di_un_altra_lega_non_reimposta(self):
        altrove = replace(PRESIDENTE_DI_LEGA, lega_id=99)
        with pytest.raises(PermessoNegato):
            reimposta_password(self.bersaglio(), altrove)

    def test_un_presidente_disattivato_non_reimposta(self):
        sospeso = replace(PRESIDENTE_DI_LEGA, attivo=False)
        with pytest.raises(PermessoNegato):
            reimposta_password(self.bersaglio(), sospeso)

    def test_permesso_senza_lega_negato(self):
        senza = replace(PRESIDENTE_DI_LEGA, lega_id=None)
        assert not puo_reimpostare(senza, self.bersaglio().utente)

    def test_la_vecchia_password_smette_di_funzionare(self):
        nuove, _ = reimposta_password(self.bersaglio(), PRESIDENTE_DI_LEGA)
        assert not nuove.corrisponde("password1")


# Un presidente valido della lega 1, usato dalle prove sui permessi.
PRESIDENTE_DI_LEGA = Utente(
    id=1, nome_utente="marco", nome="Marco", ruolo=Ruolo.PRESIDENTE, lega_id=1
)
