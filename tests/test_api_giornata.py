"""La giornata vista dall'API: le partite, i due campi, e chi puo' calcolare.

Il conto ha i suoi test in `test_giornata.py` e `test_formazioni.py`. Qui si
prova quello che l'API aggiunge: che il punteggio **provvisorio** si veda
prima di salvarlo e sia lo stesso che poi viene scritto; che il calcolo sia
del presidente; e che una squadra senza formazione faccia saltare la sua
partita e non l'intera giornata.
"""

from __future__ import annotations

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
    client.post("/api/esci")
    client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})


def giornata(client, **parametri):
    return client.get("/api/giornata", params=parametri).json()


def schiera_tutti(client, numero: int) -> list[str]:
    """Fa schierare le dieci squadre e torna i nomi di chi gioca.

    Passa dalle credenziali di ciascuno invece di scrivere a mano nel
    database: cosi' le formazioni sono valide per davvero, perche' a crearle
    e' lo stesso codice che userebbe la gente.
    """
    from fantacalcio.demo_data import SQUADRE

    nomi: list[str] = []
    for _, presidente, *_ in SQUADRE:
        entra(client, presidente)
        dati = client.get("/api/formazione", params={"giornata": numero}).json()
        client.post(
            "/api/formazione",
            json={
                "giornata": numero,
                "competizione": "CAMPIONATO",
                "modulo": dati["modulo"],
                "titolari": dati["titolari"],
                "panchina": dati["panchina"],
            },
        )
        per_id = {g["id"]: g["nome"] for g in dati["rosa"]}
        nomi += [per_id[g] for g in dati["titolari"]]
    entra(client)
    return nomi


def csv_voti(nomi: list[str], voto: str = "6.5") -> str:
    return "giocatore;voto\n" + "".join(f"{n};{voto}\n" for n in nomi)


class TestLaPagina:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/giornata").status_code == 401

    def test_propone_la_prima_giornata_da_giocare(self, client):
        entra(client)
        dati = giornata(client)
        assert dati["calendario_vuoto"] is False
        assert dati["giornata"] in dati["giornate"]
        assert dati["partite"]

    def test_una_giornata_gia_disputata_mostra_il_risultato_salvato(self, client):
        entra(client)
        prima = giornata(client, giornata=1)
        partita = prima["partite"][0]
        assert partita["stato"] == "salvata"
        assert partita["gol_casa"] is not None
        assert partita["punti_casa"] is not None

    def test_senza_formazioni_le_partite_sono_da_giocare(self, client):
        entra(client)
        dati = giornata(client)
        assert all(p["stato"] == "da giocare" for p in dati["partite"])
        assert len(dati["senza_formazione"]) == 10

    def test_chi_non_calcola_lo_sa(self, client):
        entra(client, "Luca")
        assert giornata(client)["posso_calcolare"] is False


class TestIlCampo:
    def test_chi_ha_schierato_porta_i_suoi_reparti(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        schiera_tutti(client, numero)

        partita = giornata(client, giornata=numero)["partite"][0]

        assert partita["casa"]["ha_schierato"] is True
        assert [len(r) for r in partita["casa"]["reparti"]] == [1, 3, 4, 3]
        assert partita["casa"]["modulo"]
        # Senza voti nessun punteggio: il campo mostra solo chi gioca.
        assert all(
            g["punti"] is None for riga in partita["casa"]["reparti"] for g in riga
        )

    def test_coi_voti_il_punteggio_e_provvisorio_ma_c_e(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)
        client.post(
            "/api/giornata/voti",
            json={"giornata": numero, "testo": csv_voti(nomi)},
        )

        partita = giornata(client, giornata=numero)["partite"][0]

        assert partita["stato"] == "provvisoria"
        assert partita["punti_casa"] is not None
        assert partita["casa"]["tabellino"] is not None
        assert all(
            g["punti"] is not None for riga in partita["casa"]["reparti"] for g in riga
        )

    def test_chi_non_schiera_si_vede_subito(self, client):
        entra(client)
        dati = giornata(client)
        partita = dati["partite"][0]
        assert partita["casa"]["ha_schierato"] is False
        assert partita["casa"]["reparti"] == []
        assert partita["casa"]["modulo"] is None


class TestICaricareIVoti:
    def test_un_fantallenatore_e_respinto(self, client):
        entra(client, "Luca")
        risposta = client.post(
            "/api/giornata/voti", json={"giornata": 12, "testo": "giocatore;voto\n"}
        )
        assert risposta.status_code == 403
        assert "presidente" in risposta.json()["detail"]

    def test_il_testo_incollato_basta(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)

        risposta = client.post(
            "/api/giornata/voti",
            json={"giornata": numero, "testo": csv_voti(nomi[:5])},
        )

        assert risposta.status_code == 200
        assert risposta.json()["salvati"] == 5
        assert giornata(client, giornata=numero)["voti_caricati"] == 5

    def test_anche_un_file_in_base64(self, client):
        import base64

        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)
        grezzo = base64.b64encode(csv_voti(nomi[:3]).encode()).decode()

        risposta = client.post(
            "/api/giornata/voti",
            json={"giornata": numero, "contenuto_base64": grezzo},
        )

        assert risposta.status_code == 200
        assert risposta.json()["salvati"] == 3

    def test_chi_non_si_abbina_si_dice(self, client):
        """Un voto perso in silenzio e' un punteggio sbagliato che nessuno spiega."""
        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)

        risposta = client.post(
            "/api/giornata/voti",
            json={
                "giornata": numero,
                "testo": csv_voti(nomi[:3]) + "Nessuno Di Nessuno;7\n",
            },
        )

        assert risposta.status_code == 200
        assert risposta.json()["salvati"] == 3
        assert risposta.json()["non_abbinati"] == ["Nessuno Di Nessuno"]

    def test_un_file_in_cui_non_si_abbina_nessuno_e_un_errore(self, client):
        """Qui non e' una riga storta, e' il file sbagliato: meglio fermarsi."""
        entra(client)
        risposta = client.post(
            "/api/giornata/voti",
            json={"giornata": 12, "testo": "giocatore;voto\nNessuno Di Nessuno;7\n"},
        )
        assert risposta.status_code == 422
        assert "Controlla i nomi" in risposta.json()["detail"]

    def test_senza_niente_da_leggere_lo_dice(self, client):
        entra(client)
        risposta = client.post("/api/giornata/voti", json={"giornata": 12})
        assert risposta.status_code == 422
        assert "ne' un file" in risposta.json()["detail"]

    def test_un_base64_storto_e_un_422_leggibile(self, client):
        entra(client)
        risposta = client.post(
            "/api/giornata/voti",
            json={"giornata": 12, "contenuto_base64": "non-e-base64!!"},
        )
        assert risposta.status_code == 422
        assert "leggibile" in risposta.json()["detail"]


class TestCalcolare:
    def test_un_fantallenatore_e_respinto(self, client):
        entra(client, "Luca")
        risposta = client.post("/api/giornata/calcola", params={"giornata": 12})
        assert risposta.status_code == 403

    def test_senza_voti_non_calcola_e_lo_spiega(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        schiera_tutti(client, numero)

        risposta = client.post("/api/giornata/calcola", params={"giornata": numero})

        assert risposta.status_code == 200
        assert risposta.json()["calcolate"] == 0
        assert any("voti" in a for a in risposta.json()["avvisi"])

    def test_scrive_i_risultati_e_la_pagina_li_mostra_salvati(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)
        client.post(
            "/api/giornata/voti",
            json={"giornata": numero, "testo": csv_voti(nomi)},
        )
        prima = giornata(client, giornata=numero)["partite"][0]

        risposta = client.post("/api/giornata/calcola", params={"giornata": numero})

        assert risposta.status_code == 200
        assert risposta.json()["calcolate"] == 5
        dopo = giornata(client, giornata=numero)["partite"][0]
        assert dopo["stato"] == "salvata"
        # Il provvisorio era lo stesso conto, non una stima.
        assert dopo["punti_casa"] == prima["punti_casa"]
        assert dopo["gol_casa"] == prima["gol_casa"]

    def test_una_squadra_senza_formazione_salta_solo_la_sua_partita(self, client):
        from fantacalcio.demo_data import SQUADRE

        entra(client)
        numero = giornata(client)["giornata"]

        # Tutti tranne l'ultimo.
        nomi: list[str] = []
        for _, presidente, *_ in SQUADRE[:-1]:
            entra(client, presidente)
            dati = client.get("/api/formazione", params={"giornata": numero}).json()
            client.post(
                "/api/formazione",
                json={
                    "giornata": numero,
                    "competizione": "CAMPIONATO",
                    "modulo": dati["modulo"],
                    "titolari": dati["titolari"],
                    "panchina": dati["panchina"],
                },
            )
            per_id = {g["id"]: g["nome"] for g in dati["rosa"]}
            nomi += [per_id[g] for g in dati["titolari"]]

        entra(client)
        client.post(
            "/api/giornata/voti",
            json={"giornata": numero, "testo": csv_voti(nomi)},
        )

        esito = client.post("/api/giornata/calcola", params={"giornata": numero}).json()

        assert esito["calcolate"] == 4
        assert esito["saltate"] == 1
        assert "saltate per formazione mancante" in esito["messaggio"]

    def test_si_puo_ricalcolare_quando_arrivano_voti_corretti(self, client):
        entra(client)
        numero = giornata(client)["giornata"]
        nomi = schiera_tutti(client, numero)
        client.post(
            "/api/giornata/voti", json={"giornata": numero, "testo": csv_voti(nomi, "6")}
        )
        client.post("/api/giornata/calcola", params={"giornata": numero})
        con_sei = giornata(client, giornata=numero)["partite"][0]["punti_casa"]

        client.post(
            "/api/giornata/voti", json={"giornata": numero, "testo": csv_voti(nomi, "8")}
        )
        client.post("/api/giornata/calcola", params={"giornata": numero})
        con_otto = giornata(client, giornata=numero)["partite"][0]["punti_casa"]

        assert con_otto > con_sei

    def test_una_giornata_che_non_esiste_e_un_422(self, client):
        entra(client)
        risposta = client.post("/api/giornata/calcola", params={"giornata": 999})
        assert risposta.status_code == 422
        assert "Nessuna partita" in risposta.json()["detail"]
