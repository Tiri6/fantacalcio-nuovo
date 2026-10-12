"""La finestra per correggere gli anni di contratto dopo una draft room.

Il draft si fa di corsa: un contratto scritto male va potuto correggere prima
che conti. La finestra si chiude con l'inizio della giornata successiva, lo
stesso istante in cui si bloccano le formazioni — e non e' un caso che sia lo
stesso: «il giorno prima della giornata» e «il giorno della giornata» sono due
frasi diverse di ventiquattr'ore, mentre il calcio d'inizio e' un istante solo
su cui sono d'accordo tutte e due.
"""

from datetime import datetime, timedelta

from fantacalcio.contratti import finestra_modifica_anni

DRAFT = datetime(2026, 10, 3, 22, 0)
GIORNATA = datetime(2026, 10, 10, 15, 0)


class TestQuandoSiApre:
    def test_senza_draft_conclusa_non_si_apre(self):
        """Altrimenti gli anni si cambierebbero tutto l'anno, che e' la cosa
        che l'articolo 8 vieta."""
        finestra = finestra_modifica_anni(None, GIORNATA, adesso=DRAFT)

        assert finestra.aperta is False
        assert "draft room" in finestra.motivo

    def test_prima_che_la_draft_chiuda_non_si_apre(self):
        finestra = finestra_modifica_anni(
            DRAFT, GIORNATA, adesso=DRAFT - timedelta(hours=1)
        )

        assert finestra.aperta is False
        assert "non e' ancora chiusa" in finestra.motivo

    def test_appena_la_draft_chiude_si_apre(self):
        finestra = finestra_modifica_anni(DRAFT, GIORNATA, adesso=DRAFT)

        assert finestra.aperta is True
        assert finestra.motivo == ""


class TestQuandoSiChiude:
    def test_si_chiude_col_calcio_d_inizio_della_giornata_dopo(self):
        finestra = finestra_modifica_anni(
            DRAFT, GIORNATA, adesso=DRAFT + timedelta(days=3)
        )

        assert finestra.aperta is True
        assert finestra.chiude_il == GIORNATA - timedelta(minutes=1)

    def test_il_giorno_prima_e_ancora_aperta(self):
        """«Mercato a inizio ottobre, modificabili fino al 10»: il 9 si puo'."""
        finestra = finestra_modifica_anni(
            DRAFT, GIORNATA, adesso=datetime(2026, 10, 9, 23, 59)
        )

        assert finestra.aperta is True

    def test_la_mattina_della_giornata_e_ancora_aperta(self):
        """L'altra frase della lega, «fino al giorno della giornata», e' questa:
        finche' non si gioca, si corregge."""
        finestra = finestra_modifica_anni(
            DRAFT, GIORNATA, adesso=datetime(2026, 10, 10, 9, 0)
        )

        assert finestra.aperta is True

    def test_a_giornata_cominciata_e_chiusa(self):
        finestra = finestra_modifica_anni(
            DRAFT, GIORNATA, adesso=GIORNATA + timedelta(minutes=1)
        )

        assert finestra.aperta is False
        assert "10/10" in finestra.motivo

    def test_si_chiude_nello_stesso_istante_delle_formazioni(self):
        """Un istante solo per due blocchi: quando comincia la giornata, non si
        tocca piu' ne' chi gioca ne' con che contratto."""
        from fantacalcio.formazioni import stato_blocco

        un_attimo_prima = GIORNATA - timedelta(minutes=2)
        un_attimo_dopo = GIORNATA - timedelta(seconds=30)

        for quando in (un_attimo_prima, un_attimo_dopo):
            formazioni = stato_blocco(GIORNATA, quando)
            anni = finestra_modifica_anni(DRAFT, GIORNATA, adesso=quando)
            assert anni.aperta is formazioni.modificabile, quando


class TestSenzaCalendario:
    def test_una_giornata_non_programmata_non_chiude_niente(self):
        """Chiudere su una scadenza che nessuno ha fissato sarebbe peggio che
        lasciare aperto: e' la stessa scelta di `stato_blocco`."""
        finestra = finestra_modifica_anni(DRAFT, None, adesso=DRAFT)

        assert finestra.aperta is True
        assert finestra.chiude_il is None
        assert "Nessuna giornata in programma" in finestra.motivo


class TestLOpzioneDellaLega:
    def test_e_accesa_di_partenza_ma_si_puo_spegnere(self):
        """Finche' l'articolo 8 non e' votato, la lega decide da li'."""
        from dataclasses import replace

        from fantacalcio.leghe import OpzioniLega

        assert OpzioniLega().modifica_anni_dopo_draft is True
        spenta = replace(OpzioniLega(), modifica_anni_dopo_draft=False)
        assert spenta.modifica_anni_dopo_draft is False

    def test_la_chat_sul_regolamento_la_vede_da_sola(self):
        """`scheda_regolamento` scorre i campi delle opzioni: un'opzione nuova
        arriva alla chat senza che nessuno la ricopi nel prompt."""
        from datetime import date

        from fantacalcio.assistente import scheda_regolamento
        from fantacalcio.leghe import OpzioniLega
        from fantacalcio.regole import ParametriLega

        scheda = scheda_regolamento(
            ParametriLega(),
            OpzioniLega(),
            nome_lega="Prova",
            data_u21=date(2026, 8, 31),
        )

        assert "modifica_anni_dopo_draft" in scheda
