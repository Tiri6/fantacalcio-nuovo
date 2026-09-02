"""La tabella delle sostituzioni: e' un dato trascritto a mano da un'immagine.

Un errore di battitura qui non alza nessuna eccezione: cambia in silenzio chi
puo' entrare in campo, e quindi il risultato di una giornata. Percio' i test
non guardano solo il codice che la legge, ma **la forma della tabella**: che
sia quadrata, che la diagonale sia tutta OK, che il portiere sia isolato, e
che l'asimmetria — si arretra, non si avanza — valga riga per riga.
"""

import pytest

from fantacalcio.mantra import (
    ASTERISCHI_NON_IN_ALTERNATIVA,
    CASELLE_PER_MODULO,
    RUOLI_TABELLA,
    TABELLA_SOSTITUZIONI,
    Esito,
    caselle_di,
    costo_in_casella,
    esito_grezzo,
    esito_in_casella,
    esito_sostituzione,
)

# I ruoli dal piu' avanzato al piu' arretrato, senza il portiere che sta
# fuori da ogni scala.
DALL_ATTACCO_ALLA_DIFESA = ("Pc", "A", "T", "W", "C", "M", "E", "B", "Dc", "Dd", "Ds")


class TestFormaDellaTabella:
    def test_e_quadrata(self):
        assert set(TABELLA_SOSTITUZIONI) == set(RUOLI_TABELLA)
        for uscito, riga in TABELLA_SOSTITUZIONI.items():
            assert set(riga) == set(RUOLI_TABELLA), uscito

    def test_ogni_ruolo_copre_se_stesso_gratis(self):
        for ruolo in RUOLI_TABELLA:
            assert TABELLA_SOSTITUZIONI[ruolo][ruolo] is Esito.LIBERA, ruolo

    def test_il_portiere_e_isolato(self):
        for ruolo in RUOLI_TABELLA:
            if ruolo == "Por":
                continue
            # Ne' un portiere copre un giocatore di movimento...
            assert esito_grezzo(ruolo, "Por") is Esito.VIETATA, ruolo
            # ...ne' un giocatore di movimento copre il portiere.
            assert esito_grezzo("Por", ruolo) is Esito.VIETATA, ruolo

    def test_non_ci_sono_caselle_lasciate_in_bianco(self):
        simboli = {e for riga in TABELLA_SOSTITUZIONI.values() for e in riga.values()}
        assert simboli <= set(Esito)
        assert Esito.LIBERA in simboli and Esito.VIETATA in simboli


class TestAsimmetria:
    """Il principio del regolamento: si copre con la stessa linea o piu' arretrata."""

    def test_una_punta_non_copre_un_difensore(self):
        for difensore in ("B", "Dc", "Dd", "Ds"):
            for attaccante in ("Pc", "A", "T", "W"):
                assert esito_grezzo(difensore, attaccante) is Esito.VIETATA, (
                    f"{attaccante} non dovrebbe poter coprire {difensore}"
                )

    def test_un_difensore_copre_una_punta_pagando(self):
        for attaccante in ("Pc", "A", "T"):
            for difensore in ("B", "Dc", "Dd", "Ds"):
                assert esito_grezzo(attaccante, difensore) is Esito.MALUS, (
                    f"{difensore} dovrebbe coprire {attaccante} col malus"
                )

    def test_i_centrocampisti_non_coprono_i_difensori(self):
        for difensore in ("B", "Dc", "Dd", "Ds"):
            for centrocampista in ("C", "M", "E"):
                assert esito_grezzo(difensore, centrocampista) is Esito.VIETATA

    def test_fra_difensori_ci_si_copre_sempre(self):
        for uscito in ("B", "Dc", "Dd", "Ds"):
            for entrato in ("B", "Dc", "Dd", "Ds"):
                assert esito_grezzo(uscito, entrato).possibile


class TestDueRuoliPerGiocatore:
    def test_vale_la_casella_migliore(self):
        # Un «Dd/E» che entra per un «M»: da Dd sarebbe malus, da E pure —
        # ma per un «C/T» il ruolo C entra gratis.
        assert esito_sostituzione(("M",), ("Dd", "E")) is Esito.MALUS
        assert esito_sostituzione(("M", "C"), ("C", "T")) is Esito.LIBERA

    def test_un_ruolo_sconosciuto_non_fa_entrare_nessuno(self):
        assert esito_sostituzione(("Dc",), ("Attaccante",)) is Esito.VIETATA
        assert esito_sostituzione((), ("Dc",)) is Esito.VIETATA
        assert esito_sostituzione(("Dc",), ()) is Esito.VIETATA


class TestAsterischi:
    """La legenda: «OK negli schemi con i ruoli in alternativa»."""

    def test_sono_quindici(self):
        speciali = [
            (uscito, entrato)
            for uscito, riga in TABELLA_SOSTITUZIONI.items()
            for entrato, esito in riga.items()
            if esito in ASTERISCHI_NON_IN_ALTERNATIVA
        ]
        assert len(speciali) == 15

    def test_in_alternativa_e_sempre_gratis(self):
        # Una punta in una casella «A/Pc» non paga: il ruolo e' fra quelli che
        # la casella ammette, e li' l'asterisco vale OK.
        assert esito_grezzo("A", "Pc") is Esito.SPECIALE_1
        assert esito_in_casella(("A", "Pc"), ("Pc",)) is Esito.LIBERA

    def test_un_asterisco_solo_e_altrimenti_un_divieto(self):
        # Se la casella e' una «A» pura, lo stesso Pc non ci va proprio.
        assert esito_in_casella(("A",), ("Pc",)) is Esito.VIETATA

    def test_due_asterischi_altrimenti_costano(self):
        # Dc <- B e' «**»: nella casella «Dc/B» gratis, in una «Dc» pura si paga.
        assert esito_grezzo("Dc", "B") is Esito.SPECIALE_2
        assert esito_in_casella(("Dc", "B"), ("B",)) is Esito.LIBERA
        assert esito_in_casella(("Dc",), ("B",)) is Esito.MALUS

    def test_tre_asterischi_sono_vietati_solo_nel_4_1_4_1(self):
        # T <- W e' «***»: in una casella «W/T» e' gratis, altrove si paga, e
        # nel 4-1-4-1 — dove le due caselle sono separate — non si puo'.
        assert esito_grezzo("T", "W") is Esito.SPECIALE_3
        assert esito_in_casella(("W", "T"), ("W",), "4-2-3-1") is Esito.LIBERA
        assert esito_in_casella(("T",), ("W",), "3-4-1-2") is Esito.MALUS
        assert esito_in_casella(("T",), ("W",), "4-1-4-1") is Esito.VIETATA


class TestCaselleDeiModuli:
    """Gli schemi ufficiali: undici caselle, e i conti che tornano."""

    def test_ogni_modulo_ha_undici_caselle(self):
        for nome, caselle in CASELLE_PER_MODULO.items():
            assert len(caselle) == 11, nome

    def test_ogni_modulo_comincia_col_portiere(self):
        for nome, caselle in CASELLE_PER_MODULO.items():
            assert caselle[0] == ("Por",), nome

    def test_il_portiere_non_compare_altrove(self):
        for nome, caselle in CASELLE_PER_MODULO.items():
            for casella in caselle[1:]:
                assert "Por" not in casella, nome

    def test_i_numeri_del_nome_tornano(self):
        # Il controllo vero lo fa il modulo quando si carica: qui si verifica
        # che ci sia, perche' e' l'unica rete contro una trascrizione storta.
        import re

        for nome, caselle in CASELLE_PER_MODULO.items():
            assert sum(int(n) for n in re.findall(r"\d+", nome)) == len(caselle) - 1

    def test_un_modulo_che_non_conosciamo_non_esplode(self):
        assert caselle_di("5-3-2") == ()
        assert caselle_di("") == ()


class TestCosto:
    def test_gratis_paga_zero(self):
        assert costo_in_casella(("Dc",), ("Dc",), malus=1.0) == 0.0

    def test_adattato_paga_il_malus(self):
        assert costo_in_casella(("Dc",), ("Dd",), malus=1.0) == pytest.approx(1.0)

    def test_vietato_non_ha_prezzo(self):
        assert costo_in_casella(("Dc",), ("Pc",), malus=1.0) is None
