"""Registrarsi dal sito nuovo.

Il modulo Streamlit c'era gia': qui si prova che la versione React applica le
**stesse** regole, perche' sono le stesse funzioni di dominio. Quel che si
controlla davvero e' il contorno — il primo utente diventa presidente, la
sessione parte da sola, e un database che rifiuta le scritture lo dice invece
di far sparire l'iscrizione.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

VALIDO = {
    "nome": "Chiara",
    "cognome": "Rossi",
    "data_nascita": "24/03/1991",
    "sesso": "FEMMINA",
    "citta": "Cuneo",
    "squadra_preferita": "Juventus",
    "nome_utente": "chiara.rossi",
    "email": "chiara.rossi@esempio.it",
    "password": "unapasswordlunga",
    "conferma": "unapasswordlunga",
}


@pytest.fixture(autouse=True)
def segreto_di_prova(monkeypatch):
    monkeypatch.setenv("FANTA_SEGRETO_JWT", "segreto-lungo-abbastanza-solo-per-i-test")
    monkeypatch.setenv("FANTA_AMBIENTE", "sviluppo")


@pytest.fixture
def client(monkeypatch, db_demo):
    monkeypatch.setenv("FANTA_DB_DEMO", str(db_demo))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    # Vedi il commento gemello in test_api_accesso: senza svuotare la cache il
    # primo test fissa il file del database per tutti gli altri.
    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


@pytest.fixture
def client_vuoto(monkeypatch, tmp_path):
    """Un client su un database **senza utenti**: il caso del primo arrivato."""
    import sqlite3

    percorso = tmp_path / "vuoto.db"
    from fantacalcio.demo_data import costruisci_db

    costruisci_db(percorso)
    with sqlite3.connect(percorso) as conn:
        conn.execute("delete from utenti")

    monkeypatch.setenv("FANTA_DB_DEMO", str(percorso))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


class TestIlModulo:
    def test_si_apre_senza_essere_entrati(self, client):
        """E' la pagina d'ingresso: chiederle un cookie sarebbe un circolo."""
        assert client.get("/api/registrazione").status_code == 200

    def test_porta_le_tendine_dal_dominio(self, client):
        dati = client.get("/api/registrazione").json()
        assert [v["nome"] for v in dati["sessi"]] == [
            "MASCHIO",
            "FEMMINA",
            "ALTRO",
            "NON_DICHIARATO",
        ]
        assert "Juventus" in dati["squadre_preferite"]
        # L'ultima voce e' sempre «nessuna»: chi non tifa non deve mentire.
        assert dati["squadre_preferite"][-1].startswith("Nessuna")

    def test_porta_i_minimi_invece_di_farli_indovinare(self, client):
        """Le regole si mostrano accanto al campo, non solo nell'errore."""
        dati = client.get("/api/registrazione").json()
        assert dati["password_minima"] == 8
        assert dati["eta_minima"] == 13

    def test_con_utenti_gia_presenti_non_sei_il_primo(self, client):
        assert client.get("/api/registrazione").json()["primo_utente"] is False

    def test_su_un_database_vuoto_sei_il_primo(self, client_vuoto):
        assert client_vuoto.get("/api/registrazione").json()["primo_utente"] is True


class TestIscriversi:
    def test_crea_l_account_e_fa_entrare(self, client):
        risposta = client.post("/api/registrazione", json=VALIDO)
        assert risposta.status_code == 201
        assert risposta.json()["nome_utente"] == "chiara.rossi"

        # Il cookie c'e' gia': non serve ripassare dal modulo di accesso.
        assert client.get("/api/io").json()["nome_utente"] == "chiara.rossi"

    def test_il_nome_utente_si_normalizza(self, client):
        corpo = {**VALIDO, "nome_utente": "  Chiara.Rossi  "}
        assert client.post("/api/registrazione", json=corpo).json()["nome_utente"] == (
            "chiara.rossi"
        )

    def test_chi_arriva_dopo_e_un_fantallenatore(self, client):
        assert client.post("/api/registrazione", json=VALIDO).json()["ruolo"] == (
            "FANTALLENATORE"
        )

    def test_il_primo_arrivato_e_presidente(self, client_vuoto):
        """Senza, un database appena creato non avrebbe chi fonda la lega."""
        risposta = client_vuoto.post("/api/registrazione", json=VALIDO)
        assert risposta.status_code == 201
        assert risposta.json()["ruolo"] == "PRESIDENTE"
        assert risposta.json()["puo_importare"] is True

    def test_i_dati_anagrafici_finiscono_nel_profilo(self, client):
        client.post("/api/registrazione", json=VALIDO)
        profilo = client.get("/api/profilo").json()
        assert profilo["nome_completo"] == "Chiara Rossi"
        assert profilo["citta"] == "Cuneo"
        assert profilo["squadra_preferita"] == "Juventus"
        # Il profilo la mostra come la si scrive, non come la salva il database.
        assert profilo["data_nascita"] == "24/03/1991"

    def test_poi_si_entra_con_quelle_credenziali(self, client):
        client.post("/api/registrazione", json=VALIDO)
        client.post("/api/esci")
        risposta = client.post(
            "/api/accesso",
            json={"nome_utente": "chiara.rossi", "password": "unapasswordlunga"},
        )
        assert risposta.status_code == 200


class TestLeRegoleSonoQuelleDelDominio:
    """Non riscritte qui: sono le stesse che applica la versione Streamlit."""

    def test_nome_utente_gia_preso(self, client):
        corpo = {**VALIDO, "nome_utente": "marco"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "gia' preso" in risposta.json()["detail"]

    def test_email_gia_registrata(self, client):
        corpo = {**VALIDO, "email": "marco@esempio.it"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "gia' registrato" in risposta.json()["detail"]

    def test_password_troppo_corta(self, client):
        corpo = {**VALIDO, "password": "corta", "conferma": "corta"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "almeno 8" in risposta.json()["detail"]

    def test_le_password_non_coincidono(self, client):
        corpo = {**VALIDO, "conferma": "un-altra-password"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "non coincidono" in risposta.json()["detail"]

    def test_nome_utente_troppo_corto(self, client):
        corpo = {**VALIDO, "nome_utente": "ab"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "almeno 3" in risposta.json()["detail"]

    def test_email_malformata(self, client):
        corpo = {**VALIDO, "email": "non-e-una-email"}
        assert client.post("/api/registrazione", json=corpo).status_code == 422

    @pytest.mark.parametrize(
        "data,atteso",
        [
            ("", "non puo' essere vuota"),
            ("32/01/1990", "non e' una data esistente"),
            ("24/03/2099", "non puo' essere nel futuro"),
            ("pippo", "si scrive gg/mm/aaaa"),
        ],
    )
    def test_date_di_nascita_impossibili(self, client, data, atteso):
        corpo = {**VALIDO, "data_nascita": data}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert atteso in risposta.json()["detail"]

    def test_troppo_giovane(self, client):
        from datetime import date

        quest_anno = date.today().year
        corpo = {**VALIDO, "data_nascita": f"01/01/{quest_anno - 5}"}
        risposta = client.post("/api/registrazione", json=corpo)
        assert risposta.status_code == 422
        assert "almeno 13 anni" in risposta.json()["detail"]

    def test_una_squadra_sconosciuta_non_fa_fallire_l_iscrizione(self, client):
        """Diventa «Altro (Italia)»: non e' un motivo per respingere nessuno."""
        corpo = {**VALIDO, "squadra_preferita": "Dinamo Kiev"}
        assert client.post("/api/registrazione", json=corpo).status_code == 201
        assert client.get("/api/profilo").json()["squadra_preferita"] == "Altro (Italia)"

    def test_un_sesso_sconosciuto_non_fa_fallire_l_iscrizione(self, client):
        corpo = {**VALIDO, "sesso": "QUALCOSA"}
        assert client.post("/api/registrazione", json=corpo).status_code == 201

    @pytest.mark.parametrize("campo", ["nome", "cognome", "citta"])
    def test_i_campi_obbligatori_non_possono_essere_vuoti(self, client, campo):
        corpo = {**VALIDO, campo: ""}
        assert client.post("/api/registrazione", json=corpo).status_code == 422


class TestQuandoIlDatabaseRifiuta:
    def test_lo_dice_invece_di_perdere_l_iscrizione(self, client, monkeypatch):
        """Il caso quasi sempre vero e' la chiave `anon` invece della
        `service_role`: la RLS blocca le scritture, e chi pubblica deve
        capirlo dal messaggio invece di perderci mezz'ora."""
        from api.rotte import registrazione

        def rifiuta(*_args, **_kwargs):
            raise RuntimeError("new row violates row-level security policy")

        monkeypatch.setattr(registrazione, "salva_credenziali", rifiuta)

        risposta = client.post("/api/registrazione", json=VALIDO)
        assert risposta.status_code == 503
        assert "service_role" in risposta.json()["detail"]
