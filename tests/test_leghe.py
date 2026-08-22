"""Leghe, codici d'invito e opzioni di gioco."""

import pytest

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
        [(5.5, 0.0), (6.0, 1.0), (6.24, 1.0), (6.25, 2.0), (6.5, 3.0), (9.0, 6.0)],
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
