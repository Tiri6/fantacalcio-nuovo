"""La sala del draft: chi chiama, quando, e cosa ferma una chiamata.

Il pezzo da non sbagliare e' il turno. Dieci persone guardano la stessa sala e
premono nello stesso momento: di chi sia il turno deve dipendere **solo** da
quante chiamate sono state fatte, perche' un campo «turno corrente» da tenere
aggiornato e' un campo che prima o poi dice una cosa diversa dal registro.
"""

from datetime import date, datetime, timedelta

import pytest

from fantacalcio.conformita import Momento, verifica_rosa
from fantacalcio.sala import (
    SalaNonAmmessa,
    Scelta,
    StatoSala,
    TipoSala,
    apri,
    chiudi,
    comincia,
    componi_chiamate,
    registra,
    scelte_di,
    turno,
    verifica_chiamata,
)
from tests.conftest import costruisci_rosa, giocatore

DATA_DRAFT = date(2026, 9, 15)
LOTTERY = [10, 20, 30]
CLASSIFICA = [30, 20, 10]  # dalla prima all'ultima


def sala_pronta(tipo=TipoSala.SETTEMBRE, round_totali=3, **extra):
    return comincia(
        apri(1, 1, tipo, "2026/27", round_totali, LOTTERY, CLASSIFICA, **extra)
    )


class TestLOrdineDiChiamata:
    def test_settembre_segue_la_lottery(self):
        chiamate = componi_chiamate(TipoSala.SETTEMBRE, 2, LOTTERY, CLASSIFICA)
        assert chiamate == (10, 20, 30, 10, 20, 30)

    def test_il_terzo_round_segue_la_classifica(self):
        """Art. 3: i round multipli di 3 vanno in ordine di arrivo."""
        chiamate = componi_chiamate(TipoSala.SETTEMBRE, 3, LOTTERY, CLASSIFICA)
        assert chiamate[6:] == (30, 20, 10)

    def test_niente_serpente(self):
        """Il V3 non lo prevede, e il draft 2026/27 vero ha ripetuto il primo
        giro identico al secondo."""
        chiamate = componi_chiamate(TipoSala.SETTEMBRE, 2, LOTTERY, CLASSIFICA)
        assert chiamate[:3] == chiamate[3:6]

    def test_la_riparazione_va_al_contrario_in_ogni_round(self):
        chiamate = componi_chiamate(TipoSala.RIPARAZIONE, 3, LOTTERY, CLASSIFICA)
        assert chiamate == (10, 20, 30) * 3

    def test_senza_round_non_si_compone(self):
        with pytest.raises(ValueError, match="almeno un round"):
            componi_chiamate(TipoSala.SETTEMBRE, 0, LOTTERY, CLASSIFICA)


class TestLOrdineSiCongela:
    def test_restano_quelle_decise_all_apertura(self):
        """La classifica cambia a sala aperta — una giornata calcolata mentre
        si chiama — e i turni non si devono riordinare a meta' draft."""
        sala = apri(1, 1, TipoSala.RIPARAZIONE, "2026/27", 2, LOTTERY, CLASSIFICA)
        prima = sala.chiamate_previste

        CLASSIFICA.reverse()
        try:
            assert sala.chiamate_previste == prima
        finally:
            CLASSIFICA.reverse()

    def test_la_sala_sa_quante_chiamate_ha(self):
        sala = apri(1, 1, TipoSala.SETTEMBRE, "2026/27", 4, LOTTERY, CLASSIFICA)
        assert sala.chiamate_totali == 12
        assert sala.round_totali == 4
        assert sala.squadre == (10, 20, 30)


class TestLeTransizioni:
    def test_si_apre_aperta(self):
        assert apri(
            1, 1, TipoSala.SETTEMBRE, "2026/27", 2, LOTTERY, CLASSIFICA
        ).stato is (StatoSala.APERTA)

    def test_si_comincia_una_volta_sola(self):
        sala = comincia(apri(1, 1, TipoSala.SETTEMBRE, "2026/27", 2, LOTTERY, CLASSIFICA))
        assert sala.stato is StatoSala.IN_CORSO
        with pytest.raises(SalaNonAmmessa, match="in corso"):
            comincia(sala)

    def test_una_sala_chiusa_non_si_richiude(self):
        sala = chiudi(sala_pronta())
        assert sala.stato is StatoSala.CHIUSA
        with pytest.raises(SalaNonAmmessa, match="gia' chiusa"):
            chiudi(sala)


class TestDiChiEIlTurno:
    def test_la_prima_chiamata_e_del_primo(self):
        attuale = turno(sala_pronta(), [])
        assert attuale.numero == 1
        assert attuale.squadra_id == 10
        assert attuale.etichetta == "Round 1 · chiamata 1"

    def test_si_conta_dal_registro_non_da_un_contatore(self):
        sala = sala_pronta()
        scelte = [
            Scelta(numero=1, squadra_id=10, giocatore_id=1, anni=1),
            Scelta(numero=2, squadra_id=20, giocatore_id=2, anni=1),
        ]
        assert turno(sala, scelte).squadra_id == 30

    def test_passa_al_round_dopo(self):
        sala = sala_pronta()
        scelte = [
            Scelta(numero=n, squadra_id=s, giocatore_id=n, anni=1)
            for n, s in enumerate(sala.chiamate_previste[:3], start=1)
        ]
        attuale = turno(sala, scelte)
        assert attuale.round == 2
        assert attuale.posizione == 1

    def test_una_sala_non_cominciata_non_ha_turno(self):
        sala = apri(1, 1, TipoSala.SETTEMBRE, "2026/27", 2, LOTTERY, CLASSIFICA)
        assert turno(sala, []) is None

    def test_a_chiamate_finite_non_c_e_piu_turno(self):
        sala = sala_pronta(round_totali=1)
        scelte = [
            Scelta(numero=n, squadra_id=s, giocatore_id=n, anni=1)
            for n, s in enumerate(sala.chiamate_previste, start=1)
        ]
        assert turno(sala, scelte) is None

    def test_col_timer_il_turno_ha_una_scadenza(self):
        sala = sala_pronta(secondi_per_chiamata=90)
        quando = datetime(2026, 9, 15, 21, 0)
        scelte = [
            Scelta(1, 10, 1, 1, quando.isoformat(timespec="seconds")),
        ]
        assert turno(sala, scelte).scade_il == quando + timedelta(seconds=90)

    def test_senza_timer_il_turno_non_scade(self):
        """Un timer che passa il turno mentre qualcuno sta ancora decidendo e'
        peggio di un draft lento."""
        assert turno(sala_pronta(), []).scade_il is None


class TestChiamare:
    @staticmethod
    def _chiama(sala, scelte, squadra_id, gio, anni=1, rosa=None, disponibili=None):
        return verifica_chiamata(
            sala,
            scelte,
            squadra_id,
            gio,
            anni,
            rosa
            if rosa is not None
            else costruisci_rosa(squadra_id=squadra_id, dimensione=5),
            disponibili if disponibili is not None else {gio.id},
            data_draft=DATA_DRAFT,
        )

    def test_una_chiamata_sensata_passa(self):
        assert self._chiama(sala_pronta(), [], 10, giocatore(900)) == []

    def test_non_e_il_tuo_turno(self):
        violazioni = self._chiama(sala_pronta(), [], 20, giocatore(900))
        codici = [v.codice for v in violazioni]
        assert "non_e_il_tuo_turno" in codici
        # Dice anche di chi e': davanti a dieci persone che aspettano serve.
        assert "tocca alla chiamata 1" in violazioni[0].messaggio

    def test_un_giocatore_gia_chiamato_non_si_richiama(self):
        scelte = [Scelta(1, 10, 900, 1)]
        violazioni = verifica_chiamata(
            sala_pronta(),
            scelte,
            20,
            giocatore(900),
            1,
            costruisci_rosa(squadra_id=20, dimensione=5),
            {900},
            data_draft=DATA_DRAFT,
        )
        assert "gia_chiamato" in [v.codice for v in violazioni]

    def test_un_giocatore_non_libero_non_si_chiama(self):
        violazioni = self._chiama(
            sala_pronta(), [], 10, giocatore(900), disponibili=set()
        )
        assert "non_disponibile" in [v.codice for v in violazioni]

    def test_una_durata_fuori_scala_e_bloccante(self):
        violazioni = self._chiama(sala_pronta(), [], 10, giocatore(900), anni=9)
        assert "durata_contratto" in [v.codice for v in violazioni]

    def test_in_una_sala_non_cominciata_non_si_chiama(self):
        sala = apri(1, 1, TipoSala.SETTEMBRE, "2026/27", 2, LOTTERY, CLASSIFICA)
        violazioni = self._chiama(sala, [], 10, giocatore(900))
        assert [v.codice for v in violazioni] == ["sala_chiusa"]


class TestITettiBloccanoIMinimiNo:
    """Durante il draft la rosa si sta costruendo.

    Alla terza chiamata la rosa e' corta per definizione: se il minimo
    bloccasse, nessuno arriverebbe alla quarta. I tetti invece fermano subito,
    perche' una chiamata non si annulla.
    """

    @staticmethod
    def _chiama(rosa, gio, anni=1):
        return verifica_chiamata(
            sala_pronta(),
            [],
            10,
            gio,
            anni,
            rosa,
            {gio.id},
            data_draft=DATA_DRAFT,
        )

    def test_una_rosa_corta_non_ferma_la_chiamata(self):
        corta = costruisci_rosa(squadra_id=10, dimensione=2, annuali=0, portieri=0)
        assert self._chiama(corta, giocatore(900)) == []

    def test_la_rosa_massima_ferma_la_chiamata(self):
        piena = costruisci_rosa(squadra_id=10, dimensione=33, annuali=11)
        violazioni = self._chiama(piena, giocatore(900))
        assert "rosa_massima" in [v.codice for v in violazioni]

    def test_troppi_portieri_fermano_la_chiamata(self):
        con_portieri = costruisci_rosa(squadra_id=10, dimensione=10, portieri=4)
        violazioni = self._chiama(con_portieri, giocatore(900, ruoli=("Por",)))
        assert "portieri" in [v.codice for v in violazioni]

    def test_il_monte_anni_ferma_la_chiamata(self):
        quasi = costruisci_rosa(
            squadra_id=10, dimensione=22, annuali=0, anni_altri=3
        )  # 66 anni esatti
        violazioni = self._chiama(quasi, giocatore(900), anni=1)
        assert "monte_anni" in [v.codice for v in violazioni]

    def test_il_salary_cap_ferma_la_chiamata(self):
        """In stagione lo sforamento e' un avviso (art. 8b), qui no: una
        chiamata non si annulla, e scoprirlo a draft finito vorrebbe dire una
        rosa invalida senza modo di tornare indietro."""
        ricca = costruisci_rosa(squadra_id=10, dimensione=25, ingaggio=3_900_000)
        violazioni = self._chiama(ricca, giocatore(900, ingaggio=9_000_000))
        assert "salary_cap" in [v.codice for v in violazioni]

    def test_in_stagione_lo_stesso_sforamento_resta_un_avviso(self):
        """Il contrario del test sopra, per far vedere che e' il momento a
        decidere e non il numero."""
        ricca = costruisci_rosa(squadra_id=10, dimensione=25, ingaggio=3_900_000)
        futura = ricca.con_giocatore(giocatore(900, ingaggio=9_000_000), 1)
        stato = verifica_rosa(futura, DATA_DRAFT, momento=Momento.STAGIONE)
        cap = next(v for v in stato.violazioni if v.codice == "salary_cap")
        assert cap.bloccante is False


class TestIlRegistro:
    def test_il_numero_lo_decide_il_registro(self):
        """E' quello che impedisce a due persone che premono insieme di
        prendere lo stesso posto."""
        scelte = [Scelta(1, 10, 1, 1), Scelta(2, 20, 2, 1)]
        nuova = registra(sala_pronta(), scelte, 30, 900, 3)
        assert nuova.numero == 3
        assert nuova.squadra_id == 30
        assert nuova.anni == 3
        assert nuova.quando

    def test_cosa_ha_preso_una_squadra(self):
        """Serve alla finestra degli anni: si correggono solo i presi qui."""
        scelte = [Scelta(1, 10, 100, 1), Scelta(2, 20, 200, 2), Scelta(3, 10, 300, 3)]
        assert [s.giocatore_id for s in scelte_di(scelte, 10)] == [100, 300]
        assert scelte_di(scelte, 99) == []
