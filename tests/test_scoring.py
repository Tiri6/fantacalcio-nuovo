import pytest

from fantacalcio.scoring import (
    Prestazione,
    RegoleLega,
    calcola_formazione,
    fantavoto,
    punti_in_gol,
    regole_da_dict,
)

REGOLE = RegoleLega()


def presta(id_: int, ruolo: str = "C", voto: float | None = 6.0, **extra) -> Prestazione:
    return Prestazione(
        giocatore_id=id_, nome=f"Giocatore {id_}", ruolo=ruolo, voto=voto, **extra
    )


def undici(voto: float = 6.0) -> list[Prestazione]:
    ruoli = ["P"] + ["D"] * 4 + ["C"] * 4 + ["A"] * 2
    return [presta(i, ruolo, voto) for i, ruolo in enumerate(ruoli, start=1)]


class TestFantavoto:
    def test_voto_senza_bonus(self):
        assert fantavoto(presta(1, voto=6.5), REGOLE) == 6.5

    def test_gol_e_assist(self):
        p = presta(1, "A", 7.0, gol_segnati=2, assist=1)
        assert fantavoto(p, REGOLE) == 7.0 + 6.0 + 1.0

    def test_malus(self):
        p = presta(1, "D", 5.5, ammonizioni=1, espulsioni=1, autogol=1)
        assert fantavoto(p, REGOLE) == 5.5 - 0.5 - 1.0 - 2.0

    def test_portiere_gol_subiti_e_rigore_parato(self):
        p = presta(1, "P", 6.0, gol_subiti=2, rigori_parati=1)
        assert fantavoto(p, REGOLE) == 6.0 - 2.0 + 3.0

    def test_senza_voto_solleva(self):
        with pytest.raises(ValueError):
            fantavoto(presta(1, voto=None), REGOLE)

    def test_porta_inviolata_disattivata_di_default(self):
        p = presta(1, "P", 6.0, gol_subiti=0)
        assert fantavoto(p, REGOLE) == 6.0
        con_bonus = RegoleLega(porta_inviolata=1.0)
        assert fantavoto(p, con_bonus) == 7.0


class TestPuntiInGol:
    @pytest.mark.parametrize(
        "punti,gol",
        [(0, 0), (65.5, 0), (66, 1), (71.5, 1), (72, 2), (77.9, 2), (78, 3), (102, 7)],
    )
    def test_soglie_standard(self, punti, gol):
        assert punti_in_gol(punti, REGOLE) == gol

    def test_soglia_personalizzata(self):
        regole = RegoleLega(soglia_primo_gol=60, passo_gol=4)
        assert punti_in_gol(59.9, regole) == 0
        assert punti_in_gol(60, regole) == 1
        assert punti_in_gol(64, regole) == 2


class TestCalcolaFormazione:
    def test_undici_da_sei_fa_66_punti_e_un_gol(self):
        risultato = calcola_formazione(undici(6.0), regole=REGOLE)
        assert risultato.totale == 66.0
        assert risultato.gol == 1
        assert risultato.panchinari_entrati == ()

    def test_numero_titolari_sbagliato_solleva(self):
        with pytest.raises(ValueError, match="11 titolari"):
            calcola_formazione(undici()[:10], regole=REGOLE)

    def test_sostituzione_stesso_ruolo(self):
        titolari = undici(6.0)
        titolari[5] = presta(6, "C", None)  # centrocampista s.v.
        panchina = [presta(90, "D", 7.0), presta(91, "C", 7.5)]

        risultato = calcola_formazione(titolari, panchina, REGOLE)

        assert [p.giocatore_id for p in risultato.panchinari_entrati] == [91]
        assert risultato.totale == 66.0 - 6.0 + 7.5
        assert risultato.non_sostituiti == ()

    def test_panchinaro_senza_voto_non_entra(self):
        titolari = undici(6.0)
        titolari[5] = presta(6, "C", None)
        panchina = [presta(90, "C", None), presta(91, "C", 7.0)]

        risultato = calcola_formazione(titolari, panchina, REGOLE)

        assert [p.giocatore_id for p in risultato.panchinari_entrati] == [91]

    def test_massimo_tre_sostituzioni(self):
        titolari = undici(6.0)
        for indice in range(1, 5):  # 4 difensori/centrocampisti s.v.
            titolari[indice] = presta(indice + 1, titolari[indice].ruolo, None)
        panchina = [presta(100 + i, "D", 6.0) for i in range(4)]

        risultato = calcola_formazione(titolari, panchina, REGOLE)

        assert len(risultato.panchinari_entrati) == 3
        assert len(risultato.non_sostituiti) == 1
        assert risultato.totale == 6.0 * 10  # 11 - 1 non sostituito

    def test_nessun_sostituto_del_ruolo(self):
        titolari = undici(6.0)
        titolari[0] = presta(1, "P", None)
        panchina = [presta(90, "A", 8.0)]

        risultato = calcola_formazione(titolari, panchina, REGOLE)

        assert risultato.panchinari_entrati == ()
        assert [p.giocatore_id for p in risultato.non_sostituiti] == [1]
        assert risultato.totale == 60.0

    def test_un_panchinaro_non_puo_entrare_due_volte(self):
        titolari = undici(6.0)
        titolari[1] = presta(2, "D", None)
        titolari[2] = presta(3, "D", None)
        panchina = [presta(90, "D", 7.0)]

        risultato = calcola_formazione(titolari, panchina, REGOLE)

        assert [p.giocatore_id for p in risultato.panchinari_entrati] == [90]
        assert [p.giocatore_id for p in risultato.non_sostituiti] == [3]

    def test_modificatore_difesa(self):
        regole = RegoleLega(modificatore_difesa=True)
        titolari = undici(6.0)
        titolari[0] = presta(1, "P", 7.0)
        for indice in range(1, 5):
            titolari[indice] = presta(indice + 1, "D", 7.0)

        risultato = calcola_formazione(titolari, regole=regole)

        # Media portiere + 3 difensori = 7.0 -> +2 di modificatore.
        assert risultato.modificatore == 2.0
        assert risultato.totale == 66.0 + 5.0 + 2.0


class TestRegoleDaDict:
    def test_ignora_chiavi_sconosciute(self):
        regole = regole_da_dict({"gol_segnato": 4.0, "chiave_inventata": 99})
        assert regole.gol_segnato == 4.0
        assert regole.assist == RegoleLega().assist
