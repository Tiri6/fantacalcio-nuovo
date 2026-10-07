"""Impostazioni: il profilo e la lega, visti dall'API.

Due cose girano qui dentro che esistono **in chiaro una volta sola** — la
password temporanea e il codice di recupero — e i test ci stanno sopra: che
nascano, che funzionino, e che non si possano rileggere dopo.

E tre permessi che non sono lo stesso permesso: amministrare la lega,
cambiarne le regole (`admin_id`), reimpostare le password (presidente).
Confonderli vorrebbe dire dare a qualcuno una chiave che non gli spetta.
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


def entra(client, chi="marco", password="fantanuovo26"):
    client.post("/api/esci")
    risposta = client.post(
        "/api/accesso", json={"nome_utente": chi, "password": password}
    )
    return risposta


class TestProfilo:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/profilo").status_code == 401

    def test_dice_chi_sei_e_dove_sei(self, client):
        entra(client)
        p = client.get("/api/profilo").json()
        assert p["nome_utente"] == "marco"
        assert p["ruolo_etichetta"] == "Presidente"
        assert p["squadra"]
        assert p["nome_lega"]

    def test_il_codice_di_recupero_non_si_rilegge(self, client):
        """Esiste in chiaro solo nell'istante in cui nasce.

        Se tornasse anche dal profilo, varrebbe quanto una password scritta
        in chiaro nel database: chiunque veda una sessione aperta se lo
        porterebbe via.
        """
        entra(client)
        assert client.get("/api/profilo").json()["ha_codice_recupero"] is False

        codice = client.post("/api/profilo/codice-recupero").json()["codice"]
        assert codice

        dopo = client.get("/api/profilo")
        assert dopo.json()["ha_codice_recupero"] is True
        assert codice not in dopo.text


class TestCambioPassword:
    def cambia(self, client, attuale, nuova, conferma=None):
        return client.put(
            "/api/profilo/password",
            json={
                "attuale": attuale,
                "nuova": nuova,
                "conferma": conferma if conferma is not None else nuova,
            },
        )

    def test_senza_quella_attuale_non_si_cambia(self, client):
        """Non e' una formalita': senza, chiunque trovasse una sessione aperta
        si prenderebbe l'account per sempre."""
        entra(client)
        assert self.cambia(client, "sbagliata", "unaNuovaBuona1").status_code == 422

    def test_le_due_devono_coincidere(self, client):
        entra(client)
        risposta = self.cambia(client, "fantanuovo26", "unaNuovaBuona1", "altraDiversa1")
        assert risposta.status_code == 422
        assert "coincidono" in risposta.json()["detail"]

    def test_non_si_rimette_la_stessa(self, client):
        entra(client)
        risposta = self.cambia(client, "fantanuovo26", "fantanuovo26")
        assert risposta.status_code == 422

    def test_troppo_corta_non_passa(self, client):
        entra(client)
        assert self.cambia(client, "fantanuovo26", "abc").status_code == 422

    def test_cambiata_si_entra_con_quella_nuova(self, client):
        entra(client)
        assert self.cambia(client, "fantanuovo26", "unaNuovaBuona1").status_code == 204

        assert entra(client, "marco", "fantanuovo26").status_code == 401
        assert entra(client, "marco", "unaNuovaBuona1").status_code == 200


class TestLega:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/lega").status_code == 401

    def test_porta_codice_partecipanti_e_regole(self, client):
        entra(client)
        d = client.get("/api/lega").json()
        assert d["codice_invito"]
        assert len(d["partecipanti"]) == 10
        assert d["regole"] and all(g["voci"] for g in d["regole"])
        assert len(d["fasce_gol"]) == 6
        assert d["bonus"]

    def test_i_numeri_delle_regole_vengono_dalle_opzioni(self, client):
        """Nessuna soglia si riscrive qui: la lega le cambia per votazione."""
        from fantacalcio.data import archivio, carica_leghe

        entra(client)
        d = client.get("/api/lega").json()
        opzioni = next(iter(carica_leghe(archivio()).values())).opzioni

        assert d["posti"] == opzioni.partecipanti
        assert d["moduli_ammessi"] == list(opzioni.moduli_ammessi)
        assert d["fasce_gol"][0]["da"] == f"{opzioni.soglia_primo_gol:g}+"

    def test_il_codice_lo_vedono_tutti_i_membri(self, client):
        """E' quello che si gira agli amici: non e' un segreto da presidenti."""
        entra(client, "luca")
        assert client.get("/api/lega").json()["codice_invito"]

    def test_inviti_e_richieste_solo_a_chi_amministra(self, client):
        entra(client, "marco")
        client.post("/api/lega/inviti", json={"email": "tizio@esempio.it"})

        entra(client, "luca")
        d = client.get("/api/lega").json()
        assert d["posso_amministrare"] is False
        assert d["inviti"] == []
        assert d["richieste_password"] == []

    def test_i_tre_permessi_sono_distinti(self, client):
        """Amministrare, cambiare le regole e reimpostare le password non
        sono lo stesso permesso, e il dominio li decide separatamente."""
        entra(client, "marco")
        d = client.get("/api/lega").json()
        assert d["posso_amministrare"] is True
        assert d["posso_cambiare_regole"] is True
        assert d["posso_reimpostare_password"] is True

        entra(client, "luca")
        d = client.get("/api/lega").json()
        assert d["posso_amministrare"] is False
        assert d["posso_cambiare_regole"] is False
        assert d["posso_reimpostare_password"] is False


class TestInviti:
    def test_il_fantallenatore_non_invita(self, client):
        entra(client, "luca")
        risposta = client.post("/api/lega/inviti", json={"email": "x@esempio.it"})
        assert risposta.status_code == 403

    def test_il_presidente_invita(self, client):
        entra(client, "marco")
        risposta = client.post("/api/lega/inviti", json={"email": "x@esempio.it"})
        assert risposta.status_code == 201
        assert any(i["email"] == "x@esempio.it" for i in risposta.json()["inviti"])

    def test_un_indirizzo_non_valido_lo_dice_il_dominio(self, client):
        entra(client, "marco")
        risposta = client.post("/api/lega/inviti", json={"email": "non-una-email"})
        assert risposta.status_code == 422

    def test_lo_stesso_indirizzo_due_volte_e_un_conflitto(self, client):
        entra(client, "marco")
        client.post("/api/lega/inviti", json={"email": "x@esempio.it"})
        doppio = client.post("/api/lega/inviti", json={"email": "x@esempio.it"})
        assert doppio.status_code == 409


class TestRuoli:
    def assegna(self, client, chi, ruolo):
        return client.put("/api/lega/ruoli", json={"nome_utente": chi, "ruolo": ruolo})

    def test_il_fantallenatore_non_cambia_ruoli(self, client):
        entra(client, "luca")
        assert self.assegna(client, "andrea", "EDITOR").status_code == 403

    def test_il_presidente_promuove_a_editor(self, client):
        entra(client, "marco")
        risposta = self.assegna(client, "andrea", "EDITOR")
        assert risposta.status_code == 200
        andrea = next(
            p for p in risposta.json()["partecipanti"] if p["nome_utente"] == "andrea"
        )
        assert andrea["ruolo"] == "EDITOR"

    def test_il_proprio_ruolo_non_si_cambia(self, client):
        entra(client, "marco")
        assert self.assegna(client, "marco", "EDITOR").status_code == 422

    def test_la_presidenza_non_si_cede_da_una_tendina(self, client):
        entra(client, "marco")
        assert self.assegna(client, "andrea", "PRESIDENTE").status_code == 422

    def test_un_ruolo_inventato_non_passa(self, client):
        entra(client, "marco")
        assert self.assegna(client, "andrea", "IMPERATORE").status_code == 422

    def test_chi_non_e_in_questa_lega_non_si_tocca(self, client):
        entra(client, "marco")
        assert self.assegna(client, "nessuno", "EDITOR").status_code == 404


class TestReimpostaPassword:
    def test_il_fantallenatore_non_reimposta(self, client):
        entra(client, "luca")
        assert client.post("/api/lega/reimposta/andrea").status_code == 403

    def test_il_presidente_reimposta_e_la_temporanea_funziona(self, client):
        entra(client, "marco")
        risposta = client.post("/api/lega/reimposta/andrea")
        assert risposta.status_code == 200
        temporanea = risposta.json()["password"]

        dentro = entra(client, "andrea", temporanea)
        assert dentro.status_code == 200
        # Chi la riceve e' obbligato a sostituirla: vive pochi minuti.
        assert dentro.json()["deve_cambiare_password"] is True

    def test_la_vecchia_password_smette_di_valere(self, client):
        entra(client, "marco")
        client.post("/api/lega/reimposta/andrea")
        assert entra(client, "andrea", "fantanuovo26").status_code == 401

    def test_reimpostare_chiude_la_richiesta_aperta(self, client):
        """Lasciarla aperta vorrebbe dire che il presidente la rivede domani
        e reimposta una seconda volta per niente."""
        from fantacalcio.autenticazione import RichiestaPassword
        from fantacalcio.data import archivio, salva_richiesta_password

        entra(client, "marco")
        lega_id = client.get("/api/lega").json() and 1
        salva_richiesta_password(
            archivio(),
            RichiestaPassword(
                id=1, lega_id=lega_id, utente_id=None, nome_utente="andrea"
            ),
        )
        assert client.get("/api/lega").json()["richieste_password"]

        client.post("/api/lega/reimposta/andrea")
        assert client.get("/api/lega").json()["richieste_password"] == []

    def test_chi_non_esiste_da_404(self, client):
        entra(client, "marco")
        assert client.post("/api/lega/reimposta/nessuno").status_code == 404
