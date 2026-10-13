"""Registrare chi si e' preso chi, un giocatore alla volta.

La pagina serve a **prendere nota**, non a condurre il draft: una chiamata
concordata al telefono, uno scambio fatto a voce, un errore da correggere.
Per questo una rosa che sfora avvisa e non ferma — un sito che si rifiuta di
registrare quel che e' successo costringe a tenerne una copia altrove, ed e'
li' che i conti cominciano a divergere.
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

    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


def entra(client, chi="marco"):
    client.post("/api/esci")
    risposta = client.post(
        "/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"}
    )
    assert risposta.status_code == 200, risposta.json()


def un_libero(client) -> dict:
    return client.get("/api/assegnazioni").json()["liberi"][0]


class TestLaPagina:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/assegnazioni").status_code == 401

    def test_porta_liberi_squadre_e_limiti(self, client):
        entra(client)

        dati = client.get("/api/assegnazioni").json()

        assert dati["posso_assegnare"] is True
        assert len(dati["squadre"]) == 10
        assert dati["liberi"]
        assert dati["anni_massimo"] == 5
        assert dati["monte_anni"] == 66

    def test_ogni_squadra_dice_quanto_spazio_le_resta(self, client):
        """E' il numero che decide se un'assegnazione e' tranquilla: il
        browser non deve ricavarselo da solo — e soprattutto non deve
        ricavarselo **male**, perche' sul Cap pesa anche il Dead Money, che
        dagli ingaggi in rosa non si vede."""
        from fantacalcio.data import archivio, carica_rose

        entra(client)
        rose = carica_rose(archivio())

        squadre = client.get("/api/assegnazioni").json()["squadre"]

        for s in squadre:
            rosa = rose[s["id"]]
            assert s["spazio_salariale"] == pytest.approx(
                100_000_000 - rosa.spesa_salariale, abs=1
            )
            assert s["spazio_salariale"] <= 100_000_000 - s["monte_ingaggi"] + 1

    def test_i_liberi_dicono_se_sono_under_21(self, client):
        """Senza, chi assegna non sa se sta usando uno slot in piu'."""
        entra(client)

        liberi = client.get("/api/assegnazioni").json()["liberi"]

        assert all("u21" in g and "nazionalita" in g for g in liberi)

    def test_chi_non_e_presidente_la_vede_ma_non_assegna(self, client):
        entra(client, "luca")

        dati = client.get("/api/assegnazioni").json()

        assert dati["posso_assegnare"] is False


class TestAssegnare:
    def test_il_contratto_finisce_in_rosa(self, client):
        from fantacalcio.data import archivio, carica_rose

        entra(client)
        libero = un_libero(client)
        prima = carica_rose(archivio())[1]

        esito = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 3},
        )

        assert esito.status_code == 200
        assert esito.json()["fatta"] is True
        assert libero["nome"] in esito.json()["messaggio"]
        dopo = carica_rose(archivio())[1]
        assert dopo.dimensione == prima.dimensione + 1
        contratto = next(c for c in dopo.contratti if c.giocatore_id == libero["id"])
        assert contratto.anni_residui == 3

    def test_un_anno_e_al_singolare(self, client):
        entra(client)
        libero = un_libero(client)

        esito = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 1},
        ).json()

        assert "1 anno." in esito["messaggio"]

    def test_una_rosa_che_sfora_avvisa_e_registra_lo_stesso(self, client):
        """Chi assegna sta scrivendo quel che e' successo davvero: rifiutarlo
        vorrebbe dire tenerne una copia da un'altra parte."""
        from fantacalcio.data import archivio, carica_rose

        entra(client)
        libero = un_libero(client)

        esito = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 5},
        ).json()

        assert esito["fatta"] is True
        codici = [v["codice"] for v in esito["violazioni"]]
        assert "monte_anni" in codici
        assert any(v["bloccante"] for v in esito["violazioni"])
        # E in rosa c'e' finito davvero.
        rosa = carica_rose(archivio())[1]
        assert any(c.giocatore_id == libero["id"] for c in rosa.contratti)

    def test_l_anteprima_non_scrive_niente(self, client):
        from fantacalcio.data import archivio, carica_rose

        entra(client)
        libero = un_libero(client)
        prima = carica_rose(archivio())[1].dimensione

        esito = client.post(
            "/api/assegnazioni/anteprima",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 5},
        ).json()

        assert esito["fatta"] is False
        assert esito["violazioni"]
        assert carica_rose(archivio())[1].dimensione == prima

    def test_un_giocatore_di_un_altra_squadra_non_si_registra(self, client):
        """Questo invece non vuol dire niente: un giocatore sta in una rosa
        sola, e il messaggio dice di chi e'."""
        from fantacalcio.data import archivio, carica_rose

        entra(client)
        gia_di_qualcuno = carica_rose(archivio())[2].contratti[0].giocatore_id

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": gia_di_qualcuno, "squadra_id": 1, "anni": 2},
        )

        assert risposta.status_code == 422
        assert "gia' di" in risposta.json()["detail"]

    def test_sei_anni_non_passano(self, client):
        entra(client)
        libero = un_libero(client)

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 6},
        )

        assert risposta.status_code == 422
        assert "da 1 a 5" in risposta.json()["detail"]

    def test_zero_anni_li_ferma_pydantic(self, client):
        entra(client)
        libero = un_libero(client)

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 0},
        )

        assert risposta.status_code == 422

    def test_un_giocatore_che_non_esiste(self, client):
        entra(client)

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": 999_999, "squadra_id": 1, "anni": 2},
        )

        assert risposta.status_code == 422
        assert "non esiste" in risposta.json()["detail"]

    def test_una_squadra_che_non_esiste(self, client):
        entra(client)
        libero = un_libero(client)

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 999, "anni": 2},
        )

        assert risposta.status_code == 422

    def test_solo_il_presidente_registra(self, client):
        entra(client)
        libero = un_libero(client)
        entra(client, "luca")

        risposta = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 2},
        )

        assert risposta.status_code == 403
        assert "art. 1" in risposta.json()["detail"]
