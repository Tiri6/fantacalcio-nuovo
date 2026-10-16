"""Leghe, codici d'invito e opzioni di gioco."""

import json

import pytest

from fantacalcio.competizioni import RegoleF1Rush, TipoCompetizione
from fantacalcio.leghe import (
    FASCE_DIFESA,
    MODULI_CLASSIC,
    MODULI_MANTRA,
    Bonus,
    CodiceNonValido,
    EmailNonValida,
    FasciaModificatore,
    FormatoCampionato,
    Invito,
    Lega,
    LegaNonValida,
    Modalita,
    OpzioniLega,
    StatoInvito,
    TipoAsta,
    bonus_modificatore,
    crea_invito,
    crea_lega,
    genera_codice_invito,
    invito_per_email,
    moduli_disponibili,
    normalizza_codice,
    normalizza_email,
    trova_per_codice,
)


class TestCodiceInvito:
    def test_formato(self):
        codice = genera_codice_invito()
        assert len(codice) == 9
        assert codice[4] == "-"

    def test_non_contiene_caratteri_confondibili(self):
        """O/0 e I/1 si sbagliano ricopiando il codice da uno screenshot."""
        insieme = "".join(genera_codice_invito() for _ in range(200))
        assert not set(insieme) & set("OI1L0UV")

    def test_due_codici_sono_diversi(self):
        assert len({genera_codice_invito() for _ in range(50)}) > 45

    @pytest.mark.parametrize(
        "scritto",
        ["abcd2345", "ABCD-2345", " abcd-2345 ", "AbCd 2345", "abcd\t2345"],
    )
    def test_normalizzazione_tollerante(self, scritto):
        assert normalizza_codice(scritto) == "ABCD-2345"

    @pytest.mark.parametrize("scritto", ["", "   ", "abc", "abcdefghij", None])
    def test_codici_rifiutati(self, scritto):
        with pytest.raises(CodiceNonValido):
            normalizza_codice(scritto)

    def test_il_messaggio_riporta_quello_che_hai_scritto(self):
        with pytest.raises(CodiceNonValido, match="pippo"):
            normalizza_codice("pippo")


class TestEmail:
    @pytest.mark.parametrize(
        "scritta", ["Marco@Esempio.IT", " marco@esempio.it ", "m.tirinato@sub.dominio.eu"]
    )
    def test_accettate(self, scritta):
        assert "@" in normalizza_email(scritta)
        assert normalizza_email(scritta) == normalizza_email(scritta).lower().strip()

    @pytest.mark.parametrize(
        "scritta", ["", "marco", "marco@", "@esempio.it", "a b@c.it"]
    )
    def test_rifiutate(self, scritta):
        with pytest.raises(EmailNonValida):
            normalizza_email(scritta)


class TestOpzioni:
    def test_default_e_mantra(self):
        assert OpzioniLega().modalita is Modalita.MANTRA

    def test_rosa_totale_e_la_somma_dei_reparti(self):
        opzioni = OpzioniLega(
            rosa_portieri=3, rosa_difensori=8, rosa_centrocampisti=8, rosa_attaccanti=6
        )
        assert opzioni.rosa_totale == 25

    def test_moduli_dipendono_dalla_modalita(self):
        assert moduli_disponibili(Modalita.CLASSIC) == MODULI_CLASSIC
        assert moduli_disponibili(Modalita.MANTRA) == MODULI_MANTRA

    def test_modulo_estraneo_alla_modalita_e_rifiutato(self):
        with pytest.raises(LegaNonValida, match="4-2-3-1"):
            OpzioniLega(modalita=Modalita.CLASSIC, moduli_ammessi=("4-2-3-1",))

    def test_serve_almeno_un_modulo(self):
        with pytest.raises(LegaNonValida, match="modulo"):
            OpzioniLega(moduli_ammessi=())

    @pytest.mark.parametrize("quanti", [1, 21, 0, -3])
    def test_partecipanti_fuori_scala(self, quanti):
        with pytest.raises(LegaNonValida):
            OpzioniLega(partecipanti=quanti)

    def test_passo_gol_deve_essere_positivo(self):
        with pytest.raises(LegaNonValida, match="passo"):
            OpzioniLega(passo_gol=0)


class TestFasceGol:
    @pytest.mark.parametrize(
        "punti,gol",
        [(0, 0), (65.5, 0), (66, 1), (71.9, 1), (72, 2), (78, 3), (84, 4), (120, 10)],
    )
    def test_soglia_66_passo_6(self, punti, gol):
        assert OpzioniLega().gol_da_punti(punti) == gol

    def test_una_lega_puo_cambiare_le_fasce(self):
        """Le fasce sono un'opzione, non una costante: la lega puo' votarle."""
        opzioni = OpzioniLega(soglia_primo_gol=60.0, passo_gol=4.0)
        assert opzioni.gol_da_punti(59) == 0
        assert opzioni.gol_da_punti(60) == 1
        assert opzioni.gol_da_punti(64) == 2


class TestModificatori:
    @pytest.mark.parametrize(
        "media,atteso",
        [
            (5.5, 0.0),
            (6.0, 0.5),
            (6.24, 0.5),
            (6.25, 1.0),
            (6.5, 1.5),
            (6.75, 2.0),
            (7.0, 2.5),
            # Oltre l'ultima fascia non si sale piu': la tabella finisce li'.
            (9.0, 2.5),
        ],
    )
    def test_tabella_difesa(self, media, atteso):
        assert bonus_modificatore(media, FASCE_DIFESA) == atteso

    def test_fasce_disordinate_danno_lo_stesso_risultato(self):
        """L'ordine in cui si scrivono le fasce non deve contare."""
        disordinate = tuple(reversed(FASCE_DIFESA))
        assert bonus_modificatore(6.6, disordinate) == bonus_modificatore(
            6.6, FASCE_DIFESA
        )

    def test_sotto_la_prima_soglia_nessun_bonus(self):
        assert bonus_modificatore(0.0, (FasciaModificatore(6.0, 1.0),)) == 0.0


class TestSerializzazione:
    def test_andata_e_ritorno(self):
        originali = OpzioniLega(
            modalita=Modalita.CLASSIC,
            moduli_ammessi=("4-4-2", "3-5-2"),
            formato=FormatoCampionato.SOLO_ANDATA,
            tipo_asta=TipoAsta.BUSTA_CHIUSA,
            partecipanti=8,
            soglia_primo_gol=60.0,
            bonus=Bonus(gol_segnato=4.0),
        )
        rilette = OpzioniLega.da_json(originali.a_json())
        assert rilette == originali

    def test_le_fasce_sopravvivono_al_giro(self):
        originali = OpzioniLega(fasce_difesa=(FasciaModificatore(6.0, 2.5),))
        assert OpzioniLega.da_json(originali.a_json()).fasce_difesa == (
            FasciaModificatore(6.0, 2.5),
        )

    @pytest.mark.parametrize("testo", [None, "", "non json", "[1,2,3]", "null"])
    def test_json_illeggibile_da_i_default(self, testo):
        assert OpzioniLega.da_json(testo) == OpzioniLega()

    def test_chiavi_sconosciute_ignorate(self):
        """Una lega creata da una versione piu' recente resta leggibile."""
        assert OpzioniLega.da_json('{"funzione_del_futuro": 42}') == OpzioniLega()

    def test_valori_di_enum_sconosciuti_non_esplodono(self):
        assert OpzioniLega.da_json('{"modalita": "SUBBUTEO"}').modalita is Modalita.MANTRA


class TestLeghePrimaDelCambioDiModuli:
    """Una lega salvata con l'elenco vecchio deve restare una lega.

    I moduli Mantra erano sedici ed erano il valore predefinito: ogni lega
    creata prima del 14 ottobre 2026 li ha scritti tutti nel database. Quando
    la piattaforma ne ha lasciati undici, quelle leghe hanno cominciato ad
    alzare `LegaNonValida` alla lettura — e `carica_leghe` salta in silenzio
    le righe illeggibili, quindi il sito diceva al presidente che non era in
    nessuna lega. Il guasto non si vedeva da nessun test, perche' le leghe dei
    test nascono gia' con l'elenco nuovo.
    """

    SEDICI = [
        "3-4-3", "3-4-1-2", "3-4-2-1", "3-5-2", "3-5-1-1", "4-3-3", "4-4-2",
        "4-3-1-2", "4-1-4-1", "4-2-3-1", "4-4-1-1", "4-3-2-1",
        "5-3-2", "5-4-1", "5-2-2-1", "5-3-1-1",
    ]  # fmt: skip

    def salvata(self, **altro) -> str:
        return json.dumps({"modalita": "MANTRA", "moduli_ammessi": self.SEDICI, **altro})

    def test_la_lega_si_legge_ancora(self):
        opzioni = OpzioniLega.da_json(self.salvata())

        assert opzioni.modalita is Modalita.MANTRA
        assert opzioni.partecipanti == OpzioniLega().partecipanti

    def test_i_moduli_che_non_esistono_piu_vanno_via(self):
        opzioni = OpzioniLega.da_json(self.salvata())

        assert set(opzioni.moduli_ammessi) == set(MODULI_MANTRA)
        assert not {"4-4-1-1", "5-3-2", "5-4-1", "5-2-2-1", "5-3-1-1"} & set(
            opzioni.moduli_ammessi
        )

    def test_una_scelta_della_lega_si_rispetta(self):
        """Se la lega aveva ristretto l'elenco, restano i suoi moduli, non
        tutti quelli che esistono."""
        opzioni = OpzioniLega.da_json(
            json.dumps({"modalita": "MANTRA", "moduli_ammessi": ["4-4-2", "5-3-2"]})
        )

        assert opzioni.moduli_ammessi == ("4-4-2",)

    def test_se_non_resta_nessun_modulo_si_torna_al_predefinito(self):
        """Una lega che ammetteva solo difese a cinque non puo' restare senza
        moduli: meglio l'elenco intero che una lega che non si apre."""
        opzioni = OpzioniLega.da_json(
            json.dumps({"modalita": "MANTRA", "moduli_ammessi": ["5-3-2", "5-4-1"]})
        )

        assert opzioni.moduli_ammessi == MODULI_MANTRA

    def test_un_elenco_scritto_male_non_fa_sparire_la_lega(self):
        opzioni = OpzioniLega.da_json('{"moduli_ammessi": 42}')

        assert opzioni.moduli_ammessi == MODULI_MANTRA

    def test_in_classic_si_guarda_l_elenco_classic(self):
        """La difesa a cinque esiste ancora nel Classic: li' non si toglie."""
        opzioni = OpzioniLega.da_json(
            json.dumps({"modalita": "CLASSIC", "moduli_ammessi": ["5-3-2", "4-4-2"]})
        )

        assert opzioni.moduli_ammessi == ("5-3-2", "4-4-2")


class TestLega:
    def test_creazione_genera_il_codice(self):
        lega = crea_lega(1, "Lega degli Amici", admin_id=7)
        assert lega.codice_invito
        assert lega.admin_id == 7
        assert lega.creata_il

    def test_il_codice_si_puo_imporre(self):
        assert crea_lega(1, "Amici", 1, codice="abcd2345").codice_invito == "ABCD-2345"

    @pytest.mark.parametrize("nome", ["", "  ", "ab"])
    def test_nome_troppo_corto(self, nome):
        with pytest.raises(LegaNonValida):
            crea_lega(1, nome, admin_id=1)

    def test_il_nome_perde_gli_spazi_ai_bordi(self):
        assert crea_lega(1, "  Amici  ", 1).nome == "Amici"

    def test_ricerca_per_codice_tollera_come_lo_scrivi(self):
        lega = crea_lega(1, "Amici", 1, codice="abcd2345")
        leghe = {1: lega}
        for scritto in ("abcd2345", "ABCD-2345", " AbCd 2345 "):
            assert trova_per_codice(leghe, scritto) is lega

    def test_codice_inesistente(self):
        assert trova_per_codice({1: crea_lega(1, "Amici", 1)}, "ZZZZ-9999") is None

    def test_codice_malformato_non_esplode(self):
        """Chi digita male deve vedere «non trovata», non un errore."""
        assert trova_per_codice({1: crea_lega(1, "Amici", 1)}, "pippo") is None

    def test_con_opzioni_non_muta_l_originale(self):
        lega = crea_lega(1, "Amici", 1)
        nuova = lega.con_opzioni(OpzioniLega(partecipanti=12))
        assert lega.opzioni.partecipanti == 10
        assert nuova.opzioni.partecipanti == 12
        assert nuova.codice_invito == lega.codice_invito


class TestInviti:
    def test_l_invito_porta_il_codice_della_lega(self):
        lega = crea_lega(1, "Amici", 1)
        invito = crea_invito(1, lega, "Luca@Esempio.IT", creato_da=1)
        assert invito.codice == lega.codice_invito
        assert invito.email == "luca@esempio.it"
        assert invito.in_attesa

    def test_email_non_valida_rifiutata(self):
        with pytest.raises(EmailNonValida):
            crea_invito(1, crea_lega(1, "Amici", 1), "non-una-email")

    def test_si_trova_per_email_senza_badare_alle_maiuscole(self):
        lega = crea_lega(3, "Amici", 1)
        inviti = [crea_invito(1, lega, "luca@esempio.it")]
        assert invito_per_email(inviti, 3, "LUCA@ESEMPIO.IT") is not None

    def test_un_invito_gia_accettato_non_si_ripresenta(self):
        lega = crea_lega(3, "Amici", 1)
        accettato = Invito(
            id=1,
            lega_id=3,
            email="luca@esempio.it",
            codice=lega.codice_invito,
            stato=StatoInvito.ACCETTATO,
        )
        assert invito_per_email([accettato], 3, "luca@esempio.it") is None

    def test_invito_di_un_altra_lega_non_vale(self):
        lega = crea_lega(3, "Amici", 1)
        inviti = [crea_invito(1, lega, "luca@esempio.it")]
        assert invito_per_email(inviti, 99, "luca@esempio.it") is None

    def test_email_malformata_in_ricerca_non_esplode(self):
        assert invito_per_email([], 1, "pippo") is None


def test_una_lega_resta_uguale_a_se_stessa_dopo_il_giro_completo():
    """Prova d'insieme: crea, serializza le opzioni, ricostruisci."""
    lega = crea_lega(
        5,
        "Fantacalcio NuoVo",
        admin_id=2,
        opzioni=OpzioniLega(modalita=Modalita.CLASSIC, moduli_ammessi=MODULI_CLASSIC),
    )
    ricostruita = Lega(
        id=lega.id,
        nome=lega.nome,
        codice_invito=lega.codice_invito,
        admin_id=lega.admin_id,
        stagione=lega.stagione,
        opzioni=OpzioniLega.da_json(lega.opzioni.a_json()),
        creata_il=lega.creata_il,
    )
    assert ricostruita == lega


class TestLimitiDiRuolo:
    def test_senza_limiti_il_totale_non_esiste(self):
        """Sommare ignorando i ruoli liberi darebbe un totale che non vincola."""
        opzioni = OpzioniLega(
            rosa_portieri=None,
            rosa_difensori=None,
            rosa_centrocampisti=None,
            rosa_attaccanti=None,
        )
        assert opzioni.rosa_totale is None
        assert not opzioni.limiti_per_ruolo

    def test_basta_un_ruolo_libero_perche_il_totale_sparisca(self):
        opzioni = OpzioniLega(rosa_portieri=None)
        assert opzioni.rosa_totale is None
        assert opzioni.limiti_per_ruolo

    def test_con_tutti_i_limiti_il_totale_e_la_somma(self):
        opzioni = OpzioniLega(
            rosa_portieri=3, rosa_difensori=8, rosa_centrocampisti=8, rosa_attaccanti=6
        )
        assert opzioni.rosa_totale == 25
        assert opzioni.limiti_per_ruolo

    def test_senza_limiti_sopravvive_al_json(self):
        originali = OpzioniLega(
            rosa_portieri=None,
            rosa_difensori=None,
            rosa_centrocampisti=None,
            rosa_attaccanti=None,
        )
        assert OpzioniLega.da_json(originali.a_json()).rosa_totale is None


class TestVincoliDiRosa:
    def test_default_nessun_vincolo(self):
        opzioni = OpzioniLega()
        assert opzioni.minimo_italiani == 0
        assert opzioni.minimo_u21_italiani == 0
        assert opzioni.scambi_illimitati

    @pytest.mark.parametrize(
        "campo", ["minimo_italiani", "minimo_u21_italiani", "scambi_per_stagione"]
    )
    def test_numeri_negativi_rifiutati(self, campo):
        with pytest.raises(LegaNonValida):
            OpzioniLega(**{campo: -1})

    def test_gli_u21_non_possono_superare_gli_italiani(self):
        """Un Under 21 italiano e' gia' un italiano: il contrario e' incoerente."""
        with pytest.raises(LegaNonValida, match="gia' un italiano"):
            OpzioniLega(minimo_italiani=3, minimo_u21_italiani=5)

    def test_senza_minimo_italiani_gli_u21_sono_liberi(self):
        """Con 0 italiani richiesti il vincolo U21 vale da solo."""
        assert (
            OpzioniLega(minimo_italiani=0, minimo_u21_italiani=3).minimo_u21_italiani == 3
        )

    def test_non_si_possono_chiedere_piu_italiani_della_rosa(self):
        with pytest.raises(LegaNonValida, match="rosa e' di"):
            OpzioniLega(
                rosa_portieri=3,
                rosa_difensori=8,
                rosa_centrocampisti=8,
                rosa_attaccanti=6,
                minimo_italiani=30,
            )

    def test_senza_limiti_di_ruolo_il_minimo_italiani_non_si_puo_verificare(self):
        """Senza un totale non c'e' niente con cui confrontare: si accetta."""
        assert OpzioniLega(rosa_portieri=None, minimo_italiani=30).minimo_italiani == 30


class TestScambiPerStagione:
    def test_illimitati_per_default(self):
        assert OpzioniLega().scambi_residui(99) is None

    def test_residui_scalano(self):
        opzioni = OpzioniLega(scambi_per_stagione=5)
        assert opzioni.scambi_residui(0) == 5
        assert opzioni.scambi_residui(3) == 2
        assert opzioni.scambi_residui(5) == 0

    def test_non_diventano_negativi(self):
        assert OpzioniLega(scambi_per_stagione=5).scambi_residui(9) == 0

    def test_un_conteggio_negativo_non_regala_scambi(self):
        assert OpzioniLega(scambi_per_stagione=5).scambi_residui(-3) == 5


class TestAnniContratto:
    def test_default_cinque(self):
        assert OpzioniLega().anni_contratto_massimi == 5

    @pytest.mark.parametrize("anni", [0, -1, 11])
    def test_fuori_scala(self, anni):
        with pytest.raises(LegaNonValida, match="anni di contratto"):
            OpzioniLega(anni_contratto_massimi=anni)

    def test_sopravvive_al_json(self):
        originali = OpzioniLega(anni_contratto_massimi=3)
        assert OpzioniLega.da_json(originali.a_json()).anni_contratto_massimi == 3


class TestOpzioniDraft:
    """L'ordine di chiamata vive nelle opzioni: niente tabella nuova."""

    def test_sopravvive_al_giro_in_json(self):
        opzioni = OpzioniLega(ordine_draft=(3, 1, 2), draft_serpente=False)
        tornate = OpzioniLega.da_json(opzioni.a_json())
        assert tornate.ordine_draft == (3, 1, 2)
        assert tornate.draft_serpente is False

    def test_il_valore_di_partenza_e_nessun_ordine_a_serpente(self):
        opzioni = OpzioniLega()
        assert opzioni.ordine_draft == ()
        assert opzioni.draft_serpente is True

    def test_un_json_vecchio_senza_i_campi_si_legge_lo_stesso(self):
        # Le leghe create prima di questa funzione non hanno le due chiavi.
        tornate = OpzioniLega.da_json('{"partecipanti": 10}')
        assert tornate.ordine_draft == ()
        assert tornate.partecipanti == 10

    def test_un_ordine_scritto_male_non_fa_saltare_la_lega(self):
        tornate = OpzioniLega.da_json('{"ordine_draft": ["a", "b"]}')
        assert tornate.ordine_draft == ()


class TestModificareLeRegole:
    """Le regole si cambiano a lega avviata, ma solo da chi l'ha creata.

    Rifare la lega per cambiare una soglia vorrebbe dire perdere rose,
    calendario e albo: il motivo per cui questa funzione esiste.
    """

    def lega(self):
        from fantacalcio.leghe import crea_lega

        return crea_lega(1, "FantaCalcio NuoVo", admin_id=7)

    def utente(self, id_=7, attivo=True):
        from fantacalcio.autenticazione import Ruolo, Utente

        return Utente(
            id=id_,
            nome_utente="marco",
            nome="Marco",
            ruolo=Ruolo.PRESIDENTE,
            lega_id=1,
            attivo=attivo,
        )

    def test_l_amministratore_puo(self):
        from fantacalcio.leghe import puo_modificare_regole

        assert puo_modificare_regole(self.utente(), self.lega())

    def test_un_altro_partecipante_no(self):
        from fantacalcio.leghe import puo_modificare_regole

        assert not puo_modificare_regole(self.utente(id_=8), self.lega())

    def test_nemmeno_il_presidente_di_un_altra_lega(self):
        """Il ruolo non basta: conta essere l'amministratore **di questa**."""
        from fantacalcio.autenticazione import Ruolo, Utente
        from fantacalcio.leghe import puo_modificare_regole

        altro = Utente(
            id=99,
            nome_utente="altro",
            nome="Altro",
            ruolo=Ruolo.PRESIDENTE,
            lega_id=2,
        )
        assert not puo_modificare_regole(altro, self.lega())

    def test_un_utente_disattivato_no(self):
        from fantacalcio.leghe import puo_modificare_regole

        assert not puo_modificare_regole(self.utente(attivo=False), self.lega())

    def test_senza_utente_o_senza_lega_no(self):
        from fantacalcio.leghe import puo_modificare_regole

        assert not puo_modificare_regole(None, self.lega())
        assert not puo_modificare_regole(self.utente(), None)

    def test_le_regole_nuove_prendono_il_posto_delle_vecchie(self):
        from dataclasses import replace

        from fantacalcio.leghe import aggiorna_opzioni

        lega = self.lega()
        nuove = replace(lega.opzioni, budget_cap=120_000_000.0, coppa_italia=True)
        dopo = aggiorna_opzioni(lega, nuove, self.utente())
        assert dopo.opzioni.budget_cap == 120_000_000.0
        assert dopo.opzioni.coppa_italia
        # Tutto il resto della lega resta dov'era: id, codice, nome.
        assert (dopo.id, dopo.codice_invito, dopo.nome) == (
            lega.id,
            lega.codice_invito,
            lega.nome,
        )

    def test_a_chi_non_puo_si_dice_di_no(self):
        from fantacalcio.leghe import RegoleNonModificabili, aggiorna_opzioni

        lega = self.lega()
        with pytest.raises(RegoleNonModificabili):
            aggiorna_opzioni(lega, lega.opzioni, self.utente(id_=8))

    def test_non_si_scende_sotto_le_squadre_gia_iscritte(self):
        # Dieci squadre stanno giocando: portare i partecipanti a otto ne
        # lascerebbe fuori due, e non e' un errore che si scopre in tempo.
        from dataclasses import replace

        from fantacalcio.leghe import LegaNonValida, aggiorna_opzioni

        lega = self.lega()
        strette = replace(lega.opzioni, partecipanti=8)
        with pytest.raises(LegaNonValida, match="gia' 10 squadre"):
            aggiorna_opzioni(lega, strette, self.utente(), squadre_iscritte=10)

    def test_ridurre_i_partecipanti_si_puo_se_c_e_spazio(self):
        from dataclasses import replace

        from fantacalcio.leghe import aggiorna_opzioni

        lega = self.lega()
        strette = replace(lega.opzioni, partecipanti=8)
        dopo = aggiorna_opzioni(lega, strette, self.utente(), squadre_iscritte=6)
        assert dopo.opzioni.partecipanti == 8

    def test_le_regole_assurde_le_rifiuta_gia_la_dataclass(self):
        from dataclasses import replace

        from fantacalcio.leghe import LegaNonValida

        with pytest.raises(LegaNonValida):
            replace(self.lega().opzioni, moduli_ammessi=())

    def test_si_puo_cambiare_anche_la_stagione(self):
        from fantacalcio.leghe import aggiorna_opzioni

        lega = self.lega()
        dopo = aggiorna_opzioni(lega, lega.opzioni, self.utente(), stagione="2027/28")
        assert dopo.stagione == "2027/28"

    def test_una_stagione_vuota_non_cancella_quella_buona(self):
        from fantacalcio.leghe import aggiorna_opzioni

        lega = self.lega()
        dopo = aggiorna_opzioni(lega, lega.opzioni, self.utente(), stagione="   ")
        assert dopo.stagione == lega.stagione


class TestCosaCambia:
    """Il riepilogo che si legge prima di salvare."""

    def test_senza_modifiche_non_dice_niente(self):
        from fantacalcio.leghe import OpzioniLega, differenze

        assert differenze(OpzioniLega(), OpzioniLega()) == []

    def test_dice_cosa_diventa_cosa(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, minimo_italiani=4)
        assert differenze(prima, dopo) == ["Minimo italiani: 0 → 4"]

    def test_i_milioni_si_leggono_come_milioni(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, budget_cap=110_000_000.0)
        assert differenze(prima, dopo) == ["Budget cap: 100M → 110M"]

    def test_i_si_e_i_no_non_sono_true_e_false(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        assert differenze(prima, replace(prima, coppa_italia=True)) == [
            "Coppa Italia: no → si"
        ]

    def test_gli_elenchi_si_leggono_per_esteso(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, moduli_ammessi=("3-4-3", "4-4-2"))
        assert differenze(prima, dopo) == [
            f"Moduli ammessi: {', '.join(prima.moduli_ammessi)} → 3-4-3, 4-4-2"
        ]

    def test_il_nessun_limite_si_dice(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, rosa_portieri=None)
        assert differenze(prima, dopo) == ["Portieri in rosa: 3 → nessun limite"]

    def test_le_enumerazioni_si_leggono_con_la_loro_etichetta(self):
        from dataclasses import replace

        from fantacalcio.leghe import ModalitaSostituzioni, OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, modalita_sostituzioni=ModalitaSostituzioni.MASTER)
        assert differenze(prima, dopo) == ["Modalita' delle sostituzioni: Basic → Master"]

    def test_ogni_campo_delle_opzioni_ha_un_nome_leggibile(self):
        """Se domani si aggiunge una casella, il riepilogo deve saperla dire."""
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        for campo in OpzioniLega.__dataclass_fields__:
            if campo in ("modalita", "moduli_ammessi"):
                continue  # vincolati fra loro: cambiarli a caso non e' valido
            valore = getattr(prima, campo)
            diverso = _qualcosa_di_diverso(valore)
            if diverso is None:
                continue
            try:
                dopo = replace(prima, **{campo: diverso})
            except Exception:  # noqa: BLE001 - alcune combinazioni non sono valide
                continue
            righe = differenze(prima, dopo)
            assert righe, campo
            assert "_" not in righe[0].split(":")[0], (
                f"«{campo}» compare col nome del codice: aggiungilo a ETICHETTE_OPZIONI"
            )


def _qualcosa_di_diverso(valore):
    """Un valore valido ma diverso da quello dato, per far scattare il confronto."""
    if isinstance(valore, bool):
        return not valore
    if isinstance(valore, int):
        return valore + 1
    if isinstance(valore, float):
        return valore + 1.0
    if isinstance(valore, str):
        return f"{valore}x"
    return None


class TestAvvisiSulleRegole:
    """Quel che il salvataggio accetta ma conviene sapere prima.

    Non sono divieti: sono cambiamenti legittimi che pero' toccano cose gia'
    salvate — formazioni schierate, giornate calcolate — e scoprirli dopo
    costa piu' che leggerli prima.
    """

    def test_togliere_un_modulo_gia_usato_si_vede_nel_confronto(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega(moduli_ammessi=("3-4-3", "4-3-3"))
        dopo = replace(prima, moduli_ammessi=("3-4-3",))
        assert differenze(prima, dopo) == ["Moduli ammessi: 3-4-3, 4-3-3 → 3-4-3"]

    def test_cambiare_le_fasce_di_gol_si_vede(self):
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega, differenze

        prima = OpzioniLega()
        dopo = replace(prima, soglia_primo_gol=60.0)
        assert differenze(prima, dopo) == ["Punti per il primo gol: 66 → 60"]

    def test_i_limiti_di_ruolo_sono_indipendenti(self):
        # La lega di demo limita i portieri e lascia liberi gli altri: chi
        # riapre le regole non deve ritrovarsi tre limiti che non ha scelto.
        from fantacalcio.leghe import OpzioniLega, differenze

        mista = OpzioniLega(
            rosa_portieri=3,
            rosa_difensori=None,
            rosa_centrocampisti=None,
            rosa_attaccanti=None,
        )
        assert differenze(mista, mista) == []
        assert mista.rosa_portieri == 3 and mista.rosa_difensori is None


class TestF1RushNelleOpzioni:
    """La F1 Rush ha preso il posto della Supercoppa, anche nelle leghe salvate."""

    def test_round_trip(self):
        opzioni = OpzioniLega(f1_rush=True)
        assert OpzioniLega.da_json(opzioni.a_json()) == opzioni

    def test_la_scala_sopravvive_al_json(self):
        opzioni = OpzioniLega(
            f1_rush=True, regole_f1_rush=RegoleF1Rush(punti_per_posizione=(10, 6, 3))
        )
        rifatta = OpzioniLega.da_json(opzioni.a_json()).regole_f1_rush
        assert rifatta.punti_per_posizione == (10, 6, 3)

    def test_una_lega_che_aveva_la_supercoppa_trova_la_f1_rush(self):
        """Perderla in silenzio farebbe sparire una voce di menu da sola."""
        vecchia = json.dumps({"supercoppa": True})
        assert OpzioniLega.da_json(vecchia).f1_rush

    def test_una_lega_senza_supercoppa_non_la_trova_accesa(self):
        assert not OpzioniLega.da_json(json.dumps({"supercoppa": False})).f1_rush

    def test_la_f1_rush_compare_fra_le_competizioni(self):
        attive = OpzioniLega(f1_rush=True).competizioni
        assert TipoCompetizione.F1_RUSH in attive

    def test_spenta_non_compare(self):
        assert TipoCompetizione.F1_RUSH not in OpzioniLega().competizioni


class TestParametriDiPunteggio:
    """Il regolamento e le opzioni di lega si incontrano in un posto solo.

    Erano fusi dentro `ui.py`, cioe' dietro Streamlit: l'API non poteva
    arrivarci e si sarebbe ritrovata a rifare la fusione per conto suo. Due
    copie vogliono dire la stessa giornata calcolata con fasce diverse a
    seconda di da dove la guardi.
    """

    def test_senza_lega_valgono_i_parametri_del_regolamento(self):
        from fantacalcio.leghe import parametri_di_punteggio
        from fantacalcio.regole import ParametriLega

        base = ParametriLega()
        assert parametri_di_punteggio(base, None) is base

    def test_la_lega_sovrascrive_fasce_e_modificatore(self):
        from fantacalcio.leghe import OpzioniLega, crea_lega, parametri_di_punteggio
        from fantacalcio.regole import ParametriLega

        lega = crea_lega(
            1,
            "Prova",
            admin_id=1,
            opzioni=OpzioniLega(
                soglia_primo_gol=60.0,
                passo_gol=4.0,
                modificatore_difesa=True,
            ),
        )
        uniti = parametri_di_punteggio(ParametriLega(), lega)

        assert uniti.soglia_primo_gol == 60.0
        assert uniti.passo_gol == 4.0
        assert uniti.modificatore_difesa is True

    def test_il_resto_del_regolamento_non_si_tocca(self):
        """Solo i tre campi che la lega puo' votare, non gli altri."""
        from fantacalcio.leghe import crea_lega, parametri_di_punteggio
        from fantacalcio.regole import ParametriLega

        base = ParametriLega()
        lega = crea_lega(1, "Prova", admin_id=1)
        uniti = parametri_di_punteggio(base, lega)

        assert uniti.monte_anni == base.monte_anni
        assert uniti.salary_cap == base.salary_cap


class TestLeRegoleComeModulo:
    """La descrizione da cui il sito disegna il modulo delle regole.

    Il punto di tutto: un'opzione aggiunta domani deve comparire nel sito
    **da sola**. Scrivere le caselle a mano vorrebbe dire una terza copia
    dell'elenco delle opzioni — dopo la dataclass e le etichette — e la terza
    copia e' quella che si dimentica.
    """

    def test_ogni_opzione_sta_in_un_gruppo_o_e_esclusa_col_motivo(self):
        """Il test che tiene in piedi il patto: aggiungere un campo a
        `OpzioniLega` senza metterlo da qualche parte fa fallire questo."""
        from fantacalcio.leghe import FUORI_MODULO, GRUPPI_OPZIONI, OpzioniLega

        nei_gruppi = {
            nome.partition(".")[0] for _, nomi in GRUPPI_OPZIONI for nome in nomi
        }
        tutti = set(OpzioniLega.__dataclass_fields__)

        assert tutti - nei_gruppi - set(FUORI_MODULO) == set()
        # Chi e' escluso lo e' per un motivo scritto, non per dimenticanza.
        assert all(FUORI_MODULO.values())
        assert nei_gruppi & set(FUORI_MODULO) == set()

    def test_il_tipo_si_ricava_dal_valore(self):
        from fantacalcio.leghe import OpzioniLega, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}

        assert campi["partecipanti"].tipo == "intero"
        assert campi["budget_cap"].tipo == "decimale"
        assert campi["coppa_italia"].tipo == "booleano"
        assert campi["modalita"].tipo == "scelta"
        assert campi["moduli_ammessi"].tipo == "multi"

    def test_un_enum_si_porta_dietro_le_sue_voci(self):
        from fantacalcio.leghe import OpzioniLega, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}
        sostituzioni = campi["modalita_sostituzioni"]

        assert sostituzioni.valore == "BASIC"
        assert [s.valore for s in sostituzioni.scelte] == ["EASY", "BASIC", "MASTER"]
        assert all(s.etichetta for s in sostituzioni.scelte)

    def test_i_moduli_dipendono_dalla_modalita(self):
        """Mantra e Classic hanno moduli diversi: offrire gli altri vorrebbe
        dire far scegliere una cosa che poi `OpzioniLega` rifiuta."""
        from dataclasses import replace

        from fantacalcio.leghe import Modalita, OpzioniLega, descrivi_opzioni

        def moduli(opzioni):
            campi = {c.nome: c for g in descrivi_opzioni(opzioni) for c in g.campi}
            return [s.valore for s in campi["moduli_ammessi"].scelte]

        mantra = moduli(OpzioniLega())
        classic = moduli(
            replace(
                OpzioniLega(),
                modalita=Modalita.CLASSIC,
                moduli_ammessi=("4-4-2",),
            )
        )

        assert mantra != classic
        assert "3-4-1-2" in mantra

    def test_un_tetto_per_ruolo_puo_non_esserci(self):
        from fantacalcio.leghe import OpzioniLega, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}

        assert campi["rosa_portieri"].opzionale is True
        assert campi["partecipanti"].opzionale is False

    def test_i_campi_annidati_si_vedono_uno_per_uno(self):
        from fantacalcio.leghe import OpzioniLega, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}

        assert campi["bonus.assist"].valore == 1.0
        assert campi["bonus.assist"].etichetta == "Assist"
        assert campi["regole_coppa.gironi"].valore == 2


class TestApplicareIlModulo:
    def test_rimette_i_valori_al_loro_tipo(self):
        from fantacalcio.leghe import (
            ModalitaSostituzioni,
            OpzioniLega,
            con_valori,
        )

        nuove = con_valori(
            OpzioniLega(),
            {
                "partecipanti": 12,
                "coppa_italia": True,
                "modalita_sostituzioni": "MASTER",
                "bonus.assist": 2.0,
                "regole_f1_rush.punti_per_posizione": "25, 18, 15",
            },
        )

        assert nuove.partecipanti == 12
        assert nuove.coppa_italia is True
        assert nuove.modalita_sostituzioni is ModalitaSostituzioni.MASTER
        assert nuove.bonus.assist == 2.0
        assert nuove.regole_f1_rush.punti_per_posizione == (25, 18, 15)

    def test_quel_che_non_si_tocca_resta(self):
        from fantacalcio.leghe import OpzioniLega, con_valori

        prima = OpzioniLega()
        dopo = con_valori(prima, {"partecipanti": 12})

        assert dopo.moduli_ammessi == prima.moduli_ammessi
        assert dopo.bonus == prima.bonus

    def test_un_nome_sconosciuto_ferma_tutto(self):
        """Ignorarlo in silenzio vorrebbe dire far credere a chi compila di
        aver cambiato una regola che invece e' rimasta com'era."""
        from fantacalcio.leghe import LegaNonValida, OpzioniLega, con_valori

        with pytest.raises(LegaNonValida, match="non esistono"):
            con_valori(OpzioniLega(), {"partecipantii": 12})

    def test_un_tetto_per_ruolo_si_puo_togliere(self):
        """«Nessun limite» e' una scelta legittima: il fantacalcio
        manageriale spesso non impone quanti difensori avere."""
        from fantacalcio.leghe import OpzioniLega, con_valori

        assert con_valori(OpzioniLega(), {"rosa_portieri": ""}).rosa_portieri is None

    def test_una_voce_inventata_per_un_enum_lo_dice(self):
        from fantacalcio.leghe import LegaNonValida, OpzioniLega, con_valori

        with pytest.raises(LegaNonValida, match="non e' un valore ammesso"):
            con_valori(OpzioniLega(), {"modalita": "SUBBUTEO"})

    def test_i_controlli_di_sempre_restano(self):
        """`con_valori` non valida: costruisce. A dire di no e' `OpzioniLega`,
        dov'e' sempre stato."""
        from fantacalcio.leghe import LegaNonValida, OpzioniLega, con_valori

        with pytest.raises(LegaNonValida):
            con_valori(OpzioniLega(), {"partecipanti": 1})

    def test_le_differenze_scendono_dentro_gli_oggetti(self):
        """Prima stampava due righe di `Bonus(gol_segnato=3.0, ...)` da
        confrontare a occhio: e' la riga che si legge prima di salvare."""
        from fantacalcio.leghe import OpzioniLega, con_valori, differenze

        prima = OpzioniLega()
        dopo = con_valori(prima, {"bonus.assist": 2.0})

        assert differenze(prima, dopo) == ["Assist: 1 → 2"]

    def test_il_salary_cap_si_scrive_in_milioni(self):
        """Nessuno lo dice in euro: la lega vota «cento milioni», e scrivere
        100000000 a mano e' un modo per sbagliare uno zero."""
        from fantacalcio.leghe import OpzioniLega, con_valori, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}

        assert campi["budget_cap"].valore == 100.0
        assert campi["budget_cap"].unita == "milioni"
        assert con_valori(OpzioniLega(), {"budget_cap": 80}).budget_cap == 80_000_000

    def test_il_formato_della_coppa_non_si_chiama_come_quello_del_campionato(self):
        """Due campi diversi che si chiamano `formato`: senza il nome intero
        la coppa ereditava l'etichetta del campionato."""
        from fantacalcio.leghe import OpzioniLega, descrivi_opzioni

        campi = {c.nome: c for g in descrivi_opzioni(OpzioniLega()) for c in g.campi}

        assert campi["regole_coppa.formato"].etichetta == "Formato della coppa"
        assert campi["formato"].etichetta == "Formato del campionato"
