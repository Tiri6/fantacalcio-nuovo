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

    def test_un_file_che_non_e_excel_lo_dice(self, client):
        entra(client)
        dati = client.post(
            "/api/importazione/listone/anteprima",
            json=caricato("sono un csv, non xlsx"),
        ).json()
        assert dati["importabile"] is False
        assert any("Excel" in e["messaggio"] for e in dati["errori"])

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
