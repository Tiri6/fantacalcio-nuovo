from dataclasses import replace
from datetime import datetime

import pytest
from conftest import STAGIONE, costruisci_rosa

from fantacalcio.autenticazione import Ruolo, Utente
from fantacalcio.conformita import Gravita, Momento
from fantacalcio.mercato import (
    Finestra,
    PropostaScambio,
    SvincoloNonAmmesso,
    applica_scambio,
    calcola_dead_money,
    scambio_ratificabile,
    stato_mercato,
    svincola,
    valida_scambio,
    verifica_svincolo,
)
from fantacalcio.modelli import Contratto, Giocatore, Rosa, Squadra
from fantacalcio.regole import CalendarioStagione, ParametriLega

CALENDARIO = CalendarioStagione(
    data_draft_settembre=__import__("datetime").date(2026, 9, 15)
)


# Il V3 vieta di toccare la durata in uno scambio. I lodi Bono, Corti e
# Longoni regolavano **come** si prolunga: restano provati, ma solo nel mondo
# in cui un lodo li riaccende.
CON_PROLUNGAMENTI = ParametriLega(prolungamenti_ammessi=True)


def codici(violazioni) -> set[str]:
    return {v.codice for v in violazioni}


def due_rose(**extra):
    a = costruisci_rosa(squadra_id=1, nome="Tiri Team", **extra)
    b = costruisci_rosa(squadra_id=2, nome="Padel United")
    return a, b


class TestFinestreDiMercato:
    @pytest.mark.parametrize(
        "giornate,attese",
        [
            (0, (Finestra.SETTEMBRE,)),
            (8, (Finestra.SETTEMBRE,)),
            (9, (Finestra.SETTEMBRE, Finestra.INVERNALE)),
            (17, (Finestra.SETTEMBRE, Finestra.INVERNALE)),
            (18, (Finestra.SETTEMBRE, Finestra.INVERNALE, Finestra.PRIMAVERILE)),
        ],
    )
    def test_le_finestre_aprono_a_fine_gironcino(self, giornate, attese):
        assert stato_mercato(giornate, CALENDARIO).finestre_aperte == attese

    def test_dopo_la_primaverile_scatta_la_trade_deadline(self):
        assert not stato_mercato(18, CALENDARIO).trade_deadline_superata
        assert stato_mercato(19, CALENDARIO).trade_deadline_superata


class TestDeadMoney:
    """Art. 7 del V3: conta solo quel che resta **oltre** l'anno in corso.

    L'anno in corso si paga comunque — «i salari vengono pagati in anticipo,
    anche se il giocatore viene successivamente venduto» — quindi non entra
    nella buonuscita.
    """

    def test_l_esempio_del_regolamento(self):
        """Il caso scritto nel V3, parola per parola.

        «Ingaggio 10M, contratto di 5 anni, svincolo durante il primo anno;
        anni residui oltre quello in corso: 4; buonuscita: 4 x 10M / 2 = 20M.»
        """
        contratto = Contratto(giocatore_id=1, squadra_id=1, anni_residui=5)
        assert calcola_dead_money(contratto, 10_000_000) == 20_000_000

    def test_meta_degli_anni_oltre_quello_in_corso(self):
        contratto = Contratto(giocatore_id=1, squadra_id=1, anni_residui=3)
        # 4M x 2 anni oltre quello in corso = 8M, la meta' fa 4M.
        assert calcola_dead_money(contratto, 4_000_000) == 4_000_000

    def test_un_annuale_non_costa_buonuscita(self):
        """Chi scade a fine stagione non lascia niente dietro di se'."""
        contratto = Contratto(giocatore_id=1, squadra_id=1, anni_residui=1)
        assert calcola_dead_money(contratto, 5_000_000) == 0

    def test_quota_configurabile(self):
        contratto = Contratto(giocatore_id=1, squadra_id=1, anni_residui=3)
        parametri = ParametriLega(quota_dead_money=1.0)
        assert calcola_dead_money(contratto, 3_000_000, parametri) == 6_000_000


class TestChiPuoSvincolare:
    """Il permesso vive nel dominio: nascondere un bottone non e' un controllo."""

    PRESIDENTE = Utente(1, "marco", "Marco", Ruolo.PRESIDENTE, squadra_id=1)
    ALLENATORE = Utente(2, "luca", "Luca", Ruolo.FANTALLENATORE, squadra_id=1)

    def test_il_presidente_passa(self, rosa):
        verifica_svincolo(self.PRESIDENTE, rosa, rosa.contratti[0].giocatore_id)

    def test_il_fantallenatore_e_respinto_anche_sulla_sua(self, rosa):
        with pytest.raises(SvincoloNonAmmesso, match="presidente"):
            verifica_svincolo(self.ALLENATORE, rosa, rosa.contratti[0].giocatore_id)

    def test_un_giocatore_che_non_e_in_rosa_e_respinto(self, rosa):
        with pytest.raises(SvincoloNonAmmesso, match="non ha in rosa"):
            verifica_svincolo(self.PRESIDENTE, rosa, 999_999)


class TestSvincolo:
    def test_libera_subito_gli_anni(self, rosa):
        anni_prima = rosa.anni_impegnati
        bersaglio = rosa.contratti[-1]

        nuova, _ = svincola(rosa, bersaglio.giocatore_id, STAGIONE)

        assert nuova.dimensione == rosa.dimensione - 1
        assert nuova.anni_impegnati == anni_prima - bersaglio.anni_residui

    def test_genera_dead_money(self, rosa):
        bersaglio = rosa.contratti[-1]  # contratto da 2 anni, ingaggio 3M
        nuova, voce = svincola(rosa, bersaglio.giocatore_id, STAGIONE)

        # 3M x 1 anno oltre quello in corso = 3M, la meta' fa 1,5M.
        assert voce.importo == 1_500_000
        assert not voce.addebitato
        assert nuova.dead_money_totale == 1_500_000

    def test_il_taglio_in_riparazione_non_libera_niente_sul_cap(self, rosa):
        """Art. 7: l'ingaggio «continua a pesare fino al termine della stagione».

        Tagliare a stagione iniziata restituisce gli **anni**, non i soldi: il
        Salary Cap anzi peggiora, perche' alla buonuscita si somma l'ingaggio
        di chi se n'e' andato.
        """
        spesa_prima = rosa.spesa_salariale
        bersaglio = rosa.contratti[-1]

        nuova, voce = svincola(rosa, bersaglio.giocatore_id, STAGIONE)

        assert nuova.monte_ingaggi == rosa.monte_ingaggi - 3_000_000
        assert voce.ingaggio_a_carico == 3_000_000
        assert nuova.spesa_salariale == spesa_prima + voce.importo
        assert nuova.ingaggi_degli_svincolati == 3_000_000

    def test_l_esempio_del_regolamento_sul_cap(self):
        """«10M di ingaggio piu' 20M di buonuscita: 30M in totale.»"""
        squadra = Squadra(id=1, nome="Tiri Team", presidente="Mister")
        giocatore = Giocatore(
            id=1, nome="Origi", club="Milan", ruoli=("A",), ingaggio=10_000_000
        )
        contratto = Contratto(giocatore_id=1, squadra_id=1, anni_residui=5)
        rosa = Rosa(squadra=squadra, contratti=[contratto]).collega({1: giocatore})

        _, voce = svincola(rosa, 1, STAGIONE)

        assert voce.importo == 20_000_000
        assert voce.ingaggio_a_carico == 10_000_000
        assert voce.totale == 30_000_000

    def test_prima_dell_asta_lo_svincolo_non_tocca_il_cap(self, rosa):
        """«Gli svincoli effettuati prima dell'asta di Settembre non hanno
        alcun effetto sul Salary Cap»: ne' buonuscita ne' ingaggio a carico."""
        bersaglio = rosa.contratti[-1]

        nuova, voce = svincola(
            rosa, bersaglio.giocatore_id, STAGIONE, momento=Momento.ASTA_SETTEMBRE
        )

        assert voce is None
        assert nuova.dead_money == []
        assert nuova.spesa_salariale == rosa.spesa_salariale - 3_000_000

    def test_prima_dell_asta_gli_anni_si_liberano_lo_stesso(self, rosa):
        """L'effetto sul monte anni non e' legato a nessuna sessione."""
        anni_prima = rosa.anni_impegnati
        bersaglio = rosa.contratti[-1]

        nuova, _ = svincola(
            rosa, bersaglio.giocatore_id, STAGIONE, momento=Momento.ASTA_SETTEMBRE
        )

        assert nuova.anni_impegnati == anni_prima - bersaglio.anni_residui

    def test_una_voce_addebitata_non_pesa_piu(self, rosa):
        """Dalla stagione successiva non resta niente, ne' debito ne' ingaggio."""
        bersaglio = rosa.contratti[-1]
        nuova, _ = svincola(rosa, bersaglio.giocatore_id, STAGIONE)
        nuova.dead_money = [replace(v, addebitato=True) for v in nuova.dead_money]
        assert nuova.dead_money_totale == 0
        assert nuova.ingaggi_degli_svincolati == 0
        assert nuova.spesa_salariale == nuova.monte_ingaggi

    def test_la_rosa_originale_non_viene_toccata(self, rosa):
        prima = rosa.dimensione
        svincola(rosa, rosa.contratti[-1].giocatore_id, STAGIONE)
        assert rosa.dimensione == prima
        assert rosa.dead_money == []

    def test_giocatore_non_in_rosa(self, rosa):
        with pytest.raises(ValueError, match="non ha in rosa"):
            svincola(rosa, 999_999, STAGIONE)


class TestApplicaScambio:
    def test_i_giocatori_cambiano_squadra(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1000,), da_squadra_b=(2000,))

        nuova_a, nuova_b = applica_scambio(a, b, proposta, STAGIONE)

        assert nuova_a.contratto_di(2000) is not None
        assert nuova_a.contratto_di(1000) is None
        assert nuova_b.contratto_di(1000) is not None
        assert nuova_a.dimensione == a.dimensione
        assert nuova_b.dimensione == b.dimensione

    def test_il_contratto_viaggia_con_la_durata_residua(self):
        a, b = due_rose()
        durata = a.contratto_di(1029).anni_residui
        proposta = PropostaScambio(da_squadra_a=(1029,), da_squadra_b=(2029,))

        _, nuova_b = applica_scambio(a, b, proposta, STAGIONE)

        assert nuova_b.contratto_di(1029).anni_residui == durata
        assert nuova_b.contratto_di(1029).squadra_id == 2

    def test_il_prolungamento_marca_il_contratto(self):
        a, b = due_rose()
        proposta = PropostaScambio(
            da_squadra_a=(1029,), da_squadra_b=(2029,), prolungamenti={1029: 4}
        )

        _, nuova_b = applica_scambio(a, b, proposta, STAGIONE)
        contratto = nuova_b.contratto_di(1029)

        assert contratto.anni_residui == 4
        assert contratto.prolungato
        assert contratto.stagione_prolungamento == STAGIONE


class TestValidaScambio:
    def test_scambio_semplice_valido(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1029,), da_squadra_b=(2029,))
        assert valida_scambio(a, b, proposta, STAGIONE) == []

    def test_scambio_vuoto(self):
        a, b = due_rose()
        violazioni = valida_scambio(a, b, PropostaScambio(), STAGIONE)
        assert codici(violazioni) == {"scambio_vuoto"}

    def test_giocatore_non_posseduto(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(2000,))
        assert codici(valida_scambio(a, b, proposta, STAGIONE)) == {"scambio_impossibile"}

    def test_il_v3_vieta_di_cambiare_la_durata(self):
        """«Il contratto si trasferisce con ingaggio e anni residui invariati»."""
        a, b = due_rose()
        for nuova_durata in (1, 4):
            proposta = PropostaScambio(
                da_squadra_a=(1029,), prolungamenti={1029: nuova_durata}
            )
            violazioni = valida_scambio(a, b, proposta, STAGIONE)
            assert "durata_invariata" in codici(violazioni)
            assert all(v.bloccante for v in violazioni)

    def test_la_stessa_durata_non_e_un_cambio(self):
        """Riscrivere il numero che c'e' gia' non viola niente."""
        a, b = due_rose()
        attuale = a.contratto_di(1029).anni_residui
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: attuale})
        assert valida_scambio(a, b, proposta, STAGIONE) == []

    def test_uno_scambio_senza_tocchi_alla_durata_passa(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1029,), da_squadra_b=(2029,))
        assert valida_scambio(a, b, proposta, STAGIONE) == []

    def test_col_divieto_i_lodi_non_si_contano_nemmeno(self):
        """Se cambiare durata non si puo', non serve dire quante volte."""
        a, b = due_rose()
        a = a.con_contratto(replace(a.contratto_di(1029), prolungato=True))
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 4})
        trovati = codici(valida_scambio(a, b, proposta, STAGIONE))
        assert trovati == {"durata_invariata"}

    def test_lodo_bono_vieta_di_ridurre_la_durata(self):
        """Vale solo se un lodo riaccende i prolungamenti (`prolungamenti_ammessi`)."""
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 1})
        violazioni = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)
        assert "lodo_bono" in codici(violazioni)

    def test_lodo_corti_un_solo_prolungamento_per_giocatore(self):
        a, b = due_rose()
        gia_prolungato = replace(
            a.contratto_di(1029), prolungato=True, stagione_prolungamento="2025/26"
        )
        a = a.con_contratto(gia_prolungato)

        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 4})
        trovate = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)
        assert "lodo_corti" in codici(trovate)

    def test_lodo_corti_non_impedisce_lo_scambio_senza_prolungamento(self):
        a, b = due_rose()
        a = a.con_contratto(replace(a.contratto_di(1029), prolungato=True))
        proposta = PropostaScambio(da_squadra_a=(1029,))
        assert valida_scambio(a, b, proposta, STAGIONE) == []

    def test_lodo_longoni_massimo_due_prolungamenti_a_stagione(self):
        a, b = due_rose()
        # B ha gia' prolungato due giocatori in questa stagione.
        for gid in (2000, 2001):
            b = b.con_contratto(
                replace(
                    b.contratto_di(gid),
                    prolungato=True,
                    stagione_prolungamento=STAGIONE,
                )
            )

        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 4})
        violazioni = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)

        assert "lodo_longoni" in codici(violazioni)
        assert "Padel United" in next(
            v.messaggio for v in violazioni if v.codice == "lodo_longoni"
        )

    def test_lodo_longoni_conta_solo_la_stagione_corrente(self):
        a, b = due_rose()
        for gid in (2000, 2001):
            b = b.con_contratto(
                replace(
                    b.contratto_di(gid),
                    prolungato=True,
                    stagione_prolungamento="2025/26",
                )
            )
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 4})
        trovate = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)
        assert "lodo_longoni" not in codici(trovate)

    def test_durata_oltre_cinque_anni(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1029: 6})
        trovate = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)
        assert "durata_contratto" in codici(trovate)

    def test_prolungamento_di_un_giocatore_estraneo(self):
        a, b = due_rose()
        proposta = PropostaScambio(da_squadra_a=(1029,), prolungamenti={1028: 4})
        assert "prolungamento_estraneo" in codici(
            valida_scambio(a, b, proposta, STAGIONE)
        )

    def test_monte_anni_esaurito_blocca(self):
        """A ha gia' 66 anni impegnati: non puo' assorbire un contratto piu' lungo."""
        a, b = due_rose(annuali=12, anni_altri=3)
        assert a.anni_impegnati == 66

        proposta = PropostaScambio(
            da_squadra_a=(1029,), da_squadra_b=(2029,), prolungamenti={2029: 5}
        )
        violazioni = valida_scambio(a, b, proposta, STAGIONE, CON_PROLUNGAMENTI)

        assert "monte_anni" in codici(violazioni)
        assert "Tiri Team" in next(
            v.messaggio for v in violazioni if v.codice == "monte_anni"
        )

    def test_sforamento_del_cap_e_solo_un_avviso(self):
        """Articolo 8b: in stagione lo scambio puo' far sforare il Salary Cap."""
        a = costruisci_rosa(squadra_id=1, nome="Tiri Team", ingaggio=3_300_000)  # 99M
        b = costruisci_rosa(squadra_id=2, nome="Padel United", ingaggio=2_000_000)
        # B mette sul piatto un giocatore da 5M: A passerebbe a 100,7M.
        b._indice[2029] = replace(b._indice[2029], ingaggio=5_000_000)

        proposta = PropostaScambio(da_squadra_a=(1029,), da_squadra_b=(2029,))
        violazioni = valida_scambio(a, b, proposta, STAGIONE)

        assert codici(violazioni) == {"salary_cap"}
        assert all(v.gravita is Gravita.AVVISO for v in violazioni)
        assert "Tiri Team" in violazioni[0].messaggio


class TestRatifica:
    def test_ventiquattro_ore_prima_e_valido(self):
        inizio = datetime(2026, 10, 4, 15, 0)
        assert scambio_ratificabile(datetime(2026, 10, 3, 15, 0), inizio)
        assert scambio_ratificabile(datetime(2026, 10, 2, 9, 0), inizio)

    def test_oltre_il_termine_non_vale_per_la_giornata_imminente(self):
        inizio = datetime(2026, 10, 4, 15, 0)
        assert not scambio_ratificabile(datetime(2026, 10, 3, 15, 1), inizio)
        assert not scambio_ratificabile(datetime(2026, 10, 4, 14, 0), inizio)
