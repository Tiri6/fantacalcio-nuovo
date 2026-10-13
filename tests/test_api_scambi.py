"""Scambi visti dall'API: chi puo' fare cosa, e cosa ferma uno scambio.

Il ciclo di vita e le regole stanno nel dominio e hanno gia' i loro test:
qui si prova il contorno. Che i permessi valgano anche a bottone nascosto,
che una proposta non valida **non si salvi** ma torni indietro con le sue
violazioni, e che la ratifica sposti davvero i giocatori.
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


def un_giocatore(client, squadra: int) -> int:
    """Un giocatore con contratto lungo: cosi' lo scambio non tocca la
    regola «1/3», che conta i contratti annuali."""
    rosa = client.get(f"/api/squadre/{squadra}").json()["rosa"]
    return next(g["id"] for g in rosa if g["anni_residui"] > 1)


class TestLaPagina:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/scambi").status_code == 401

    def test_porta_le_squadre_con_cui_scambiare(self, client):
        entra(client)
        dati = client.get("/api/scambi").json()
        assert len(dati["squadre"]) == 10
        assert dati["mia_squadra_id"] == 1

    def test_dice_quanti_scambi_restano(self, client):
        entra(client)
        dati = client.get("/api/scambi").json()
        assert dati["conclusi"] == 0
        assert dati["residui"] is None or dati["residui"] >= 0


class TestProporre:
    def test_uno_scambio_sensato_parte(self, client):
        entra(client)
        mio = un_giocatore(client, 1)
        suo = un_giocatore(client, 2)

        risposta = client.post(
            "/api/scambi",
            json={"squadra_b_id": 2, "da_me": [mio], "da_loro": [suo], "note": "ok?"},
        )
        assert risposta.status_code == 200, risposta.text
        esito = risposta.json()
        assert esito["inviata"] is True
        assert esito["scambio"]["stato"] == "PROPOSTO"
        assert len(esito["scambio"]["movimenti"]) == 2

    def test_lo_scambio_compare_nell_elenco(self, client):
        entra(client)
        client.post(
            "/api/scambi",
            json={
                "squadra_b_id": 2,
                "da_me": [un_giocatore(client, 1)],
                "da_loro": [un_giocatore(client, 2)],
            },
        )
        assert len(client.get("/api/scambi").json()["scambi"]) == 1

    def test_con_se_stessi_non_si_scambia(self, client):
        entra(client)
        risposta = client.post(
            "/api/scambi", json={"squadra_b_id": 1, "da_me": [un_giocatore(client, 1)]}
        )
        assert risposta.status_code == 422
        assert "se stessi" in risposta.json()["detail"]

    def test_uno_scambio_vuoto_non_passa(self, client):
        entra(client)
        risposta = client.post("/api/scambi", json={"squadra_b_id": 2})
        assert risposta.json()["inviata"] is False
        assert "scambio_vuoto" in {v["codice"] for v in risposta.json()["violazioni"]}

    def test_una_proposta_invalida_non_si_salva_ma_torna_indietro(self, client):
        """Chi l'ha composta deve vedere cosa non va, non perdere il lavoro."""
        entra(client)
        risposta = client.post("/api/scambi", json={"squadra_b_id": 2})
        assert risposta.json()["inviata"] is False
        assert risposta.json()["scambio"] is None
        assert client.get("/api/scambi").json()["scambi"] == []

    def test_una_squadra_che_non_esiste(self, client):
        entra(client)
        risposta = client.post(
            "/api/scambi", json={"squadra_b_id": 999, "da_me": [un_giocatore(client, 1)]}
        )
        assert risposta.status_code == 404


class TestIPermessi:
    """Li solleva il dominio: nascondere un bottone non e' un controllo."""

    def proponi(self, client) -> int:
        entra(client, "Luca")  # squadra 2
        mio = un_giocatore(client, 2)
        suo = un_giocatore(client, 3)
        esito = client.post(
            "/api/scambi", json={"squadra_b_id": 3, "da_me": [mio], "da_loro": [suo]}
        ).json()
        return esito["scambio"]["id"]

    def test_chi_riceve_accetta(self, client):
        identificativo = self.proponi(client)
        entra(client, "Giulia")  # squadra 3, la destinataria
        risposta = client.post(
            f"/api/scambi/{identificativo}", json={"azione": "accetta"}
        )
        assert risposta.status_code == 200
        assert risposta.json()["stato"] == "ACCETTATO"

    def test_un_estraneo_non_accetta(self, client):
        identificativo = self.proponi(client)
        entra(client, "Andrea")  # squadra 4: non c'entra niente
        risposta = client.post(
            f"/api/scambi/{identificativo}", json={"azione": "accetta"}
        )
        assert risposta.status_code == 403

    def test_chi_propone_non_accetta_da_solo(self, client):
        identificativo = self.proponi(client)
        entra(client, "Luca")
        assert (
            client.post(
                f"/api/scambi/{identificativo}", json={"azione": "accetta"}
            ).status_code
            == 403
        )

    def test_chi_propone_puo_ritirare(self, client):
        identificativo = self.proponi(client)
        entra(client, "Luca")
        risposta = client.post(
            f"/api/scambi/{identificativo}", json={"azione": "annulla"}
        )
        assert risposta.json()["stato"] == "ANNULLATO"

    def test_solo_il_presidente_ratifica(self, client):
        identificativo = self.proponi(client)
        entra(client, "Giulia")
        client.post(f"/api/scambi/{identificativo}", json={"azione": "accetta"})
        risposta = client.post(
            f"/api/scambi/{identificativo}", json={"azione": "ratifica"}
        )
        assert risposta.status_code == 403

    def test_non_si_accetta_due_volte(self, client):
        identificativo = self.proponi(client)
        entra(client, "Giulia")
        client.post(f"/api/scambi/{identificativo}", json={"azione": "accetta"})
        risposta = client.post(
            f"/api/scambi/{identificativo}", json={"azione": "accetta"}
        )
        assert risposta.status_code == 403
        # E' lo stato a fermarlo, non il permesso: Giulia poteva accettare,
        # ma l'ha gia' fatto.
        assert "nello stato «Accettato»" in risposta.json()["detail"]


class TestRatificare:
    def test_i_giocatori_cambiano_davvero_squadra(self, client):
        entra(client)
        mio = un_giocatore(client, 1)
        suo = un_giocatore(client, 2)
        esito = client.post(
            "/api/scambi", json={"squadra_b_id": 2, "da_me": [mio], "da_loro": [suo]}
        ).json()
        identificativo = esito["scambio"]["id"]

        entra(client, "Luca")  # squadra 2 accetta
        client.post(f"/api/scambi/{identificativo}", json={"azione": "accetta"})

        entra(client)  # il presidente ratifica
        risposta = client.post(
            f"/api/scambi/{identificativo}",
            json={"azione": "ratifica", "giornata_efficacia": 12},
        )
        assert risposta.status_code == 200, risposta.text
        assert risposta.json()["stato"] == "RATIFICATO"
        assert risposta.json()["giornata_efficacia"] == 12

        mia = {g["id"] for g in client.get("/api/squadre/1").json()["rosa"]}
        altra = {g["id"] for g in client.get("/api/squadre/2").json()["rosa"]}
        assert suo in mia and mio not in mia
        assert mio in altra and suo not in altra

    def test_le_dimensioni_delle_rose_restano_quelle(self, client):
        entra(client)
        prima = client.get("/api/squadre/1").json()["conti"]["giocatori"]
        mio = un_giocatore(client, 1)
        suo = un_giocatore(client, 2)
        esito = client.post(
            "/api/scambi", json={"squadra_b_id": 2, "da_me": [mio], "da_loro": [suo]}
        ).json()
        entra(client, "Luca")
        client.post(f"/api/scambi/{esito['scambio']['id']}", json={"azione": "accetta"})
        entra(client)
        client.post(f"/api/scambi/{esito['scambio']['id']}", json={"azione": "ratifica"})

        assert client.get("/api/squadre/1").json()["conti"]["giocatori"] == prima

    def test_non_si_ratifica_una_proposta_non_accettata(self, client):
        entra(client)
        esito = client.post(
            "/api/scambi",
            json={
                "squadra_b_id": 2,
                "da_me": [un_giocatore(client, 1)],
                "da_loro": [un_giocatore(client, 2)],
            },
        ).json()
        risposta = client.post(
            f"/api/scambi/{esito['scambio']['id']}", json={"azione": "ratifica"}
        )
        assert risposta.status_code == 403

    def test_un_azione_inventata_si_rifiuta(self, client):
        entra(client)
        esito = client.post(
            "/api/scambi",
            json={
                "squadra_b_id": 2,
                "da_me": [un_giocatore(client, 1)],
                "da_loro": [un_giocatore(client, 2)],
            },
        ).json()
        risposta = client.post(
            f"/api/scambi/{esito['scambio']['id']}", json={"azione": "pasticcio"}
        )
        assert risposta.status_code == 422

    def test_uno_scambio_che_non_esiste(self, client):
        entra(client)
        assert (
            client.post("/api/scambi/999", json={"azione": "accetta"}).status_code == 404
        )


class TestIProlungamenti:
    """Il V3 li ha aboliti, ma e' un parametro: se la lega li rivota la
    pagina deve adeguarsi da sola invece di continuare a dire che non si
    fanno. La pagina lo diceva scritto a mano."""

    def test_la_pagina_dice_se_si_possono_fare(self, client):
        entra(client)

        pagina = client.get("/api/scambi").json()

        assert pagina["prolungamenti_ammessi"] is False
        assert pagina["anni_contratto_massimo"] == 5

    def test_col_v3_una_proposta_che_prolunga_viene_respinta(self, client):
        """A dire di no e' `valida_scambio`, non un controllo scritto qui."""
        entra(client)
        rose = client.get("/api/squadre").json()
        mia = next(s for s in rose if s["e_mia"])
        altra = next(s for s in rose if not s["e_mia"])
        miei = client.get(f"/api/squadre/{mia['id']}").json()["rosa"]
        loro = client.get(f"/api/squadre/{altra['id']}").json()["rosa"]

        esito = client.post(
            "/api/scambi",
            json={
                "squadra_b_id": altra["id"],
                "da_me": [miei[0]["id"]],
                "da_loro": [loro[0]["id"]],
                "prolungamenti": {str(miei[0]["id"]): 5},
            },
        ).json()

        assert esito["inviata"] is False
        assert any("prolung" in v["messaggio"].lower() for v in esito["violazioni"])

    def test_dice_da_che_giornata_avrebbe_effetto(self, client):
        """L'articolo 8 vuole 24 ore di preavviso: chi ratifica deve
        leggerlo, non indovinarlo. Su Streamlit lo leggeva, qui no."""
        entra(client)

        pagina = client.get("/api/scambi").json()

        for scambio in pagina["scambi"]:
            assert scambio["efficacia_proposta"] >= 1
