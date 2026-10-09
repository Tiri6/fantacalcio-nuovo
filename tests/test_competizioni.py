"""Competizioni: coppa, F1 Rush, albo d'oro e calendario dei weekend."""

from datetime import date

import pytest

from fantacalcio.competizioni import (
    GIORNATE_SERIE_A,
    CompetizioneNonValida,
    CriterioF1Rush,
    FormatoCoppa,
    RegoleCoppa,
    RegoleF1Rush,
    TipoCompetizione,
    Titolo,
    bacheca_squadre,
    classifica_f1,
    conta_per_competizione,
    costruisci_weekend,
    crea_titolo,
    data_riferimento_u21,
    giornate_f1_rush,
    ordina_albo,
    titoli_di,
    titolo_esistente,
)


class TestDataU21:
    @pytest.mark.parametrize(
        "stagione,atteso", [("2026/27", 2026), ("2030/31", 2030), ("1999/00", 1999)]
    )
    def test_si_ricava_l_anno_dalla_stagione(self, stagione, atteso):
        assert data_riferimento_u21(stagione) == date(atteso, 8, 31)

    @pytest.mark.parametrize("stagione", ["", None, "boh", 42])
    def test_stagione_illeggibile_non_esplode(self, stagione):
        """Una stagione scritta male non deve impedire di caricare una rosa."""
        assert data_riferimento_u21(stagione).month == 8

    def test_senza_draft_il_ripiego_e_il_31_agosto(self):
        # La regola vera e' «alla data del draft» (art. 2). Il 31 agosto resta
        # solo per quando il draft non e' ancora fissato: vedi TestDataUnder21.
        assert data_riferimento_u21("2026/27").day == 31


def coppa_secca(**extra) -> RegoleCoppa:
    """La coppa com'era prima del V3: eliminazione diretta, intervallata al
    campionato. Resta un formato scegliibile, quindi resta provato."""
    return RegoleCoppa(
        formato=FormatoCoppa.ELIMINAZIONE_SECCA,
        dopo_il_campionato=False,
        **extra,
    )


class TestRegoleCoppa:
    def test_turni_da_otto_squadre(self):
        assert coppa_secca(squadre_ammesse=8).turni == 3

    @pytest.mark.parametrize("quante,turni", [(2, 1), (4, 2), (8, 3), (16, 4)])
    def test_turni_per_dimensione(self, quante, turni):
        assert coppa_secca(squadre_ammesse=quante).turni == turni

    @pytest.mark.parametrize("quante", [3, 5, 6, 7, 10, 12])
    def test_solo_potenze_di_due(self, quante):
        """Con un numero diverso il tabellone non si chiude."""
        with pytest.raises(CompetizioneNonValida, match="potenza di due"):
            coppa_secca(squadre_ammesse=quante)

    def test_almeno_due_squadre(self):
        with pytest.raises(CompetizioneNonValida, match="due squadre"):
            coppa_secca(squadre_ammesse=1)

    def test_nomi_dei_turni(self):
        regole = coppa_secca(squadre_ammesse=8)
        assert regole.nome_turno(1) == "Quarti di finale"
        assert regole.nome_turno(2) == "Semifinali"
        assert regole.nome_turno(3) == "Finale"

    def test_a_sedici_si_parte_dagli_ottavi(self):
        assert coppa_secca(squadre_ammesse=16).nome_turno(1) == "Ottavi di finale"

    def test_giornate_dei_turni(self):
        regole = coppa_secca(squadre_ammesse=8, prima_giornata=5, ogni_quante_giornate=4)
        assert regole.giornate_dei_turni() == (5, 9, 13)

    @pytest.mark.parametrize("campo", ["prima_giornata", "ogni_quante_giornate"])
    def test_valori_non_positivi(self, campo):
        with pytest.raises(CompetizioneNonValida):
            coppa_secca(**{campo: 0})


class TestCoppaAGironi:
    """Il formato del V3: due gironi andata e ritorno, poi scontri diretti."""

    def test_e_il_formato_predefinito(self):
        assert RegoleCoppa().formato is FormatoCoppa.GIRONI_PIU_SCONTRI
        assert RegoleCoppa().dopo_il_campionato

    def test_due_gironi_da_cinque_per_una_lega_da_dieci(self):
        regole = RegoleCoppa()
        assert regole.squadre_ammesse == 10
        assert regole.gironi == 2
        assert regole.squadre_per_girone == 5

    def test_quattro_qualificate_fanno_semifinali_e_finale(self):
        regole = RegoleCoppa()
        assert regole.squadre_a_eliminazione == 4
        assert regole.turni == 2
        assert regole.nome_turno(1) == "Semifinali"
        assert regole.nome_turno(2) == "Finale"

    def test_coi_gironi_le_ammesse_non_sono_una_potenza_di_due(self):
        """Entrano tutte e dieci: a doverlo essere sono le qualificate."""
        assert RegoleCoppa(squadre_ammesse=10).squadre_a_eliminazione == 4

    def test_qualificate_che_non_chiudono_il_tabellone(self):
        with pytest.raises(CompetizioneNonValida, match="potenza di due"):
            RegoleCoppa(squadre_ammesse=12, gironi=3, qualificate_per_girone=1)

    def test_gironi_disuguali_si_rifiutano(self):
        with pytest.raises(CompetizioneNonValida, match="gironi uguali"):
            RegoleCoppa(squadre_ammesse=10, gironi=3)

    def test_non_si_qualificano_piu_squadre_di_quante_ce_ne_siano(self):
        with pytest.raises(CompetizioneNonValida, match="Non possono qualificarsi"):
            RegoleCoppa(squadre_ammesse=4, gironi=2, qualificate_per_girone=4)

    def test_le_giornate_di_girone_sono_andata_e_ritorno(self):
        """Cinque squadre per girone: cinque turni con un riposo, per due."""
        assert RegoleCoppa().giornate_di_girone == 10
        # Con un numero pari non c'e' riposo: quattro squadre, sei giornate.
        assert RegoleCoppa(squadre_ammesse=8, gironi=2).giornate_di_girone == 6

    def test_senza_gironi_non_ci_sono_giornate_di_girone(self):
        assert coppa_secca(squadre_ammesse=8).giornate_di_girone == 0


class TestLaCoppaInCalendario:
    def test_a_gironi_si_accoda_al_campionato(self):
        """«Disputati a fine campionato» (art. 1): non si intervalla piu'."""
        turni = costruisci_weekend(38, 18, RegoleCoppa(), prima_giornata_serie_a=1)

        def con(tipo):
            return [t for t in turni if any(i[0] is tipo for i in t.impegni)]

        campionato = con(TipoCompetizione.CAMPIONATO)
        coppa = con(TipoCompetizione.COPPA_ITALIA)
        assert len(campionato) == 18
        assert campionato[-1].giornata_serie_a < coppa[0].giornata_serie_a

    def test_prima_i_gironi_poi_gli_scontri(self):
        turni = costruisci_weekend(38, 18, RegoleCoppa(), prima_giornata_serie_a=1)
        impegni = [
            i[1]
            for t in turni
            for i in t.impegni
            if i[0] is TipoCompetizione.COPPA_ITALIA
        ]
        assert impegni[:2] == ["1ª giornata dei gironi", "2ª giornata dei gironi"]
        assert impegni[-2:] == ["Semifinali", "Finale"]

    def test_a_eliminazione_diretta_continua_a_slittare(self):
        regole = coppa_secca(squadre_ammesse=8, prima_giornata=5, ogni_quante_giornate=4)
        turni = costruisci_weekend(12, 27, regole, prima_giornata_serie_a=1)
        assert turni[4].impegni[0][0] is TipoCompetizione.COPPA_ITALIA


class TestWeekend:
    def test_senza_coppa_le_numerazioni_restano_allineate(self):
        turni = costruisci_weekend(10, 27, None, prima_giornata_serie_a=1)
        assert turni[0].descrizione.endswith("1ª giornata")
        assert turni[4].descrizione.endswith("5ª giornata")

    def test_la_lega_parte_a_stagione_iniziata(self):
        turni = costruisci_weekend(10, 27, None, prima_giornata_serie_a=6)
        assert turni[0].giornata_serie_a == 6
        assert "1ª giornata" in turni[0].descrizione

    def test_il_turno_di_coppa_fa_slittare_il_campionato(self):
        """La giornata di campionato non sparisce: si sposta di un weekend."""
        regole = coppa_secca(squadre_ammesse=8, prima_giornata=5, ogni_quante_giornate=4)
        turni = costruisci_weekend(12, 27, regole, prima_giornata_serie_a=1)
        assert "4ª giornata" in turni[3].descrizione
        assert turni[4].impegni[0][0] is TipoCompetizione.COPPA_ITALIA
        # dopo la coppa il campionato riprende dalla quinta, non dalla sesta
        assert "5ª giornata" in turni[5].descrizione

    def test_nessuna_giornata_di_campionato_va_persa(self):
        regole = coppa_secca(squadre_ammesse=8, prima_giornata=3, ogni_quante_giornate=3)
        turni = costruisci_weekend(20, 10, regole, prima_giornata_serie_a=1)
        giocate = [
            e[1] for t in turni for e in t.impegni if e[0] is TipoCompetizione.CAMPIONATO
        ]
        assert giocate == [f"{n}ª giornata" for n in range(1, 11)]

    def test_finito_il_campionato_i_weekend_restano_liberi(self):
        turni = costruisci_weekend(10, 3, None)
        assert turni[3].libero
        assert turni[3].descrizione == "— nessun impegno —"


class TestAlbo:
    def titolo(self, id_, competizione, stagione, squadra):
        return crea_titolo(id_, 1, competizione, stagione, squadra)

    def test_un_titolo_senza_squadra_non_ha_senso(self):
        with pytest.raises(CompetizioneNonValida, match="squadra"):
            Titolo(1, 1, TipoCompetizione.CAMPIONATO, "2026/27", None, "  ")

    def test_un_titolo_senza_stagione_non_e_storicizzabile(self):
        with pytest.raises(CompetizioneNonValida, match="stagione"):
            Titolo(1, 1, TipoCompetizione.CAMPIONATO, "", None, "Tiri Team")

    def test_ordine_dalla_stagione_piu_recente(self):
        titoli = [
            self.titolo(1, TipoCompetizione.CAMPIONATO, "2024/25", "A"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "B"),
            self.titolo(3, TipoCompetizione.CAMPIONATO, "2025/26", "C"),
        ]
        assert [t.stagione for t in ordina_albo(titoli)] == [
            "2026/27",
            "2025/26",
            "2024/25",
        ]

    def test_nella_stessa_stagione_prima_il_campionato(self):
        titoli = [
            self.titolo(1, TipoCompetizione.F1_RUSH, "2026/27", "A"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "B"),
        ]
        assert ordina_albo(titoli)[0].competizione is TipoCompetizione.CAMPIONATO

    def test_conteggio_per_squadra(self):
        titoli = [
            self.titolo(1, TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team"),
            self.titolo(2, TipoCompetizione.CAMPIONATO, "2026/27", "Tiri Team"),
            self.titolo(3, TipoCompetizione.COPPA_ITALIA, "2026/27", "Padel United"),
        ]
        conteggio = bacheca_squadre(titoli)
        assert conteggio["Tiri Team"][TipoCompetizione.CAMPIONATO] == 2
        assert conteggio["Padel United"][TipoCompetizione.COPPA_ITALIA] == 1

    def test_si_trova_il_titolo_di_una_stagione(self):
        titoli = [self.titolo(1, TipoCompetizione.CAMPIONATO, "2026/27", "A")]
        assert titolo_esistente(titoli, TipoCompetizione.CAMPIONATO, "2026/27")
        assert not titolo_esistente(titoli, TipoCompetizione.COPPA_ITALIA, "2026/27")
        assert not titolo_esistente(titoli, TipoCompetizione.CAMPIONATO, "2025/26")


class TestF1Rush:
    """La F1 Rush Finale, che nel V3 ha preso il posto della Supercoppa."""

    def test_si_corre_sulle_ultime_giornate_di_serie_a(self):
        assert giornate_f1_rush() == (33, 34, 35, 36, 37, 38)

    def test_con_un_campionato_piu_corto_si_prende_quel_che_c_e(self):
        """Meglio quattro tappe che sei giornate che non esistono."""
        assert giornate_f1_rush(4) == (1, 2, 3, 4)

    def test_quante_giornate_e_un_parametro(self):
        regole = RegoleF1Rush(giornate_serie_a=3)
        assert giornate_f1_rush(GIORNATE_SERIE_A, regole) == (36, 37, 38)

    def test_zero_giornate_non_fa_nessuna_tappa(self):
        assert giornate_f1_rush(0) == ()

    def test_una_durata_impossibile_si_rifiuta(self):
        with pytest.raises(CompetizioneNonValida, match="almeno una giornata"):
            RegoleF1Rush(giornate_serie_a=0)

    def test_la_scala_arriva_dai_parametri(self):
        regole = RegoleF1Rush(punti_per_posizione=(10, 6, 3))
        assert regole.punti_di_posizione(1) == 10
        assert regole.punti_di_posizione(3) == 3

    def test_oltre_la_scala_non_si_prende_niente(self):
        """Come in Formula 1: oltre l'ultima posizione premiata, zero."""
        regole = RegoleF1Rush(punti_per_posizione=(10, 6, 3))
        assert regole.punti_di_posizione(4) == 0
        assert regole.punti_di_posizione(0) == 0

    def test_da_json_la_scala_torna_una_tupla(self):
        """Una dataclass congelata con una lista dentro non e' hashabile."""
        regole = RegoleF1Rush(punti_per_posizione=[10, 6, 3])
        assert regole.punti_per_posizione == (10, 6, 3)
        assert hash(regole)


class TestClassificaF1:
    def test_i_punti_di_tappa_si_sommano(self):
        tappe = [
            {"A": 80.0, "B": 70.0, "C": 60.0},
            {"A": 50.0, "B": 90.0, "C": 70.0},
        ]
        classifica = classifica_f1(tappe, RegoleF1Rush(punti_per_posizione=(10, 6, 3)))
        punti = {r.squadra: r.punti for r in classifica}
        assert punti == {"A": 13, "B": 16, "C": 9}

    def test_i_pari_merito_prendono_i_punti_della_posizione_migliore(self):
        tappe = [{"A": 90.0, "B": 90.0, "C": 60.0}]
        classifica = classifica_f1(tappe, RegoleF1Rush(punti_per_posizione=(10, 6, 3)))
        punti = {r.squadra: r.punti for r in classifica}
        assert punti["A"] == punti["B"] == 10
        assert punti["C"] == 3

    def test_a_pari_punti_valgono_le_vittorie_di_tappa(self):
        """E' il primo spareggio della Formula 1, nel suo stesso ordine."""
        tappe = [
            {"A": 90.0, "B": 10.0},
            {"A": 10.0, "B": 90.0},
            {"A": 90.0, "B": 10.0},
            {"A": 10.0, "B": 11.0},
        ]
        classifica = classifica_f1(tappe, RegoleF1Rush(punti_per_posizione=(10, 10)))
        assert classifica[0].squadra == "A"
        assert classifica[0].punti == classifica[1].punti
        assert classifica[0].vittorie_di_tappa == 2

    def test_a_pari_punti_e_vittorie_valgono_i_fantapunti(self):
        tappe = [{"A": 90.0, "B": 80.0}]
        classifica = classifica_f1(tappe, RegoleF1Rush(punti_per_posizione=(10, 10)))
        assert classifica[0].squadra == "A"
        assert classifica[0].fantapunti == 90.0

    def test_col_criterio_a_fantapunti_i_punti_restano_a_zero(self):
        tappe = [{"A": 90.0, "B": 80.0}]
        regole = RegoleF1Rush(criterio=CriterioF1Rush.SOMMA_FANTAPUNTI)
        classifica = classifica_f1(tappe, regole)
        assert all(r.punti == 0 for r in classifica)
        assert classifica[0].squadra == "A"

    def test_senza_tappe_non_c_e_classifica(self):
        assert classifica_f1([]) == []

    def test_le_tappe_vuote_si_saltano(self):
        assert classifica_f1([{}, {"A": 10.0}])[0].tappe == 1

    def test_la_scala_in_vigore_premia_dieci_squadre(self):
        """Dieci partecipanti, dieci posizioni a punti: nessuno corre per nulla."""
        assert len(RegoleF1Rush().punti_per_posizione) == 10


class TestLaF1RushNelCalendario:
    def test_non_occupa_un_weekend_suo(self):
        """Corre sugli stessi fantapunti del campionato: non fa slittare niente."""
        senza = costruisci_weekend(38, 18, prima_giornata_serie_a=1)
        con = costruisci_weekend(
            38, 18, prima_giornata_serie_a=1, regole_f1_rush=RegoleF1Rush()
        )
        campionato = [
            [i for i in t.impegni if i[0] is TipoCompetizione.CAMPIONATO] for t in senza
        ]
        uguale = [
            [i for i in t.impegni if i[0] is TipoCompetizione.CAMPIONATO] for t in con
        ]
        assert campionato == uguale

    def test_le_tappe_cadono_sugli_ultimi_sei_turni(self):
        turni = costruisci_weekend(
            38, 18, prima_giornata_serie_a=1, regole_f1_rush=RegoleF1Rush()
        )
        con_f1 = [
            t.giornata_serie_a
            for t in turni
            if any(i[0] is TipoCompetizione.F1_RUSH for i in t.impegni)
        ]
        assert con_f1 == [33, 34, 35, 36, 37, 38]

    def test_la_tappa_si_numera_da_uno(self):
        turni = costruisci_weekend(
            38, 18, prima_giornata_serie_a=1, regole_f1_rush=RegoleF1Rush()
        )
        prima = next(
            t for t in turni if any(i[0] is TipoCompetizione.F1_RUSH for i in t.impegni)
        )
        assert "1ª tappa di 6" in prima.descrizione

    def test_senza_regole_non_compare(self):
        turni = costruisci_weekend(38, 18, prima_giornata_serie_a=1)
        assert not any(i[0] is TipoCompetizione.F1_RUSH for t in turni for i in t.impegni)


def test_ogni_competizione_ha_icona_ed_etichetta():
    assert all(c.icona and c.etichetta for c in TipoCompetizione)


def test_ogni_formato_di_coppa_ha_un_etichetta():
    assert all(f.etichetta for f in FormatoCoppa)


class TestBachecaDiUnaSquadra:
    """La bacheca di una squadra si ricava dall'albo d'oro, senza dati doppi."""

    def titolo(self, id_, competizione, stagione, nome, squadra_id=None):
        return Titolo(
            id=id_,
            lega_id=1,
            competizione=competizione,
            stagione=stagione,
            squadra_id=squadra_id,
            squadra_nome=nome,
        )

    def albo(self):
        return [
            self.titolo(1, TipoCompetizione.CAMPIONATO, "2025/26", "Tiri Team", 7),
            self.titolo(2, TipoCompetizione.COPPA_ITALIA, "2025/26", "Padel United", 8),
            self.titolo(3, TipoCompetizione.CAMPIONATO, "2026/27", "Tiri Team", 7),
            self.titolo(4, TipoCompetizione.F1_RUSH, "2026/27", "Tiri Team", 7),
        ]

    def test_prende_solo_i_suoi(self):
        suoi = titoli_di(self.albo(), 7, "Tiri Team")
        assert len(suoi) == 3
        assert all(t.squadra_id == 7 for t in suoi)

    def test_ordinati_dal_piu_recente(self):
        suoi = titoli_di(self.albo(), 7, "Tiri Team")
        assert suoi[0].stagione == "2026/27"
        assert suoi[-1].stagione == "2025/26"

    def test_una_squadra_senza_titoli_ha_bacheca_vuota(self):
        assert titoli_di(self.albo(), 99, "Nuova Arrivata") == []

    def test_un_titolo_senza_id_resta_agganciato_al_nome(self):
        """Registrato prima che l'id fosse noto: e' comunque suo."""
        albo = [self.titolo(5, TipoCompetizione.CAMPIONATO, "2024/25", "Tiri Team")]
        assert len(titoli_di(albo, 7, "Tiri Team")) == 1

    def test_il_nome_si_confronta_senza_maiuscole_ne_spazi(self):
        albo = [self.titolo(5, TipoCompetizione.CAMPIONATO, "2024/25", "  TIRI team ")]
        assert len(titoli_di(albo, 7, "Tiri Team")) == 1

    def test_un_titolo_con_id_di_un_altra_squadra_non_si_prende_per_nome(self):
        """L'id, quando c'e', comanda: due squadre possono chiamarsi uguale."""
        albo = [self.titolo(5, TipoCompetizione.CAMPIONATO, "2024/25", "Tiri Team", 99)]
        assert titoli_di(albo, 7, "Tiri Team") == []

    def test_conteggio_per_competizione(self):
        conteggio = conta_per_competizione(titoli_di(self.albo(), 7, "Tiri Team"))
        assert conteggio[TipoCompetizione.CAMPIONATO] == 2
        assert conteggio[TipoCompetizione.F1_RUSH] == 1
        assert conteggio[TipoCompetizione.COPPA_ITALIA] == 0

    def test_il_conteggio_elenca_tutte_le_competizioni(self):
        """Anche quelle a zero: la bacheca mostra i vuoti, non li nasconde."""
        assert set(conta_per_competizione([])) == set(TipoCompetizione)


class TestDataUnder21:
    """La data che decide gli Under 21: il 31 agosto, fissa tutti gli anni.

    L'articolo 2 scrive «alla data del draft di Settembre»; la lega ha scelto
    una data fissa, cosi' lo status non si muove se l'asta slitta. E' una
    divergenza voluta dal testo, e questi test la tengono ferma: se qualcuno
    un giorno tornera' alla data del draft, dovra' passare di qui.
    """

    def test_e_il_31_agosto_della_stagione(self):
        from datetime import date

        from fantacalcio.competizioni import data_riferimento_u21

        assert data_riferimento_u21("2026/27") == date(2026, 8, 31)
        assert data_riferimento_u21("2030/31") == date(2030, 8, 31)

    def test_non_dipende_da_quando_si_fa_il_draft(self):
        from datetime import date

        from fantacalcio.modelli import Giocatore
        from fantacalcio.regole import ParametriLega

        # Compie 21 anni il 1 ottobre 2026: al 31 agosto e' ancora Under, e
        # resta Under per tutta la stagione anche se il draft slitta a ottobre.
        ragazzo = Giocatore(
            id=1,
            nome="Giovane",
            club="Roma",
            ruoli=("C",),
            ingaggio=0,
            nazionalita="Italia",
            data_nascita=date(2005, 10, 1),
        )
        assert ragazzo.under_21(data_riferimento_u21("2026/27"), ParametriLega())

    def test_chi_li_compie_prima_del_31_agosto_non_e_under(self):
        from datetime import date

        from fantacalcio.modelli import Giocatore
        from fantacalcio.regole import ParametriLega

        grande = Giocatore(
            id=2,
            nome="Appena Grande",
            club="Roma",
            ruoli=("C",),
            ingaggio=0,
            nazionalita="Italia",
            data_nascita=date(2005, 8, 30),
        )
        assert not grande.under_21(data_riferimento_u21("2026/27"), ParametriLega())

    def test_una_stagione_scritta_male_non_fa_fallire_niente(self):
        from datetime import date

        from fantacalcio.competizioni import data_riferimento_u21

        assert data_riferimento_u21("boh").month == 8
        assert data_riferimento_u21("boh").year == date.today().year
