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
    # Tre panchinari che servono a far parlare la tabella delle sostituzioni:
    # per coprire un Dc, un altro Dc entra gratis, un Dd paga il malus, e una
    # punta non entra affatto.
    40: ("Dc",),
    41: ("Dd",),
    42: ("Pc",),
}
ROSA = set(RUOLI)


def formazione_343(**extra) -> Formazione:
    """Un 3-4-3 legittimo secondo lo schema ufficiale.

    Le caselle sono `Por | Dc Dc Dc/B | E M/C C E | W/A W/A A/Pc`, e ogni
    titolare sta nella sua: i test sul punteggio partono da una formazione che
    non paga niente, cosi' quando un malus compare e' perche' lo si e' voluto.

    In panchina, in ordine: il secondo portiere, un C/T, un Dd e un W/T.
    """
    valori = {
        "squadra_id": 1,
        "giornata": 1,
        "modulo": "3-4-3",
        "titolari": (1, 10, 11, 12, 23, 20, 21, 13, 30, 33, 31),
        "panchina": (2, 22, 41, 25),
    }
    return Formazione(**{**valori, **extra})


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

    def test_un_difensore_in_attacco_e_lecito_ma_si_dichiara(self):
        # Il difensore 40 occupa la casella «A/Pc»: si copre una linea avanzata
        # con una piu' arretrata, quindi la tabella lo ammette — pagando.
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 10, 11, 12, 23, 20, 21, 13, 30, 33, 40)
        )
        assert valida(formazione, RUOLI, ROSA) == []
        assert [g for g, _ in adattamenti(formazione, RUOLI)] == [40]

    def test_un_attaccante_in_difesa_non_si_puo_proprio(self):
        # L'altro verso e' chiuso: una punta in una casella «Dc» la tabella non
        # la ammette, nemmeno pagando, in nessuna modalita'.
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 31, 11, 12, 23, 20, 21, 13, 30, 33, 10)
        )
        for modalita in ModalitaSostituzioni:
            problemi = valida(formazione, RUOLI, ROSA, modalita)
            assert any("posizione 2" in p for p in problemi), modalita

    def test_in_easy_anche_un_adattamento_lecito_e_un_errore(self):
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 10, 11, 12, 23, 20, 21, 13, 30, 33, 40)
        )
        problemi = valida(formazione, RUOLI, ROSA, ModalitaSostituzioni.EASY)
        assert any("Easy" in p for p in problemi)

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
        # Il centrocampista 20 (M/C) non gioca. In panchina c'e' (2, 13, 22,
        # 33): il portiere 2 e' escluso sempre, il 13 (Dd/E) coprirebbe con
        # malus, e il 22 (C/T) copre gratis — la tabella dice che un C entra
        # per un C senza pagare. In Basic il gratis vince sull'ordine.
        voti = voti_pieni(6.0, {20: Voto(20, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert [s.entrato for s in tabellino.sostituzioni] == [22]
        assert tabellino.sostituzioni[0].uscito == 20
        assert not tabellino.sostituzioni[0].adattato
        assert tabellino.somma_voti == pytest.approx(66.0)

    def test_chi_non_puo_fare_quel_ruolo_si_salta(self):
        # Buco in una casella «Dc»: il portiere 2 non entra mai, il 22 (C/T) e
        # il 25 (W/T) sono troppo avanti — un difensore non si copre con un
        # centrocampista. Resta il 41 (Dd), che entra adattandosi: un terzino
        # in una casella da centrale costa il malus.
        voti = voti_pieni(6.0, {10: Voto(10, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert [s.entrato for s in tabellino.sostituzioni] == [41]
        assert tabellino.sostituzioni[0].reparto is Reparto.DIFESA
        assert tabellino.sostituzioni[0].adattato

    def test_chi_entra_deve_aver_giocato(self):
        # Buco in difesa: il 41 sarebbe l'unico che puo' coprirlo, ma e' senza
        # voto anche lui. Nessun altro in panchina puo' fare il difensore, e
        # il posto resta a zero.
        voti = voti_pieni(6.0, {10: Voto(10, 1, voto=None), 41: Voto(41, 1, voto=None)})
        tabellino = calcola_squadra(formazione_343(), voti, RUOLI, ParametriLega())
        assert tabellino.sostituzioni == []
        assert (Reparto.DIFESA, 10, 0.0) in tabellino.schierati

    def test_finite_le_sostituzioni_chi_resta_vale_zero(self):
        # Tutto il centrocampo senza voto e quattro panchinari: ne entrano
        # tre, il quarto posto resta a zero.
        formazione = formazione_343(panchina=(22, 41, 40, 25))
        senza = {g: Voto(g, 1, voto=None) for g in (23, 20, 21, 13)}
        tabellino = calcola_squadra(
            formazione, voti_pieni(6.0, senza), RUOLI, ParametriLega()
        )
        assert len(tabellino.sostituzioni) == SOSTITUZIONI_MASSIME
        assert len(tabellino.senza_voto) == 4
        # Sette titolari a 6 fanno 42. Nella casella «E» nessuno entra gratis
        # e tocca al 41 adattato (5); nella «M/C» il 22 entra gratis (6);
        # nella «C» il 40 si adatta (5); la seconda «E» resta a zero perche' i
        # cambi sono finiti.
        assert [s.adattato for s in tabellino.sostituzioni] == [True, False, True]
        assert tabellino.somma_voti == pytest.approx(58.0)

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
        fuori = formazione_343(squadra_id=2)
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

    Il banco di prova e' la casella «M/C» del 3-4-3, con in panchina — in
    quest'ordine — il 41 (Dd, che la copre pagando) e il 22 (C/T, che la copre
    gratis). Mettendo per primo quello che costa si vede subito la differenza
    fra chi rispetta l'ordine della panchina e chi cerca la soluzione gratis.
    """

    def buco_in_mezzo(self):
        """Il 20, che occupa la casella «M/C», resta senza voto."""
        return voti_pieni(6.0, {20: Voto(20, 1, voto=None)})

    def calcola(self, modalita, panchina=(41, 22), parametri=None):
        return calcola_squadra(
            formazione_343(panchina=panchina),
            self.buco_in_mezzo(),
            RUOLI,
            parametri or ParametriLega(),
            modalita=modalita,
        )

    def test_easy_prende_solo_chi_entra_senza_malus(self):
        tabellino = self.calcola(ModalitaSostituzioni.EASY)
        assert [s.entrato for s in tabellino.sostituzioni] == [22]
        assert tabellino.adattati == []
        assert tabellino.malus_adattamento == 0.0

    def test_easy_lascia_il_posto_vuoto_se_si_dovrebbe_pagare(self):
        # In panchina solo il Dd, che per una casella «M/C» paga: in Easy non
        # si paga mai, e il posto vale zero.
        tabellino = self.calcola(ModalitaSostituzioni.EASY, panchina=(41,))
        assert tabellino.sostituzioni == []
        assert (Reparto.CENTROCAMPO, 20, 0.0) in tabellino.schierati

    def test_basic_preferisce_il_gratis_all_ordine(self):
        # Il primo in panchina e' il 41, che costa: Basic lo scavalca e
        # prende il 22, che entra senza malus.
        tabellino = self.calcola(ModalitaSostituzioni.BASIC)
        assert [s.entrato for s in tabellino.sostituzioni] == [22]
        assert tabellino.adattati == []

    def test_basic_paga_solo_quando_non_ha_scelta(self):
        tabellino = self.calcola(ModalitaSostituzioni.BASIC, panchina=(41,))
        assert [s.entrato for s in tabellino.sostituzioni] == [41]
        assert tabellino.sostituzioni[0].adattato
        assert tabellino.adattati == [41]
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_master_segue_l_ordine_della_panchina(self):
        # Master non scavalca: entra il 41, adattato e col malus.
        tabellino = self.calcola(ModalitaSostituzioni.MASTER)
        assert [s.entrato for s in tabellino.sostituzioni] == [41]
        assert tabellino.sostituzioni[0].adattato
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_il_malus_si_vede_nel_punteggio(self):
        senza = self.calcola(ModalitaSostituzioni.BASIC)
        con = self.calcola(ModalitaSostituzioni.MASTER)
        # Stessi voti, stesso numero di giocatori: la differenza e' il malus.
        assert senza.somma_voti - con.somma_voti == pytest.approx(1.0)

    def test_il_malus_lo_decide_il_regolamento(self):
        tabellino = self.calcola(
            ModalitaSostituzioni.MASTER, parametri=ParametriLega(malus_adattamento=2.5)
        )
        assert tabellino.malus_adattamento == pytest.approx(-2.5)

    def test_nessuna_modalita_manda_una_punta_a_fare_il_difensore(self):
        # La tabella e' asimmetrica e questo e' il lato chiuso: una casella
        # «Dc» non si copre con un attaccante, nemmeno pagando, nemmeno in
        # Master, che di solito prende il primo che trova.
        voti = voti_pieni(6.0, {10: Voto(10, 1, voto=None)})
        for modalita in ModalitaSostituzioni:
            tabellino = calcola_squadra(
                formazione_343(panchina=(42,)),
                voti,
                RUOLI,
                ParametriLega(),
                modalita=modalita,
            )
            assert tabellino.sostituzioni == [], modalita
            assert (Reparto.DIFESA, 10, 0.0) in tabellino.schierati

    def test_ma_un_difensore_puo_coprire_una_punta(self):
        # L'altro lato della stessa asimmetria: si arretra, non si avanza.
        voti = voti_pieni(6.0, {31: Voto(31, 1, voto=None)})
        tabellino = calcola_squadra(
            formazione_343(panchina=(40,)),
            voti,
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.MASTER,
        )
        assert [s.entrato for s in tabellino.sostituzioni] == [40]
        assert tabellino.sostituzioni[0].adattato

    def test_un_titolare_fuori_posizione_paga_il_malus(self):
        # Il difensore 40 nella casella «A/Pc»: gioca, con un punto in meno.
        formazione = formazione_343(titolari=(1, 10, 11, 12, 23, 20, 21, 13, 30, 33, 40))
        tabellino = calcola_squadra(formazione, voti_pieni(6.0), RUOLI, ParametriLega())
        assert tabellino.adattati == [40]
        assert tabellino.malus_adattamento == pytest.approx(-1.0)

    def test_in_easy_il_titolare_fuori_posizione_non_vale_niente(self):
        formazione = formazione_343(titolari=(1, 10, 11, 12, 23, 20, 21, 13, 30, 33, 40))
        tabellino = calcola_squadra(
            formazione,
            voti_pieni(6.0),
            RUOLI,
            ParametriLega(),
            modalita=ModalitaSostituzioni.EASY,
        )
        assert (Reparto.ATTACCO, 40, 0.0) in tabellino.schierati
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
        # Il secondo portiere messo in difesa non e' un adattamento caro: e'
        # una casella che non si puo' riempire cosi'.
        formazione = Formazione(
            1, 1, "3-4-3", titolari=(1, 2, 11, 12, 23, 20, 21, 13, 30, 33, 31)
        )
        assert adattamenti(formazione, RUOLI) == []
