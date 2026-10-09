from dataclasses import replace
from datetime import date

from conftest import DATA_DRAFT, costruisci_rosa, giocatore

from fantacalcio.conformita import Gravita, Momento, verifica_rosa
from fantacalcio.modelli import VoceDeadMoney
from fantacalcio.regole import ParametriLega


def codici(stato) -> set[str]:
    return {v.codice for v in stato.violazioni}


class TestRosaConforme:
    def test_nessuna_violazione(self, rosa):
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.violazioni == ()
        assert stato.conforme

    def test_fotografia_coerente(self, rosa):
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.dimensione == 30
        assert stato.anni_impegnati == 10 * 1 + 20 * 2
        assert stato.anni_disponibili == 66 - stato.anni_impegnati
        assert stato.monte_ingaggi == 90_000_000
        assert stato.spazio_salariale == 10_000_000


class TestDimensioneRosa:
    def test_sotto_il_minimo_blocca_a_fine_mercato(self):
        rosa = costruisci_rosa(dimensione=29)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.RIPARAZIONE)
        assert "rosa_minima" in codici(stato)
        assert not stato.conforme

    def test_sotto_il_minimo_in_stagione_e_solo_avviso(self):
        rosa = costruisci_rosa(dimensione=29)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        violazione = next(v for v in stato.violazioni if v.codice == "rosa_minima")
        assert violazione.gravita is Gravita.AVVISO
        assert stato.conforme

    def test_sopra_il_massimo_senza_u21(self):
        rosa = costruisci_rosa(dimensione=34, annuali=12)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert "rosa_massima" in codici(stato)

    def test_un_u21_amplia_il_limite_di_un_posto(self):
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 1
        assert stato.limite_dimensione == 34
        assert "rosa_massima" not in codici(stato)

    def test_tre_u21_portano_a_trentasei(self):
        rosa = costruisci_rosa(dimensione=36, annuali=12, u21=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.limite_dimensione == 36
        assert "rosa_massima" not in codici(stato)

    def test_u21_straniero_non_da_diritto_al_posto(self):
        """Articolo 2: il posto extra spetta solo all'Under 21 italiano."""
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        u21 = min(rosa._indice.values(), key=lambda g: g.id)
        rosa._indice[u21.id] = replace(u21, nazionalita="Francia")

        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 0
        assert "rosa_massima" in codici(stato)

    def test_ventunenne_al_draft_non_e_piu_u21(self):
        """Chi compie 21 anni prima del draft perde lo status per la stagione."""
        rosa = costruisci_rosa(dimensione=34, annuali=12, u21=1)
        u21 = min(rosa._indice.values(), key=lambda g: g.id)
        from datetime import date

        rosa._indice[u21.id] = replace(u21, data_nascita=date(2005, 1, 1))

        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 0


class TestPortieri:
    def test_quattro_portieri_bloccano(self):
        stato = verifica_rosa(costruisci_rosa(portieri=4), DATA_DRAFT)
        assert "portieri" in codici(stato)

    def test_meno_di_tre_portieri_e_una_violazione(self):
        """Il V3 torna a «3 Portieri obbligatori»: non e' solo un tetto."""
        stato = verifica_rosa(costruisci_rosa(portieri=2), DATA_DRAFT)
        assert "portieri_minimo" in codici(stato)

    def test_tre_portieri_vanno_bene(self):
        stato = verifica_rosa(costruisci_rosa(portieri=3), DATA_DRAFT)
        assert "portieri_minimo" not in codici(stato)
        assert "portieri" not in codici(stato)

    def test_portiere_in_meno_in_stagione_e_solo_un_avviso(self):
        """Durante la stagione si rimpiazza al mercato, non si blocca tutto."""
        stato = verifica_rosa(
            costruisci_rosa(portieri=2), DATA_DRAFT, momento=Momento.STAGIONE
        )
        manca = next(v for v in stato.violazioni if v.codice == "portieri_minimo")
        assert not manca.bloccante

    def test_portiere_in_meno_blocca_la_chiusura_dell_asta(self):
        stato = verifica_rosa(
            costruisci_rosa(portieri=2), DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE
        )
        manca = next(v for v in stato.violazioni if v.codice == "portieri_minimo")
        assert manca.bloccante


class TestMonteAnni:
    def test_oltre_sessantasei_anni_blocca(self):
        # 30 giocatori: 5 annuali + 25 da 3 anni = 80 anni.
        rosa = costruisci_rosa(annuali=5, anni_altri=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.anni_impegnati == 80
        assert "monte_anni" in codici(stato)

    def test_esattamente_sessantasei_e_ammesso(self):
        # 30 giocatori: 24 annuali + 6 da 7... serve una combinazione valida:
        # 12 annuali + 18 da 3 anni = 66.
        rosa = costruisci_rosa(annuali=12, anni_altri=3)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.anni_impegnati == 66
        assert "monte_anni" not in codici(stato)

    def test_contratto_oltre_cinque_anni_blocca(self):
        rosa = costruisci_rosa(dimensione=30, annuali=29, anni_altri=6)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert "durata_contratto" in codici(stato)


class TestRegolaUnTerzo:
    def test_annuali_insufficienti_bloccano_a_fine_mercato(self):
        rosa = costruisci_rosa(dimensione=30, annuali=9)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        violazione = next(v for v in stato.violazioni if v.codice == "regola_un_terzo")
        assert violazione.valore == 9
        assert violazione.limite == 10
        assert not stato.conforme

    def test_in_stagione_e_solo_avviso(self):
        rosa = costruisci_rosa(dimensione=30, annuali=9)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        assert stato.conforme

    def test_rosa_ampliata_alza_la_soglia(self):
        """34 giocatori richiedono 12 annuali, non piu' 10."""
        rosa = costruisci_rosa(dimensione=34, annuali=11, u21=1)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.annuali_richiesti == 12
        assert "regola_un_terzo" in codici(stato)


class TestEconomia:
    def test_sopra_il_cap_blocca_a_fine_asta(self):
        rosa = costruisci_rosa(ingaggio=3_500_000)  # 105M
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert "salary_cap" in codici(stato)
        assert not stato.conforme

    def test_sopra_il_cap_in_stagione_e_solo_avviso(self):
        """Articolo 8b: lo sforamento da scambio si sana prima dell'asta."""
        rosa = costruisci_rosa(ingaggio=3_500_000)
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.STAGIONE)
        violazione = next(v for v in stato.violazioni if v.codice == "salary_cap")
        assert violazione.gravita is Gravita.AVVISO
        assert stato.conforme

    def test_col_v3_il_floor_non_esiste(self):
        """Il regolamento V3 non prevede nessuna soglia minima di spesa.

        L'articolo 4 parla solo del tetto massimo, e vale il principio di
        tassativita': «e' consentito solo cio' che il regolamento prevede
        espressamente». Una squadra che spende poco non sta violando niente.
        """
        rosa = costruisci_rosa(ingaggio=2_000_000)  # 60M, sotto i vecchi 80M
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.RIPARAZIONE)
        assert "salary_floor" not in codici(stato)

    def test_sotto_il_floor_blocca_a_fine_asta_se_la_lega_lo_riaccende(self):
        """Il meccanismo resta: basta un lodo per rimetterlo in funzione."""
        con_floor = ParametriLega(salary_floor_attivo=True)
        rosa = costruisci_rosa(ingaggio=2_000_000)  # 60M
        stato = verifica_rosa(rosa, DATA_DRAFT, con_floor, momento=Momento.RIPARAZIONE)
        assert "salary_floor" in codici(stato)

    def test_il_floor_non_si_verifica_in_stagione(self):
        con_floor = ParametriLega(salary_floor_attivo=True)
        rosa = costruisci_rosa(ingaggio=2_000_000)
        stato = verifica_rosa(rosa, DATA_DRAFT, con_floor, momento=Momento.STAGIONE)
        assert "salary_floor" not in codici(stato)


class TestDeadMoney:
    def test_pesa_sul_cap(self):
        rosa = costruisci_rosa(ingaggio=3_200_000)  # 96M di ingaggi
        rosa.dead_money = [VoceDeadMoney(1, "Tagliato", 6_000_000, "2026/27")]

        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.spesa_salariale == 102_000_000
        assert "salary_cap" in codici(stato)

    def test_non_conta_per_il_floor(self):
        """La soglia minima, dove la lega la usi, va raggiunta con gli ingaggi.

        Il V3 il floor non ce l'ha, quindi il caso si prova accendendolo:
        la buonuscita non deve poter far figurare una rosa come se spendesse
        piu' di quanto spende davvero.
        """
        con_floor = ParametriLega(salary_floor_attivo=True)
        rosa = costruisci_rosa(ingaggio=2_500_000)  # 75M, sotto gli 80M
        rosa.dead_money = [VoceDeadMoney(1, "Tagliato", 20_000_000, "2026/27")]

        stato = verifica_rosa(rosa, DATA_DRAFT, con_floor, momento=Momento.ASTA_SETTEMBRE)
        assert stato.monte_ingaggi == 75_000_000
        assert "salary_floor" in codici(stato)

    def test_gia_addebitato_non_pesa_piu(self):
        rosa = costruisci_rosa()
        rosa.dead_money = [
            VoceDeadMoney(1, "Tagliato", 9_000_000, "2025/26", addebitato=True)
        ]
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.dead_money == 0
        assert stato.spesa_salariale == 90_000_000


class TestSlotU21Congelati:
    """Art. 2: il numero di Under 21 si ricalcola una volta l'anno.

    «Svincoli o cessioni di Under 21 in corso d'anno non modificano il limite
    fino al ricalcolo successivo»: e' quel che impedisce a una rosa da 35 di
    diventare irregolare per una cessione fatta a mercato aperto.
    """

    def test_senza_congelamento_si_contano_quelli_in_rosa(self):
        """Prima della prima asta non c'e' niente da congelare."""
        rosa = costruisci_rosa(dimensione=34, u21=2)
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 2
        assert stato.limite_dimensione == 35

    def test_il_valore_congelato_vince_sul_conteggio(self):
        rosa = costruisci_rosa(dimensione=34, u21=0)
        rosa.slot_u21_congelato = 2
        stato = verifica_rosa(rosa, DATA_DRAFT)
        assert stato.slot_u21 == 2
        assert stato.limite_dimensione == 35
        assert "rosa_massima" not in codici(stato)

    def _scambia_l_under_con_un_veterano(self, rosa):
        """Come uno scambio vero: entra uno, esce un Under, la rosa resta uguale."""
        parametri = ParametriLega()
        under = next(g for g in rosa.giocatori if g.under_21(DATA_DRAFT, parametri))
        contratto = rosa.contratto_di(under.id)
        # Stesso ruolo: cosi' l'unica cosa che cambia e' l'eta', ed e' l'unica
        # cosa di cui parla la regola.
        veterano = giocatore(99_001, ruoli=under.ruoli, data_nascita=date(1994, 1, 1))
        senza = rosa.senza_giocatore(under.id)
        return senza.con_contratto(replace(contratto, giocatore_id=veterano.id), veterano)

    def test_cedere_un_u21_in_corso_d_anno_non_restringe_la_rosa(self):
        """E' il caso che l'articolo 2 nomina espressamente."""
        rosa = costruisci_rosa(dimensione=34, u21=1)
        rosa.slot_u21_congelato = rosa.u21_in_rosa(DATA_DRAFT, ParametriLega())
        assert rosa.slot_u21_congelato == 1

        dopo = self._scambia_l_under_con_un_veterano(rosa)
        stato = verifica_rosa(dopo, DATA_DRAFT)

        assert dopo.dimensione == 34
        assert dopo.u21_in_rosa(DATA_DRAFT, ParametriLega()) == 0
        assert stato.limite_dimensione == 34
        assert "rosa_massima" not in codici(stato)

    def test_senza_congelamento_la_cessione_restringerebbe(self):
        """Il comportamento di prima, che e' quello che il V3 vieta."""
        rosa = costruisci_rosa(dimensione=34, u21=1)
        dopo = self._scambia_l_under_con_un_veterano(rosa)
        stato = verifica_rosa(dopo, DATA_DRAFT)

        assert dopo.dimensione == 34
        assert stato.limite_dimensione == 33
        assert "rosa_massima" in codici(stato)

    def test_non_si_superano_mai_i_tre_posti(self):
        rosa = costruisci_rosa()
        rosa.slot_u21_congelato = 9
        assert rosa.slot_u21(DATA_DRAFT, ParametriLega()) == 3

    def test_un_valore_negativo_non_toglie_posti(self):
        rosa = costruisci_rosa()
        rosa.slot_u21_congelato = -2
        assert rosa.slot_u21(DATA_DRAFT, ParametriLega()) == 0
