"""Il CSV del draft deve essere letto con tolleranza e validato con rigore."""

from datetime import date

import pandas
import pytest

from fantacalcio.data import carica_rose
from fantacalcio.importazione import (
    CAMPI_RISULTATI,
    CAMPI_ROSE,
    COLONNE_RISULTATI,
    COLONNE_ROSE,
    OBBLIGATORIE_RISULTATI,
    OBBLIGATORIE_ROSE,
    anteprima_conformita,
    applica_calendario,
    applica_risultati,
    applica_rose,
    campi_rose,
    importa_calendario,
    importa_risultati,
    importa_rose,
    leggi_data,
    leggi_numero,
    leggi_ruoli,
    mappa_colonne,
    modello_risultati,
    modello_rose,
    normalizza_intestazione,
)

DATA_DRAFT = date(2026, 9, 15)

INTESTAZIONI = "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;italiano_u21"


def csv_rose(*righe: str) -> str:
    return "\n".join([INTESTAZIONI, *righe])


def rosa_completa(
    squadra: str, quanti: int = 30, ingaggio: str = "3.000.000"
) -> list[str]:
    """Una rosa che rispetta monte anni, regola 1/3 e forbice salariale."""
    righe = []
    for indice in range(quanti):
        ruolo = "Por" if indice < 3 else "Dc"
        anni = 1 if indice < 10 else 2
        righe.append(
            f"{squadra};Giocatore {squadra[:3]}{indice};Inter;{ruolo};"
            f"{ingaggio};{anni};Italia;NO"
        )
    return righe


class TestNormalizzazione:
    @pytest.mark.parametrize(
        "testo,atteso",
        [
            ("Anni Residui ", "anniresidui"),
            ("Nazionalità", "nazionalita"),
            ("ITALIANO_U21", "italianou21"),
            ("Ruolo (Mantra)", "ruolomantra"),
        ],
    )
    def test_intestazioni(self, testo, atteso):
        assert normalizza_intestazione(testo) == atteso

    def test_mappa_riconosce_i_sinonimi(self):
        colonne, ignorate = mappa_colonne(
            ["Fantasquadra", "Calciatore", "Stipendio", "Durata", "RM", "Note"],
            COLONNE_ROSE,
        )
        assert colonne["squadra"] == "Fantasquadra"
        assert colonne["giocatore"] == "Calciatore"
        assert colonne["ingaggio"] == "Stipendio"
        assert colonne["anni"] == "Durata"
        assert colonne["ruoli"] == "RM"
        assert ignorate == ["Note"]

    def test_costo_sono_gli_anni_di_contratto(self):
        """Convenzione della lega: nel loro export 'costo' e' la durata."""
        colonne, _ = mappa_colonne(["Squadra", "Giocatore", "Costo"], COLONNE_ROSE)
        assert colonne["anni"] == "Costo"


class TestLetturaValori:
    @pytest.mark.parametrize(
        "valore,atteso",
        [
            ("3.500.000", 3_500_000),
            ("1500000", 1_500_000),
            ("3,5", 3.5),
            ("3,5M", 3_500_000),
            ("4 mln", 4_000_000),
            ("€ 2.100.000", 2_100_000),
            ("0,75", 0.75),
        ],
    )
    def test_numeri_all_italiana(self, valore, atteso):
        assert leggi_numero(valore) == pytest.approx(atteso)

    @pytest.mark.parametrize("valore", ["", None, "tanti", "3..5,,"])
    def test_numeri_non_leggibili(self, valore):
        with pytest.raises(ValueError):
            leggi_numero(valore)

    @pytest.mark.parametrize(
        "valore,atteso",
        [
            ("Dc", ("Dc",)),
            ("Dc/Dd", ("Dc", "Dd")),
            ("W;T", ("W", "T")),
            ("w, t", ("W", "T")),
        ],
    )
    def test_ruoli(self, valore, atteso):
        assert leggi_ruoli(valore) == atteso

    def test_ruoli_classici_tradotti(self):
        assert leggi_ruoli("P") == ("Por",)
        assert leggi_ruoli("A") == ("A",)

    def test_ruolo_duplicato_compare_una_volta(self):
        assert leggi_ruoli("Dc;Dc") == ("Dc",)

    def test_ruolo_sconosciuto(self):
        with pytest.raises(ValueError, match="sconosciuto"):
            leggi_ruoli("Libero")

    @pytest.mark.parametrize(
        "valore", ["17/04/2001", "2001-04-17", "17-04-2001", "17.04.2001"]
    )
    def test_date(self, valore):
        assert leggi_data(valore) == date(2001, 4, 17)

    def test_data_vuota_ammessa(self):
        assert leggi_data("") is None

    def test_data_illeggibile(self):
        with pytest.raises(ValueError, match="gg/mm/aaaa"):
            leggi_data("il giorno di San Valentino")


class TestImportaRose:
    def test_il_modello_e_importabile(self):
        esito = importa_rose(modello_rose())
        assert esito.importabile
        assert len(esito.righe) == 3

    def test_separatore_virgola(self):
        contenuto = (
            INTESTAZIONI.replace(";", ",")
            + "\n"
            + ("Tiri Team,Rossi,Inter,Dc,2.000.000,3,Italia,NO")
        )
        esito = importa_rose(contenuto)
        assert esito.importabile
        assert esito.righe[0]["ingaggio"] == 2_000_000

    def test_bytes_in_latin1(self):
        contenuto = csv_rose("Tiri Team;Pérez;Inter;Dc;2.000.000;3;Spagna;NO").encode(
            "latin-1"
        )
        esito = importa_rose(contenuto)
        assert esito.importabile
        assert esito.righe[0]["giocatore"] == "Pérez"

    def test_colonne_obbligatorie_mancanti(self):
        esito = importa_rose("squadra;giocatore\nTiri Team;Rossi")
        assert not esito.importabile
        assert "obbligatorie mancanti" in esito.errori[0].messaggio

    def test_file_vuoto(self):
        esito = importa_rose("")
        assert not esito.importabile
        assert esito.errori[0].colonna == "file"

    def test_righe_vuote_ignorate(self):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;NO",
                ";;;;;;;",
                "",
            )
        )
        assert esito.importabile
        assert len(esito.righe) == 1

    def test_contratto_fuori_scala_e_bloccante(self):
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;7;Italia;NO"))
        assert not esito.importabile
        errore = esito.errori[0]
        assert errore.colonna == "anni"
        assert "art. 2" in errore.messaggio.lower()

    def test_il_numero_di_riga_e_quello_del_foglio(self):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;NO",
                "Tiri Team;Bianchi;Inter;Libero;2.000.000;3;Italia;NO",
            )
        )
        # Riga 1 = intestazioni, riga 2 = Rossi, riga 3 = Bianchi.
        assert esito.errori[0].riga == 3

    def test_giocatore_in_due_rose(self):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;NO",
                "Padel United;rossi;Inter;Dc;2.000.000;3;Italia;NO",
            )
        )
        assert not esito.importabile
        assert "una sola rosa" in esito.errori[0].messaggio

    def test_flag_vuoto_vale_no_e_non_e_un_avviso(self):
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;"))
        assert esito.importabile
        assert esito.avvisi == []
        assert esito.righe[0]["italiano_u21"] is False

    def test_riga_disallineata_spiega_la_causa(self):
        """Il caso piu' comune: ruoli scritti "M;C" in un CSV separato da ';'."""
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;M;C;2.000.000;3;Italia;NO"))
        assert not esito.importabile
        errore = esito.errori[0]
        assert errore.colonna == "riga"
        assert "1 colonna in piu'" in errore.messaggio
        assert "Dc/Dd" in errore.messaggio

    def test_ruoli_multipli_con_barra_funzionano(self):
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;M/C;2.000.000;3;Italia;NO"))
        assert esito.importabile
        assert esito.righe[0]["ruoli"] == ("M", "C")

    def test_intestazioni_extra_segnalate_ma_non_bloccanti(self):
        contenuto = (
            (INTESTAZIONI + ";note")
            + "\n"
            + ("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;NO;pick 1")
        )
        esito = importa_rose(contenuto)
        assert esito.importabile
        assert esito.intestazioni_ignorate == ["note"]


class TestItalianoU21:
    """Il flag lo decide la lega: SI/NO, anche nelle varianti piu' comuni."""

    @pytest.mark.parametrize(
        "scritto, atteso",
        [
            ("SI", True),
            ("si", True),
            ("sì", True),
            ("1", True),
            ("true", True),
            ("NO", False),
            ("no", False),
            ("0", False),
            ("false", False),
            ("", False),
        ],
    )
    def test_le_varianti_di_si_e_no(self, scritto, atteso):
        esito = importa_rose(
            csv_rose(f"Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;{scritto}")
        )
        assert esito.importabile, esito.errori
        assert esito.righe[0]["italiano_u21"] is atteso

    def test_un_valore_che_non_e_si_ne_no_blocca_la_riga(self):
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;forse")
        )
        assert not esito.importabile
        assert esito.errori[0].colonna == "italiano_u21"
        assert "non e' SI ne' NO" in esito.errori[0].messaggio

    def test_un_under_21_italiano_non_puo_essere_straniero(self):
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Francia;SI"))
        assert not esito.importabile
        assert "Un Under 21 italiano" in esito.errori[0].messaggio

    def test_senza_la_colonna_il_flag_non_dice_niente(self):
        esito = importa_rose(
            "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita\n"
            "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia"
        )
        assert esito.importabile
        assert esito.righe[0]["italiano_u21"] is None

    def test_i_sinonimi_dell_intestazione(self):
        for nome in ("Italiano U21", "u21", "italiano_u21"):
            esito = importa_rose(
                f"squadra;giocatore;club;ruoli;ingaggio;anni;{nome}\n"
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;SI"
            )
            assert esito.righe[0]["italiano_u21"] is True, nome

    def test_il_modello_scaricabile_ha_il_formato_nuovo(self):
        intestazione = modello_rose().splitlines()[0]
        assert "italiano_u21" in intestazione
        assert "data_nascita" not in intestazione
        assert "prolungato" not in intestazione


class TestAnteprimaConformita:
    def test_una_rosa_completa_e_conforme(self):
        esito = importa_rose(csv_rose(*rosa_completa("Tiri Team")))
        stati = anteprima_conformita(esito, DATA_DRAFT)
        assert stati["Tiri Team"].conforme

    def test_rosa_incompleta_segnalata_prima_di_scrivere(self):
        esito = importa_rose(csv_rose(*rosa_completa("Tiri Team", quanti=20)))
        stato = anteprima_conformita(esito, DATA_DRAFT)["Tiri Team"]
        assert not stato.conforme
        assert "rosa_minima" in {v.codice for v in stato.violazioni}

    def test_sforamento_del_cap_visto_in_anteprima(self):
        esito = importa_rose(csv_rose(*rosa_completa("Tiri Team", ingaggio="4.000.000")))
        stato = anteprima_conformita(esito, DATA_DRAFT)["Tiri Team"]
        assert "salary_cap" in {v.codice for v in stato.violazioni}


class TestApplicaRose:
    @pytest.fixture
    def archivio(self, archivio_demo):
        return archivio_demo

    def test_scrive_le_rose_importate(self, archivio):
        esito = importa_rose(
            csv_rose(*rosa_completa("Tiri Team"), *rosa_completa("Padel United"))
        )
        riepilogo = applica_rose(archivio, esito, sostituisci=True)

        assert riepilogo["giocatori"] == 60
        rose = carica_rose(archivio)
        per_nome = {r.squadra.nome: r for r in rose.values()}
        assert per_nome["Tiri Team"].dimensione == 30
        assert per_nome["Tiri Team"].monte_ingaggi == 90_000_000

    def test_le_squadre_esistenti_mantengono_l_identita(self, archivio):
        prima = archivio.squadre()
        motto_originale = prima[prima["nome"] == "Tiri Team"]["motto"].iloc[0]

        esito = importa_rose(csv_rose(*rosa_completa("Tiri Team")))
        applica_rose(archivio, esito, sostituisci=True)

        dopo = archivio.squadre()
        assert dopo[dopo["nome"] == "Tiri Team"]["motto"].iloc[0] == motto_originale

    def test_crea_le_squadre_nuove(self, archivio):
        quante_prima = len(archivio.squadre())
        esito = importa_rose(csv_rose(*rosa_completa("Squadra Inedita")))
        riepilogo = applica_rose(archivio, esito, sostituisci=True)

        assert riepilogo["squadre_create"] == 1
        assert len(archivio.squadre()) == quante_prima + 1

    def test_rifiuta_un_esito_con_errori(self, archivio):
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi;Inter;Libero;2.000.000;3;Italia;NO")
        )
        with pytest.raises(ValueError, match="errori da correggere"):
            applica_rose(archivio, esito)


class TestCosaUnImportNonPerde:
    """Il CSV non porta data di nascita ne' prolungamento: restano del database."""

    @pytest.fixture
    def archivio(self, archivio_demo):
        # Una rosa piccola e nota: due giocatori, uno dei quali ha gia' usato il
        # prolungamento da scambio (Lodo Corti) in una stagione.
        archivio_demo.svuota("contratti")
        archivio_demo.svuota("giocatori")
        base = {"club": "Roma", "ruoli": "Dc", "nazionalita": "Italia"}
        archivio_demo.scrivi(
            "giocatori",
            [
                {
                    **base,
                    "id": 1,
                    "nome": "Rossi Marco",
                    "ingaggio": 2_000_000,
                    "data_nascita": "2005-10-01",
                    "italiano_u21": 1,
                },
                {
                    **base,
                    "id": 2,
                    "nome": "Bianchi Luca",
                    "ingaggio": 1_000_000,
                    "data_nascita": None,
                    "italiano_u21": 0,
                },
            ],
            chiave="id",
        )
        archivio_demo.scrivi(
            "contratti",
            [
                {
                    "giocatore_id": 1,
                    "squadra_id": 1,
                    "anni_residui": 2,
                    "prolungato": 1,
                    "stagione_prolungamento": "2025/26",
                },
                {
                    "giocatore_id": 2,
                    "squadra_id": 1,
                    "anni_residui": 1,
                    "prolungato": 0,
                    "stagione_prolungamento": None,
                },
            ],
            chiave="giocatore_id",
        )
        return archivio_demo

    def righe(self, archivio):
        giocatori = archivio.giocatori().set_index("nome")
        contratti = archivio.contratti().set_index("giocatore_id")
        return {
            nome: (g, contratti.loc[int(g["id"])]) for nome, g in giocatori.iterrows()
        }

    def test_il_prolungamento_resta_anche_se_il_file_non_ne_parla(self, archivio):
        """Il caso che conta: un import non azzera mai `prolungato`."""
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia;SI",
                "Tiri Team;Bianchi Luca;Roma;Dc;1.500.000;2;Italia;NO",
            )
        )
        applica_rose(archivio, esito, sostituisci=True)

        rossi, contratto = self.righe(archivio)["Rossi Marco"]
        assert int(contratto["prolungato"]) == 1
        assert contratto["stagione_prolungamento"] == "2025/26"
        # Gli anni e l'ingaggio, invece, sono quelli del file nuovo.
        assert int(contratto["anni_residui"]) == 3
        assert rossi["ingaggio"] == 2_500_000
        _, altro = self.righe(archivio)["Bianchi Luca"]
        assert int(altro["prolungato"]) == 0

    def test_un_file_vecchio_con_prolungato_no_non_lo_azzera(self, archivio):
        """Chi ha ancora la colonna `prolungato` nel foglio non cancella lo stato."""
        vecchio = (
            "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;prolungato\n"
            "Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia;no\n"
        )
        applica_rose(archivio, importa_rose(vecchio), sostituisci=True)

        _, contratto = self.righe(archivio)["Rossi Marco"]
        assert int(contratto["prolungato"]) == 1

    def test_un_file_vecchio_con_prolungato_si_non_lo_accende(self, archivio):
        vecchio = (
            "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;prolungato\n"
            "Tiri Team;Bianchi Luca;Roma;Dc;1.500.000;2;Italia;si\n"
        )
        applica_rose(archivio, importa_rose(vecchio), sostituisci=True)

        _, contratto = self.righe(archivio)["Bianchi Luca"]
        assert int(contratto["prolungato"]) == 0

    def test_la_data_di_nascita_non_si_cancella(self, archivio):
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia;SI")
        )
        applica_rose(archivio, esito, sostituisci=True)

        rossi, _ = self.righe(archivio)["Rossi Marco"]
        assert rossi["data_nascita"] == "2005-10-01"

    def test_la_data_nel_file_si_ignora(self, archivio):
        vecchio = (
            "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;datanascita\n"
            "Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia;01/01/1990\n"
        )
        applica_rose(archivio, importa_rose(vecchio), sostituisci=True)

        rossi, _ = self.righe(archivio)["Rossi Marco"]
        assert rossi["data_nascita"] == "2005-10-01"

    def test_il_flag_del_file_vince(self, archivio):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia;NO",
                "Tiri Team;Bianchi Luca;Roma;Dc;1.500.000;2;Italia;SI",
            )
        )
        applica_rose(archivio, esito, sostituisci=True)

        righe = self.righe(archivio)
        assert int(righe["Rossi Marco"][0]["italiano_u21"]) == 0
        assert int(righe["Bianchi Luca"][0]["italiano_u21"]) == 1

    def test_senza_la_colonna_il_flag_resta_com_era(self, archivio):
        senza = (
            "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita\n"
            "Tiri Team;Rossi Marco;Roma;Dc;2.500.000;3;Italia\n"
            "Tiri Team;Bianchi Luca;Roma;Dc;1.500.000;2;Italia\n"
        )
        applica_rose(archivio, importa_rose(senza), sostituisci=True)

        righe = self.righe(archivio)
        assert int(righe["Rossi Marco"][0]["italiano_u21"]) == 1
        assert int(righe["Bianchi Luca"][0]["italiano_u21"]) == 0

    def test_un_giocatore_nuovo_parte_senza_flag(self, archivio):
        esito = importa_rose(
            csv_rose("Tiri Team;Nuovo Arrivato;Roma;Dc;1.500.000;2;Italia;")
        )
        applica_rose(archivio, esito, sostituisci=True)

        nuovo, contratto = self.righe(archivio)["Nuovo Arrivato"]
        assert int(nuovo["italiano_u21"]) == 0
        assert int(contratto["prolungato"]) == 0


class TestRisultati:
    def test_il_modello_e_importabile(self):
        esito = importa_risultati(modello_risultati())
        assert esito.importabile
        assert esito.righe[0]["punti_casa"] == pytest.approx(72.5)

    def test_squadra_contro_se_stessa(self):
        esito = importa_risultati(
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            "1;Tiri Team;Tiri Team;70;66"
        )
        assert not esito.importabile
        assert "contro se stessa" in esito.errori[0].messaggio

    def test_giornata_non_valida(self):
        esito = importa_risultati(
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n0;A;B;70;66"
        )
        assert not esito.importabile

    def test_una_squadra_due_volte_nella_stessa_giornata(self):
        esito = importa_risultati(
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            "1;Tiri Team;Padel United;70;66\n"
            "1;Tiri Team;Real Bisalta;70;66"
        )
        assert len(esito.righe) == 1
        assert "compare gia' nella giornata 1" in esito.errori[0].messaggio

    def test_applica_aggiorna_la_partita_esistente(self, archivio_demo):
        """Il calendario esiste gia': importare i punti non deve duplicarlo."""
        archivio = archivio_demo
        squadre = archivio.squadre()
        nomi = dict(zip(squadre["id"], squadre["nome"], strict=True))
        calendario = archivio.calendario()
        prima = calendario[calendario["giornata"] == 1]
        casa_id = int(prima.iloc[0]["casa_id"])
        trasferta_id = int(prima.iloc[0]["trasferta_id"])

        esito = importa_risultati(
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            f"1;{nomi[casa_id]};{nomi[trasferta_id]};72,0;65,5"
        )
        applica_risultati(archivio, esito)

        dopo = archivio.calendario()
        assert len(dopo[dopo["giornata"] == 1]) == len(prima)

        partita = dopo[
            (dopo["giornata"] == 1)
            & (dopo["casa_id"] == casa_id)
            & (dopo["trasferta_id"] == trasferta_id)
        ].iloc[0]
        # 72 punti = 2 gol (primo gol a 66, poi uno ogni 6); 65,5 = nessun gol.
        assert partita["gol_casa"] == 2
        assert partita["gol_trasferta"] == 0

    def test_accoppiamento_in_conflitto_col_calendario(self, archivio_demo):
        """Se la squadra e' gia' impegnata in quella giornata, meglio fermarsi."""
        archivio = archivio_demo
        squadre = archivio.squadre()
        nomi = dict(zip(squadre["id"], squadre["nome"], strict=True))
        calendario = archivio.calendario()
        prima = calendario[calendario["giornata"] == 1]
        casa = nomi[int(prima.iloc[0]["casa_id"])]
        altra = nomi[int(prima.iloc[1]["casa_id"])]

        esito = importa_risultati(
            f"giornata;casa;trasferta;punti_casa;punti_trasferta\n1;{casa};{altra};70;66"
        )
        with pytest.raises(ValueError, match="gia' impegnata"):
            applica_risultati(archivio, esito)

    def test_squadra_sconosciuta(self, archivio_demo):
        archivio = archivio_demo
        esito = importa_risultati(
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            "1;Marziani FC;Padel United;70;66"
        )
        with pytest.raises(ValueError, match="non presenti in lega"):
            applica_risultati(archivio, esito)


class TestListone:
    """Il listone ufficiale di Fantacalcio.it: anagrafica e quotazioni."""

    def costruisci_xlsx(self, righe: list[tuple]) -> bytes:
        import io

        from openpyxl import Workbook

        cartella = Workbook()
        foglio = cartella.active
        foglio.title = "Tutti"
        foglio.append(("Quotazioni Fantacalcio Stagione 2026 27",))
        foglio.append(
            (
                "Id",
                "R",
                "RM",
                "Nome",
                "Squadra",
                "Qt.A",
                "Qt.I",
                "Diff.",
                "Qt.A M",
                "Qt.I M",
                "Diff.M",
                "FVM",
                "FVM M",
            )
        )
        for riga in righe:
            foglio.append(riga)
        buffer = io.BytesIO()
        cartella.save(buffer)
        return buffer.getvalue()

    def test_legge_anagrafica_e_quotazioni(self):
        from fantacalcio.importazione import importa_listone

        contenuto = self.costruisci_xlsx(
            [(5841, "P", "Por", "Svilar", "Roma", 18, 18, 0, 18, 18, 0, 65, 65)]
        )
        esito = importa_listone(contenuto)

        assert esito.importabile
        riga = esito.righe[0]
        assert riga["id_ufficiale"] == 5841
        assert riga["nome"] == "Svilar"
        assert riga["club"] == "Roma"
        assert riga["ruoli"] == ("Por",)
        assert riga["quotazione"] == 18

    def test_ruoli_mantra_multipli(self):
        from fantacalcio.importazione import importa_listone

        contenuto = self.costruisci_xlsx(
            [(254, "D", "E;W", "Dimarco", "Inter", 32, 32, 0, 30, 30, 0, 265, 265)]
        )
        assert importa_listone(contenuto).righe[0]["ruoli"] == ("E", "W")

    def test_il_braccetto_e_un_ruolo_valido(self):
        """Ruolo B della difesa a tre: c'e' nel listone vero."""
        from fantacalcio.importazione import importa_listone

        contenuto = self.costruisci_xlsx(
            [(1, "D", "B;Dc", "Tizio", "Atalanta", 10, 10, 0, 10, 10, 0, 30, 30)]
        )
        esito = importa_listone(contenuto)
        assert esito.importabile
        assert esito.righe[0]["ruoli"] == ("B", "Dc")

    def test_id_duplicati_ignorati(self):
        from fantacalcio.importazione import importa_listone

        contenuto = self.costruisci_xlsx(
            [
                (1, "P", "Por", "Tizio", "Roma", 1, 1, 0, 1, 1, 0, 1, 1),
                (1, "P", "Por", "Tizio", "Roma", 1, 1, 0, 1, 1, 0, 1, 1),
            ]
        )
        assert len(importa_listone(contenuto).righe) == 1

    def test_file_non_excel(self):
        from fantacalcio.importazione import importa_listone

        esito = importa_listone(b"non sono un xlsx")
        assert not esito.importabile
        assert esito.errori[0].colonna == "file"

    def test_applica_conserva_ingaggi_e_contratti(self, archivio_demo):
        """Ri-caricare il listone non deve azzerare gli ingaggi Capology."""
        from fantacalcio.importazione import applica_listone, importa_listone

        archivio = archivio_demo
        contenuto = self.costruisci_xlsx(
            [(5841, "P", "Por", "Svilar", "Roma", 18, 18, 0, 18, 18, 0, 65, 65)]
        )
        applica_listone(archivio, importa_listone(contenuto))

        # Il presidente inserisce l'ingaggio vero.
        giocatori = archivio.giocatori()
        identificativo = int(giocatori[giocatori["id_ufficiale"] == 5841]["id"].iloc[0])
        archivio.scrivi(
            "giocatori",
            [
                {
                    "id": identificativo,
                    "id_ufficiale": 5841,
                    "nome": "Svilar",
                    "club": "Roma",
                    "ruoli": "Por",
                    "ingaggio": 4_500_000,
                    "nazionalita": "Serbia",
                    "data_nascita": None,
                    "quotazione": 18,
                    "fvm": 65,
                }
            ],
            chiave="id",
        )

        # Il listone si aggiorna: il club cambia, l'ingaggio no.
        aggiornato = self.costruisci_xlsx(
            [(5841, "P", "Por", "Svilar", "Milan", 20, 20, 0, 20, 20, 0, 70, 70)]
        )
        riepilogo = applica_listone(archivio, importa_listone(aggiornato))

        assert riepilogo["aggiornati"] == 1
        assert riepilogo["nuovi"] == 0
        riga = archivio.giocatori().query("id_ufficiale == 5841").iloc[0]
        assert riga["club"] == "Milan"
        assert riga["ingaggio"] == 4_500_000
        assert riga["nazionalita"] == "Serbia"


class TestRoseRisolteDalListone:
    """Con il catalogo caricato, il file delle rose puo' essere minimale."""

    @pytest.fixture
    def catalogo(self):
        return {
            "svilar": {"nome": "Svilar", "club": "Roma", "ruoli": ("Por",)},
            "dimarco": {"nome": "Dimarco", "club": "Inter", "ruoli": ("E", "W")},
        }

    def test_ruoli_e_club_dal_catalogo(self, catalogo):
        esito = importa_rose(
            "squadra;giocatore;anni;ingaggio\nTiri Team;Svilar;3;4.500.000",
            catalogo=catalogo,
        )
        assert esito.importabile
        riga = esito.righe[0]
        assert riga["ruoli"] == ("Por",)
        assert riga["club"] == "Roma"

    def test_il_nome_prende_la_grafia_del_listone(self, catalogo):
        esito = importa_rose(
            "squadra;giocatore;anni;ingaggio\nTiri Team;  svilar ;3;4.500.000",
            catalogo=catalogo,
        )
        assert esito.righe[0]["giocatore"] == "Svilar"

    def test_nome_sconosciuto_con_suggerimento(self, catalogo):
        esito = importa_rose(
            "squadra;giocatore;anni;ingaggio\nTiri Team;Svilarr;3;4.500.000",
            catalogo=catalogo,
        )
        assert not esito.importabile
        assert len(esito.errori) == 1, "un solo errore, non anche 'ruoli mancanti'"
        assert "Forse intendevi: Svilar" in esito.errori[0].messaggio

    def test_i_ruoli_nel_file_hanno_la_precedenza(self, catalogo):
        esito = importa_rose(
            "squadra;giocatore;ruoli;anni;ingaggio\nTiri Team;Dimarco;Ds;2;6M",
            catalogo=catalogo,
        )
        assert esito.righe[0]["ruoli"] == ("Ds",)

    def test_senza_catalogo_i_ruoli_restano_obbligatori(self):
        esito = importa_rose(
            "squadra;giocatore;anni;ingaggio\nTiri Team;Svilar;3;4.500.000"
        )
        assert not esito.importabile
        assert "obbligatorie mancanti" in esito.errori[0].messaggio


class TestLaTabellaDeiFormati:
    """La tabella che si mostra prima di caricare, e il lettore, devono dire
    la stessa cosa.

    E' la copia che diverge piu' facilmente: documentare una colonna che il
    lettore non conosce manda a riempirla per niente, e dimenticarne una
    obbligatoria fa scoprire il requisito dall'errore. Nessuna delle due si
    nota guardando il codice.
    """

    FILE = (
        ("rose", CAMPI_ROSE, COLONNE_ROSE, OBBLIGATORIE_ROSE),
        ("risultati", CAMPI_RISULTATI, COLONNE_RISULTATI, OBBLIGATORIE_RISULTATI),
    )

    @staticmethod
    def _chiave_per_sinonimo(sinonimi: dict) -> dict:
        return {
            normalizza_intestazione(nome): chiave
            for chiave, gruppo in sinonimi.items()
            for nome in gruppo
        }

    @pytest.mark.parametrize("nome,campi,sinonimi,_obbligatorie", FILE)
    def test_ogni_colonna_documentata_la_riconosce_il_lettore(
        self, nome, campi, sinonimi, _obbligatorie
    ):
        riconosciute = self._chiave_per_sinonimo(sinonimi)
        for campo in campi:
            assert normalizza_intestazione(campo.nome) in riconosciute, (
                f"{nome}: la colonna «{campo.nome}» e' documentata ma il "
                f"lettore non la conosce"
            )

    @pytest.mark.parametrize("nome,campi,sinonimi,obbligatorie", FILE)
    def test_gli_obbligatori_sono_quelli_che_il_lettore_pretende(
        self, nome, campi, sinonimi, obbligatorie
    ):
        riconosciute = self._chiave_per_sinonimo(sinonimi)
        documentati = {
            riconosciute[normalizza_intestazione(c.nome)] for c in campi if c.obbligatorio
        }
        assert documentati == set(obbligatorie), nome

    def test_col_listone_ruoli_e_club_diventano_facoltativi(self):
        """La stessa condizione che applica `importa_rose` col catalogo."""
        obbligatori = {c.nome for c in campi_rose(con_catalogo=True) if c.obbligatorio}
        assert obbligatori == {"squadra", "giocatore", "ingaggio", "anni"}

    def test_senza_listone_restano_quelli_di_sempre(self):
        assert campi_rose() == CAMPI_ROSE


class TestIRisultatiNonCancellanoIlCalendario:
    """Il CSV dei risultati non parla di calendario, e non deve cancellarlo.

    `arch.scrivi` e' un «insert or replace»: quello che non si rimanda sparisce.
    Scrivendo solo giornata, squadre, punti e gol, l'import azzerava
    `inizio_previsto` — che e' l'orario su cui si **chiudono le formazioni** —
    e `giornata_serie_a`, che e' quello su cui la F1 Rush conta le tappe.
    Caricare i risultati di una giornata riapriva le formazioni di tutte le
    altre, senza che nessuno se ne accorgesse.
    """

    @staticmethod
    def _con_calendario(arch):
        from fantacalcio.data import calendario_dettagliato

        partite = calendario_dettagliato(arch)
        riga = partite.iloc[0]
        righe = [
            {**r, "inizio_previsto": "2026-09-20T15:00:00", "giornata_serie_a": 33}
            for r in arch.calendario().to_dict("records")
            if int(r["id"]) == int(riga["id"])
        ]
        arch.scrivi("calendario", righe, "id")
        return riga

    def test_l_orario_e_la_giornata_di_serie_a_restano(self, archivio_demo):
        from fantacalcio.data import calendario_dettagliato

        riga = self._con_calendario(archivio_demo)
        csv = (
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            f"{int(riga['giornata'])};{riga['casa']};{riga['trasferta']};70;60\n"
        )

        applica_risultati(archivio_demo, importa_risultati(csv))

        partite = calendario_dettagliato(archivio_demo)
        dopo = partite[partite["id"] == int(riga["id"])].iloc[0]
        assert dopo["inizio_previsto"] == "2026-09-20T15:00:00"
        assert int(dopo["giornata_serie_a"]) == 33

    def test_il_risultato_si_scrive_lo_stesso(self, archivio_demo):
        from fantacalcio.data import calendario_dettagliato

        riga = self._con_calendario(archivio_demo)
        csv = (
            "giornata;casa;trasferta;punti_casa;punti_trasferta\n"
            f"{int(riga['giornata'])};{riga['casa']};{riga['trasferta']};70;60\n"
        )

        applica_risultati(archivio_demo, importa_risultati(csv))

        partite = calendario_dettagliato(archivio_demo)
        dopo = partite[partite["id"] == int(riga["id"])].iloc[0]
        assert dopo["punti_casa"] == 70
        assert dopo["gol_casa"] >= dopo["gol_trasferta"]


class TestCalendarioUfficiale:
    """Il calendario esportato da Leghe Fantacalcio.

    E' un xlsx fatto per essere letto da una persona: due giornate affiancate
    per blocco di righe, il nome della giornata dentro una cella di testo
    («1ª Giornata lega» accanto a «6ª Giornata serie a») e il risultato
    scritto «2-2», oppure «-» se non si e' ancora giocato.

    Si legge comunque perche' e' l'unico posto da cui arriva la
    corrispondenza fra giornata di lega e giornata di Serie A, che e' quella
    su cui contano la coppa e la F1 Rush.
    """

    def costruisci(self, righe: list[tuple]) -> bytes:
        import io

        from openpyxl import Workbook

        cartella = Workbook()
        foglio = cartella.active
        foglio.title = "Calendario"
        foglio.append(("Calendario NUoVO League 2026/2027",))
        foglio.append(("https://leghe.fantacalcio.it/nuovo-fanta-manageriale",))
        foglio.append(())
        for riga in righe:
            foglio.append(riga)
        memoria = io.BytesIO()
        cartella.save(memoria)
        return memoria.getvalue()

    def due_giornate(self) -> bytes:
        """Le prime due giornate come le scrive davvero la piattaforma."""
        return self.costruisci(
            [
                (
                    "1ª Giornata lega",
                    None,
                    "6ª Giornata serie a",
                    None,
                    None,
                    None,
                    "2ª Giornata lega",
                    None,
                    "7ª Giornata serie a",
                ),
                (
                    "MaGuardaCheRoba",
                    73.5,
                    72,
                    "Tiri Team",
                    "2-2",
                    None,
                    "ASD Boca Seniors",
                    0,
                    0,
                    "MaGuardaCheRoba",
                    "-",
                ),
                (
                    "A.S. Fregio",
                    78,
                    67.5,
                    "ASD Boca Seniors",
                    "3-1",
                    None,
                    "SkoReggina",
                    0,
                    0,
                    "Tiri Team",
                    "-",
                ),
            ]
        )

    def test_legge_le_due_giornate_affiancate(self):
        esito = importa_calendario(self.due_giornate())

        assert esito.errori == []
        assert len(esito.righe) == 4
        # In ordine di giornata: nel file stanno affiancate, quindi lette riga
        # per riga arriverebbero alternate.
        assert [r["giornata"] for r in esito.righe] == [1, 1, 2, 2]

    def test_la_giornata_di_serie_a_arriva_dall_intestazione(self):
        """E' il dato che non si puo' ricavare: la 1ª di lega e' la 6ª di
        Serie A, e senza questo la F1 Rush conta le tappe sulle giornate
        sbagliate."""
        esito = importa_calendario(self.due_giornate())

        mappa = {r["giornata"]: r["giornata_serie_a"] for r in esito.righe}

        assert mappa == {1: 6, 2: 7}

    def test_la_partita_giocata_porta_punti_e_gol(self):
        esito = importa_calendario(self.due_giornate())

        partita = next(r for r in esito.righe if r["casa"] == "MaGuardaCheRoba")

        assert partita["trasferta"] == "Tiri Team"
        assert partita["punti_casa"] == 73.5
        assert partita["punti_trasferta"] == 72
        assert (partita["gol_casa"], partita["gol_trasferta"]) == (2, 2)

    def test_il_trattino_vuol_dire_non_giocata_e_i_punti_restano_vuoti(self):
        """Gli zeri del file sono riempimento. Tenerli vorrebbe dire una
        partita 0-0 **giocata**, che in classifica vale un punto a testa."""
        esito = importa_calendario(self.due_giornate())

        partita = next(r for r in esito.righe if r["giornata"] == 2)

        assert partita["punti_casa"] is None
        assert partita["punti_trasferta"] is None
        assert partita["gol_casa"] is None
        assert partita["gol_trasferta"] is None

    def test_una_squadra_contro_se_stessa_e_un_errore(self):
        contenuto = self.costruisci(
            [
                ("1ª Giornata lega", None, "6ª Giornata serie a"),
                ("Tiri Team", 70, 70, "Tiri Team", "1-1"),
            ]
        )

        esito = importa_calendario(contenuto)

        assert esito.righe == []
        assert any("contro se stessa" in p.messaggio for p in esito.errori)

    def test_una_squadra_due_volte_nella_stessa_giornata_e_un_errore(self):
        """Una partita in piu' falserebbe la classifica di quella giornata, e
        nel calendario e' il sintomo di un file incollato male."""
        contenuto = self.costruisci(
            [
                ("1ª Giornata lega", None, "6ª Giornata serie a"),
                ("Tiri Team", 70, 70, "AS Bronzi", "1-1"),
                ("Tiri Team", 70, 70, "SkoReggina", "1-1"),
            ]
        )

        esito = importa_calendario(contenuto)

        assert len(esito.righe) == 1
        assert any("due volte" in p.messaggio for p in esito.errori)

    def test_la_stessa_squadra_in_due_giornate_diverse_va_benissimo(self):
        esito = importa_calendario(self.due_giornate())

        quante = [
            r for r in esito.righe if "MaGuardaCheRoba" in (r["casa"], r["trasferta"])
        ]

        assert len(quante) == 2

    def test_un_xlsx_che_non_e_il_calendario_lo_dice(self):
        contenuto = self.costruisci([("Qualcosa", "Altro"), ("Tiri Team", 70)])

        esito = importa_calendario(contenuto)

        assert esito.righe == []
        assert not esito.importabile
        assert any("Nessuna partita leggibile" in p.messaggio for p in esito.errori)

    def test_un_file_che_non_e_excel_non_fa_esplodere_niente(self):
        esito = importa_calendario(b"giornata;casa;trasferta\n1;Tiri Team;AS Bronzi\n")

        assert esito.righe == []
        assert not esito.importabile
        assert any("Excel" in p.messaggio for p in esito.errori)

    def test_senza_la_giornata_di_serie_a_si_legge_lo_stesso(self):
        """Il dato manca, le partite no: rifiutare tutto per un'intestazione
        in meno vorrebbe dire non caricare il calendario."""
        contenuto = self.costruisci(
            [
                ("1ª Giornata lega",),
                ("Tiri Team", 70, 60, "AS Bronzi", "1-0"),
            ]
        )

        esito = importa_calendario(contenuto)

        assert len(esito.righe) == 1
        assert esito.righe[0]["giornata_serie_a"] is None
        assert esito.importabile


class TestApplicaCalendario:
    """Precaricare il campionato vero, con le squadre che ancora non esistono.

    E' il primo passo di una lega nuova: le dieci squadre si conoscono prima
    dei presidenti — stanno scritte nel calendario — e vengono create senza
    presidente, che lo dira' chi entra col codice della lega.
    """

    def costruisci(self, righe: list[tuple]) -> bytes:
        return TestCalendarioUfficiale().costruisci(righe)

    def file_con(self, *partite: tuple, giornata: int = 1, serie_a: int = 6) -> bytes:
        """Un calendario di una giornata: (casa, punti, punti, trasferta, esito)."""
        return self.costruisci(
            [
                (f"{giornata}ª Giornata lega", None, f"{serie_a}ª Giornata serie a"),
                *partite,
            ]
        )

    def test_le_squadre_che_mancano_vengono_create(self, archivio_demo):
        contenuto = self.file_con(
            ("Tiri Team", 70, 60, "SkoReggina", "1-0"),
            ("MaGuardaCheRoba", 80, 50, "Padel United", "3-0"),
        )

        riepilogo = applica_calendario(
            archivio_demo, importa_calendario(contenuto), lega_id=1
        )

        assert sorted(riepilogo["squadre_create"]) == ["MaGuardaCheRoba", "SkoReggina"]
        squadre = archivio_demo.squadre()
        nomi = {str(r["nome"]) for _, r in squadre.iterrows()}
        assert {"SkoReggina", "MaGuardaCheRoba"} <= nomi
        nuova = squadre[squadre["nome"] == "SkoReggina"].iloc[0]
        assert int(nuova["lega_id"]) == 1
        assert not str(nuova["presidente"] or "")

    def test_quelle_che_ci_sono_gia_non_si_duplicano(self, archivio_demo):
        """Anche scritte con un'altra maiuscola: due «Tiri Team» vorrebbero
        dire due rose e mezzo campionato contro il fantasma."""
        quante_prima = len(archivio_demo.squadre())
        contenuto = self.file_con(("tiri team", 70, 60, "PADEL UNITED", "1-0"))

        riepilogo = applica_calendario(archivio_demo, importa_calendario(contenuto))

        assert riepilogo["squadre_create"] == []
        assert len(archivio_demo.squadre()) == quante_prima

    def test_senza_crea_squadre_un_nome_sconosciuto_ferma_tutto(self, archivio_demo):
        contenuto = self.file_con(("Tiri Team", 70, 60, "SkoReggina", "1-0"))

        with pytest.raises(ValueError, match="SkoReggina"):
            applica_calendario(
                archivio_demo, importa_calendario(contenuto), crea_squadre=False
            )

    def test_il_campionato_precedente_viene_rifatto_da_zero(self, archivio_demo):
        """Il file e' il campionato intero: tenere anche il vecchio vorrebbe
        dire giornate doppie e una classifica che non torna."""
        assert len(archivio_demo.calendario()) == 90
        contenuto = self.file_con(("Tiri Team", 70, 60, "Padel United", "1-0"))

        applica_calendario(archivio_demo, importa_calendario(contenuto))

        assert len(archivio_demo.calendario()) == 1

    def test_le_partite_delle_altre_competizioni_restano(self, archivio_demo):
        """Il calendario del campionato non e' la coppa: rifare l'uno non
        deve cancellare l'altra."""
        righe = archivio_demo.calendario().to_dict("records")
        coppa = {**righe[0], "id": 999, "competizione": "COPPA_ITALIA", "turno": "Finale"}
        archivio_demo.scrivi("calendario", [coppa], chiave="id")
        contenuto = self.file_con(("Tiri Team", 70, 60, "Padel United", "1-0"))

        applica_calendario(archivio_demo, importa_calendario(contenuto))

        dopo = archivio_demo.calendario()
        rimaste = dopo[dopo["competizione"] == "COPPA_ITALIA"]
        assert len(rimaste) == 1
        assert str(rimaste.iloc[0]["turno"]) == "Finale"

    def test_l_orario_di_una_partita_che_non_cambia_si_conserva(self, archivio_demo):
        """`inizio_previsto` e' l'ora in cui si chiudono le formazioni, e il
        file non lo porta: ricaricare il calendario non deve riaprirle."""
        partite = archivio_demo.calendario().to_dict("records")
        prima = partite[0]
        archivio_demo.scrivi(
            "calendario",
            [{**prima, "inizio_previsto": "2026-10-04T15:00:00"}],
            chiave="id",
        )
        squadre = {
            int(r["id"]): str(r["nome"]) for _, r in archivio_demo.squadre().iterrows()
        }
        contenuto = self.file_con(
            (
                squadre[int(prima["casa_id"])],
                70,
                60,
                squadre[int(prima["trasferta_id"])],
                "1-0",
            ),
            giornata=int(prima["giornata"]),
        )

        applica_calendario(archivio_demo, importa_calendario(contenuto))

        dopo = archivio_demo.calendario().iloc[0]
        assert str(dopo["inizio_previsto"]) == "2026-10-04T15:00:00"

    def test_la_giornata_di_serie_a_finisce_nel_database(self, archivio_demo):
        contenuto = self.file_con(
            ("Tiri Team", 70, 60, "Padel United", "1-0"), giornata=3, serie_a=8
        )

        riepilogo = applica_calendario(archivio_demo, importa_calendario(contenuto))

        riga = archivio_demo.calendario().iloc[0]
        assert int(riga["giornata"]) == 3
        assert int(riga["giornata_serie_a"]) == 8
        assert riepilogo["con_giornata_serie_a"] == 1

    def test_una_partita_non_giocata_resta_senza_punti(self, archivio_demo):
        contenuto = self.file_con(("Tiri Team", 0, 0, "Padel United", "-"))

        riepilogo = applica_calendario(archivio_demo, importa_calendario(contenuto))

        riga = archivio_demo.calendario().iloc[0]
        assert pandas.isna(riga["punti_casa"])
        assert pandas.isna(riga["gol_casa"])
        assert riepilogo["giocate"] == 0

    def test_i_gol_li_decidono_le_fasce_della_lega(self, archivio_demo):
        """73,5 punti con il primo gol a 66 e il passo a 6 fanno due gol: e'
        il conto del regolamento, non quello copiato dal file."""
        contenuto = self.file_con(("Tiri Team", 73.5, 72, "Padel United", "2-2"))

        riepilogo = applica_calendario(archivio_demo, importa_calendario(contenuto))

        riga = archivio_demo.calendario().iloc[0]
        assert (int(riga["gol_casa"]), int(riga["gol_trasferta"])) == (2, 2)
        assert riepilogo["discordanze"] == []

    def test_un_file_che_non_torna_con_le_fasce_lo_dice(self, archivio_demo):
        """Se la piattaforma conta i gol in un altro modo, il parametro
        sbagliato e' `soglia_primo_gol` — e va saputo subito, perche' da li'
        in poi ogni risultato calcolato in casa sarebbe diverso dal vero."""
        contenuto = self.file_con(("Tiri Team", 73.5, 72, "Padel United", "5-0"))

        riepilogo = applica_calendario(archivio_demo, importa_calendario(contenuto))

        assert riepilogo["discordanze"]
        assert "5-0" in riepilogo["discordanze"][0]
        assert "2-2" in riepilogo["discordanze"][0]
        # Quello che si scrive e' comunque il conto del regolamento.
        assert int(archivio_demo.calendario().iloc[0]["gol_casa"]) == 2

    def test_un_esito_con_errori_non_si_scrive(self, archivio_demo):
        contenuto = self.file_con(("Tiri Team", 70, 70, "Tiri Team", "1-1"))

        with pytest.raises(ValueError, match="errori"):
            applica_calendario(archivio_demo, importa_calendario(contenuto))


class TestIlFormatoVecchioSiImportaAncora:
    """Chi ha un CSV col formato di prima non deve vederlo rifiutato.

    Il formato vecchio aveva `datanascita` e `prolungato`. Il file nuovo non li
    porta piu', ma i fogli gia' pronti in giro li hanno ancora: devono entrare
    senza errori.
    """

    VECCHIO = (
        "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;datanascita;prolungato\n"
        "Tiri Team;Rossi Marco;Inter;Dc;2.500.000;3;Italia;17/04/2001;no\n"
        "Tiri Team;Bianchi Luca;Juventus;Por;1.800.000;2;Italia;02/11/1996;si\n"
        "Padel United;Silva Joao;Napoli;W/T;4,2M;2;Brasile;30/06/1999;no\n"
    )

    def test_si_importa_senza_errori(self):
        esito = importa_rose(self.VECCHIO)
        assert esito.importabile
        assert esito.errori == []
        assert len(esito.righe) == 3

    def test_le_colonne_tolte_sono_segnalate_come_ignorate(self):
        esito = importa_rose(self.VECCHIO)
        assert esito.intestazioni_ignorate == ["datanascita", "prolungato"]
        assert esito.avvisi == []
        # E il loro contenuto non entra: niente chiavi per data e prolungamento.
        assert "data_nascita" not in esito.righe[0]
        assert "prolungato" not in esito.righe[0]
