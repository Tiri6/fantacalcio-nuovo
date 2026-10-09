"""Portiere d'emergenza: il Lodo Messina dell'articolo 8.

Il caso che il regolamento descrive e' raro ma non teorico: tre portieri
infortunati insieme capita, e senza questa regola la squadra scenderebbe in
campo senza portiere. Qui si prova che si apre **solo** in quel caso, che si
chiude da sola quando non serve piu', e che il punto di malus c'e'.
"""

from __future__ import annotations

import pytest
from conftest import costruisci_rosa, giocatore

from fantacalcio.emergenza import (
    EmergenzaNonAmmessa,
    malus_emergenza,
    stato_emergenza,
    verifica_attivazione,
    verifica_revoca,
)
from fantacalcio.formazioni import Formazione, Voto, calcola_squadra
from fantacalcio.regole import ParametriLega

# Uno svincolato qualsiasi, portiere, fuori da ogni rosa.
LIBERO = giocatore(9001, ruoli=("Por",))
SVINCOLATI = {LIBERO.id}


def tutti_i_portieri(rosa) -> set[int]:
    return {g.id for g in rosa.portieri}


class TestQuandoSiApre:
    def test_con_tutti_i_portieri_fuori_e_ammessa(self):
        rosa = costruisci_rosa()
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        assert stato.ammessa
        assert len(stato.indisponibili) == 3

    def test_con_un_portiere_disponibile_non_e_ammessa(self):
        rosa = costruisci_rosa()
        fuori = sorted(tutti_i_portieri(rosa))[:2]
        stato = stato_emergenza(rosa, indisponibili=fuori)
        assert not stato.ammessa
        with pytest.raises(EmergenzaNonAmmessa, match="indisponibili tutti"):
            verifica_attivazione(stato, LIBERO, SVINCOLATI)

    def test_senza_indisponibili_non_e_ammessa(self):
        stato = stato_emergenza(costruisci_rosa())
        assert not stato.ammessa
        assert not stato.attiva

    def test_una_rosa_senza_portieri_non_e_in_emergenza(self):
        """Non e' un'emergenza: e' una rosa da completare (art. 2)."""
        rosa = costruisci_rosa(portieri=0)
        stato = stato_emergenza(rosa)
        assert not stato.ammessa
        assert "rosa da completare" in stato.motivo
        with pytest.raises(EmergenzaNonAmmessa, match="nessun portiere"):
            verifica_attivazione(stato, LIBERO, SVINCOLATI)


class TestChiPuoEssereScelto:
    def test_uno_svincolato_portiere_va_bene(self):
        rosa = costruisci_rosa()
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        verifica_attivazione(stato, LIBERO, SVINCOLATI)  # non solleva

    def test_un_movimento_no(self):
        rosa = costruisci_rosa()
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        attaccante = giocatore(9002, ruoli=("Pc",))
        with pytest.raises(EmergenzaNonAmmessa, match="non e' un portiere"):
            verifica_attivazione(stato, attaccante, {attaccante.id})

    def test_un_portiere_sotto_contratto_altrove_no(self):
        """Per averlo serve uno scambio: l'emergenza pesca fra i liberi."""
        rosa = costruisci_rosa()
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        tesserato = giocatore(9003, ruoli=("Por",))
        with pytest.raises(EmergenzaNonAmmessa, match="non e' svincolato"):
            verifica_attivazione(stato, tesserato, SVINCOLATI)

    def test_un_proprio_portiere_no(self):
        rosa = costruisci_rosa()
        suo = rosa.portieri[0]
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        with pytest.raises(EmergenzaNonAmmessa, match="gia' un portiere di questa"):
            verifica_attivazione(stato, suo, SVINCOLATI | {suo.id})


class TestLaSceltaEUnica:
    def test_con_uno_in_carica_non_se_ne_attiva_un_altro(self):
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        stato = stato_emergenza(
            rosa, indisponibili=tutti_i_portieri(rosa), in_carica_nome=LIBERO.nome
        )
        assert stato.attiva
        altro = giocatore(9004, ruoli=("Por",))
        with pytest.raises(EmergenzaNonAmmessa, match="la scelta e' unica"):
            verifica_attivazione(stato, altro, {altro.id})


class TestQuandoSiChiude:
    def test_un_portiere_che_torna_fa_decadere_l_emergenza(self):
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        fuori = sorted(tutti_i_portieri(rosa))[:2]
        stato = stato_emergenza(rosa, indisponibili=fuori, in_carica_nome=LIBERO.nome)
        assert stato.va_revocata
        assert "va revocato" in stato.motivo

    def test_finche_sono_tutti_fuori_non_va_revocata(self):
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        assert stato.attiva
        assert not stato.va_revocata

    def test_si_puo_revocare_anche_senza_obbligo(self):
        """Rinunciarci e' una facolta': non si viola niente a tenerne tre."""
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        stato = stato_emergenza(rosa, indisponibili=tutti_i_portieri(rosa))
        verifica_revoca(stato)  # non solleva

    def test_senza_nessuno_in_carica_non_c_e_niente_da_revocare(self):
        stato = stato_emergenza(costruisci_rosa())
        with pytest.raises(EmergenzaNonAmmessa, match="nessun portiere d'emergenza"):
            verifica_revoca(stato)


class TestNonPesaSuiConti:
    """Non firma contratto: rosa, monte anni e Salary Cap non si muovono."""

    def test_i_conti_della_rosa_non_cambiano(self):
        rosa = costruisci_rosa()
        prima = (rosa.dimensione, rosa.anni_impegnati, rosa.spesa_salariale)
        rosa.portiere_emergenza_id = LIBERO.id
        assert (rosa.dimensione, rosa.anni_impegnati, rosa.spesa_salariale) == prima

    def test_la_conformita_non_lo_vede(self):
        from datetime import date

        from fantacalcio.conformita import verifica_rosa

        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        stato = verifica_rosa(rosa, date(2026, 9, 15))
        assert stato.conforme
        assert stato.dimensione == 30


class TestIlMalusDelLodoMessinaBis:
    """Vota con malus di -1, «come un giocatore schierato fuori ruolo»."""

    def test_il_malus_e_quello_del_fuori_ruolo(self):
        parametri = ParametriLega()
        assert malus_emergenza(parametri) == abs(parametri.malus_adattamento)

    def _formazione(self, portiere: int, emergenza: int | None) -> Formazione:
        # 3-4-3: portiere, tre difensori, quattro di centrocampo, tre davanti.
        difensori = (201, 202, 203)
        centrocampo = (301, 302, 303, 304)
        attacco = (401, 402, 403)
        return Formazione(
            squadra_id=1,
            giornata=1,
            modulo="3-4-3",
            titolari=(portiere, *difensori, *centrocampo, *attacco),
            portiere_emergenza=emergenza,
        )

    def _ruoli(self, portiere: int) -> dict[int, tuple[str, ...]]:
        ruoli = {portiere: ("Por",)}
        ruoli.update(dict.fromkeys((201, 202, 203), ("Dc",)))
        ruoli.update(dict.fromkeys((301, 302, 303, 304), ("C",)))
        ruoli.update(dict.fromkeys((401, 402, 403), ("A",)))
        return ruoli

    def _voti(self, portiere: int) -> dict[int, Voto]:
        tutti = [portiere, 201, 202, 203, 301, 302, 303, 304, 401, 402, 403]
        return {g: Voto(giocatore_id=g, giornata=1, voto=6.0) for g in tutti}

    def test_il_portiere_d_emergenza_prende_un_punto_in_meno(self):
        parametri = ParametriLega(modificatore_difesa=False)
        normale = calcola_squadra(
            self._formazione(101, None), self._voti(101), self._ruoli(101), parametri
        )
        emergenza = calcola_squadra(
            self._formazione(101, 101), self._voti(101), self._ruoli(101), parametri
        )
        assert emergenza.totale == normale.totale - 1.0
        assert emergenza.malus_emergenza == -1.0

    def test_il_malus_e_dichiarato_a_parte_da_quello_di_adattamento(self):
        """Il portiere e' in porta: chiamarlo «fuori ruolo» sarebbe falso."""
        parametri = ParametriLega(modificatore_difesa=False)
        tabellino = calcola_squadra(
            self._formazione(101, 101), self._voti(101), self._ruoli(101), parametri
        )
        assert tabellino.malus_adattamento == 0.0
        assert tabellino.adattati == []
        assert tabellino.malus_emergenza == -1.0

    def test_senza_portiere_d_emergenza_nessun_malus(self):
        parametri = ParametriLega(modificatore_difesa=False)
        tabellino = calcola_squadra(
            self._formazione(101, None), self._voti(101), self._ruoli(101), parametri
        )
        assert tabellino.malus_emergenza == 0.0


class TestIMessaggi:
    """Il motivo lo legge una persona: deve essere italiano, non un template."""

    def test_al_plurale_concorda(self):
        rosa = costruisci_rosa()
        stato = stato_emergenza(rosa)
        assert "sono ancora disponibili" in stato.motivo

    def test_al_singolare_concorda(self):
        rosa = costruisci_rosa()
        fuori = sorted(tutti_i_portieri(rosa))[:2]
        stato = stato_emergenza(rosa, indisponibili=fuori)
        assert "e ancora disponibile" in stato.motivo

    def test_la_revoca_al_singolare_concorda(self):
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        fuori = sorted(tutti_i_portieri(rosa))[:2]
        stato = stato_emergenza(rosa, indisponibili=fuori, in_carica_nome=LIBERO.nome)
        assert "e di nuovo disponibile" in stato.motivo

    def test_la_revoca_al_plurale_concorda(self):
        rosa = costruisci_rosa()
        rosa.portiere_emergenza_id = LIBERO.id
        fuori = sorted(tutti_i_portieri(rosa))[:1]
        stato = stato_emergenza(rosa, indisponibili=fuori, in_carica_nome=LIBERO.nome)
        assert "sono di nuovo disponibili" in stato.motivo
