"""Media voto e percentuale di titolarita': calcolate dal server, mai dal browser.

Tutti i dati sono finti. Il punto delicato e' il denominatore: contano solo le
giornate in cui il giocatore ha preso voto, perche' un senza voto non e' una
brutta partita ma una partita non giocata.
"""

from fantacalcio.data import (
    carica_titolari_per_giornata,
    carica_voti_stagione,
    salva_formazione,
    salva_voti,
)
from fantacalcio.formazioni import Formazione, Voto
from fantacalcio.leghe import Bonus
from fantacalcio.statistiche import statistiche_stagione


def v(giocatore, giornata, voto, **altro):
    return Voto(giocatore_id=giocatore, giornata=giornata, voto=voto, **altro)


class TestLaMedia:
    def test_e_la_media_dei_voti_presi(self):
        s = statistiche_stagione([v(1, 1, 6.0), v(1, 2, 7.0), v(1, 3, 6.5)], {})
        assert s[1].media == 6.5
        assert s[1].presenze == 3

    def test_il_senza_voto_non_abbassa_la_media(self):
        s = statistiche_stagione([v(1, 1, 7.0), v(1, 2, None)], {})
        assert s[1].media == 7.0
        assert s[1].presenze == 1

    def test_chi_non_ha_mai_preso_voto_non_compare(self):
        # Alla pagina manca la voce: mostra il trattino, non uno zero.
        assert statistiche_stagione([v(1, 1, None)], {}) == {}
        assert statistiche_stagione([], {}) == {}

    def test_si_arrotonda_a_due_decimali(self):
        s = statistiche_stagione([v(1, 1, 6.0), v(1, 2, 6.0), v(1, 3, 7.0)], {})
        assert s[1].media == 6.33

    def test_una_riga_ripetuta_non_conta_due_volte(self):
        s = statistiche_stagione([v(1, 1, 8.0), v(1, 1, 8.0), v(1, 2, 6.0)], {})
        assert s[1].presenze == 2
        assert s[1].media == 7.0


class TestLaFantamedia:
    """FM: voto piu' bonus e malus, accanto alla MV che resta sul voto puro."""

    def test_mv_e_fm_stanno_insieme(self):
        gol = v(1, 1, 6.0, gol=1)
        s = statistiche_stagione([gol, v(1, 2, 6.0)], {}, bonus=Bonus(gol_segnato=3.0))
        assert s[1].media == 6.0
        assert s[1].fantamedia == 7.5

    def test_senza_bonus_particolari_vale_la_lega_di_partenza(self):
        s = statistiche_stagione([v(1, 1, 6.0, ammonizioni=1)], {})
        assert s[1].fantamedia == 5.5

    def test_il_senza_voto_non_entra_nemmeno_nella_fm(self):
        s = statistiche_stagione([v(1, 1, 7.0), v(1, 2, None, gol=2)], {})
        assert s[1].fantamedia == 7.0


class TestLaTitolarita:
    def test_e_la_quota_di_giornate_con_voto_da_titolare(self):
        voti = [v(1, 1, 6.0), v(1, 2, 6.0), v(1, 3, 6.0), v(1, 4, 6.0)]
        titolari = {1: {1}, 2: {1}, 3: set(), 4: {1}}
        s = statistiche_stagione(voti, titolari)
        assert s[1].da_titolare == 3
        assert s[1].percentuale_titolare == 75

    def test_la_giornata_senza_voto_non_entra_nel_denominatore(self):
        # Titolare ma senza voto: non e' una giornata «giocata».
        voti = [v(1, 1, 6.0), v(1, 2, None)]
        s = statistiche_stagione(voti, {1: {1}, 2: {1}})
        assert s[1].percentuale_titolare == 100

    def test_chi_entra_dalla_panchina_ha_voto_ma_non_era_titolare(self):
        s = statistiche_stagione([v(1, 1, 6.0)], {1: {2, 3}})
        assert s[1].percentuale_titolare == 0

    def test_senza_formazioni_salvate_e_zero_non_assente(self):
        # Ha giocato davvero: lo zero e' un dato, il trattino sarebbe falso.
        assert statistiche_stagione([v(1, 1, 6.0)], {})[1].percentuale_titolare == 0


class TestDalDatabase:
    def test_voti_e_formazioni_si_rileggono(self, archivio_demo):
        ids = list(archivio_demo.tabella("giocatori")["id"][:2])
        a, b = int(ids[0]), int(ids[1])
        salva_voti(archivio_demo, [v(a, 1, 6.5), v(a, 2, 7.5), v(b, 2, 5.5)])
        salva_formazione(
            archivio_demo,
            Formazione(squadra_id=1, giornata=1, modulo="3-4-3", titolari=(a,)),
        )
        salva_formazione(
            archivio_demo,
            Formazione(
                squadra_id=1,
                giornata=2,
                modulo="3-4-3",
                titolari=(b,),
                competizione="COPPA",
            ),
        )

        voti = carica_voti_stagione(archivio_demo)
        titolari = carica_titolari_per_giornata(archivio_demo)

        assert len(voti) == 3
        # La coppa non e' campionato: la sua formazione non conta.
        assert titolari == {1: {a}}
        s = statistiche_stagione(voti, titolari)
        assert s[a].media == 7.0
        assert s[a].percentuale_titolare == 50
        assert s[b].percentuale_titolare == 0
