"""Importazione vista dall'API: chi puo' scrivere, e cosa non entra.

Le validazioni riga per riga hanno i loro test in `test_importazione.py`:
qui si prova il contorno, che e' dove un'API sbaglia. Che l'import sia del
presidente anche senza passare dalla pagina; che l'anteprima **non scriva**;
e soprattutto che la conferma rilegga e rivalidi il file, perche' fra
anteprima e conferma il server non ricorda niente — chi chiama potrebbe
mandare direttamente la seconda.

Giocatori e partite si leggono dalla demo invece di scriverli a mano. Un nome
inventato finirebbe fuori dal catalogo e un accoppiamento inventato fuori dal
calendario: proverebbero quello, non quello che interessa qui.
"""

from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def segreto_di_prova(monkeypatch):
    monkeypatch.setenv("FANTA_SEGRETO_JWT", "segreto-lungo-abbastanza-solo-per-i-test")
    monkeypatch.setenv("FANTA_AMBIENTE", "sviluppo")


@pytest.fixture
def client(monkeypatch, db_demo):
    monkeypatch.setenv("FANTA_DB_DEMO", str(db_demo))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    # Vedi il commento gemello in test_api_accesso.
    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


def entra(client, chi="Marco"):
    """Marco e' il presidente della lega di demo; Luca un fantallenatore."""
    client.post("/api/esci")
    client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})


def caricato(contenuto, **extra) -> dict:
    grezzo = contenuto.encode("utf-8") if isinstance(contenuto, str) else contenuto
    return {
        "contenuto_base64": base64.b64encode(grezzo).decode("ascii"),
        "nome": "prova.csv",
        **extra,
    }


# Per le rotte in cui conta solo il permesso, non il contenuto.
QUALUNQUE = "squadra;giocatore;ingaggio;anni\n"


@pytest.fixture
def nomi(client):
    """Un giocatore della prima squadra e uno della seconda."""
    entra(client)
    return (
        client.get("/api/squadre/1").json()["rosa"][0]["nome"],
        client.get("/api/squadre/2").json()["rosa"][0]["nome"],
    )


@pytest.fixture
def rose_buone(nomi):
    """Due rose da un giocatore: leggibili, e fuori dai paletti.

    Il CSV tace ruoli e club: la demo ha il catalogo, quindi si ricavano dal
    nome — ed e' il caso normale per chi importa dopo il draft.
    """
    uno, due = nomi
    return (
        "squadra;giocatore;ingaggio;anni\n"
        f"Tiri Team;{uno};6000000;3\n"
        f"Padel United;{due};7000000;2\n"
    )


@pytest.fixture
def rose_rotte(nomi):
    """Lo stesso giocatore due volte: art. 6, una sola rosa."""
    uno, _ = nomi
    return (
        "squadra;giocatore;ingaggio;anni\n"
        f"Tiri Team;{uno};6000000;3\n"
        f"Tiri Team;{uno};6000000;2\n"
    )


@pytest.fixture
def partita(client):
    """La prima partita del calendario di demo."""
    entra(client)
    return client.get("/api/campionato").json()["partite"][0]


def csv_risultati(*partite: dict) -> str:
    righe = "".join(
        f"{p['giornata']};{p['casa']};{p['trasferta']};72,5;66\n" for p in partite
    )
    return "giornata;casa;trasferta;punti_casa;punti_trasferta\n" + righe


def listone_xlsx(righe: list[tuple]) -> bytes:
    """Un listone come quello di Fantacalcio.it: titolo in prima riga,
    intestazioni in seconda, foglio «Tutti»."""
    from openpyxl import Workbook

    cartella = Workbook()
    foglio = cartella.active
    foglio.title = "Tutti"
    foglio.append(["Quotazioni Fantacalcio Stagione 2026 27"])
    foglio.append(["Id", "R", "RM", "Nome", "Squadra", "Qt.A M", "FVM M"])
    for riga in righe:
        foglio.append(list(riga))
    memoria = io.BytesIO()
    cartella.save(memoria)
    return memoria.getvalue()


class TestIFormati:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/importazione").status_code == 401

    def test_dice_che_colonne_vogliono_i_file(self, client):
        entra(client)
        dati = client.get("/api/importazione").json()
        assert dati["posso_importare"] is True
        nomi = [c["nome"] for c in dati["campi_rose"]]
        assert {"squadra", "giocatore", "anni", "ingaggio"} <= set(nomi)
        assert dati["campi_listone"] and dati["campi_risultati"]

    def test_col_listone_caricato_ruoli_e_club_sono_facoltativi(self, client):
        """La demo ha gia' il catalogo: il CSV puo' tacerli, e la pagina deve
        dirlo invece di farli riempire per niente."""
        entra(client)
        dati = client.get("/api/importazione").json()
        assert dati["giocatori_in_catalogo"] > 0
        obbligatori = {c["nome"] for c in dati["campi_rose"] if c["obbligatorio"]}
        assert obbligatori == {"squadra", "giocatore", "anni", "ingaggio"}

    def test_porta_i_modelli_e_le_fasce_dei_gol(self, client):
        entra(client)
        dati = client.get("/api/importazione").json()
        assert dati["modello_rose"].startswith("squadra;")
        assert dati["modello_risultati"].startswith("giornata;")
        # Le fasce arrivano dai parametri, non scritte nella pagina.
        assert dati["soglia_primo_gol"] == 66

    def test_a_chi_non_importa_lo_dice(self, client):
        entra(client, "Luca")
        assert client.get("/api/importazione").json()["posso_importare"] is False


class TestSoloIlPresidente:
    """Art. 1: l'import e' suo. E la rotta si chiama anche a bottone nascosto."""

    ROTTE = (
        "/api/importazione/rose/anteprima",
        "/api/importazione/rose",
        "/api/importazione/listone/anteprima",
        "/api/importazione/listone",
        "/api/importazione/risultati/anteprima",
        "/api/importazione/risultati",
        "/api/importazione/calendario/anteprima",
        "/api/importazione/calendario",
    )

    @pytest.mark.parametrize("rotta", ROTTE)
    def test_un_fantallenatore_e_respinto(self, client, rotta):
        entra(client, "Luca")
        risposta = client.post(rotta, json=caricato(QUALUNQUE))
        assert risposta.status_code == 403
        assert "presidente" in risposta.json()["detail"]

    @pytest.mark.parametrize("rotta", ROTTE)
    def test_senza_sessione_e_respinto(self, client, rotta):
        client.post("/api/esci")
        assert client.post(rotta, json=caricato(QUALUNQUE)).status_code == 401

    def test_un_fantallenatore_non_scrive_niente(self, client, rose_buone):
        """Il 403 deve arrivare prima della scrittura, non dopo."""
        entra(client)
        prima = len(client.get("/api/squadre/1").json()["rosa"])

        entra(client, "Luca")
        client.post("/api/importazione/rose", json=caricato(rose_buone))

        entra(client)
        assert len(client.get("/api/squadre/1").json()["rosa"]) == prima


class TestAnteprimaDelleRose:
    def test_legge_le_righe_e_dice_che_e_importabile(self, client, rose_buone):
        entra(client)
        dati = client.post(
            "/api/importazione/rose/anteprima", json=caricato(rose_buone)
        ).json()
        assert dati["lette"] == 2
        assert dati["errori"] == []
        assert dati["importabile"] is True
        # Ruoli e club li ha ricavati dal catalogo, non dal file.
        assert all(r["ruoli"] for r in dati["righe"])

    def test_dice_come_sarebbero_le_rose_prima_di_scriverle(self, client, rose_buone):
        entra(client)
        dati = client.post(
            "/api/importazione/rose/anteprima", json=caricato(rose_buone)
        ).json()
        squadre = {s["squadra"]: s for s in dati["squadre"]}
        assert set(squadre) == {"Tiri Team", "Padel United"}
        # Una rosa da un giocatore e' fuori dai paletti, e si vede adesso.
        assert squadre["Tiri Team"]["conforme"] is False
        assert squadre["Tiri Team"]["dimensione"] == 1
        assert squadre["Tiri Team"]["monte_anni"] == 66
        assert all(v["articolo"] for v in squadre["Tiri Team"]["violazioni"]), (
            "una violazione senza articolo non dice all'utente cosa ha sforato"
        )

    def test_un_giocatore_due_volte_e_un_errore(self, client, rose_rotte):
        entra(client)
        dati = client.post(
            "/api/importazione/rose/anteprima", json=caricato(rose_rotte)
        ).json()
        assert dati["importabile"] is False
        assert any("una sola rosa" in e["messaggio"] for e in dati["errori"])
        assert all(e["riga"] > 0 for e in dati["errori"])

    def test_l_anteprima_non_scrive(self, client, rose_buone):
        entra(client)
        prima = len(client.get("/api/squadre/1").json()["rosa"])
        client.post("/api/importazione/rose/anteprima", json=caricato(rose_buone))
        assert len(client.get("/api/squadre/1").json()["rosa"]) == prima

    def test_un_file_che_non_e_un_csv_lo_dice_senza_rompersi(self, client):
        entra(client)
        risposta = client.post(
            "/api/importazione/rose/anteprima", json=caricato("non sono un csv")
        )
        assert risposta.status_code == 200
        assert risposta.json()["importabile"] is False
        assert risposta.json()["errori"]

    def test_un_base64_storto_e_un_422_leggibile(self, client):
        entra(client)
        risposta = client.post(
            "/api/importazione/rose/anteprima",
            json={"contenuto_base64": "non-e-base64!!", "nome": "x.csv"},
        )
        assert risposta.status_code == 422
        assert "leggibile" in risposta.json()["detail"]


class TestScrivereLeRose:
    def test_sostituisce_le_rose_e_lo_racconta(self, client, rose_buone, nomi):
        entra(client)
        risposta = client.post("/api/importazione/rose", json=caricato(rose_buone))
        assert risposta.status_code == 200
        assert "2 giocatori" in risposta.json()["messaggio"]

        # Con `sostituisci` il file e' la situazione completa: la rosa di
        # prima (trenta e piu' giocatori) e' stata azzerata.
        rosa = client.get("/api/squadre/1").json()["rosa"]
        assert [g["nome"] for g in rosa] == [nomi[0]]

    def test_la_squadra_tiene_la_sua_identita(self, client, rose_buone):
        """L'import tocca le rose, non le maglie."""
        entra(client)
        prima = client.get("/api/squadre/1").json()
        client.post("/api/importazione/rose", json=caricato(rose_buone))
        dopo = client.get("/api/squadre/1").json()
        assert dopo["nome"] == prima["nome"]
        assert dopo["id"] == prima["id"]

    def test_senza_sostituisci_si_aggiunge(self, client, rose_buone):
        entra(client)
        prima = len(client.get("/api/squadre/1").json()["rosa"])
        client.post(
            "/api/importazione/rose",
            json=caricato(rose_buone, sostituisci=False),
        )
        assert len(client.get("/api/squadre/1").json()["rosa"]) >= prima

    def test_un_file_con_errori_non_si_scrive(self, client, rose_rotte):
        """Il server non ricorda l'anteprima, quindi la conferma rivalida.

        Senza, chi chiama l'API a mano scriverebbe quello che vuole: basterebbe
        non chiedere mai l'anteprima.
        """
        entra(client)
        prima = len(client.get("/api/squadre/1").json()["rosa"])

        risposta = client.post("/api/importazione/rose", json=caricato(rose_rotte))

        assert risposta.status_code == 422
        assert "errori" in risposta.json()["detail"]
        assert len(client.get("/api/squadre/1").json()["rosa"]) == prima

    def test_le_violazioni_non_fermano_la_scrittura(self, client, rose_buone):
        """Una rosa da un giocatore viola mezzo regolamento, e si scrive
        comunque: dopo il draft si sana entro la chiusura del mercato, e
        tenerla fuori dal sito non la sana — la nasconde."""
        entra(client)
        anteprima = client.post(
            "/api/importazione/rose/anteprima", json=caricato(rose_buone)
        ).json()
        assert all(s["conforme"] is False for s in anteprima["squadre"])

        risposta = client.post("/api/importazione/rose", json=caricato(rose_buone))
        assert risposta.status_code == 200


class TestIRisultati:
    def test_anteprima_e_scrittura(self, client, partita):
        entra(client)
        testo = csv_risultati(partita)

        anteprima = client.post(
            "/api/importazione/risultati/anteprima", json=caricato(testo)
        ).json()
        assert anteprima["importabile"] is True
        assert anteprima["righe"][0]["punti_casa"] == 72.5

        risposta = client.post("/api/importazione/risultati", json=caricato(testo))
        assert risposta.status_code == 200
        assert "1 partite" in risposta.json()["messaggio"]

    def test_una_squadra_che_non_esiste_e_un_422(self, client, partita):
        entra(client)
        finta = csv_risultati({**partita, "trasferta": "Squadra Inventata"})
        risposta = client.post("/api/importazione/risultati", json=caricato(finta))
        assert risposta.status_code == 422
        assert "Inventata" in risposta.json()["detail"]

    def test_la_stessa_squadra_due_volte_nella_giornata_e_un_errore(
        self, client, partita
    ):
        entra(client)
        dati = client.post(
            "/api/importazione/risultati/anteprima",
            json=caricato(csv_risultati(partita, partita)),
        ).json()
        assert dati["importabile"] is False


class TestIlListone:
    RIGHE = [
        (2071, "A", "A;Pc", "Dybala", "Roma", 26, 70),
        (588, "P", "Por", "Maignan", "Milan", 17, 30),
    ]

    def test_anteprima_e_scrittura(self, client):
        entra(client)
        file = caricato(listone_xlsx(self.RIGHE))

        anteprima = client.post("/api/importazione/listone/anteprima", json=file).json()
        assert anteprima["lette"] == 2
        assert anteprima["club"] == 2
        assert anteprima["importabile"] is True
        assert anteprima["righe"][0]["ruoli"] == ["A", "Pc"]

        risposta = client.post("/api/importazione/listone", json=file)
        assert risposta.status_code == 200
        assert "catalogo" in risposta.json()["messaggio"]

    def test_un_file_che_non_e_ne_l_uno_ne_l_altro_lo_dice(self, client):
        """Si accettano due formati, quindi il rifiuto deve dire cosa si
        aspettava: «non e' un Excel» a chi aveva in mano un CSV non serviva."""
        entra(client)
        dati = client.post(
            "/api/importazione/listone/anteprima",
            json=caricato("non sono niente di leggibile"),
        ).json()
        assert dati["importabile"] is False
        assert any("id giocatore" in e["messaggio"] for e in dati["errori"])

    def test_il_listone_non_tocca_le_rose(self, client):
        """Aggiorna ruoli, club e quotazioni: contratti e ingaggi no."""
        entra(client)
        prima = client.get("/api/squadre/1").json()["rosa"]
        client.post("/api/importazione/listone", json=caricato(listone_xlsx(self.RIGHE)))
        dopo = client.get("/api/squadre/1").json()["rosa"]
        assert len(dopo) == len(prima)
        per_nome = {g["nome"]: g["anni_residui"] for g in dopo}
        for giocatore in prima:
            assert per_nome[giocatore["nome"]] == giocatore["anni_residui"]


class TestIlListoneInUnFileSolo:
    """Il CSV con dentro stipendi, date di nascita e nazionalita'.

    E' la ragione per cui si accettano due formati. L'xlsx ufficiale di
    Fantacalcio.it porta anagrafica, ruoli e quotazioni e **nient'altro**:
    senza stipendio il Salary Cap resta a zero, senza data di nascita lo
    status Under 21 non si puo' determinare, e sono due terzi del regolamento.
    """

    CSV = (
        "id giocatore;nome giocatore;cognome giocatore;squadra di provenienza;"
        "ruolo classic;ruolo mantra;data di nascita;nazionalita;stipendio lordo\n"
        "2071;Paulo;Dybala;Roma;A;A/Pc;15/11/1993;Argentina;6000000\n"
        "555;Nicolo;Barella;Inter;C;M/C;07/02/1997;Italia;9000000\n"
    )

    def test_l_anteprima_conta_cosa_porta_il_file(self, client):
        entra(client)

        dati = client.post(
            "/api/importazione/listone/anteprima", json=caricato(self.CSV)
        ).json()

        assert dati["lette"] == 2
        assert dati["importabile"] is True
        assert dati["con_stipendio"] == 2
        assert dati["con_data_nascita"] == 2
        assert dati["con_nazionalita"] == 2
        assert dati["righe"][0]["ingaggio"] == 6_000_000
        assert dati["righe"][0]["data_nascita"] == "1993-11-15"
        assert dati["righe"][0]["nazionalita"] == "Argentina"

    def test_dice_che_file_ha_riconosciuto(self, client):
        """Due formati accettati vuol dire che chi carica deve vedere per quale
        dei due e' stato preso il suo."""
        entra(client)

        dati = client.post(
            "/api/importazione/listone/anteprima", json=caricato(self.CSV)
        ).json()

        assert any("CSV" in f for f in dati["fonti"])

    def test_i_tre_dati_arrivano_davvero_in_archivio(self, client):
        from datetime import date

        from fantacalcio.data import archivio, carica_giocatori

        entra(client)
        risposta = client.post("/api/importazione/listone", json=caricato(self.CSV))

        assert risposta.status_code == 200
        per_ufficiale = {g.id_ufficiale: g for g in carica_giocatori(archivio()).values()}
        dybala = per_ufficiale[2071]
        assert dybala.ingaggio == 6_000_000
        assert dybala.data_nascita == date(1993, 11, 15)
        assert dybala.nazionalita == "Argentina"
        # E con la data di nascita lo status Under 21 si puo' finalmente
        # calcolare: e' tutto il punto di caricarla.
        assert dybala.eta_al(date(2026, 8, 31)) == 32

    def test_una_riga_rotta_e_un_avviso_non_un_errore(self, client):
        """Le altre quattrocentonovantanove entrano lo stesso, ma quella che
        manca si deve poter leggere prima di scrivere."""
        entra(client)
        rotto = self.CSV + "xx;Chi;Sa;Roma;C;M;;;\n"

        dati = client.post(
            "/api/importazione/listone/anteprima", json=caricato(rotto)
        ).json()

        assert dati["importabile"] is True
        assert dati["lette"] == 2
        assert len(dati["avvisi"]) == 1
        assert "id non numerico" in dati["avvisi"][0]["messaggio"]

    def test_ricaricare_l_xlsx_non_azzera_gli_stipendi(self, client):
        """L'xlsx lo stipendio non ce l'ha: se ricaricarlo lo cancellasse,
        il Salary Cap di tutta la lega tornerebbe a zero a ogni aggiornamento
        di quotazioni."""
        from fantacalcio.data import archivio, carica_giocatori

        entra(client)
        client.post("/api/importazione/listone", json=caricato(self.CSV))

        client.post(
            "/api/importazione/listone",
            json=caricato(listone_xlsx([(2071, "A", "A;Pc", "Dybala", "Roma", 30, 80)])),
        )

        dybala = next(
            g for g in carica_giocatori(archivio()).values() if g.id_ufficiale == 2071
        )
        assert dybala.ingaggio == 6_000_000
        assert dybala.quotazione == 30  # la quotazione invece si aggiorna

    def test_di_partenza_unisce_e_non_cancella(self, client):
        from fantacalcio.data import archivio, carica_giocatori

        entra(client)
        quanti_prima = len(carica_giocatori(archivio()))

        client.post("/api/importazione/listone", json=caricato(self.CSV))

        assert len(carica_giocatori(archivio())) >= quanti_prima

    def test_sostituendo_resta_solo_quel_che_c_e_nel_file(self, client):
        """Serve quando il file precedente era sbagliato. Cancella anche i
        contratti di chi sparisce, ed e' per questo che non e' il modo
        normale di aggiornare."""
        from fantacalcio.data import archivio, carica_giocatori

        entra(client)

        risposta = client.post(
            "/api/importazione/listone",
            json=caricato(self.CSV, sostituisci=True),
        )

        assert risposta.status_code == 200
        assert "cancellati" in risposta.json()["messaggio"]
        assert len(carica_giocatori(archivio())) == 2

    def test_il_modello_del_csv_si_scarica(self, client):
        """Il formato va mostrato, non indovinato: e' un file che si prepara
        a mano in Excel."""
        entra(client)

        formati = client.get("/api/importazione").json()

        assert "stipendio lordo" in formati["modello_listone"]
        assert "data di nascita" in formati["modello_listone"]


class TestSvuotareIlListone:
    """L'azione piu' distruttiva del sito: senza giocatori non esistono rose."""

    def test_serve_la_parola_scritta_a_mano(self, client):
        from fantacalcio.data import archivio, carica_giocatori

        entra(client)

        risposta = client.post(
            "/api/importazione/listone/svuota", json={"conferma": "si"}
        )

        assert risposta.status_code == 422
        assert "CANCELLA" in risposta.json()["detail"]
        assert carica_giocatori(archivio())

    def test_con_la_parola_giusta_porta_via_anche_le_rose(self, client):
        from fantacalcio.data import archivio, carica_giocatori, carica_rose

        entra(client)

        esito = client.post(
            "/api/importazione/listone/svuota", json={"conferma": "cancella"}
        )

        assert esito.status_code == 200
        assert esito.json()["giocatori"] > 0
        assert esito.json()["contratti"] > 0
        assert carica_giocatori(archivio()) == {}
        # Le squadre restano: sono le rose a svuotarsi.
        rose = carica_rose(archivio())
        assert len(rose) == 10
        assert all(r.dimensione == 0 for r in rose.values())

    def test_non_lo_fa_chi_non_importa(self, client):
        entra(client, "luca")

        risposta = client.post(
            "/api/importazione/listone/svuota", json={"conferma": "CANCELLA"}
        )

        assert risposta.status_code == 403


def calendario_xlsx(blocchi: list[tuple]) -> bytes:
    """Il calendario come lo esporta Leghe Fantacalcio.

    Due giornate affiancate, l'intestazione dentro una cella di testo e il
    risultato scritto «2-2» oppure «-» se non si e' giocato. `blocchi` sono
    le righe del foglio, cosi' come stanno nel file.
    """
    from openpyxl import Workbook

    cartella = Workbook()
    foglio = cartella.active
    foglio.title = "Calendario"
    foglio.append(["Calendario NUoVO League 2026/2027"])
    foglio.append(["https://leghe.fantacalcio.it/nuovo-fanta-manageriale"])
    foglio.append([])
    for riga in blocchi:
        foglio.append(list(riga))
    memoria = io.BytesIO()
    cartella.save(memoria)
    return memoria.getvalue()


@pytest.fixture
def calendario_nuovo() -> bytes:
    """Una giornata fra due squadre che nella lega di demo non esistono."""
    return calendario_xlsx(
        [
            ("1ª Giornata lega", None, "6ª Giornata serie a"),
            ("MaGuardaCheRoba", 73.5, 72, "SkoReggina", "2-2"),
            ("A.S. Fregio", 0, 0, "Tiri Team", "-"),
        ]
    )


class TestIlCalendarioUfficiale:
    """Precaricare il campionato vero prima che i presidenti siano entrati."""

    def test_l_anteprima_dice_quali_squadre_nascerebbero(self, client, calendario_nuovo):
        """E' il dato da controllare prima di confermare: un nome scritto
        diversamente fa nascere una squadra in piu' invece di riconoscere
        quella che c'e' gia'."""
        entra(client)

        dati = client.post(
            "/api/importazione/calendario/anteprima", json=caricato(calendario_nuovo)
        ).json()

        assert dati["importabile"] is True
        assert dati["lette"] == 2
        assert dati["giornate"] == 1
        assert dati["giocate"] == 1
        assert dati["squadre_nuove"] == ["A.S. Fregio", "MaGuardaCheRoba", "SkoReggina"]
        assert "Tiri Team" in dati["squadre"]
        assert dati["senza_giornata_serie_a"] == 0

    def test_l_anteprima_non_crea_niente(self, client, calendario_nuovo):
        entra(client)
        prima = len(client.get("/api/squadre").json())

        client.post(
            "/api/importazione/calendario/anteprima", json=caricato(calendario_nuovo)
        )

        assert len(client.get("/api/squadre").json()) == prima

    def test_la_partita_non_giocata_arriva_senza_punti(self, client, calendario_nuovo):
        entra(client)

        righe = client.post(
            "/api/importazione/calendario/anteprima", json=caricato(calendario_nuovo)
        ).json()["righe"]

        ferma = next(r for r in righe if r["casa"] == "A.S. Fregio")
        assert ferma["punti_casa"] is None
        assert ferma["giornata_serie_a"] == 6

    def test_la_conferma_scrive_il_campionato_e_crea_le_squadre(
        self, client, calendario_nuovo
    ):
        entra(client)

        esito = client.post(
            "/api/importazione/calendario", json=caricato(calendario_nuovo)
        )

        assert esito.status_code == 200, esito.json()
        messaggio = esito.json()["messaggio"]
        assert "2 partite" in messaggio
        assert "SkoReggina" in messaggio
        assert "senza presidente" in messaggio
        nomi = {s["nome"] for s in client.get("/api/squadre").json()}
        assert {"MaGuardaCheRoba", "SkoReggina", "A.S. Fregio"} <= nomi
        partite = client.get("/api/campionato").json()["partite"]
        assert len(partite) == 2

    def test_le_squadre_create_sono_nella_lega_di_chi_importa(
        self, client, calendario_nuovo
    ):
        """Senza `lega_id` la squadra esisterebbe fuori da ogni lega: non la
        vedrebbe nessuno, calendario compreso."""
        from fantacalcio.data import archivio

        entra(client)
        client.post("/api/importazione/calendario", json=caricato(calendario_nuovo))

        squadre = archivio().squadre()
        nuova = squadre[squadre["nome"] == "SkoReggina"].iloc[0]
        assert int(nuova["lega_id"]) == 1

    def test_un_file_che_non_e_il_calendario_non_scrive_niente(self, client):
        entra(client)
        prima = len(client.get("/api/campionato").json()["partite"])

        risposta = client.post("/api/importazione/calendario", json=caricato(QUALUNQUE))

        assert risposta.status_code == 422
        assert len(client.get("/api/campionato").json()["partite"]) == prima

    def test_i_campi_del_calendario_stanno_nella_tabella_dei_formati(self, client):
        entra(client)

        dati = client.get("/api/importazione").json()

        nomi = [c["nome"] for c in dati["campi_calendario"]]
        assert any("Giornata lega" in n for n in nomi)
        assert any("serie a" in n.lower() for n in nomi)


@pytest.fixture
def tabellino_g1() -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / "dati" / "formazioni_leghe_g1.xlsx").read_bytes()


class TestIlTabellinoDiGiornata:
    """Registrare la giornata com'e' andata sulla piattaforma."""

    def test_l_anteprima_dice_cosa_entrerebbe(self, client, tabellino_g1):
        entra(client)

        dati = client.post(
            "/api/importazione/tabellino/anteprima", json=caricato(tabellino_g1)
        ).json()

        assert dati["leggibile"] is True
        assert dati["giornata"] == 1
        assert len(dati["partite"]) == 5
        assert dati["partite"][0]["punti_casa"] > 0

    def test_dice_quali_squadre_mancano_e_non_lascia_scrivere(self, client, tabellino_g1):
        """La demo ha altre squadre: senza quelle del file non si scrive
        niente, e il motivo si legge prima di premere."""
        entra(client)

        dati = client.post(
            "/api/importazione/tabellino/anteprima", json=caricato(tabellino_g1)
        ).json()

        assert dati["scrivibile"] is False
        assert len(dati["squadre_mancanti"]) == 9

    def test_i_giocatori_che_non_si_abbinano_si_vedono_prima(self, client, tabellino_g1):
        """Ognuno e' un voto che non entrera': dopo si vedrebbe solo dalla
        classifica."""
        entra(client)

        dati = client.post(
            "/api/importazione/tabellino/anteprima", json=caricato(tabellino_g1)
        ).json()

        assert len(dati["non_abbinati"]) > 100

    def test_un_file_che_non_e_il_tabellino_lo_dice(self, client):
        entra(client)

        dati = client.post(
            "/api/importazione/tabellino/anteprima", json=caricato(QUALUNQUE)
        ).json()

        assert dati["leggibile"] is False
        assert dati["problemi"]

    def test_scrivere_senza_le_squadre_non_passa(self, client, tabellino_g1):
        entra(client)

        risposta = client.post("/api/importazione/tabellino", json=caricato(tabellino_g1))

        assert risposta.status_code == 422
        assert "non presenti in lega" in risposta.json()["detail"]

    def test_lo_carica_solo_il_presidente(self, client, tabellino_g1):
        entra(client, "luca")

        risposta = client.post("/api/importazione/tabellino", json=caricato(tabellino_g1))

        assert risposta.status_code == 403
