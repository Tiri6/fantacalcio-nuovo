"""L'API: entrare, restare dentro, e restarne fuori.

E' lo strato che sostituisce `st.session_state`, quindi i test guardano
proprio quello che Streamlit faceva da solo e che adesso scriviamo noi: il
cookie, la sua scadenza, e il fatto che l'utente venga **riletto** a ogni
richiesta invece di essere ricostruito dal token.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import sicurezza


@pytest.fixture(autouse=True)
def segreto_di_prova(monkeypatch):
    monkeypatch.setenv("FANTA_SEGRETO_JWT", "segreto-lungo-abbastanza-solo-per-i-test")
    monkeypatch.setenv("FANTA_AMBIENTE", "sviluppo")


@pytest.fixture
def client(monkeypatch, db_demo):
    """Un client HTTP che legge dal database di demo."""
    monkeypatch.setenv("FANTA_DB_DEMO", str(db_demo))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    from api.main import app

    return TestClient(app)


class TestSegreto:
    def test_senza_segreto_non_si_firma(self, monkeypatch):
        """Meglio fermarsi che firmare col vuoto: un default finirebbe in
        produzione e chiunque lo conosca si fabbricherebbe un token."""
        monkeypatch.delenv("FANTA_SEGRETO_JWT", raising=False)
        with pytest.raises(sicurezza.SegretoMancante):
            sicurezza.crea_token("marco")

    def test_un_segreto_corto_e_rifiutato(self, monkeypatch):
        """PyJWT si limita a un warning, che in produzione non legge nessuno."""
        monkeypatch.setenv("FANTA_SEGRETO_JWT", "corto")
        with pytest.raises(sicurezza.SegretoMancante, match="almeno 32"):
            sicurezza.crea_token("marco")


class TestToken:
    def test_porta_il_nome_e_torna_indietro(self):
        token = sicurezza.crea_token("marco")
        sessione = sicurezza.leggi_token(token)
        assert sessione is not None
        assert sessione.nome_utente == "marco"

    def test_un_token_scaduto_non_vale(self):
        vecchio = datetime.now(timezone.utc) - sicurezza.DURATA - timedelta(minutes=1)
        assert (
            sicurezza.leggi_token(sicurezza.crea_token("marco", adesso=vecchio)) is None
        )

    def test_un_token_firmato_con_un_altro_segreto_non_vale(self, monkeypatch):
        token = sicurezza.crea_token("marco")
        monkeypatch.setenv(
            "FANTA_SEGRETO_JWT", "un-altro-segreto-lungo-abbastanza-davvero"
        )
        assert sicurezza.leggi_token(token) is None

    @pytest.mark.parametrize("spazzatura", ["", "non-un-token", "a.b.c"])
    def test_spazzatura_non_vale(self, spazzatura):
        assert sicurezza.leggi_token(spazzatura) is None

    def test_nel_token_c_e_solo_il_nome_utente(self):
        """Mai l'oggetto `Utente`: la riga cambia, il token no."""
        import jwt

        carico = jwt.decode(
            sicurezza.crea_token("marco"),
            sicurezza.segreto(),
            algorithms=[sicurezza.ALGORITMO],
        )
        assert set(carico) == {"sub", "iat", "exp"}


class TestAccesso:
    def test_le_credenziali_giuste_fanno_entrare(self, client):
        r = client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        assert r.status_code == 200
        corpo = r.json()
        assert corpo["nome_utente"] == "marco"
        assert corpo["ruolo"] == "PRESIDENTE"
        assert corpo["puo_importare"] is True
        assert sicurezza.NOME_COOKIE in r.cookies

    def test_il_cookie_non_si_legge_da_javascript(self, client):
        """httpOnly, cosi' un XSS non si porta via la sessione di nessuno."""
        r = client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        impostato = r.headers["set-cookie"].lower()
        assert "httponly" in impostato
        assert "samesite=lax" in impostato

    @pytest.mark.parametrize(
        "nome,password",
        [
            ("marco", "sbagliata"),
            ("nessuno", "fantanuovo26"),
            ("", ""),
        ],
    )
    def test_le_credenziali_sbagliate_danno_sempre_lo_stesso_errore(
        self, client, nome, password
    ):
        """Un messaggio diverso per «utente inesistente» direbbe a chi prova
        quali nomi utente esistono."""
        r = client.post("/api/accesso", json={"nome_utente": nome, "password": password})
        assert r.status_code == 401
        assert r.json()["detail"] == "Nome utente o password non corretti."


class TestChiSono:
    def test_senza_cookie_si_resta_fuori(self, client):
        assert client.get("/api/io").status_code == 401

    def test_con_un_cookie_inventato_si_resta_fuori(self, client):
        client.cookies.set(sicurezza.NOME_COOKIE, "token.inventato.qui")
        assert client.get("/api/io").status_code == 401

    def test_dopo_l_accesso_si_sa_chi_si_e(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        r = client.get("/api/io")
        assert r.status_code == 200
        assert r.json()["nome_utente"] == "marco"

    def test_l_utente_e_riletto_non_ricostruito_dal_token(self, client):
        """Il token dice *chi*, il database dice *com'e' adesso*."""
        token = sicurezza.crea_token("luca")
        client.cookies.set(sicurezza.NOME_COOKIE, token)
        r = client.get("/api/io")
        assert r.status_code == 200
        # Il token non contiene il ruolo: arriva dalla riga di `luca`.
        assert r.json()["ruolo"] == "FANTALLENATORE"
        assert r.json()["puo_importare"] is False

    def test_esci_toglie_il_cookie(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        assert client.post("/api/esci").status_code == 204
        assert client.get("/api/io").status_code == 401


class TestSquadre:
    def test_senza_entrare_non_si_vedono(self, client):
        assert client.get("/api/squadre").status_code == 401

    def test_elenco_con_i_conti_del_dominio(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        r = client.get("/api/squadre")
        assert r.status_code == 200
        squadre = r.json()
        assert len(squadre) == 10
        assert [s["nome"] for s in squadre] == sorted(s["nome"] for s in squadre)

        mie = [s for s in squadre if s["e_mia"]]
        assert len(mie) == 1, "marco ha una squadra sola"

        prima = squadre[0]
        assert prima["giocatori"] > 0
        assert prima["monte_ingaggi"] > 0
        assert prima["colori"]["primario"].startswith("#")

    def test_salute_dice_su_che_backend_legge(self, client):
        r = client.get("/api/salute")
        assert r.status_code == 200
        assert r.json()["stato"] == "ok"
        assert "SQLite" in r.json()["backend"]
