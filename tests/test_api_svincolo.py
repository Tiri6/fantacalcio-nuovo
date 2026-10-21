"""Lo svincolo (art. 7) visto dall'API: chi puo', quanto costa, cosa resta scritto.

La formula del Lodo Origi ha i suoi test in `test_mercato.py`, con l'esempio
dell'articolo. Qui si guarda che il giro intero torni: il permesso e' del
presidente anche sulla propria squadra, un giocatore appena assegnato si puo'
svincolare, un secondo svincolo dello stesso giocatore non raddoppia il debito,
e il Cap residuo che la pagina mostra e' quello che il server ha calcolato.
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


def entra(client, chi="marco"):
    client.post("/api/esci")
    risposta = client.post(
        "/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"}
    )
    assert risposta.status_code == 200, risposta.json()


def squadra(client, id_: int) -> dict:
    return client.get(f"/api/squadre/{id_}").json()


def con_anni(client, id_: int, minimo: int = 3) -> dict:
    """Un giocatore della rosa con abbastanza anni da avere un valore residuo."""
    return next(g for g in squadra(client, id_)["rosa"] if g["anni_residui"] >= minimo)


def svincola(client, id_: int, giocatore: int, motivo: str = "riparazione"):
    return client.post(
        f"/api/squadre/{id_}/svincoli", json={"giocatore_id": giocatore, "motivo": motivo}
    )


class TestChiPuo:
    def test_il_presidente_svincola_anche_dalla_propria_squadra(self, client):
        entra(client, "marco")
        g = con_anni(client, 1)
        assert svincola(client, 1, g["id"]).status_code == 200

    def test_il_presidente_svincola_da_un_altra_squadra(self, client):
        entra(client, "marco")
        g = con_anni(client, 2)
        assert svincola(client, 2, g["id"]).status_code == 200

    def test_un_fantallenatore_non_svincola_nemmeno_dalla_sua(self, client):
        """Piu' stretto di `puo_gestire`: e' del presidente e basta."""
        entra(client, "luca")
        mia = next(s["id"] for s in client.get("/api/squadre").json() if s["e_mia"])
        g = con_anni(client, mia)

        risposta = svincola(client, mia, g["id"])

        assert risposta.status_code == 403
        assert any(x["id"] == g["id"] for x in squadra(client, mia)["rosa"])

    def test_a_chi_non_puo_il_pannello_non_porta_giocatori(self, client):
        entra(client, "luca")
        dati = client.get("/api/squadre/1/svincoli").json()
        assert dati["posso_svincolare"] is False
        assert dati["giocatori"] == []

    def test_senza_entrare_non_si_puo(self, client):
        assert (
            client.post(
                "/api/squadre/1/svincoli",
                json={"giocatore_id": 1, "motivo": "riparazione"},
            ).status_code
            == 401
        )


class TestQuantoCosta:
    def test_in_riparazione_restano_buonuscita_e_ingaggio_a_carico(self, client):
        entra(client)
        g = con_anni(client, 1)
        prima = squadra(client, 1)

        esito = svincola(client, 1, g["id"], "riparazione")

        assert esito.status_code == 200
        dopo = squadra(client, 1)
        voce = dopo["registro_dead_money"][-1]
        assert voce["giocatore"] == g["nome"]
        assert voce["buonuscita"] == g["dead_money_se_tagliato"]
        assert voce["buonuscita"] > 0
        assert voce["ingaggio_a_carico"] == g["ingaggio"]
        assert voce["totale"] == voce["buonuscita"] + g["ingaggio"]
        assert len(dopo["registro_dead_money"]) == len(prima["registro_dead_money"]) + 1

    def test_il_cap_residuo_lo_calcola_il_server_e_conta_gli_svincoli(self, client):
        """Il Cap residuo lo fa il server: include dead money e ingaggio a carico."""
        entra(client)
        g = con_anni(client, 1)
        prima = squadra(client, 1)["conti"]

        svincola(client, 1, g["id"], "riparazione")
        dopo = squadra(client, 1)["conti"]

        # L'ingaggio esce dal monte ma resta a carico, e la buonuscita si somma:
        # la spesa sul Cap cresce della sola buonuscita.
        assert dopo["monte_ingaggi"] == pytest.approx(
            prima["monte_ingaggi"] - g["ingaggio"]
        )
        assert dopo["spesa_salariale"] == pytest.approx(
            prima["spesa_salariale"] + g["dead_money_se_tagliato"]
        )
        assert dopo["cap_residuo"] == pytest.approx(
            dopo["limite_cap"] - dopo["spesa_salariale"]
        )
        assert dopo["cap_residuo"] < prima["cap_residuo"]

    def test_prima_dell_asta_non_resta_niente_sul_cap(self, client):
        entra(client)
        g = con_anni(client, 1)
        prima = squadra(client, 1)

        svincola(client, 1, g["id"], "pre-asta")
        dopo = squadra(client, 1)

        assert dopo["registro_dead_money"] == prima["registro_dead_money"]
        assert dopo["conti"]["spesa_salariale"] == pytest.approx(
            prima["conti"]["spesa_salariale"] - g["ingaggio"]
        )
        assert dopo["conti"]["cap_residuo"] > prima["conti"]["cap_residuo"]

    def test_la_correzione_non_addebita_niente(self, client):
        entra(client)
        g = con_anni(client, 1)
        prima = squadra(client, 1)

        svincola(client, 1, g["id"], "correzione")

        assert squadra(client, 1)["registro_dead_money"] == prima["registro_dead_money"]

    def test_gli_anni_si_liberano_sempre(self, client):
        entra(client)
        g = con_anni(client, 1)
        prima = squadra(client, 1)["conti"]["anni_impegnati"]

        svincola(client, 1, g["id"], "pre-asta")

        assert squadra(client, 1)["conti"]["anni_impegnati"] == prima - g["anni_residui"]


class TestIlRegistro:
    def test_e_visibile_dopo_lo_svincolo_a_tutta_la_lega(self, client):
        entra(client, "marco")
        g = con_anni(client, 2)
        svincola(client, 2, g["id"])

        # Lo vede anche chi non e' presidente: i debiti della lega non sono segreti.
        entra(client, "luca")
        registro = squadra(client, 2)["registro_dead_money"]
        assert any(v["giocatore"] == g["nome"] for v in registro)

    def test_una_squadra_senza_svincoli_ha_il_registro_vuoto(self, client):
        from fantacalcio.data import archivio

        archivio().svuota("dead_money")
        entra(client)
        assert squadra(client, 1)["registro_dead_money"] == []


class TestSvincolareDueVolte:
    def test_il_secondo_svincolo_dello_stesso_giocatore_si_rifiuta(self, client):
        """E non raddoppia il debito: il giocatore non e' piu' in rosa."""
        entra(client)
        g = con_anni(client, 1)
        prima = len(squadra(client, 1)["registro_dead_money"])

        primo = svincola(client, 1, g["id"])
        secondo = svincola(client, 1, g["id"])

        assert primo.status_code == 200
        assert secondo.status_code == 422
        assert len(squadra(client, 1)["registro_dead_money"]) == prima + 1


class TestUnGiocatoreAppenaAssegnato:
    def test_si_puo_svincolare_subito(self, client):
        entra(client)
        libero = client.get("/api/assegnazioni").json()["liberi"][0]
        assegnato = client.post(
            "/api/assegnazioni",
            json={"giocatore_id": libero["id"], "squadra_id": 1, "anni": 3},
        )
        assert assegnato.status_code == 200
        prima = len(squadra(client, 1)["registro_dead_money"])

        esito = svincola(client, 1, libero["id"])

        assert esito.status_code == 200
        dopo = squadra(client, 1)
        assert all(g["id"] != libero["id"] for g in dopo["rosa"])
        assert len(dopo["registro_dead_money"]) == prima + 1
        # E torna fra gli assegnabili.
        liberi = client.get("/api/assegnazioni").json()["liberi"]
        assert any(x["id"] == libero["id"] for x in liberi)


class TestDueRichiesteInsieme:
    def test_un_doppio_invio_non_lascia_due_debiti(self, client, db_demo):
        """Quattro richieste identiche, in contemporanea: ne passa una sola.

        Prima del blocco ne passavano piu' d'una e ognuna scriveva il suo Dead
        Money: un giocatore, quattro debiti.
        """
        import threading

        entra(client)
        g = con_anni(client, 1)
        prima = len(squadra(client, 1)["registro_dead_money"])
        esiti: list[int] = []
        via = threading.Barrier(4)

        def invia():
            altro = TestClient(client.app)
            altro.post(
                "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
            )
            via.wait()
            esiti.append(svincola(altro, 1, g["id"]).status_code)

        fili = [threading.Thread(target=invia) for _ in range(4)]
        for f in fili:
            f.start()
        for f in fili:
            f.join()

        assert sorted(esiti) == [200, 422, 422, 422]
        assert len(squadra(client, 1)["registro_dead_money"]) == prima + 1
