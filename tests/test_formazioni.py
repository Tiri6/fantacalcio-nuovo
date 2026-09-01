"""Il giro base del fantacalcio: schierare, bloccare, contare.

Le formazioni sono la cosa che i partecipanti guardano piu' spesso, quindi
sono anche quella dove un errore si vede subito e costa fiducia. Qui si fissa
il comportamento su casi concreti: un senza voto sostituito dal primo in
panchina che puo' fare quel ruolo, un modificatore di difesa che guarda il
voto puro, e un blocco che scatta un minuto prima e non un minuto dopo.
"""

from datetime import datetime, timedelta

import pytest

from fantacalcio.formazioni import (
    SOSTITUZIONI_MASSIME,
    TITOLARI,
    Formazione,
    FormazioneNonValida,
    Reparto,
    Voto,
    adattamenti,
    calcola_partita,
    calcola_squadra,
    formazione_suggerita,
    leggi_modulo,
    punteggio_giocatore,
    schieramento,
    stato_blocco,
    valida,
)
from fantacalcio.leghe import FASCE_DIFESA, Bonus, ModalitaSostituzioni
from fantacalcio.regole import ParametriLega

# Una rosa finta con i ruoli che servono: 1 portiere, 5 difensori,
# 6 centrocampisti, 4 attaccanti, piu' qualche panchinaro.
RUOLI = {
    1: ("Por",),
    2: ("Por",),
    10: ("Dc",),
    11: ("Dc",),
    12: ("Dc",),
    13: ("Dd", "E"),
    14: ("Ds", "E"),
    20: ("M", "C"),
    21: ("C",),
    22: ("C", "T"),
    23: ("E",),
    24: ("M",),
    25: ("W", "T"),
    30: ("A", "Pc"),
    31: ("Pc",),
    32: ("A",),
    33: ("W", "A"),
}
ROSA = set(RUOLI)


def formazione_343(**extra) -> Formazione:
    return Formazione(
        squadra_id=1,
        giornata=1,
        modulo="3-4-3",
        titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
        panchina=(2, 13, 22, 33),
        **extra,
    )


class TestModuli:
    def test_i_numeri_diventano_reparti(self):
        modulo = leggi_modulo("3-4-3")
        assert (modulo.difensori, modulo.centrocampisti, modulo.attaccanti) == (3, 4, 3)

    def test_il_trequartista_conta_a_centrocampo(self):
        # 3-4-1-2: la linea da 1 e' il trequartista, non una punta.
        modulo = leggi_modulo("3-4-1-2")
        assert (modulo.difensori, modulo.centrocampisti, modulo.attaccanti) == (3, 5, 2)

    def test_ogni_modulo_mette_in_campo_undici(self):
        from fantacalcio.leghe import MODULI_CLASSIC, MODULI_MANTRA

        for nome in MODULI_MANTRA + MODULI_CLASSIC:
            assert leggi_modulo(nome).totale == TITOLARI, nome

    def test_un_modulo_che_non_torna_si_rifiuta(self):
        with pytest.raises(FormazioneNonValida, match="devono essere 11"):
            leggi_modulo("4-4-4")

    def test_quel_che_non_e_un_modulo(self):
        with pytest.raises(FormazioneNonValida, match="non e' un modulo"):
            leggi_modulo("modulo bello")


class TestReparti:
    def test_i_ruoli_di_confine_valgono_in_due_reparti(self):
        # L'esterno fa il terzino o l'ala di centrocampo.
        assert Reparto.DIFESA.accetta(("E",))
        assert Reparto.CENTROCAMPO.accetta(("E",))
        assert not Reparto.ATTACCO.accetta(("E",))

    def test_l_ala_gioca_avanti_o_in_mezzo(self):
        assert Reparto.CENTROCAMPO.accetta(("W",))
        assert Reparto.ATTACCO.accetta(("W",))
        assert not Reparto.DIFESA.accetta(("W",))

    def test_il_portiere_sta_solo_in_porta(self):
        assert Reparto.PORTA.accetta(("Por",))
        assert not Reparto.DIFESA.accetta(("Por",))


class TestValidazione:
    def test_una_formazione_giusta_non_ha_problemi(self):
        assert valida(formazione_343(), RUOLI, ROSA) == []

    def test_dieci_titolari_non_bastano(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31)
        )
        problemi = valida(formazione, RUOLI, ROSA)
        assert any("Servono 11 titolari" in p for p in problemi)

    def test_lo_stesso_giocatore_due_volte(self):
        formazione = Formazione(
            1,
            1,
            "3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
            panchina=(32, 2),
        )
        problemi = valida(formazione, RUOLI, ROSA)
        assert any("due volte" in p for p in problemi)

    def test_un_giocatore_non_in_rosa(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 999)
        )
        problemi = valida(formazione, RUOLI, ROSA)
        assert any("non sono in rosa" in p for p in problemi)

    def test_un_attaccante_in_difesa_e_lecito_ma_si_dichiara(self):
        # 30 e' un attaccante messo al posto di un difensore, e 10 (difensore)
        # finisce in attacco: due adattamenti, uno per parte. Fuori dalla
        # modalita' Easy non e' un errore, ma costa il malus a entrambi.
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 30, 11, 12, 20, 21, 23, 24, 10, 31, 32)
        )
        assert valida(formazione, RUOLI, ROSA) == []
        assert adattamenti(formazione, RUOLI) == [
            (30, Reparto.DIFESA),
            (10, Reparto.ATTACCO),
        ]

    def test_in_easy_un_attaccante_in_difesa_e_un_errore(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 30, 11, 12, 20, 21, 23, 24, 10, 31, 32)
        )
        problemi = valida(formazione, RUOLI, ROSA, ModalitaSostituzioni.EASY)
        assert any("difesa" in p for p in problemi)

    def test_una_formazione_a_posto_non_ha_adattamenti(self):
        assert adattamenti(formazione_343(), RUOLI) == []

    def test_dice_tutti_i_problemi_non_solo_il_primo(self):
        formazione = Formazione(1, 1, "3-4-3", titolari=(1, 999), panchina=(999,))
        problemi = valida(formazione, RUOLI, ROSA)
        assert len(problemi) >= 2


class TestSchieramento:
    def test_divide_i_titolari_per_reparto(self):
        righe = schieramento(formazione_343())
        assert [(r.etichetta, len(g)) for r, g in righe] == [
            ("Porta", 1),
            ("Difesa", 3),
            ("Centrocampo", 4),
            ("Attacco", 3),
        ]

    def test_regge_una_formazione_incompleta(self):
        # Serve mentre la si sta ancora componendo.
        righe = schieramento(Formazione(1, 1, "3-4-3", titolari=(1, 10)))
        assert [len(g) for _, g in righe] == [1, 1, 0, 0]


class TestBlocco:
    INIZIO = datetime(2026, 9, 20, 15, 0)

    def test_prima_del_limite_si_puo_ancora_cambiare(self):
        stato = stato_blocco(self.INIZIO, adesso=self.INIZIO - timedelta(minutes=10))
        assert stato.modificabile
        assert stato.mancano == timedelta(minutes=9)

    def test_al_minuto_prima_si_chiude(self):
        stato = stato_blocco(self.INIZIO, adesso=self.INIZIO - timedelta(minutes=1))
        assert not stato.modificabile
        assert "un minuto prima" in stato.motivo

    def test_un_secondo_prima_del_limite_e_ancora_aperta(self):
        adesso = self.INIZIO - timedelta(minutes=1, seconds=1)
        assert stato_blocco(self.INIZIO, adesso=adesso).modificabile

    def test_a_partita_cominciata_e_chiusa(self):
        stato = stato_blocco(self.INIZIO, adesso=self.INIZIO + timedelta(hours=1))
        assert not stato.modificabile

    def test_senza_orario_non_si_blocca_niente(self):
        # Una giornata senza data non e' stata programmata: impedire di
        # schierare sarebbe peggio che permetterlo.
        assert stato_blocco(None, adesso=self.INIZIO).modificabile


class TestPunteggioGiocatore:
    def test_voto_piu_bonus(self):
        voto = Voto(1, 1, voto=6.0, gol=1, assist=1, ammonizioni=1)
        # 6 + 3 (gol) + 1 (assist) - 0.5 (giallo) = 9.5
        assert punteggio_giocatore(voto, Bonus()) == pytest.approx(9.5)

    def test_chi_non_ha_giocato_non_fa_punti(self):
        assert punteggio_giocatore(Voto(1, 1, voto=None, gol=1), Bonus()) == 0.0

    def test_il_portiere_imbattuto_prende_il_suo_bonus(self):
        voto = Voto(1, 1, voto=6.0, imbattuto=True)
        assert punteggio_giocatore(voto, Bonus()) == pytest.approx(7.0)

    def test_i_gol_subiti_pesano(self):
        voto = Voto(1, 1, voto=6.0, gol_subiti=2)
        assert punteggio_giocatore(voto, Bonus()) == pytest.approx(4.0)


def voti_pieni(valore: float = 6.0, eccezioni: dict[int, Voto] | None = None):
    """Tutti a `valore`, tranne chi e' indicato in `eccezioni`."""
    voti = {g: Voto(g, 1, voto=valore) for g in RUOLI}
    voti.update(eccezioni or {})
    return voti


class TestCalcoloSquadra:
    def test_somma_i_titolari(self):
        tabellino = calcola_squadra(
            formazione_343(), voti_pieni(6.0), RUOLI, ParametriLega()
        )
        assert tabellino.somma_voti == pytest.approx(66.0)
        assert len(tabellino.schierati) == TITOLARI

    def test_un_senza_voto_lo_sostituisce_la_panchina(self):
        # Il centrocampista 20 non gioca. In panchina c'e' (2, 13, 22, 33):
        # il portiere 2 si salta, e il primo buono e' il 13, perche' il suo
        # ruolo «E» vale anche a centrocampo. L'ordine e' la volonta' del
        # fantallenatore, e si rispetta.
        voti = voti_pieni(6.0, {20: Voto(20, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert [s.entrato for s in tabellino.sostituzioni] == [13]
        assert tabellino.sostituzioni[0].uscito == 20
        assert tabellino.somma_voti == pytest.approx(66.0)

    def test_chi_non_puo_fare_quel_ruolo_si_salta(self):
        # Un buco in difesa: in panchina il primo e' il portiere 2, che pero'
        # in difesa non ci puo' andare. Entra il 13.
        voti = voti_pieni(6.0, {10: Voto(10, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert [s.entrato for s in tabellino.sostituzioni] == [13]
        assert tabellino.sostituzioni[0].reparto is Reparto.DIFESA

    def test_chi_entra_deve_aver_giocato(self):
        # Il 13, primo utile in panchina, e' anche lui senza voto: si scende
        # al successivo che ha giocato davvero.
        voti = voti_pieni(6.0, {20: Voto(20, 1, voto=None), 13: Voto(13, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert [s.entrato for s in tabellino.sostituzioni] == [22]

    def test_finite_le_sostituzioni_chi_resta_vale_zero(self):
        # Quattro buchi a centrocampo e quattro panchinari che potrebbero
        # riempirli: ne entrano tre, il quarto posto resta a zero.
        formazione = Formazione(
            1,
            1,
            "3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
            panchina=(22, 13, 25, 33),
        )
        senza = {g: Voto(g, 1, voto=None) for g in (20, 21, 23, 24)}
        tabellino = calcola_squadra(
            formazione, voti_pieni(6.0, senza), RUOLI, ParametriLega()
        )
        assert len(tabellino.sostituzioni) == SOSTITUZIONI_MASSIME
        assert len(tabellino.senza_voto) == 4
        # Sette titolari a 6, tre entrati a 6, un posto a zero.
        assert tabellino.somma_voti == pytest.approx(60.0)

    def test_un_giocatore_senza_riga_di_voto_e_un_senza_voto(self):
        voti = voti_pieni(6.0)
        del voti[30]
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert 30 in tabellino.senza_voto


class TestModificatoreDifesa:
    def test_premia_la_difesa_che_gioca_bene(self):
        # Portiere e tre difensori a 7: media 7.0 -> +5 con le fasce di default.
        alti = {g: Voto(g, 1, voto=7.0) for g in (1, 10, 11, 12)}
        voti = voti_pieni(6.0, alti)
        tabellino = calcola_squadra(
            formazione_343(), voti, RUOLI, ParametriLega(), fasce_difesa=FASCE_DIFESA
        )
        assert tabellino.modificatore_difesa == pytest.approx(5.0)

    def test_guarda_il_voto_puro_non_i_bonus(self):
        # Un difensore che segna prende +3 nel punteggio ma il modificatore
        # continua a guardare il 6 del voto: e' una regola sulla prestazione.
        voti = voti_pieni(6.0, {10: Voto(10, 1, voto=6.0, gol=1)})
        tabellino = calcola_squadra(
            formazione_343(), voti, RUOLI, ParametriLega(), fasce_difesa=FASCE_DIFESA
        )
        assert tabellino.modificatore_difesa == pytest.approx(1.0)
        assert tabellino.somma_voti == pytest.approx(69.0)

    def test_senza_fasce_non_si_applica(self):
        tabellino = calcola_squadra(
            formazione_343(), voti_pieni(7.0), RUOLI, ParametriLega()
        )
        assert tabellino.modificatore_difesa == 0.0

    def test_spento_nelle_opzioni_non_si_applica(self):
        par = ParametriLega(modificatore_difesa=False)
        tabellino = calcola_squadra(
            formazione_343(), voti_pieni(7.0), RUOLI, par, fasce_difesa=FASCE_DIFESA
        )
        assert tabellino.modificatore_difesa == 0.0


class TestGol:
    def test_sotto_la_soglia_zero_gol(self):
        tabellino = calcola_squadra(
            formazione_343(), voti_pieni(5.0), RUOLI, ParametriLega()
        )
        assert tabellino.totale == pytest.approx(55.0)
        assert tabellino.gol == 0

    def test_alla_soglia_scatta_il_primo(self):
        # 66 punti esatti con undici sei.
        tabellino = calcola_squadra(
            formazione_343(), voti_pieni(6.0), RUOLI, ParametriLega()
        )
        assert tabellino.totale == pytest.approx(66.0)
        assert tabellino.gol == 1

    def test_poi_uno_ogni_sei(self):
        tabellino = calcola_squadra(
            formazione_343(),
            voti_pieni(6.0, {30: Voto(30, 1, voto=6.0, gol=2)}),
            RUOLI,
            ParametriLega(),
        )
        assert tabellino.totale == pytest.approx(72.0)
        assert tabellino.gol == 2


class TestPartita:
    def test_due_tabellini_e_un_risultato(self):
        casa = formazione_343()
        fuori = Formazione(
            squadra_id=2,
            giornata=1,
            modulo="3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
            panchina=(2, 13),
        )
        voti = voti_pieni(6.0)
        esito = calcola_partita(casa, fuori, voti, RUOLI, ParametriLega())
        assert esito.punteggio == "1-1"
        assert esito.casa.squadra_id == 1
        assert esito.trasferta.squadra_id == 2


class TestFormazioneSuggerita:
    def test_riempie_i_posti_con_chi_puo_occuparli(self):
        suggerita = formazione_suggerita(1, 1, "3-4-3", sorted(RUOLI), RUOLI)
        assert valida(suggerita, RUOLI, ROSA) == []

    def test_chi_avanza_finisce_in_panchina(self):
        suggerita = formazione_suggerita(1, 1, "3-4-3", sorted(RUOLI), RUOLI)
        assert len(suggerita.titolari) == TITOLARI
        assert set(suggerita.titolari) & set(suggerita.panchina) == set()
        assert set(suggerita.titolari) | set(suggerita.panchina) == ROSA

    def test_con_una_rosa_corta_non_esplode(self):
        suggerita = formazione_suggerita(1, 1, "3-4-3", [1, 10, 30], RUOLI)
        assert len(suggerita.titolari) == 3

    def test_la_panchina_si_ferma_al_massimo_della_lega(self):
        # Una rosa intera non entra in una panchina da tre: la proposta si
        # taglia, altrimenti nasce gia' oltre il limite.
        suggerita = formazione_suggerita(
            1, 1, "3-4-3", sorted(RUOLI), RUOLI, panchinari=3
        )
        assert len(suggerita.panchina) == 3
        assert set(suggerita.titolari) & set(suggerita.panchina) == set()

    def test_senza_limite_la_panchina_resta_intera(self):
        suggerita = formazione_suggerita(1, 1, "3-4-3", sorted(RUOLI), RUOLI)
        assert set(suggerita.titolari) | set(suggerita.panchina) == ROSA


class TestModalitaDiSostituzione:
    """Le tre gerarchie del Mantra: Easy, Basic, Master.

    Il banco di prova e' un buco **in difesa**, dove i ruoli contano: in
    panchina 22 (C/T) non e' un difensore, 13 (Dd/E) si'. Mettendo 22 per
    primo si vede subito la differenza fra chi rispetta l'ordine della
    panchina e chi cerca prima il ruolo giusto.
    """

    def buco_in_difesa(self):
        """Il difensore 11 resta senza voto."""
        return voti_pieni(6.0, {11: Voto(11, 1, voto=None)})

    def formazione(self, panchina=(22, 13)):
        return Formazione(
            squadra_id=1,
            giornata=1,
            modulo="3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
            panchina=panchina,
        )

    def test_easy_prende_solo_chi_e_del_reparto(self):
        tabellino = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.EASY,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [13]
        assert tabellino.adattati == []
        assert tabellino.malus_adattamento == 0.0

    def test_easy_lascia_il_posto_vuoto_se_non_c_e_il_ruolo(self):
        # In panchina solo un centrocampista: in Easy non si adatta nessuno,
        # e il posto vale zero invece di essere riempito con un malus.
        tabellino = calcola_squadra(
            self.formazione(panchina=(22,)),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.EASY,
        )
        assert tabellino.sostituzioni == []
        assert (Reparto.DIFESA, 11, 0.0) in tabellino.schierati

    def test_basic_preferisce_il_ruolo_giusto_all_ordine(self):
        # Il primo in panchina e' 22, che difensore non e': Basic lo scavalca
        # e prende 13, che il posto lo occupa davvero.
        tabellino = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.BASIC,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [13]
        assert tabellino.adattati == []

    def test_basic_adatta_solo_quando_non_ha_scelta(self):
        tabellino = calcola_squadra(
            self.formazione(panchina=(22,)),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.BASIC,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [22]
        assert tabellino.sostituzioni[0].adattato
        assert tabellino.adattati == [22]
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_master_segue_l_ordine_della_panchina(self):
        # Master non scavalca: entra 22, adattato e col malus.
        tabellino = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.MASTER,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [22]
        assert tabellino.sostituzioni[0].adattato
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_il_malus_si_vede_nel_punteggio(self):
        senza = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.BASIC,
        )
        con = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.MASTER,
        )
        # Stessi voti, stesso numero di giocatori: la differenza e' il malus.
        assert senza.somma_voti - con.somma_voti == pytest.approx(1.0)

    def test_il_malus_lo_decide_il_regolamento(self):
        tabellino = calcola_squadra(
            self.formazione(),
            self.buco_in_difesa(),
            RUOLI,
            ParametriLega(malus_adattamento=2.5),
            modalita=ModalitaSostituzioni.MASTER,
        )
        assert tabellino.malus_adattamento == pytest.approx(-2.5)

    def test_master_non_paga_il_malus_se_il_ruolo_torna(self):
        # Due buchi: il primo se lo prende 22 adattandosi, il secondo tocca a
        # 13, che a centrocampo ci sta di suo.
        voti = voti_pieni(6.0, {11: Voto(11, 1, voto=None), 21: Voto(21, 1, voto=None)})
        tabellino = calcola_squadra(
            self.formazione(),
            voti,
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.MASTER,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [22, 13]
        assert [s.adattato for s in tabellino.sostituzioni] == [True, False]
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_un_titolare_fuori_posizione_paga_il_malus(self):
        # 30 (A/Pc) schierato a centrocampo: gioca, ma con un punto in meno.
        formazione = Formazione(
            squadra_id=1,
            giornata=1,
            modulo="3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 30, 31, 32, 33),
            panchina=(),
        )
        tabellino = calcola_squadra(formazione, voti_pieni(6.0), RUOLI, ParametriLega())
        assert tabellino.adattati == [30]
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_in_easy_il_titolare_fuori_posizione_non_vale_niente(self):
        formazione = Formazione(
            squadra_id=1,
            giornata=1,
            modulo="3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 30, 31, 32, 33),
            panchina=(),
        )
        tabellino = calcola_squadra(
            formazione,
            voti_pieni(6.0),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.EASY,
        )
        assert (Reparto.CENTROCAMPO, 30, 0.0) in tabellino.schierati
        assert tabellino.adattati == []


class TestIlPortiereNonSiAdattaMai:
    """La regola assoluta del Mantra, uguale in tutte e tre le modalita'.

    Un portiere non gioca in movimento e un giocatore di movimento non va in
    porta: nemmeno pagando il malus, che altrove compra tutto.
    """

    def senza_portiere(self):
        return voti_pieni(6.0, {1: Voto(1, 1, voto=None)})

    def formazione(self, panchina):
        return Formazione(
            squadra_id=1,
            giornata=1,
            modulo="3-4-3",
            titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
            panchina=panchina,
        )

    @pytest.mark.parametrize("modalita", list(ModalitaSostituzioni))
    def test_in_porta_entra_solo_un_portiere(self, modalita):
        # In panchina prima un difensore, poi il portiere di riserva: in porta
        # ci va il portiere, in tutte e tre le modalita'.
        tabellino = calcola_squadra(
            self.formazione(panchina=(13, 2)),
            self.senza_portiere(),
            RUOLI,
            ParametriLega(),
            modalita=modalita,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [2]
        assert not tabellino.sostituzioni[0].adattato

    @pytest.mark.parametrize("modalita", list(ModalitaSostituzioni))
    def test_senza_secondo_portiere_la_porta_resta_vuota(self, modalita):
        tabellino = calcola_squadra(
            self.formazione(panchina=(13, 22, 33)),
            self.senza_portiere(),
            RUOLI,
            ParametriLega(),
            modalita=modalita,
        )
        assert tabellino.sostituzioni == []
        assert (Reparto.PORTA, 1, 0.0) in tabellino.schierati

    def test_un_portiere_di_movimento_e_un_errore(self):
        # 2 e' il secondo portiere, messo al posto di un difensore.
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 2, 11, 12, 20, 21, 23, 24, 30, 31, 32)
        )
        problemi = valida(formazione, RUOLI, ROSA)
        assert any("non si adatta mai" in p for p in problemi)

    def test_un_attaccante_in_porta_e_un_errore(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(30, 10, 11, 12, 20, 21, 23, 24, 1, 31, 32)
        )
        problemi = valida(formazione, RUOLI, ROSA)
        assert any("non si adatta mai" in p for p in problemi)

    def test_e_non_conta_come_adattamento_pagabile(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 2, 11, 12, 20, 21, 23, 24, 30, 31, 32)
        )
        assert adattamenti(formazione, RUOLI) == []
