"""Calendario, Coppa e F1 Rush viste dall'API.

Due di queste tre pagine **possono non esistere**: coppa e F1 Rush si giocano
solo se la lega le ha attivate. Qui si prova soprattutto quello — che una lega
che non le gioca non trovi una pagina mezza vuota ma un 404 netto, cosi' il
menu puo' semplicemente non mostrare la voce.

Il resto (tabellone, punti di tappa, corrispondenza fra weekend) e' calcolato
dal dominio e ha i suoi test: qui si guarda che arrivi intero.
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


def spegni(opzione: str) -> None:
    """Toglie una competizione alla lega di demo."""
    from dataclasses import replace

    from fantacalcio.data import archivio, carica_leghe, salva_lega

    arch = archivio()
    lega = next(iter(carica_leghe(arch).values()))
    salva_lega(arch, replace(lega, opzioni=replace(lega.opzioni, **{opzione: False})))


class TestCalendario:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/calendario").status_code == 401

    def test_porta_squadre_partite_e_giornate(self, client):
        entra(client)
        dati = client.get("/api/calendario").json()
        assert len(dati["squadre"]) == 10
        assert dati["senza_partite"] is False
        assert dati["giornate_disputate"] > 0
        assert dati["partite_giocate"] > 0
        assert len(dati["partite"]) == dati["giornate_totali"] * 5

    def test_le_partite_giocate_portano_il_risultato(self, client):
        entra(client)
        partite = client.get("/api/calendario").json()["partite"]
        giocata = next(p for p in partite if p["gol_casa"] is not None)
        assert giocata["punti_casa"] is not None
        da_giocare = next(p for p in partite if p["gol_casa"] is None)
        assert da_giocare["punti_casa"] is None

    def test_i_weekend_si_costruiscono_dalle_regole_non_dalle_partite(self, client):
        """E' il motivo per cui la pagina serve a inizio stagione, da vuota."""
        from fantacalcio.data import archivio

        entra(client)
        archivio().svuota("calendario")

        dati = client.get("/api/calendario").json()

        assert dati["senza_partite"] is True
        assert dati["partite"] == []
        assert len(dati["weekend"]) > 20
        assert dati["weekend"][0]["serie_a"] == 5

    def test_da_quale_giornata_di_serie_a_si_parte_e_un_parametro(self, client):
        entra(client)
        dati = client.get("/api/calendario", params={"prima_serie_a": 8}).json()
        assert dati["weekend"][0]["serie_a"] == 8

    def test_una_giornata_di_serie_a_fuori_scala_non_rompe(self, client):
        entra(client)
        dati = client.get(
            "/api/calendario", params={"prima_serie_a": 99, "fino_a": 1}
        ).json()
        # «Fino alla 1ª» partendo dalla 38ª non vuol dire niente: invece di
        # una tabella vuota si tiene l'inizio e si allunga la fine.
        assert dati["weekend"]
        assert all(1 <= w["serie_a"] <= 38 for w in dati["weekend"])


class TestCoppa:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/coppa").status_code == 401

    def test_la_lega_di_demo_la_gioca_a_gironi(self, client):
        entra(client)
        dati = client.get("/api/coppa").json()
        assert dati["si_gioca"] is True
        assert dati["a_gironi"] is True
        assert dati["gironi"] == 2
        assert dati["squadre_ammesse"] == 10
        assert dati["squadre_a_eliminazione"] == 4

    def test_il_tabellone_a_gironi_non_inventa_le_giornate(self, client):
        """Coi gironi i turni vengono dopo il campionato, non a giornate fisse."""
        entra(client)
        tabellone = client.get("/api/coppa").json()["tabellone"]
        assert all(f["quando"][:1] != "G" for f in tabellone)
        assert any(f["quando"] == "dopo il campionato" for f in tabellone)
        assert any(f["quando"] == "dopo i gironi" for f in tabellone)

    def test_i_turni_si_chiamano_col_loro_nome(self, client):
        entra(client)
        assert client.get("/api/coppa").json()["nomi_turni"] == [
            "Semifinali",
            "Finale",
        ]

    def test_una_lega_che_non_la_gioca_non_ha_la_pagina(self, client):
        entra(client)
        spegni("coppa_italia")

        risposta = client.get("/api/coppa")

        assert risposta.status_code == 404
        assert "non gioca" in risposta.json()["detail"]


class TestF1Rush:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/f1-rush").status_code == 401

    def test_corre_sulle_ultime_giornate_di_serie_a(self, client):
        entra(client)
        dati = client.get("/api/f1-rush").json()
        assert dati["giornate_serie_a"] == 6
        assert dati["ultima_giornata"] == 38
        assert dati["prima_giornata"] == 33

    def test_porta_la_classifica_e_le_tappe(self, client):
        entra(client)
        dati = client.get("/api/f1-rush").json()
        assert len(dati["classifica"]) == 10
        assert dati["classifica"][0]["posizione"] == 1
        # Ordinata: il primo non ha meno punti del secondo.
        assert dati["classifica"][0]["punti"] >= dati["classifica"][1]["punti"]
        assert dati["tappe"]
        assert all(t["podio"] for t in dati["tappe"])

    def test_dice_se_sta_usando_le_giornate_di_lega(self, client):
        """Senza `giornata_serie_a` nel calendario il conto e' un'approssimazione,
        e va dichiarata invece di far credere che sia l'articolo 1 alla lettera."""
        entra(client)
        dati = client.get("/api/f1-rush").json()
        assert isinstance(dati["senza_giornate_serie_a"], bool)

    def test_una_lega_che_non_la_gioca_non_ha_la_pagina(self, client):
        entra(client)
        spegni("f1_rush")

        risposta = client.get("/api/f1-rush")

        assert risposta.status_code == 404
        assert "non gioca" in risposta.json()["detail"]


class TestAssegnareLaF1:
    def test_chi_non_amministra_e_respinto(self, client):
        entra(client, "Luca")
        risposta = client.post("/api/f1-rush/vincitrice", json={"squadra": "Tiri Team"})
        assert risposta.status_code == 403

    def test_registra_nell_albo_e_la_pagina_lo_dice(self, client):
        entra(client)
        prima = client.get("/api/albo").json()

        risposta = client.post("/api/f1-rush/vincitrice", json={"squadra": "Tiri Team"})

        assert risposta.status_code == 200
        assert risposta.json()["vincitrice"] == "Tiri Team"
        dopo = client.get("/api/albo").json()
        assert len(dopo["titoli"]) == len(prima["titoli"]) + 1

    def test_non_si_assegna_due_volte(self, client):
        entra(client)
        client.post("/api/f1-rush/vincitrice", json={"squadra": "Tiri Team"})

        risposta = client.post(
            "/api/f1-rush/vincitrice", json={"squadra": "Padel United"}
        )

        assert risposta.status_code == 422
        assert "gia' di Tiri Team" in risposta.json()["detail"]

    def test_una_squadra_inventata_e_respinta(self, client):
        entra(client)
        risposta = client.post(
            "/api/f1-rush/vincitrice", json={"squadra": "Squadra Inventata"}
        )
        assert risposta.status_code == 422
        assert "non e' una squadra" in risposta.json()["detail"]

    def test_propone_per_prima_chi_guida_la_classifica(self, client):
        entra(client)
        dati = client.get("/api/f1-rush").json()
        assert dati["squadre"][0] == dati["classifica"][0]["squadra"]


class TestLaBachecaDiUnaSquadra:
    """I titoli nella pagina della squadra, contati per competizione."""

    def test_dice_quanti_ne_ha_vinti_per_competizione(self, client):
        """Contare le pastiglie a schermo funziona con tre titoli e smette di
        funzionare con venti: il conto lo fa il dominio."""
        entra(client)

        dettaglio = client.get("/api/squadre/1").json()

        conti = dettaglio["titoli_per_competizione"]
        assert sum(c["quanti"] for c in conti) == len(dettaglio["titoli"])
        assert all(c["etichetta"] and c["icona"] for c in conti)

    def test_una_competizione_a_zero_non_si_mostra(self, client):
        """Una bacheca piena di zeri sembra un elenco di sconfitte."""
        entra(client)

        for squadra in client.get("/api/squadre").json():
            dettaglio = client.get(f"/api/squadre/{squadra['id']}").json()
            assert all(c["quanti"] > 0 for c in dettaglio["titoli_per_competizione"])
