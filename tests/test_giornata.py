"""Leggere i voti e calcolare una giornata.

E' il pezzo che decide chi vince, quindi qui si guarda soprattutto a cosa
succede quando i dati sono imperfetti: un nome che non si abbina, una squadra
senza formazione, un voto vuoto che non e' uno zero.
"""

import pytest

from fantacalcio.formazioni import Formazione, Voto
from fantacalcio.giornata import (
    MODELLO_CSV_VOTI,
    VotiNonLeggibili,
    calcola_giornata,
    leggi_voti,
)
from fantacalcio.importazione import normalizza_nome_giocatore
from fantacalcio.regole import ParametriLega

RUOLI = {
    1: ("Por",),
    10: ("Dc",),
    11: ("Dc",),
    12: ("Dc",),
    20: ("M", "C"),
    21: ("C",),
    23: ("E",),
    24: ("M",),
    30: ("A", "Pc"),
    31: ("Pc",),
    32: ("A",),
    2: ("Por",),
    13: ("Dd", "E"),
}
NOMI = {
    "Svilar": 1,
    "Mancini": 10,
    "Ndicka": 11,
    "Hermoso": 12,
    "Kone": 20,
    "Cristante": 21,
    "Angelino": 23,
    "Pisilli": 24,
    "Dybala": 30,
    "Dovbyk": 31,
    "Soule": 32,
}
PER_NOME = {normalizza_nome_giocatore(n): i for n, i in NOMI.items()}


def formazione(squadra_id: int) -> Formazione:
    return Formazione(
        squadra_id=squadra_id,
        giornata=1,
        modulo="3-4-3",
        titolari=(1, 10, 11, 12, 20, 21, 23, 24, 30, 31, 32),
        panchina=(2, 13),
    )


class TestLetturaVoti:
    def test_legge_il_modello(self):
        # Il modello nomina anche Barella, che in questa rosa non c'e': i due
        # che ci sono si leggono, il terzo finisce fra i non abbinati.
        esito = leggi_voti(MODELLO_CSV_VOTI, giornata=1, per_nome=PER_NOME)
        assert esito.quanti == 2
        assert esito.non_abbinati == ["Barella"]
        per_id = {v.giocatore_id: v for v in esito.voti}
        assert per_id[1].voto == pytest.approx(6.5)
        assert per_id[1].gol_subiti == 1
        assert per_id[30].gol == 1 and per_id[30].assist == 1

    def test_un_voto_lasciato_in_bianco(self):
        esito = leggi_voti(
            "giocatore;voto\nSvilar;\nDybala;7\n", giornata=1, per_nome=PER_NOME
        )
        per_id = {v.giocatore_id: v for v in esito.voti}
        assert per_id[1].voto is None
        assert not per_id[1].ha_giocato
        assert esito.senza_voto == 1

    def test_la_virgola_decimale_va_bene(self):
        esito = leggi_voti("giocatore;voto\nDybala;7,5\n", giornata=1, per_nome=PER_NOME)
        assert esito.voti[0].voto == pytest.approx(7.5)

    def test_le_colonne_si_riconoscono_dai_sinonimi(self):
        esito = leggi_voti(
            "Calciatore\tRating\tReti\tAssistenze\tGialli\nDybala\t7\t1\t1\t1\n",
            giornata=1,
            per_nome=PER_NOME,
        )
        voto = esito.voti[0]
        assert (voto.voto, voto.gol, voto.assist, voto.ammonizioni) == (7.0, 1, 1, 1)

    def test_l_id_del_listone_batte_il_nome(self):
        # Con l'id non serve indovinare la grafia del nome.
        esito = leggi_voti(
            "id;giocatore;voto\n5841;Scritto Male;6.5\n",
            giornata=1,
            per_nome=PER_NOME,
            per_id_ufficiale={5841: 1},
        )
        assert esito.voti[0].giocatore_id == 1

    def test_chi_non_si_abbina_si_dichiara(self):
        esito = leggi_voti(
            "giocatore;voto\nDybala;7\nSconosciuto;6\n", giornata=1, per_nome=PER_NOME
        )
        assert esito.quanti == 1
        assert esito.non_abbinati == ["Sconosciuto"]

    def test_file_vuoto(self):
        with pytest.raises(VotiNonLeggibili, match="vuoto"):
            leggi_voti("", giornata=1, per_nome=PER_NOME)

    def test_colonne_sbagliate(self):
        with pytest.raises(VotiNonLeggibili, match="Intestazioni lette"):
            leggi_voti("pippo;pluto\n1;2\n", giornata=1, per_nome=PER_NOME)

    def test_nessuno_abbinato(self):
        with pytest.raises(VotiNonLeggibili, match="Nessuna riga abbinata"):
            leggi_voti("giocatore;voto\nTizio;6\n", giornata=1, per_nome=PER_NOME)

    def test_imbattuto_si_scrive_in_tanti_modi(self):
        esito = leggi_voti(
            "giocatore;voto;imbattuto\nSvilar;6.5;si\n", giornata=1, per_nome=PER_NOME
        )
        assert esito.voti[0].imbattuto


class TestCalcoloGiornata:
    PARTITE = [{"id": 100, "casa_id": 1, "trasferta_id": 2}]

    def voti(self, valore=6.0):
        return {g: Voto(g, 1, voto=valore) for g in RUOLI}

    def test_calcola_le_partite_con_le_formazioni(self):
        esito = calcola_giornata(
            1,
            self.PARTITE,
            {1: formazione(1), 2: formazione(2)},
            self.voti(),
            RUOLI,
            ParametriLega(),
        )
        assert esito.calcolate == 1
        risultato = esito.risultati[0]
        assert risultato.esito.punteggio == "1-1"

    def test_una_squadra_senza_formazione_salta_solo_la_sua_partita(self):
        esito = calcola_giornata(
            1, self.PARTITE, {1: formazione(1)}, self.voti(), RUOLI, ParametriLega()
        )
        assert esito.calcolate == 0
        assert "senza formazione" in esito.risultati[0].saltata

    def test_senza_voti_non_si_calcola_niente(self):
        esito = calcola_giornata(
            1,
            self.PARTITE,
            {1: formazione(1), 2: formazione(2)},
            {},
            RUOLI,
            ParametriLega(),
        )
        assert esito.risultati == []
        assert any("prima si caricano i voti" in a for a in esito.avvisi)

    def test_le_altre_partite_si_calcolano_lo_stesso(self):
        partite = [
            {"id": 100, "casa_id": 1, "trasferta_id": 2},
            {"id": 101, "casa_id": 3, "trasferta_id": 4},
        ]
        formazioni = {1: formazione(1), 2: formazione(2), 3: formazione(3)}
        esito = calcola_giornata(
            1, partite, formazioni, self.voti(), RUOLI, ParametriLega()
        )
        assert esito.calcolate == 1
        assert esito.risultati[1].saltata

    def test_il_risultato_cambia_coi_voti(self):
        voti = self.voti(6.0)
        # La squadra di casa schiera gli stessi giocatori: per differenziare
        # si guarda che punteggi diversi diano gol diversi.
        alti = {g: Voto(g, 1, voto=8.0) for g in RUOLI}
        casa = calcola_giornata(
            1,
            self.PARTITE,
            {1: formazione(1), 2: formazione(2)},
            alti,
            RUOLI,
            ParametriLega(),
        )
        bassa = calcola_giornata(
            1,
            self.PARTITE,
            {1: formazione(1), 2: formazione(2)},
            voti,
            RUOLI,
            ParametriLega(),
        )
        assert casa.risultati[0].esito.casa.gol > bassa.risultati[0].esito.casa.gol
