from dataclasses import replace

import pytest

from fantacalcio.autenticazione import (
    LUNGHEZZA_MINIMA_PASSWORD,
    Credenziali,
    EmailGiaUsata,
    NomeUtenteOccupato,
    PasswordNonValida,
    PermessoNegato,
    Ruolo,
    StatoRichiesta,
    Utente,
    UtenteNonValido,
    apri_richiesta_password,
    assegna_squadra,
    autentica,
    cambia_password,
    chiudi_richiesta,
    cifra_password,
    con_codice_recupero,
    con_nuova_password,
    controlla_password,
    crea_credenziali,
    entra_in_lega,
    genera_codice_recupero,
    genera_password_temporanea,
    normalizza_codice_recupero,
    normalizza_nome_utente,
    puo_reimpostare,
    recupera_con_codice,
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
    def test_il_primo_utente_e_il_presidente(self, archivio_demo):
        from fantacalcio.data import carica_credenziali
        from fantacalcio.demo_data import PASSWORD_DEMO

        credenziali = carica_credenziali(archivio_demo)

        assert len(credenziali) == 10
        presidenti = [c.utente for c in credenziali.values() if c.utente.e_presidente]
        assert len(presidenti) == 1

        entrato = autentica(credenziali, presidenti[0].nome_utente, PASSWORD_DEMO)
        assert entrato is not None
        assert entrato.squadra_id == 1

    def test_ogni_utente_ha_la_sua_squadra(self, archivio_demo):
        from fantacalcio.data import carica_credenziali

        credenziali = carica_credenziali(archivio_demo)
        squadre = {c.utente.squadra_id for c in credenziali.values()}
        assert squadre == set(range(1, 11))

    def test_le_password_non_sono_in_chiaro(self, archivio_demo):
        from fantacalcio.demo_data import PASSWORD_DEMO

        righe = archivio_demo.tabella("utenti")
        assert PASSWORD_DEMO not in righe.to_string()


class TestRegistrazione:
    """Chi arriva si crea l'account da solo: il presidente non lo crea a mano."""

    def test_crea_un_utente_nuovo(self):
        nuove = registra(
            {}, 1, "luca", "Luca Rossi", "password1", "password1", email="luca@esempio.it"
        )
        assert nuove.utente.nome_utente == "luca"
        assert nuove.utente.ruolo is Ruolo.FANTALLENATORE
        assert nuove.corrisponde("password1")

    def test_il_nome_utente_si_normalizza(self):
        assert (
            registra(
                {}, 1, "  LuCa  ", "Luca", "password1", email="tizio@esempio.it"
            ).utente.nome_utente
            == "luca"
        )

    def test_nome_gia_preso(self):
        esistenti = {
            "luca": registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")
        }
        with pytest.raises(NomeUtenteOccupato, match="luca"):
            registra(
                esistenti, 2, "LUCA", "Luca Bis", "password2", email="tizio@esempio.it"
            )

    def test_il_conflitto_si_dice_apertamente(self):
        """Al contrario del login: qui tacere lascerebbe l'utente bloccato."""
        esistenti = {
            "luca": registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")
        }
        with pytest.raises(NomeUtenteOccupato) as errore:
            registra(esistenti, 2, "luca", "Altro", "password2", email="luca@esempio.it")
        assert "gia' preso" in str(errore.value)

    def test_password_non_coincidenti(self):
        with pytest.raises(PasswordNonValida, match="non coincidono"):
            registra(
                {}, 1, "luca", "Luca", "password1", "password2", email="luca@esempio.it"
            )

    def test_senza_conferma_non_si_controlla(self):
        assert (
            registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")
            is not None
        )

    def test_password_troppo_corta(self):
        with pytest.raises(PasswordNonValida):
            registra({}, 1, "luca", "Luca", "corta", "corta", email="luca@esempio.it")

    def test_email_conservata(self):
        nuove = registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")
        assert nuove.utente.email == "luca@esempio.it"

    def test_chi_si_registra_non_ha_ne_lega_ne_squadra(self):
        utente = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        ).utente
        assert not utente.ha_lega
        assert not utente.ha_squadra


class TestIngressoInLega:
    def test_entrare_assegna_la_lega(self):
        credenziali = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        )
        dentro = entra_in_lega(credenziali, lega_id=7)
        assert dentro.utente.lega_id == 7
        assert dentro.utente.ha_lega

    def test_si_puo_entrare_come_presidente(self):
        credenziali = registra(
            {}, 1, "marco", "Marco", "password1", email="marco@esempio.it"
        )
        dentro = entra_in_lega(credenziali, 7, Ruolo.PRESIDENTE)
        assert dentro.utente.e_presidente
        assert dentro.utente.puo_importare

    def test_il_ruolo_resta_quello_se_non_lo_cambi(self):
        credenziali = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        )
        assert entra_in_lega(credenziali, 7).utente.ruolo is Ruolo.FANTALLENATORE

    def test_entrare_non_tocca_la_password(self):
        credenziali = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        )
        assert entra_in_lega(credenziali, 7).corrisponde("password1")

    def test_assegnare_la_squadra(self):
        credenziali = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        )
        con_squadra = assegna_squadra(entra_in_lega(credenziali, 7), squadra_id=3)
        assert con_squadra.utente.squadra_id == 3
        assert con_squadra.utente.ha_squadra
        assert con_squadra.utente.lega_id == 7
        assert con_squadra.utente.puo_gestire(3)
        assert not con_squadra.utente.puo_gestire(4)

    def test_l_originale_non_cambia(self):
        """Le credenziali sono immutabili: chi le tiene in mano non se le vede mutare."""
        credenziali = registra(
            {}, 1, "luca", "Luca", "password1", email="luca@esempio.it"
        )
        entra_in_lega(credenziali, 7)
        assert credenziali.utente.lega_id is None


class TestCambioPassword:
    def credenziali(self):
        return registra({}, 1, "luca", "Luca", "password1", email="luca@esempio.it")

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
        credenziali = registra(
            {}, 2, "luca", "Luca", "password1", email="luca@esempio.it"
        )
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
            registra(
                {}, 3, "mario", "Mario", "password1", email="mario@esempio.it"
            ).utente,
            lega_id=1,
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


class TestRegistrazioneCompleta:
    """L'email e' obbligatoria e i dati anagrafici arrivano fino al modello."""

    def test_senza_email_si_rifiuta(self):
        from fantacalcio.leghe import EmailNonValida

        with pytest.raises(EmailNonValida):
            registra({}, 1, "luca", "Luca", "password1")

    @pytest.mark.parametrize("scritta", ["", "   ", "non-una-email", "luca@"])
    def test_email_malformata(self, scritta):
        from fantacalcio.leghe import EmailNonValida

        with pytest.raises(EmailNonValida):
            registra({}, 1, "luca", "Luca", "password1", email=scritta)

    def test_email_gia_registrata(self):
        """Due account con la stessa email sono due modi di essere la stessa persona."""
        esistenti = {
            "luca": registra({}, 1, "luca", "Luca", "password1", email="l@esempio.it")
        }
        with pytest.raises(EmailGiaUsata, match="l@esempio.it"):
            registra(esistenti, 2, "luca2", "Luca Bis", "password2", email="L@Esempio.IT")

    def test_il_nome_utente_occupato_ha_la_precedenza(self):
        """Con entrambi i conflitti si segnala il primo che l'utente puo' cambiare."""
        esistenti = {
            "luca": registra({}, 1, "luca", "Luca", "password1", email="l@esempio.it")
        }
        with pytest.raises(NomeUtenteOccupato):
            registra(esistenti, 2, "luca", "Altro", "password2", email="l@esempio.it")

    def test_i_dati_anagrafici_arrivano_al_modello(self):
        from datetime import date

        from fantacalcio.anagrafica import Sesso

        nuove = registra(
            {},
            1,
            "marco",
            "Marco",
            "password1",
            email="marco@esempio.it",
            cognome="Tirinato",
            data_nascita=date(1991, 3, 24),
            sesso=Sesso.MASCHIO,
            citta="Ginevra",
            squadra_preferita="Inter",
        )
        utente = nuove.utente
        assert utente.cognome == "Tirinato"
        assert utente.nome_completo == "Marco Tirinato"
        assert utente.data_nascita == date(1991, 3, 24)
        assert utente.sesso is Sesso.MASCHIO
        assert utente.citta == "Ginevra"
        assert utente.squadra_preferita == "Inter"

    def test_l_email_si_normalizza(self):
        nuove = registra(
            {}, 1, "marco", "Marco", "password1", email="  Marco@ESEMPIO.it "
        )
        assert nuove.utente.email == "marco@esempio.it"

    def test_senza_cognome_il_nome_completo_e_solo_il_nome(self):
        nuove = registra({}, 1, "marco", "Marco", "password1", email="m@esempio.it")
        assert nuove.utente.nome_completo == "Marco"

    def test_una_password_corta_impedisce_la_creazione(self):
        """Il caso che lasciava l'utente convinto di essersi iscritto."""
        with pytest.raises(PasswordNonValida, match=str(LUNGHEZZA_MINIMA_PASSWORD)):
            registra({}, 1, "marco", "Marco", "corta", email="m@esempio.it")


class TestSbloccoDaSql:
    """Lo script di emergenza deve produrre una password che il sito accetta."""

    def test_l_hash_generato_verifica_la_password(self):
        import re
        import subprocess
        import sys
        from pathlib import Path

        radice = Path(__file__).resolve().parents[1]
        esito = subprocess.run(
            [
                sys.executable,
                str(radice / "scripts" / "reimposta_password.py"),
                "marco",
                "--password",
                "sbloccami99",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        hash_password = re.search(r"hash_password = '([0-9a-f]+)'", esito.stdout)
        sale = re.search(r"sale = '([0-9a-f]+)'", esito.stdout)
        assert hash_password and sale

        # E' questa la prova che conta: quello che finisce nel database deve
        # essere accettato dalla stessa funzione che verifica il login.
        assert verifica_password("sbloccami99", hash_password.group(1), sale.group(1))
        assert not verifica_password("altra", hash_password.group(1), sale.group(1))
        assert "deve_cambiare_password = true" in esito.stdout


class TestCodiceDiRecupero:
    """La chiave di scorta: si genera prima, serve dopo.

    E' l'unica strada per rientrare senza dipendere da un'altra persona, e in
    particolare e' l'unica che copre il presidente, che non ha nessuno sopra
    di se' a reimpostargli la password.
    """

    def utente(self):
        return registra({}, 1, "marco", "Marco", "password1", email="m@esempio.it")

    def test_chi_non_l_ha_generato_non_ne_ha(self):
        credenziali = self.utente()
        assert not credenziali.ha_codice_recupero
        assert not credenziali.codice_corrisponde("H7KP-2MQX-9TBW")

    def test_generarlo_lo_restituisce_una_volta_sola(self):
        aggiornate, codice = con_codice_recupero(self.utente())
        assert aggiornate.ha_codice_recupero
        assert aggiornate.codice_corrisponde(codice)
        # In archivio resta solo l'impronta: il codice in chiaro non c'e'.
        assert codice not in aggiornate.hash_recupero

    def test_si_scrive_come_capita(self):
        # Chi lo ricopia sbaglia trattini e maiuscole, non il codice.
        aggiornate, codice = con_codice_recupero(self.utente())
        assert aggiornate.codice_corrisponde(codice.lower())
        assert aggiornate.codice_corrisponde(codice.replace("-", " "))
        assert aggiornate.codice_corrisponde(f"  {codice.replace('-', '')}  ")

    def test_un_codice_sbagliato_non_apre_niente(self):
        aggiornate, _ = con_codice_recupero(self.utente())
        assert not aggiornate.codice_corrisponde("AAAA-BBBB-CCCC")
        assert not aggiornate.codice_corrisponde("")

    def test_non_contiene_caratteri_confondibili(self):
        """Si detta al telefono: O/0 e I/1 sono il modo classico di sbagliarlo."""
        insieme = "".join(genera_codice_recupero() for _ in range(100))
        assert not set(insieme) & set("OIl01")

    def test_normalizza_via_tutto_il_resto(self):
        assert normalizza_codice_recupero(" h7kp-2mqx 9tbw ") == "H7KP2MQX9TBW"
        assert normalizza_codice_recupero(None) == ""

    def test_con_il_codice_si_entra_e_si_cambia_password(self):
        aggiornate, codice = con_codice_recupero(self.utente())
        dopo = recupera_con_codice(aggiornate, codice, "nuova12345", "nuova12345")
        assert dopo.corrisponde("nuova12345")
        assert not dopo.corrisponde("password1")

    def test_il_codice_si_consuma(self):
        # Un codice che resta valido per sempre e' una seconda password che
        # nessuno cambia mai.
        aggiornate, codice = con_codice_recupero(self.utente())
        dopo = recupera_con_codice(aggiornate, codice, "nuova12345", "nuova12345")
        assert not dopo.ha_codice_recupero
        assert not dopo.codice_corrisponde(codice)

    def test_rientrando_non_si_e_obbligati_a_ricambiarla(self):
        # La password l'ha scelta lui adesso: fargliela rifare al primo
        # accesso sarebbe solo una seccatura.
        aggiornate, codice = con_codice_recupero(self.utente())
        in_scadenza = replace(
            aggiornate,
            utente=replace(aggiornate.utente, deve_cambiare_password=True),
        )
        dopo = recupera_con_codice(in_scadenza, codice, "nuova12345", "nuova12345")
        assert not dopo.utente.deve_cambiare_password

    def test_il_codice_sbagliato_non_cambia_niente(self):
        aggiornate, _ = con_codice_recupero(self.utente())
        with pytest.raises(PasswordNonValida, match="codice"):
            recupera_con_codice(aggiornate, "AAAA-BBBB-CCCC", "nuova12345")

    def test_la_password_nuova_deve_reggere_le_regole(self):
        aggiornate, codice = con_codice_recupero(self.utente())
        with pytest.raises(PasswordNonValida):
            recupera_con_codice(aggiornate, codice, "corta")
        with pytest.raises(PasswordNonValida, match="coincidono"):
            recupera_con_codice(aggiornate, codice, "nuova12345", "nuova54321")

    def test_generarne_un_altro_invalida_il_primo(self):
        primo_giro, primo = con_codice_recupero(self.utente())
        secondo_giro, secondo = con_codice_recupero(primo_giro)
        assert secondo_giro.codice_corrisponde(secondo)
        assert not secondo_giro.codice_corrisponde(primo)

    def test_un_codice_troppo_corto_si_rifiuta(self):
        with pytest.raises(PasswordNonValida):
            con_codice_recupero(self.utente(), "ABC")


class TestRichiestaDiAiuto:
    """Chi non ha il codice chiede al presidente, e la richiesta resta scritta."""

    def tutti(self):
        marco = registra({}, 1, "marco", "Marco", "password1", email="m@esempio.it")
        marco = replace(marco, utente=replace(marco.utente, lega_id=1))
        return {"marco": marco}

    def test_registra_chi_ha_chiesto(self):
        richiesta = apri_richiesta_password(self.tutti(), "Marco", quando="2026-09-19")
        assert richiesta is not None
        assert richiesta.nome_utente == "marco"
        assert richiesta.lega_id == 1
        assert richiesta.aperta

    def test_un_nome_che_non_esiste_non_crea_niente(self):
        # Chi chiama risponde comunque «fatto»: da fuori non si deve capire
        # quali nomi utente esistono.
        assert apri_richiesta_password(self.tutti(), "sconosciuto") is None

    def test_un_utente_disattivato_non_crea_niente(self):
        tutti = self.tutti()
        tutti["marco"] = replace(
            tutti["marco"], utente=replace(tutti["marco"].utente, attivo=False)
        )
        assert apri_richiesta_password(tutti, "marco") is None

    def test_non_si_accumulano_richieste_della_stessa_persona(self):
        prima = apri_richiesta_password(self.tutti(), "marco")
        assert apri_richiesta_password(self.tutti(), "marco", aperte=[prima]) is None

    def test_dopo_che_e_stata_chiusa_se_ne_puo_fare_un_altra(self):
        prima = apri_richiesta_password(self.tutti(), "marco")
        chiusa = chiudi_richiesta(prima, PRESIDENTE_DI_LEGA)
        assert not chiusa.aperta
        assert apri_richiesta_password(self.tutti(), "marco", aperte=[chiusa])

    def test_chiuderla_dice_chi_e_stato_e_quando(self):
        richiesta = apri_richiesta_password(self.tutti(), "marco")
        chiusa = chiudi_richiesta(
            richiesta, PRESIDENTE_DI_LEGA, StatoRichiesta.ANNULLATA, quando="2026-09-19"
        )
        assert chiusa.stato is StatoRichiesta.ANNULLATA
        assert chiusa.chiusa_da == PRESIDENTE_DI_LEGA.id
        assert chiusa.chiusa_il == "2026-09-19"

    def test_il_nome_si_normalizza_come_al_login(self):
        richiesta = apri_richiesta_password(self.tutti(), "  MARCO  ")
        assert richiesta is not None and richiesta.nome_utente == "marco"
