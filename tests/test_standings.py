from collections import Counter

import pytest

from fantacalcio.standings import (
    Partita,
    calcola_classifica,
    genera_calendario,
)

SQUADRE_8 = [f"Squadra {i}" for i in range(1, 9)]


class TestGeneraCalendario:
    def test_giornate_e_partite_pari(self):
        cal = genera_calendario(SQUADRE_8)
        assert cal.giornate == 14  # (8 - 1) * 2
        assert len(cal.partite) == 8 * 7  # ogni coppia due volte
        for giornata in range(1, 15):
            assert len(cal.giornata(giornata)) == 4

    def test_ogni_coppia_si_incontra_andata_e_ritorno(self):
        cal = genera_calendario(SQUADRE_8)
        incontri = Counter(frozenset((p.casa, p.trasferta)) for p in cal.partite)
        assert set(incontri.values()) == {2}

    def test_nessuna_squadra_gioca_due_volte_nella_stessa_giornata(self):
        cal = genera_calendario(SQUADRE_8)
        for giornata in range(1, cal.giornate + 1):
            impegnate = [
                nome
                for p in cal.giornata(giornata)
                for nome in (p.casa, p.trasferta)
            ]
            assert len(impegnate) == len(set(impegnate))

    def test_numero_dispari_una_squadra_riposa(self):
        cal = genera_calendario(SQUADRE_8[:7])
        assert cal.giornate == 14  # (8 - 1) * 2 con il turno di riposo
        for giornata in range(1, cal.giornate + 1):
            assert len(cal.giornata(giornata)) == 3

    def test_solo_andata(self):
        cal = genera_calendario(SQUADRE_8, andata_ritorno=False)
        assert cal.giornate == 7
        assert len(cal.partite) == 28

    def test_ritorno_inverte_il_campo(self):
        cal = genera_calendario(SQUADRE_8)
        andata = {(p.casa, p.trasferta) for p in cal.partite if p.giornata <= 7}
        ritorno = {(p.casa, p.trasferta) for p in cal.partite if p.giornata > 7}
        assert andata == {(t, c) for c, t in ritorno}

    def test_squadre_insufficienti(self):
        with pytest.raises(ValueError, match="almeno 2"):
            genera_calendario(["Unica"])

    def test_nomi_duplicati(self):
        with pytest.raises(ValueError, match="unici"):
            genera_calendario(["A", "B", "A"])


class TestCalcolaClassifica:
    def test_vittoria_pareggio_sconfitta(self):
        squadre = ["A", "B", "C"]
        partite = [
            Partita(1, "A", "B", 2, 1, 70.5, 66.0),
            Partita(2, "B", "C", 1, 1, 68.0, 67.0),
        ]
        classifica = {r.squadra: r for r in calcola_classifica(squadre, partite)}

        assert classifica["A"].punti == 3
        assert classifica["B"].punti == 1
        assert classifica["C"].punti == 1
        assert classifica["B"].giocate == 2
        assert classifica["A"].differenza_reti == 1
        assert classifica["B"].punti_fantacalcio == 134.0

    def test_partite_non_giocate_ignorate(self):
        classifica = calcola_classifica(["A", "B"], [Partita(1, "A", "B")])
        assert all(r.giocate == 0 for r in classifica)

    def test_ordinamento_per_differenza_reti(self):
        squadre = ["A", "B", "C"]
        partite = [
            Partita(1, "A", "C", 3, 0, 80.0, 60.0),
            Partita(2, "B", "C", 1, 0, 67.0, 60.0),
        ]
        ordine = [r.squadra for r in calcola_classifica(squadre, partite)]
        assert ordine == ["A", "B", "C"]

    def test_parita_risolta_dai_punti_fantacalcio(self):
        squadre = ["A", "B", "C", "D"]
        partite = [
            Partita(1, "A", "C", 1, 0, 70.0, 60.0),
            Partita(1, "B", "D", 1, 0, 90.0, 60.0),
        ]
        ordine = [r.squadra for r in calcola_classifica(squadre, partite)]
        assert ordine[:2] == ["B", "A"]

    def test_squadra_sconosciuta(self):
        with pytest.raises(ValueError, match="sconosciuta"):
            calcola_classifica(["A"], [Partita(1, "A", "Z", 1, 0)])
