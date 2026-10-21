"""Il listone visto dall'API: chi e' svincolato e chi puo' segnare gli Under 21."""

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


def listone(client) -> dict:
    return client.get("/api/giocatori").json()


def aggiungi_giocatore(id_: int, nome: str, nazionalita: str = "Italia") -> None:
    """Un giocatore finto nel listone, **senza** contratto con nessuna squadra."""
    from fantacalcio.data import archivio

    archivio().scrivi(
        "giocatori",
        [
            {
                "id": id_,
                "nome": nome,
                "club": "Roma",
                "ruoli": "A",
                "ingaggio": 1_000_000,
                "nazionalita": nazionalita,
                "italiano_u21": 0,
            }
        ],
        chiave="id",
    )


class TestGliSvincolati:
    """Sono gia' nel codice: qui si fissa che compaiano e che il conto torni."""

    def test_chi_non_ha_contratto_compare_come_svincolato(self, client):
        entra(client)
        aggiungi_giocatore(90_001, "Libero Finto")

        dati = listone(client)
        trovato = next(g for g in dati["giocatori"] if g["id"] == 90_001)

        assert trovato["squadra"] == dati["svincolato"]
        assert trovato["anni"] == 0

    def test_il_conteggio_degli_svincolati_e_giusto(self, client):
        from fantacalcio.data import archivio, svincolati

        entra(client)
        prima = listone(client)
        da_listone = sum(
            1 for g in prima["giocatori"] if g["squadra"] == prima["svincolato"]
        )

        aggiungi_giocatore(90_001, "Libero Finto")
        aggiungi_giocatore(90_002, "Libero Secondo")
        dopo = listone(client)
        svincolati_ora = [
            g for g in dopo["giocatori"] if g["squadra"] == dopo["svincolato"]
        ]

        assert len(svincolati_ora) == da_listone + 2
        # E coincide con la definizione del dominio: nessun contratto, nessuna squadra.
        assert {g["id"] for g in svincolati_ora} == svincolati(archivio())

    def test_chi_ha_un_contratto_non_e_svincolato(self, client):
        entra(client)
        dati = listone(client)
        con_squadra = [g for g in dati["giocatori"] if g["squadra"] != dati["svincolato"]]
        assert con_squadra
        assert all(g["anni"] > 0 for g in con_squadra)


class TestLoStatusUnder21:
    def test_lo_dice_chi_puo_modificarlo(self, client):
        entra(client, "Marco")
        assert listone(client)["posso_modificare_u21"] is True
        entra(client, "Luca")
        assert listone(client)["posso_modificare_u21"] is False

    def test_il_presidente_lo_segna_e_resta(self, client):
        entra(client, "Marco")
        aggiungi_giocatore(90_001, "Giovane Finto")

        risposta = client.put("/api/giocatori/90001/u21", json={"italiano_u21": True})

        assert risposta.status_code == 200
        assert risposta.json()["u21"] is True
        riletto = next(g for g in listone(client)["giocatori"] if g["id"] == 90_001)
        assert riletto["u21"] is True

    def test_si_toglie_come_si_mette(self, client):
        entra(client, "Marco")
        aggiungi_giocatore(90_001, "Giovane Finto")
        client.put("/api/giocatori/90001/u21", json={"italiano_u21": True})

        risposta = client.put("/api/giocatori/90001/u21", json={"italiano_u21": False})

        assert risposta.json()["u21"] is False

    def test_un_fantallenatore_non_puo_anche_saltando_il_pulsante(self, client):
        """Il controllo e' nel dominio: nascondere il pulsante non basta."""
        aggiungi_giocatore(90_001, "Giovane Finto")
        entra(client, "Luca")

        risposta = client.put("/api/giocatori/90001/u21", json={"italiano_u21": True})

        assert risposta.status_code == 403
        entra(client, "Marco")
        riletto = next(g for g in listone(client)["giocatori"] if g["id"] == 90_001)
        assert riletto["u21"] is False

    def test_senza_entrare_non_si_puo(self, client):
        assert (
            client.put("/api/giocatori/1/u21", json={"italiano_u21": True}).status_code
            == 401
        )

    def test_un_giocatore_inesistente_e_un_404(self, client):
        entra(client, "Marco")
        risposta = client.put("/api/giocatori/999999/u21", json={"italiano_u21": True})
        assert risposta.status_code == 404

    def test_uno_straniero_non_puo_essere_under_21_italiano(self, client):
        entra(client, "Marco")
        aggiungi_giocatore(90_003, "Straniero Finto", nazionalita="Francia")

        risposta = client.put("/api/giocatori/90003/u21", json={"italiano_u21": True})

        assert risposta.status_code == 422
        assert "Italia" in risposta.json()["detail"]

    def test_il_flag_decide_lo_slot_della_rosa(self, client):
        """Segnare un Under in rosa cambia i posti: e' il motivo per cui conta."""
        from fantacalcio.data import archivio, carica_rose

        entra(client, "Marco")
        rosa = next(iter(carica_rose(archivio()).values()))
        da_segnare = next(g for g in rosa.giocatori if not g.under_21() and g.italiano)
        prima = rosa.u21_in_rosa()

        client.put(f"/api/giocatori/{da_segnare.id}/u21", json={"italiano_u21": True})

        dopo = carica_rose(archivio())[rosa.squadra.id]
        assert dopo.u21_in_rosa() == prima + 1
