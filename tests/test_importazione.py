"""Il CSV del draft deve essere letto con tolleranza e validato con rigore."""

from datetime import date

import pytest

from fantacalcio.data import ArchivioSQLite, carica_rose
from fantacalcio.importazione import (
    COLONNE_ROSE,
    anteprima_conformita,
    applica_risultati,
    applica_rose,
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

INTESTAZIONI = "squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;data_nascita"


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
            f"{ingaggio};{anni};Italia;01/01/1996"
        )
    return righe


class TestNormalizzazione:
    @pytest.mark.parametrize(
        "testo,atteso",
        [
            ("Anni Residui ", "anniresidui"),
            ("Nazionalità", "nazionalita"),
            ("DATA_NASCITA", "datanascita"),
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
            + ("Tiri Team,Rossi,Inter,Dc,2.000.000,3,Italia,01/01/1996")
        )
        esito = importa_rose(contenuto)
        assert esito.importabile
        assert esito.righe[0]["ingaggio"] == 2_000_000

    def test_bytes_in_latin1(self):
        contenuto = csv_rose(
            "Tiri Team;Pérez;Inter;Dc;2.000.000;3;Spagna;01/01/1996"
        ).encode("latin-1")
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
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;01/01/1996",
                ";;;;;;;",
                "",
            )
        )
        assert esito.importabile
        assert len(esito.righe) == 1

    def test_contratto_fuori_scala_e_bloccante(self):
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;7;Italia;01/01/1996")
        )
        assert not esito.importabile
        errore = esito.errori[0]
        assert errore.colonna == "anni"
        assert "art. 2" in errore.messaggio.lower()

    def test_il_numero_di_riga_e_quello_del_foglio(self):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;01/01/1996",
                "Tiri Team;Bianchi;Inter;Libero;2.000.000;3;Italia;01/01/1996",
            )
        )
        # Riga 1 = intestazioni, riga 2 = Rossi, riga 3 = Bianchi.
        assert esito.errori[0].riga == 3

    def test_giocatore_in_due_rose(self):
        esito = importa_rose(
            csv_rose(
                "Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;01/01/1996",
                "Padel United;rossi;Inter;Dc;2.000.000;3;Italia;01/01/1996",
            )
        )
        assert not esito.importabile
        assert "una sola rosa" in esito.errori[0].messaggio

    def test_data_mancante_e_solo_un_avviso(self):
        esito = importa_rose(csv_rose("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;"))
        assert esito.importabile
        assert any(p.colonna == "data_nascita" for p in esito.avvisi)

    def test_riga_disallineata_spiega_la_causa(self):
        """Il caso piu' comune: ruoli scritti "M;C" in un CSV separato da ';'."""
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi;Inter;M;C;2.000.000;3;Italia;01/01/1996")
        )
        assert not esito.importabile
        errore = esito.errori[0]
        assert errore.colonna == "riga"
        assert "1 colonna in piu'" in errore.messaggio
        assert "Dc/Dd" in errore.messaggio

    def test_ruoli_multipli_con_barra_funzionano(self):
        esito = importa_rose(
            csv_rose("Tiri Team;Rossi;Inter;M/C;2.000.000;3;Italia;01/01/1996")
        )
        assert esito.importabile
        assert esito.righe[0]["ruoli"] == ("M", "C")

    def test_intestazioni_extra_segnalate_ma_non_bloccanti(self):
        contenuto = (
            (INTESTAZIONI + ";note")
            + "\n"
            + ("Tiri Team;Rossi;Inter;Dc;2.000.000;3;Italia;01/01/1996;pick 1")
        )
        esito = importa_rose(contenuto)
        assert esito.importabile
        assert esito.intestazioni_ignorate == ["note"]


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
    def archivio(self, tmp_path):
        return ArchivioSQLite(tmp_path / "import.db")

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
            csv_rose("Tiri Team;Rossi;Inter;Libero;2.000.000;3;Italia;01/01/1996")
        )
        with pytest.raises(ValueError, match="errori da correggere"):
            applica_rose(archivio, esito)


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

    def test_applica_aggiorna_la_partita_esistente(self, tmp_path):
        """Il calendario esiste gia': importare i punti non deve duplicarlo."""
        archivio = ArchivioSQLite(tmp_path / "ris.db")
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

    def test_accoppiamento_in_conflitto_col_calendario(self, tmp_path):
        """Se la squadra e' gia' impegnata in quella giornata, meglio fermarsi."""
        archivio = ArchivioSQLite(tmp_path / "ris3.db")
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

    def test_squadra_sconosciuta(self, tmp_path):
        archivio = ArchivioSQLite(tmp_path / "ris2.db")
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

    def test_applica_conserva_ingaggi_e_contratti(self, tmp_path):
        """Ri-caricare il listone non deve azzerare gli ingaggi Capology."""
        from fantacalcio.data import ArchivioSQLite
        from fantacalcio.importazione import applica_listone, importa_listone

        archivio = ArchivioSQLite(tmp_path / "listone.db")
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
