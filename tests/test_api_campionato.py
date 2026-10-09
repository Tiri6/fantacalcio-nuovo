"""Campionato e albo d'oro visti dall'API.

Il campionato non calcola: ripete quello che dice `standings`, e i test qui
stanno a dire che non si e' messo a dedurre punti per conto suo. L'albo
invece scrive, e li' conta che una competizione abbia **un** vincitore per
stagione.
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

    # `data.archivio()` tiene un'istanza sola in cache, ed e' giusto cosi' in
    # produzione: il database non cambia mentre il sito gira. Nei test pero'
    # ogni caso vuole la **sua** copia, e senza svuotare la cache il primo che
    # gira fissa il file per tutti gli altri: scriverebbero tutti li', e un
    # test vedrebbe le righe lasciate dai precedenti.
    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


def entra(client, chi="marco"):
    client.post("/api/esci")
    client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})


class TestCampionato:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/campionato").status_code == 401

    def test_una_riga_di_classifica_per_squadra(self, client):
        entra(client)
        dati = client.get("/api/campionato").json()
        assert len(dati["classifica"]) == 10
        assert len({r["squadra"] for r in dati["classifica"]}) == 10

    def test_la_classifica_arriva_gia_ordinata(self, client):
        entra(client)
        righe = client.get("/api/campionato").json()["classifica"]
        assert [r["posizione"] for r in righe] == list(range(1, len(righe) + 1))

    def test_i_punti_sono_quelli_del_dominio(self, client):
        """Tre per vittoria, uno per pareggio. Se qui cambiasse, l'API calcola."""
        entra(client)
        for r in client.get("/api/campionato").json()["classifica"]:
            assert r["punti"] == 3 * r["vinte"] + r["pareggiate"]
            assert r["giocate"] == r["vinte"] + r["pareggiate"] + r["perse"]
            assert r["differenza_reti"] == r["gol_fatti"] - r["gol_subiti"]

    def test_le_partite_non_giocate_non_hanno_risultato(self, client):
        entra(client)
        dati = client.get("/api/campionato").json()
        disputate = dati["giornate_disputate"]
        future = [p for p in dati["partite"] if p["giornata"] > disputate]
        # Senza partite future questo test non proverebbe niente.
        assert future
        for p in future:
            assert p["gol_casa"] is None
            assert p["punti_casa"] is None

    def test_niente_nan_nella_risposta(self, client):
        """`NaN` non e' JSON valido: il front-end non riuscirebbe a leggerla.

        Le partite da giocare arrivano da pandas con i risultati a NaN, e
        senza conversione finirebbero nel corpo come letterali non validi.
        """
        entra(client)
        assert "NaN" not in client.get("/api/campionato").text

    def test_dice_sia_le_giornate_previste_sia_quelle_in_calendario(self, client):
        """I due numeri possono non coincidere, ed e' un punto aperto.

        Con 10 squadre andata e ritorno fanno 18 giornate, ma la lega ne ha
        impostate 27 (PUNTI_APERTI.md §5). Mostrarne uno solo farebbe
        credere che manchino partite che nessuno ha mai programmato.
        """
        entra(client)
        dati = client.get("/api/campionato").json()
        assert dati["giornate_totali"] > 0
        assert dati["giornate_in_calendario"] > 0
        massima = max(p["giornata"] for p in dati["partite"])
        assert dati["giornate_in_calendario"] == massima

    def test_l_andamento_ha_una_serie_per_squadra(self, client):
        entra(client)
        dati = client.get("/api/campionato").json()
        assert len(dati["andamento"]) == len(dati["classifica"])
        for serie in dati["andamento"]:
            giornate = [p["giornata"] for p in serie["punti"]]
            assert giornate == sorted(giornate)
            assert len(giornate) == len(set(giornate))

    def test_l_andamento_copre_solo_le_giornate_disputate(self, client):
        entra(client)
        dati = client.get("/api/campionato").json()
        disputate = dati["giornate_disputate"]
        for serie in dati["andamento"]:
            assert all(p["giornata"] <= disputate for p in serie["punti"])


class TestAlbo:
    def registra(self, client, **campi):
        corpo = {
            "competizione": "CAMPIONATO",
            "stagione": "2025/26",
            "squadra_nome": "Tiri Team",
        } | campi
        return client.post("/api/albo", json=corpo)

    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/albo").status_code == 401

    def test_offre_solo_le_competizioni_che_la_lega_gioca(self, client):
        """Un albo che offre la Supercoppa a chi non la disputa racconta
        una storia che non e' successa."""
        from fantacalcio.competizioni import TipoCompetizione
        from fantacalcio.data import archivio, carica_leghe

        entra(client)
        dati = client.get("/api/albo").json()
        lega = next(iter(carica_leghe(archivio()).values()))
        attese = {c.name for c in lega.opzioni.competizioni}
        assert {c["nome"] for c in dati["competizioni"]} == attese
        assert TipoCompetizione.CAMPIONATO.name in attese

    def test_il_fantallenatore_non_registra(self, client):
        entra(client, "luca")
        assert client.get("/api/albo").json()["posso_registrare"] is False
        assert self.registra(client).status_code == 403

    def test_il_presidente_registra(self, client):
        entra(client, "marco")
        risposta = self.registra(client, note="Vinta all'ultima")
        assert risposta.status_code == 201
        titolo = risposta.json()
        assert titolo["squadra_nome"] == "Tiri Team"
        assert titolo["competizione_icona"]

    def test_il_vincitore_di_una_stagione_e_uno_solo(self, client):
        """Registrare di nuovo sostituisce, non affianca."""
        entra(client, "marco")
        primo = self.registra(client).json()
        secondo = self.registra(client, squadra_nome="Padel United").json()

        assert secondo["id"] == primo["id"]
        titoli = client.get("/api/albo").json()["titoli"]
        dello_stesso_anno = [
            t
            for t in titoli
            if t["stagione"] == "2025/26" and t["competizione"] == "CAMPIONATO"
        ]
        assert len(dello_stesso_anno) == 1
        assert dello_stesso_anno[0]["squadra_nome"] == "Padel United"

    def test_una_squadra_che_non_esiste_non_si_premia(self, client):
        entra(client, "marco")
        assert self.registra(client, squadra_nome="Inventata FC").status_code == 422

    def test_una_competizione_inventata_non_passa(self, client):
        entra(client, "marco")
        assert self.registra(client, competizione="CHAMPIONS").status_code == 422

    def test_la_bacheca_conta_i_titoli_per_squadra(self, client):
        entra(client, "marco")
        self.registra(client, stagione="2024/25")
        self.registra(client, stagione="2025/26")
        bacheche = client.get("/api/albo").json()["bacheche"]
        mia = next(b for b in bacheche if b["squadra"] == "Tiri Team")
        assert mia["totale"] == 2
        assert mia["titoli"]["CAMPIONATO"] == 2

    def test_chi_ha_vinto_di_piu_sta_in_cima(self, client):
        entra(client, "marco")
        self.registra(client, stagione="2024/25")
        self.registra(client, stagione="2025/26")
        self.registra(client, stagione="2023/24", squadra_nome="Padel United")
        totali = [b["totale"] for b in client.get("/api/albo").json()["bacheche"]]
        assert totali == sorted(totali, reverse=True)

    def test_il_fantallenatore_non_cancella(self, client):
        entra(client, "marco")
        titolo = self.registra(client).json()
        entra(client, "luca")
        assert client.delete(f"/api/albo/{titolo['id']}").status_code == 403

    def test_il_presidente_cancella(self, client):
        entra(client, "marco")
        titolo = self.registra(client).json()
        assert client.delete(f"/api/albo/{titolo['id']}").status_code == 204
        assert client.get("/api/albo").json()["titoli"] == []

    def test_cancellare_due_volte_da_404(self, client):
        entra(client, "marco")
        titolo = self.registra(client).json()
        client.delete(f"/api/albo/{titolo['id']}")
        assert client.delete(f"/api/albo/{titolo['id']}").status_code == 404
