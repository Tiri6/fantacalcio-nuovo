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

    # `data.archivio()` tiene un'istanza sola in cache, ed e' giusto cosi' in
    # produzione: il database non cambia mentre il sito gira. Nei test pero'
    # ogni caso vuole la **sua** copia, e senza svuotare la cache il primo che
    # gira fissa il file per tutti gli altri: scriverebbero tutti li', e un
    # test vedrebbe le righe lasciate dai precedenti.
    from fantacalcio.data import archivio

    archivio.cache_clear()

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


class TestListone:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/giocatori").status_code == 401

    def test_porta_tutto_in_una_volta(self, client):
        """Si manda l'elenco intero: filtrarlo nel browser e' quello che
        rende la ricerca istantanea invece di una richiesta per lettera."""
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        d = client.get("/api/giocatori").json()
        assert len(d["giocatori"]) > 100
        assert d["riferimento_u21"].endswith("-08-31"), "U21 al 31 agosto"

        g = d["giocatori"][0]
        assert isinstance(g["ruoli"], list)
        assert d["con_stipendio"] <= len(d["giocatori"])

    def test_chi_non_ha_contratto_e_marcato_svincolato(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        d = client.get("/api/giocatori").json()
        posseduti = {g["squadra"] for g in d["giocatori"]}
        assert d["svincolato"] not in posseduti or any(
            g["anni"] == 0 for g in d["giocatori"] if g["squadra"] == d["svincolato"]
        )


class TestDettaglioSquadra:
    def entra(self, client, chi="marco"):
        client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})

    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/squadre/1").status_code == 401

    def test_una_squadra_che_non_esiste_da_404(self, client):
        self.entra(client)
        assert client.get("/api/squadre/999999").status_code == 404

    def test_porta_rosa_conti_e_conformita(self, client):
        self.entra(client)
        d = client.get("/api/squadre/1").json()

        assert d["rosa"], "la squadra 1 della demo ha una rosa"
        assert d["conti"]["giocatori"] == len(d["rosa"])
        # I conti li fa il dominio: il front-end disegna numeri, non li deduce.
        assert d["conti"]["monte_anni"] == 66
        assert d["conti"]["italiani"] == sum(1 for g in d["rosa"] if g["italiano"])
        assert isinstance(d["violazioni"], list)

    def test_la_rosa_porta_il_dead_money_di_ciascuno(self, client):
        """Serve a dire *prima* quanto costa tagliare, non dopo."""
        self.entra(client)
        d = client.get("/api/squadre/1").json()
        g = d["rosa"][0]
        # Il V3 conta solo gli anni oltre quello in corso (art. 7).
        oltre = max(g["anni_residui"] - 1, 0)
        assert g["valore_residuo"] == oltre * g["ingaggio"]
        assert g["dead_money_se_tagliato"] == round(0.50 * oltre * g["ingaggio"], 2)

    def test_i_permessi_vengono_dal_dominio(self, client):
        """`posso_gestirla` e' `Utente.puo_gestire`, non una deduzione del
        front-end dal nome del ruolo."""
        self.entra(client, "marco")
        assert client.get("/api/squadre/1").json()["posso_gestirla"] is True
        assert client.get("/api/squadre/2").json()["posso_gestirla"] is True

        client.post("/api/esci")
        self.entra(client, "luca")
        mie = [s for s in client.get("/api/squadre").json() if s["e_mia"]]
        assert len(mie) == 1
        sua = mie[0]["id"]
        assert client.get(f"/api/squadre/{sua}").json()["posso_gestirla"] is True
        altra = next(s["id"] for s in client.get("/api/squadre").json() if not s["e_mia"])
        assert client.get(f"/api/squadre/{altra}").json()["posso_gestirla"] is False


class TestIdentita:
    def entra(self, client, chi="marco"):
        client.post("/api/esci")
        client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})

    def corpo_di(self, squadra: dict) -> dict:
        return {
            k: squadra[k]
            for k in (
                "nome",
                "presidente",
                "motto",
                "stadio",
                "citta",
                "curva",
                "colore_primario",
                "colore_secondario",
                "stile_maglia",
                "anno_fondazione",
            )
        }

    def test_senza_entrare_niente_galleria(self, client):
        assert client.get("/api/identita").status_code == 401

    def test_la_maglia_la_disegna_il_dominio(self, client):
        """Non React: due squadre con gli stessi colori devono venire uguali
        a chiunque le guardi."""
        self.entra(client)
        g = client.get("/api/identita").json()
        assert len(g["squadre"]) == 10
        assert all(
            s["maglia"].startswith("data:image/svg+xml;base64,") for s in g["squadre"]
        )
        assert [s["nome"] for s in g["stili"]][0] == "TINTA_UNITA"

    def test_il_presidente_puo_tutto_il_fantallenatore_solo_la_sua(self, client):
        self.entra(client, "marco")
        g = client.get("/api/identita").json()
        assert g["posso_crearne"] is True
        assert all(s["modificabile"] for s in g["squadre"])

        self.entra(client, "luca")
        g = client.get("/api/identita").json()
        assert g["posso_crearne"] is False
        assert sum(1 for s in g["squadre"] if s["modificabile"]) == 1

    def test_si_modifica_e_si_rilegge(self, client):
        self.entra(client)
        mia = next(
            s for s in client.get("/api/identita").json()["squadre"] if s["modificabile"]
        )
        corpo = {**self.corpo_di(mia), "motto": "Scritto dal test"}

        r = client.put(f"/api/squadre/{mia['id']}/identita", json=corpo)
        assert r.status_code == 200
        assert r.json()["motto"] == "Scritto dal test"

        rilette = client.get("/api/identita").json()["squadre"]
        assert next(s for s in rilette if s["id"] == mia["id"])["motto"] == (
            "Scritto dal test"
        )

    def test_il_proprio_nome_invariato_non_e_un_doppione(self, client):
        """Era il difetto che mi aspettavo: senza escludere se stessa, riaprire
        il modulo e salvare fallirebbe sempre."""
        self.entra(client)
        mia = next(
            s for s in client.get("/api/identita").json()["squadre"] if s["modificabile"]
        )
        r = client.put(f"/api/squadre/{mia['id']}/identita", json=self.corpo_di(mia))
        assert r.status_code == 200

    def test_il_nome_di_un_altra_squadra_e_rifiutato(self, client):
        self.entra(client)
        squadre = client.get("/api/identita").json()["squadre"]
        mia = squadre[0]
        altra = next(s for s in squadre if s["id"] != mia["id"])
        r = client.put(
            f"/api/squadre/{mia['id']}/identita",
            json={**self.corpo_di(mia), "nome": altra["nome"]},
        )
        assert r.status_code == 409
        assert altra["nome"] in r.json()["detail"]

    def test_un_colore_non_valido_e_rifiutato(self, client):
        self.entra(client)
        mia = client.get("/api/identita").json()["squadre"][0]
        r = client.put(
            f"/api/squadre/{mia['id']}/identita",
            json={**self.corpo_di(mia), "colore_primario": "verde"},
        )
        assert r.status_code == 422

    def test_il_fantallenatore_non_tocca_le_altre(self, client):
        """Il permesso lo impone il dominio: nascondere il modulo non basta."""
        self.entra(client, "luca")
        squadre = client.get("/api/identita").json()["squadre"]
        altrui = next(s for s in squadre if not s["modificabile"])
        r = client.put(
            f"/api/squadre/{altrui['id']}/identita", json=self.corpo_di(altrui)
        )
        assert r.status_code == 403

    def test_solo_il_presidente_crea_squadre(self, client):
        self.entra(client, "luca")
        modello = client.get("/api/identita").json()["squadre"][0]
        r = client.post(
            "/api/squadre", json={**self.corpo_di(modello), "nome": "Squadra Abusiva"}
        )
        assert r.status_code == 403

    def test_un_immagine_troppo_grande_e_rifiutata(self, client):
        """Il limite lo impone `identita.immagine_a_data_uri`, lo stesso che
        usa Streamlit: riscriverlo qui sarebbe la copia che diverge."""
        import base64

        self.entra(client)
        enorme = base64.b64encode(b"x" * (2 * 1024 * 1024)).decode()
        r = client.post(
            "/api/immagini",
            json={"contenuto_base64": enorme, "tipo_mime": "image/png"},
        )
        assert r.status_code == 422
        assert "KB" in r.json()["detail"]

    def test_un_formato_non_ammesso_e_rifiutato(self, client):
        import base64

        self.entra(client)
        r = client.post(
            "/api/immagini",
            json={
                "contenuto_base64": base64.b64encode(b"ciao").decode(),
                "tipo_mime": "application/pdf",
            },
        )
        assert r.status_code == 422
