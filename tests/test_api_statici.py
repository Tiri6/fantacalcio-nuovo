"""Un servizio solo: le pagine e l'API nello stesso posto.

Il rischio di metterle insieme e' uno e uno solo: che la rotta che serve le
pagine — e che per forza risponde a *qualunque* indirizzo — si mangi anche
le chiamate all'API. Questi test stanno li' a dire che non succede.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.statici import monta_sito

INDICE = """<!doctype html>
<html><head><title>FantaCalcio NuoVo</title>
<link rel="stylesheet" href="/assets/stile-abc123.css"></head>
<body><div id="radice"></div>
<script type="module" src="/assets/pagina-abc123.js"></script></body></html>
"""


@pytest.fixture
def sito(tmp_path):
    """Una cartella che somiglia a quella prodotta da `npm run build`."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDICE, encoding="utf-8")
    assets = tmp_path / "assets"
    (assets / "pagina-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (assets / "stile-abc123.css").write_text("body{color:red}", encoding="utf-8")
    (tmp_path / "favicon.ico").write_bytes(b"\x00")
    return tmp_path


@pytest.fixture
def client(sito, monkeypatch):
    monkeypatch.setenv("FANTA_SITO", str(sito))

    app = FastAPI()

    @app.get("/api/qualcosa")
    def qualcosa() -> dict[str, bool]:
        return {"api": True}

    assert monta_sito(app) is True
    return TestClient(app)


class TestSenzaSito:
    def test_senza_pagine_costruite_non_si_monta_niente(self, tmp_path, monkeypatch):
        """In sviluppo React sta su Vite: qui non c'e' niente da servire.

        E' importante che dica di no invece di montare una cartella vuota:
        una rotta acchiappatutto senza index dietro risponderebbe a tutto
        con un errore, API compresa.
        """
        monkeypatch.setenv("FANTA_SITO", str(tmp_path / "non-esiste"))
        app = FastAPI()
        assert monta_sito(app) is False

    def test_una_cartella_senza_index_non_conta(self, tmp_path, monkeypatch):
        (tmp_path / "assets").mkdir()
        monkeypatch.setenv("FANTA_SITO", str(tmp_path))
        app = FastAPI()
        assert monta_sito(app) is False


class TestLApiVinceSullePagine:
    def test_una_rotta_dell_api_risponde_ancora(self, client):
        risposta = client.get("/api/qualcosa")
        assert risposta.status_code == 200
        assert risposta.json() == {"api": True}

    def test_una_rotta_dell_api_che_non_esiste_resta_un_404(self, client):
        """E un 404 *JSON*, non la pagina.

        Se cadesse sull'index.html, una chiamata sbagliata del front-end
        tornerebbe 200 con dentro dell'HTML: il guasto salterebbe fuori molto
        dopo, dove nessuno lo collegherebbe piu' alla causa.
        """
        risposta = client.get("/api/non-esiste")
        assert risposta.status_code == 404
        assert risposta.headers["content-type"].startswith("application/json")

    def test_anche_api_liscio_e_un_404(self, client):
        assert client.get("/api").status_code == 404


class TestLePagine:
    def test_la_radice_serve_l_index(self, client):
        risposta = client.get("/")
        assert risposta.status_code == 200
        assert "FantaCalcio NuoVo" in risposta.text

    @pytest.mark.parametrize(
        "indirizzo", ["/squadre", "/squadre/3", "/identita", "/giocatori", "/inventato"]
    )
    def test_ogni_indirizzo_di_react_serve_l_index(self, client, indirizzo):
        """Senza questo, aprire un link o premere F5 darebbe 404.

        Gli indirizzi li conosce React, non il server: il server manda
        sempre la stessa pagina e il front-end decide cosa mostrarci.
        """
        risposta = client.get(indirizzo)
        assert risposta.status_code == 200
        assert "FantaCalcio NuoVo" in risposta.text

    def test_i_file_veri_si_servono_come_sono(self, client):
        js = client.get("/assets/pagina-abc123.js")
        assert js.status_code == 200
        assert js.text == "console.log(1)"
        assert client.get("/favicon.ico").status_code == 200

    def test_l_index_non_si_tiene_in_cache(self, client):
        """I file sotto `assets/` hanno l'impronta nel nome e non cambiano mai.

        L'index.html invece e' quello che dice *quali* file caricare: se il
        browser tiene il vecchio, dopo un aggiornamento continua a chiedere
        file che non esistono piu' e il sito resta bianco.
        """
        assert client.get("/").headers["cache-control"] == "no-cache"
        assert "cache-control" not in client.get("/assets/pagina-abc123.js").headers

    def test_anche_head_risponde(self, client):
        """Le anteprime dei link (WhatsApp, Telegram) chiedono spesso cosi'."""
        assert client.head("/squadre/3").status_code == 200


class TestNonSiEsceDallaCartella:
    @pytest.mark.parametrize(
        "indirizzo",
        [
            "/../../etc/passwd",
            "/..%2f..%2fetc%2fpasswd",
            "/assets/../../../etc/passwd",
            "/....//....//etc/passwd",
        ],
    )
    def test_un_indirizzo_che_risale_non_serve_file_del_server(self, client, indirizzo):
        """Peggio di un 404 c'e' solo un 200 con dentro `/etc/passwd`.

        La rotta serve un file solo se sta davvero dentro la cartella del
        sito; tutto il resto e' un indirizzo di React e si prende l'index.
        """
        risposta = client.get(indirizzo)
        assert "root:" not in risposta.text
        assert "FantaCalcio NuoVo" in risposta.text
