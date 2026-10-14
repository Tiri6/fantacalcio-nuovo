"""Il tabellino di giornata esportato da Leghe, e il nostro conto accanto.

Il file e' la giornata **gia' giocata e gia' calcolata dalla piattaforma**:
formazioni, chi e' entrato, voti, bonus, modificatore, totali, risultato. Due
cose diverse si provano qui:

1. che lo sappiamo **leggere** — compreso quello che sta nel colore delle
   celle, ammonizioni e panchinari entrati, che nessuna colonna riporta;
2. quanto il nostro calcolo si avvicina al loro. E' la domanda che decide se
   le formazioni possono passare sul sito: finche' i due conti non
   coincidono, calcolare in casa vorrebbe dire dire un risultato diverso da
   quello della piattaforma su cui la lega gioca davvero.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fantacalcio.formazioni import (
    Formazione,
    calcola_squadra,
    disponi_in_caselle,
    punteggio_giocatore,
)
from fantacalcio.giornata import (
    leggi_formazioni_leghe,
    voto_dal_tabellino,
)
from fantacalcio.leghe import FASCE_DIFESA, Bonus, ModalitaSostituzioni
from fantacalcio.regole import ParametriLega

FILE = Path(__file__).parent / "dati" / "formazioni_leghe_g1.xlsx"


@pytest.fixture(scope="module")
def tabellino():
    return leggi_formazioni_leghe(FILE.read_bytes())


def trova(tabellino, nome: str):
    for squadra in tabellino.squadre:
        for riga in squadra.titolari + squadra.panchina:
            if riga.nome == nome:
                return riga
    raise AssertionError(f"{nome} non e' nel file")


class TestLeggereIlTabellino:
    def test_legge_le_cinque_partite_della_giornata(self, tabellino):
        assert tabellino.giornata == 1
        assert len(tabellino.partite) == 5
        assert tabellino.leggibile

    def test_porta_risultato_totali_e_modificatore(self, tabellino):
        prima = tabellino.partite[0]

        assert (prima.casa.nome, prima.trasferta.nome) == (
            "MaGuardaCheRoba",
            "Tiri Team",
        )
        assert (prima.gol_casa, prima.gol_trasferta) == (2, 2)
        assert (prima.casa.totale, prima.trasferta.totale) == (73.5, 72)
        assert prima.casa.modificatore_difesa == 1.0
        assert prima.casa.modulo == "3-4-2-1"

    def test_undici_titolari_e_la_panchina(self, tabellino):
        for squadra in tabellino.squadre:
            assert len(squadra.titolari) == 11, squadra.nome
            assert squadra.panchina, squadra.nome

    def test_il_modificatore_che_manca_vale_zero(self, tabellino):
        """Quando non c'e' bonus la piattaforma non scrive proprio la riga:
        leggerne l'assenza come «non letto» lascerebbe un totale che non
        torna."""
        skoreggina = next(s for s in tabellino.squadre if s.nome == "SkoReggina")

        assert skoreggina.modificatore_difesa == 0.0

    def test_sv_non_e_zero(self, tabellino):
        """Senza voto si viene sostituiti; con zero si resta in campo a zero."""
        bastoni = trova(tabellino, "Bastoni")

        assert bastoni.voto is None
        assert not bastoni.ha_giocato

    def test_l_ammonizione_sta_nel_colore_della_cella(self, tabellino):
        """Nessuna colonna la riporta: il fantavoto la contiene gia', ma chi
        ricalcolasse dalle colonne regalerebbe mezzo punto a ogni ammonito."""
        kone = trova(tabellino, "Konè M.")

        assert kone.ammonito
        assert not kone.espulso
        assert (kone.voto, kone.fantavoto) == (6.0, 5.5)
        assert all(v == 0 for v in kone.bonus.values())

    def test_l_espulsione_e_il_colore_rosso(self, tabellino):
        malen = trova(tabellino, "Malen")

        assert malen.espulso
        assert (malen.voto, malen.fantavoto) == (4.5, 3.5)

    def test_i_bonus_sono_punti_non_conteggi(self, tabellino):
        """«G 3» vuol dire tre punti di gol, cioe' **un** gol con la tabella
        di questa lega."""
        ekkelenkamp = trova(tabellino, "Ekkelenkamp")

        assert ekkelenkamp.bonus["G"] == 3.0
        assert ekkelenkamp.fantavoto == 10.0
        assert voto_dal_tabellino(ekkelenkamp, 1, 1).gol == 1

    def test_si_sa_chi_e_entrato_dalla_panchina(self, tabellino):
        """Il nome in grigio e' di chi non e' entrato nel punteggio: senza
        quel dettaglio, di una panchina da dodici non si saprebbe chi ha
        giocato."""
        tiri_team = next(s for s in tabellino.squadre if s.nome == "Tiri Team")

        entrati = [g.nome for g in tiri_team.entrati]

        assert sorted(entrati) == ["Lontani", "N'Dicka"]
        # Due titolari senza voto, due che entrano: tornano.
        assert sum(1 for g in tiri_team.titolari if not g.ha_giocato) == 2

    def test_un_file_che_non_e_il_tabellino_lo_dice(self):
        esito = leggi_formazioni_leghe(b"giornata;casa;trasferta\n1;A;B\n")

        assert esito.partite == []
        assert not esito.leggibile
        assert esito.problemi


class TestIlNostroContoAccantoAlLoro:
    """Dove il nostro calcolo coincide con la piattaforma, e dove no.

    Serve a sapere **di quanto** siamo lontani e perche': e' la condizione
    per spostare le formazioni sul sito.
    """

    def test_la_tabella_dei_bonus_e_quella_giusta(self, tabellino):
        """Voto piu' eventi rifa' il fantavoto ufficiale per tutti.

        L'unica differenza ammessa e' il malus di adattamento: la piattaforma
        lo somma dentro il fantavoto, noi lo teniamo separato perche' dipende
        dalla casella, non dal giocatore.
        """
        bonus = Bonus()
        malus = ParametriLega().malus_adattamento
        fuori = []

        for squadra in tabellino.squadre:
            for riga in squadra.titolari + squadra.panchina:
                if not riga.ha_giocato:
                    continue
                nostro = punteggio_giocatore(voto_dal_tabellino(riga, 1, 1, bonus), bonus)
                if abs(nostro - riga.fantavoto) > 0.001 and (
                    abs(nostro - malus - riga.fantavoto) > 0.001
                ):
                    fuori.append(
                        f"{squadra.nome}/{riga.nome}: nostro {nostro}, "
                        f"loro {riga.fantavoto}"
                    )

        assert fuori == []

    @staticmethod
    def conto_nostro(squadra):
        """Il nostro punteggio per quella squadra, con le sue regole.

        Le caselle le sceglie `disponi_in_caselle`: il file elenca i titolari
        nell'ordine della piattaforma, che non e' il nostro, e accoppiarli
        uno per uno darebbe malus che nessuno ha pagato.
        """
        tutti = squadra.titolari + squadra.panchina
        bonus = Bonus()
        voti = {n: voto_dal_tabellino(r, n, 1, bonus) for n, r in enumerate(tutti)}
        ruoli = {n: r.ruoli for n, r in enumerate(tutti)}
        quanti = len(squadra.titolari)
        formazione = Formazione(
            squadra_id=1,
            giornata=1,
            modulo=squadra.modulo,
            titolari=disponi_in_caselle(squadra.modulo, range(quanti), ruoli),
            panchina=tuple(range(quanti, len(tutti))),
        )
        return calcola_squadra(
            formazione,
            voti,
            ruoli,
            ParametriLega(),
            bonus=bonus,
            fasce_difesa=FASCE_DIFESA,
            modalita=ModalitaSostituzioni.BASIC,
        )

    def test_i_titolari_prendono_quello_che_hanno_preso_davvero(self, tabellino):
        """Dove non c'e' stata nessuna sostituzione, il nostro conto dei
        titolari deve fare **esattamente** la somma dei loro fantavoti.

        E' la prova delle caselle dei moduli e della tabella delle
        adattabilita' messe insieme: un ruolo accettato dove noi lo vietiamo
        vale zero, e si vede subito.
        """
        fuori = []
        for squadra in tabellino.squadre:
            if any(not g.ha_giocato for g in squadra.titolari):
                continue  # con una sostituzione di mezzo si prova altro
            nostro = self.conto_nostro(squadra)
            atteso = sum(g.fantavoto for g in squadra.titolari)
            somma = sum(p for _, _, p in nostro.schierati)
            if abs(somma - atteso) > 0.001:
                fuori.append(
                    f"{squadra.nome} ({squadra.modulo}): {somma} invece di {atteso}"
                )

        assert fuori == []

    @pytest.mark.xfail(
        reason=(
            "Tre tabelle non ancora calibrate sulla piattaforma: le caselle "
            "dei moduli Mantra mancanti (vedi CASELLE_PER_MODULO), le fasce "
            "del modificatore di difesa e l'ordine con cui entra la panchina. "
            "Vedi PUNTI_APERTI.md."
        ),
        strict=True,
    )
    def test_i_totali_coincidono_con_quelli_della_piattaforma(self, tabellino):
        lontani = [
            f"{s.nome}: noi {self.conto_nostro(s).totale}, loro {s.totale}"
            for s in tabellino.squadre
            if abs(self.conto_nostro(s).totale - s.totale) > 0.001
        ]

        assert lontani == []

    @pytest.mark.xfail(
        reason="Le fasce del modificatore di difesa non sono quelle della piattaforma",
        strict=True,
    )
    def test_il_modificatore_di_difesa_coincide(self, tabellino):
        diversi = [
            f"{s.nome}: noi {self.conto_nostro(s).modificatore_difesa}, "
            f"loro {s.modificatore_difesa}"
            for s in tabellino.squadre
            if self.conto_nostro(s).modificatore_difesa != s.modificatore_difesa
        ]

        assert diversi == []

    def test_quanto_siamo_lontani_resta_scritto(self, tabellino, capsys):
        """Non e' un controllo: e' il metro. Con `-s` stampa la distanza
        squadra per squadra, che e' il numero da far scendere a zero."""
        with capsys.disabled():
            print()
            for squadra in tabellino.squadre:
                nostro = self.conto_nostro(squadra)
                print(
                    f"  {squadra.nome:22} {squadra.modulo:8} "
                    f"noi {nostro.totale:6} loro {squadra.totale:6} "
                    f"({nostro.totale - squadra.totale:+5}) | "
                    f"mod. difesa noi {nostro.modificatore_difesa} "
                    f"loro {squadra.modificatore_difesa}"
                )

        assert len(tabellino.squadre) == 10
