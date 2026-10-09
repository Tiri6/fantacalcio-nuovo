"""Il portiere d'emergenza visto dall'API (art. 8, Lodo Messina).

Qui si prova quello che il dominio da solo non puo' garantire: che il
permesso valga anche a bottone nascosto, che la dichiarazione di
indisponibilita' resti scritta — altrimenti ricaricando la pagina sembrerebbe
che i portieri siano tornati tutti — e che la revoca non lasci strascichi.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ROTTA = "/api/squadre/1/portiere-emergenza"


@pytest.fixture(autouse=True)
def segreto_di_prova(monkeypatch):
    monkeypatch.setenv("FANTA_SEGRETO_JWT", "segreto-lungo-abbastanza-solo-per-i-test")
    monkeypatch.setenv("FANTA_AMBIENTE", "sviluppo")


@pytest.fixture
def client(monkeypatch, db_demo):
    monkeypatch.setenv("FANTA_DB_DEMO", str(db_demo))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    # Vedi il commento gemello in test_api_accesso: `data.archivio()` tiene
    # un'istanza sola in cache, e senza svuotarla il primo test fissa il file
    # del database per tutti gli altri.
    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


def entra(client, chi="Marco"):
    client.post("/api/esci")
    client.post("/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"})


def portieri_di(client, squadra=1) -> list[dict]:
    dati = client.get(f"/api/squadre/{squadra}").json()
    return dati["emergenza"]["portieri"]


def un_candidato(client, squadra=1) -> dict:
    dati = client.get(f"/api/squadre/{squadra}").json()
    candidati = dati["emergenza"]["candidati"]
    assert candidati, "la demo deve avere almeno un portiere svincolato"
    return candidati[0]


class TestCosaVedeChiApre:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/squadre/1").status_code == 401

    def test_a_porta_piena_l_emergenza_non_spetta(self, client):
        entra(client)
        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert len(emergenza["portieri"]) == 3
        assert all(p["disponibile"] for p in emergenza["portieri"])
        assert not emergenza["ammessa"]
        assert not emergenza["attiva"]

    def test_il_motivo_e_scritto_dal_dominio(self, client):
        """La pagina mostra una frase, non la deduce: la regola sta in un posto."""
        entra(client)
        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert "spetta solo a chi" in emergenza["motivo"]

    def test_il_malus_arriva_dai_parametri(self, client):
        entra(client)
        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert emergenza["malus"] == 1.0

    def test_i_candidati_sono_solo_portieri_svincolati(self, client):
        entra(client)
        dati = client.get("/api/squadre/1").json()
        in_rosa = {g["id"] for g in dati["rosa"]}
        for candidato in dati["emergenza"]["candidati"]:
            assert candidato["id"] not in in_rosa

    def test_chi_non_gestisce_la_squadra_non_vede_i_candidati(self, client):
        """A chi guarda non serve l'elenco dei portieri liberi della lega."""
        entra(client, "Luca")
        dati = client.get("/api/squadre/1").json()
        assert not dati["posso_gestirla"]
        assert dati["emergenza"]["candidati"] == []


class TestAttivare:
    def test_con_tutti_i_portieri_fuori_si_attiva(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)

        risposta = client.post(
            ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori}
        )
        assert risposta.status_code == 200
        emergenza = risposta.json()
        assert emergenza["attiva"]
        assert emergenza["in_carica_id"] == libero["id"]
        assert emergenza["in_carica_nome"] == libero["nome"]

    def test_resta_scritta_e_si_rilegge(self, client):
        """Senza la dichiarazione salvata, al giro dopo il sito chiederebbe
        di revocare un'emergenza che invece serve ancora."""
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)
        client.post(ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori})

        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert emergenza["attiva"]
        assert not emergenza["va_revocata"]
        assert all(not p["disponibile"] for p in emergenza["portieri"])

    def test_con_un_portiere_ancora_in_piedi_si_rifiuta(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)][:2]
        libero = un_candidato(client)

        risposta = client.post(
            ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori}
        )
        assert risposta.status_code == 400
        assert "indisponibili tutti" in risposta.json()["detail"]

    def test_un_movimento_non_copre_la_porta(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        dati = client.get("/api/giocatori").json()
        attaccante = next(
            g
            for g in dati["giocatori"]
            if "Por" not in g["ruoli"] and g["squadra"] == dati["svincolato"]
        )
        risposta = client.post(
            ROTTA, json={"giocatore_id": attaccante["id"], "indisponibili": fuori}
        )
        assert risposta.status_code == 400
        assert "non e' un portiere" in risposta.json()["detail"]

    def test_un_portiere_tesserato_altrove_no(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        altrui = client.get("/api/squadre/2").json()
        suo_portiere = next(g for g in altrui["rosa"] if "Por" in g["ruoli"])
        risposta = client.post(
            ROTTA, json={"giocatore_id": suo_portiere["id"], "indisponibili": fuori}
        )
        assert risposta.status_code == 400
        assert "non e' svincolato" in risposta.json()["detail"]

    def test_due_volte_no_la_scelta_e_unica(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        dati = client.get("/api/squadre/1").json()
        primo, secondo = dati["emergenza"]["candidati"][:2]
        client.post(ROTTA, json={"giocatore_id": primo["id"], "indisponibili": fuori})

        risposta = client.post(
            ROTTA, json={"giocatore_id": secondo["id"], "indisponibili": fuori}
        )
        assert risposta.status_code == 400
        assert "la scelta e' unica" in risposta.json()["detail"]


class TestIPermessi:
    def test_un_altro_fantallenatore_non_puo(self, client):
        """Nascondere il bottone non e' un controllo (regola del progetto)."""
        entra(client, "Luca")
        risposta = client.post(ROTTA, json={"giocatore_id": 1, "indisponibili": []})
        assert risposta.status_code == 403

    def test_sulla_propria_squadra_puo(self, client):
        """«Il fantallenatore puo' selezionare»: non serve il presidente."""
        entra(client, "Luca")
        fuori = [p["id"] for p in portieri_di(client, squadra=2)]
        libero = un_candidato(client, squadra=2)
        risposta = client.post(
            "/api/squadre/2/portiere-emergenza",
            json={"giocatore_id": libero["id"], "indisponibili": fuori},
        )
        assert risposta.status_code == 200

    def test_il_presidente_puo_su_tutte(self, client):
        entra(client)
        fuori = [p["id"] for p in portieri_di(client, squadra=3)]
        libero = un_candidato(client, squadra=3)
        risposta = client.post(
            "/api/squadre/3/portiere-emergenza",
            json={"giocatore_id": libero["id"], "indisponibili": fuori},
        )
        assert risposta.status_code == 200

    def test_su_una_squadra_che_non_esiste_e_un_404(self, client):
        entra(client)
        risposta = client.post(
            "/api/squadre/999/portiere-emergenza",
            json={"giocatore_id": 1, "indisponibili": []},
        )
        assert risposta.status_code == 404


class TestRevocare:
    def test_senza_nessuno_in_carica_non_c_e_niente_da_revocare(self, client):
        entra(client)
        risposta = client.delete(ROTTA)
        assert risposta.status_code == 400
        assert "nessun portiere" in risposta.json()["detail"]

    def test_revocando_si_azzera_anche_la_dichiarazione(self, client):
        """Un'emergenza chiusa non lascia dietro i portieri segnati fuori."""
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)
        client.post(ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori})

        emergenza = client.delete(ROTTA).json()
        assert not emergenza["attiva"]
        assert emergenza["in_carica_id"] is None
        assert all(p["disponibile"] for p in emergenza["portieri"])

        dopo = client.get("/api/squadre/1").json()["emergenza"]
        assert not dopo["attiva"]
        assert not dopo["va_revocata"]


class TestQuandoUnPortiereTorna:
    def test_il_sito_chiede_di_revocare(self, client):
        """La dichiarazione salvata resta quella di quando si e' attivata.

        Se uno dei tre torna, la pagina non deve limitarsi a non dire niente:
        deve dire che l'emergenza e' decaduta. Qui lo si verifica scrivendo
        la dichiarazione aggiornata direttamente nel database, cioe' come se
        la squadra l'avesse corretta.
        """
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)
        client.post(ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori})

        from fantacalcio.data import archivio, imposta_portiere_emergenza

        imposta_portiere_emergenza(archivio(), 1, libero["id"], fuori[:2])

        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert emergenza["attiva"]
        assert emergenza["va_revocata"]
        assert "va revocato" in emergenza["motivo"]


class TestNonToccaIConti:
    def test_la_rosa_resta_di_trenta(self, client):
        entra(client)
        prima = client.get("/api/squadre/1").json()["conti"]
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)
        client.post(ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori})

        dopo = client.get("/api/squadre/1").json()["conti"]
        assert dopo["giocatori"] == prima["giocatori"]
        assert dopo["anni_impegnati"] == prima["anni_impegnati"]
        assert dopo["monte_ingaggi"] == prima["monte_ingaggi"]
        assert dopo["portieri"] == prima["portieri"]

    def test_l_identita_non_se_lo_porta_via(self, client):
        """`salva_squadra` riscrive la riga intera: senza cura, correggere il
        motto revocherebbe in silenzio il portiere d'emergenza."""
        entra(client)
        fuori = [p["id"] for p in portieri_di(client)]
        libero = un_candidato(client)
        client.post(ROTTA, json={"giocatore_id": libero["id"], "indisponibili": fuori})

        prima = client.get("/api/squadre/1").json()
        risposta = client.put(
            "/api/squadre/1/identita",
            json={
                "nome": prima["nome"],
                "presidente": prima["presidente"],
                "motto": "Un motto nuovo",
                "stadio": prima["stadio"],
                "citta": prima["citta"],
                "curva": prima["curva"],
                "colore_primario": prima["colori"]["primario"],
                "colore_secondario": prima["colori"]["secondario"],
                "stile_maglia": prima["colori"]["stile_maglia"],
                "anno_fondazione": prima["anno_fondazione"],
            },
        )
        assert risposta.status_code == 200, risposta.text

        emergenza = client.get("/api/squadre/1").json()["emergenza"]
        assert emergenza["attiva"], "l'emergenza e' sopravvissuta al salvataggio"
        assert emergenza["in_carica_id"] == libero["id"]
