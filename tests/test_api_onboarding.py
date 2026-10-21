"""I due cancelli: entrare in una lega, e fondare la squadra.

Sono le stesse due porte di Streamlit (`richiedi_lega`, `richiedi_squadra`),
e qui si prova che non si possano scavalcare ne' attraversare due volte: chi
sta gia' in una lega non puo' crearne un'altra, chi non e' in nessuna lega non
puo' fondare una squadra.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

ISCRIZIONE = {
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

LEGA = {
    "nome": "Lega degli Amici",
    "stagione": "2026/27",
    "modalita": "MANTRA",
    "formato": "ANDATA_RITORNO",
    "partecipanti": 10,
    "coppa_italia": True,
    "f1_rush": True,
}

SQUADRA = {
    "nome": "Real Sporcaccioni",
    "citta": "Cuneo",
    "stadio": "Arena del NuoVo",
    "curva": "Curva Nord",
    "motto": "Chi non salta un pari e'",
    "colore_primario": "#2e7d32",
    "colore_secondario": "#ffffff",
    "stile_maglia": "TINTA_UNITA",
}


@pytest.fixture(autouse=True)
def segreto_di_prova(monkeypatch):
    monkeypatch.setenv("FANTA_SEGRETO_JWT", "segreto-lungo-abbastanza-solo-per-i-test")
    monkeypatch.setenv("FANTA_AMBIENTE", "sviluppo")


def _client(monkeypatch, percorso):
    monkeypatch.setenv("FANTA_DB_DEMO", str(percorso))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    # Vedi il commento gemello in test_api_accesso: senza svuotare la cache il
    # primo test fissa il file del database per tutti gli altri.
    from fantacalcio.data import archivio

    archivio.cache_clear()

    from api.main import app

    return TestClient(app)


@pytest.fixture
def client(monkeypatch, db_demo):
    """La demo come sta: dieci squadre, una lega, utenti dentro."""
    return _client(monkeypatch, db_demo)


@pytest.fixture
def squadre_in_attesa(monkeypatch, db_demo):
    """La demo con due squadre rimaste senza presidente.

    E' la situazione di una lega vera appena aperta: le squadre arrivano dal
    calendario ufficiale, caricato prima che le persone si registrino.
    """
    with sqlite3.connect(db_demo) as conn:
        conn.execute("delete from utenti where squadra_id in (9, 10)")
    return _client(monkeypatch, db_demo)


@pytest.fixture
def nuovo(monkeypatch, tmp_path):
    """Un database **senza leghe e senza utenti**: il mondo appena nato."""
    percorso = tmp_path / "nuovo.db"
    from fantacalcio.demo_data import costruisci_db

    costruisci_db(percorso)
    with sqlite3.connect(percorso) as conn:
        for tabella in ("utenti", "leghe", "squadre", "contratti", "calendario"):
            conn.execute(f"delete from {tabella}")

    cliente = _client(monkeypatch, percorso)
    cliente.post("/api/registrazione", json=ISCRIZIONE)
    return cliente


class TestDoveSiamo:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/onboarding").status_code == 401

    def test_chi_e_a_posto_non_serve_niente(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        assert client.get("/api/onboarding").json()["serve"] == "niente"

    def test_a_chi_si_e_appena_iscritto_serve_la_lega(self, client):
        client.post("/api/registrazione", json=ISCRIZIONE)
        stato = client.get("/api/onboarding").json()
        assert stato["serve"] == "lega"
        assert stato["nome"] == "Chiara"
        assert stato["esistono_leghe"] is True

    def test_su_un_mondo_vuoto_non_ci_sono_leghe(self, nuovo):
        stato = nuovo.get("/api/onboarding").json()
        assert stato["serve"] == "lega"
        assert stato["esistono_leghe"] is False

    def test_porta_le_tendine_dal_dominio(self, nuovo):
        stato = nuovo.get("/api/onboarding").json()
        assert [m["nome"] for m in stato["modalita"]] == ["CLASSIC", "MANTRA"]
        assert any(s["nome"] == "STRISCE" for s in stato["stili_maglia"])

    def test_quante_squadre_puo_avere_una_lega_lo_dice_il_server(self, nuovo):
        """Il modulo non scrive 10, 2 e 20: li legge da qui."""
        from fantacalcio.leghe import (
            PARTECIPANTI_MASSIMI,
            PARTECIPANTI_MINIMI,
            PARTECIPANTI_PREDEFINITI,
        )

        stato = nuovo.get("/api/onboarding").json()
        assert stato["partecipanti_predefiniti"] == PARTECIPANTI_PREDEFINITI
        assert stato["partecipanti_minimi"] == PARTECIPANTI_MINIMI
        assert stato["partecipanti_massimi"] == PARTECIPANTI_MASSIMI


class TestCreareUnaLega:
    def test_chi_la_crea_ne_diventa_presidente(self, nuovo):
        risposta = nuovo.post("/api/onboarding/lega", json=LEGA)
        assert risposta.status_code == 201
        assert risposta.json()["nome"] == "Lega degli Amici"
        # Otto caratteri col trattino in mezzo: e' il codice da girare.
        assert len(risposta.json()["codice_invito"]) == 9

        chi = nuovo.get("/api/io").json()
        assert chi["ruolo"] == "PRESIDENTE"
        assert chi["lega_id"] is not None

    def test_le_opzioni_scelte_arrivano_nella_lega(self, nuovo):
        nuovo.post("/api/onboarding/lega", json=LEGA)
        lega = nuovo.get("/api/lega").json()
        assert lega["nome"] == "Lega degli Amici"
        assert lega["stagione"] == "2026/27"

    def test_dopo_averla_creata_serve_la_squadra(self, nuovo):
        nuovo.post("/api/onboarding/lega", json=LEGA)
        assert nuovo.get("/api/onboarding").json()["serve"] == "squadra"

    def test_chi_e_gia_in_una_lega_non_ne_crea_un_altra(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        risposta = client.post("/api/onboarding/lega", json=LEGA)
        assert risposta.status_code == 422
        assert "gia' in una lega" in risposta.json()["detail"]

    def test_un_nome_vuoto_si_rifiuta(self, nuovo):
        assert (
            nuovo.post("/api/onboarding/lega", json={**LEGA, "nome": ""}).status_code
            == 422
        )

    def test_una_lega_da_una_squadra_sola_si_rifiuta(self, nuovo):
        assert (
            nuovo.post(
                "/api/onboarding/lega", json={**LEGA, "partecipanti": 1}
            ).status_code
            == 422
        )


class TestUnirsiAUnaLega:
    def codice(self, client) -> str:
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        codice = client.get("/api/lega").json()["codice_invito"]
        client.post("/api/esci")
        return codice

    def test_col_codice_giusto_si_entra(self, client):
        codice = self.codice(client)
        client.post("/api/registrazione", json=ISCRIZIONE)

        risposta = client.post("/api/onboarding/unisciti", json={"codice": codice})
        assert risposta.status_code == 200
        assert client.get("/api/io").json()["lega_id"] is not None

    def test_chi_entra_e_un_fantallenatore(self, client):
        codice = self.codice(client)
        client.post("/api/registrazione", json=ISCRIZIONE)
        client.post("/api/onboarding/unisciti", json={"codice": codice})
        assert client.get("/api/io").json()["ruolo"] == "FANTALLENATORE"

    def test_il_codice_si_normalizza(self, client):
        """Scritto a mano arriva in minuscolo, con spazi, senza trattino."""
        codice = self.codice(client)
        client.post("/api/registrazione", json=ISCRIZIONE)
        storto = f"  {codice.replace('-', '').lower()} "
        assert (
            client.post("/api/onboarding/unisciti", json={"codice": storto}).status_code
            == 200
        )

    def test_un_codice_inventato_non_apre_niente(self, client):
        client.post("/api/registrazione", json=ISCRIZIONE)
        risposta = client.post("/api/onboarding/unisciti", json={"codice": "ZZZZ-9999"})
        assert risposta.status_code == 404
        assert "otto caratteri" in risposta.json()["detail"]

    def test_chi_e_gia_dentro_non_si_unisce_altrove(self, client):
        codice = self.codice(client)
        client.post(
            "/api/accesso", json={"nome_utente": "luca", "password": "fantanuovo26"}
        )
        assert (
            client.post("/api/onboarding/unisciti", json={"codice": codice}).status_code
            == 422
        )


class TestFondareLaSquadra:
    def dentro_la_lega(self, nuovo):
        nuovo.post("/api/onboarding/lega", json=LEGA)
        return nuovo

    def test_la_squadra_si_crea_e_resta_sua(self, nuovo):
        cliente = self.dentro_la_lega(nuovo)
        risposta = cliente.post("/api/onboarding/squadra", json=SQUADRA)
        assert risposta.status_code == 201

        chi = cliente.get("/api/io").json()
        assert chi["squadra_id"] == risposta.json()["id"]
        assert cliente.get("/api/onboarding").json()["serve"] == "niente"

    def test_l_identita_scelta_si_ritrova(self, nuovo):
        cliente = self.dentro_la_lega(nuovo)
        creata = cliente.post("/api/onboarding/squadra", json=SQUADRA).json()
        squadra = cliente.get(f"/api/squadre/{creata['id']}").json()
        assert squadra["nome"] == "Real Sporcaccioni"
        assert squadra["stadio"] == "Arena del NuoVo"
        assert squadra["curva"] == "Curva Nord"
        assert squadra["e_mia"] is True

    def test_senza_lega_non_si_fonda_niente(self, nuovo):
        risposta = nuovo.post("/api/onboarding/squadra", json=SQUADRA)
        assert risposta.status_code == 422
        assert "Prima entra in una lega" in risposta.json()["detail"]

    def test_non_se_ne_fondano_due(self, nuovo):
        cliente = self.dentro_la_lega(nuovo)
        cliente.post("/api/onboarding/squadra", json=SQUADRA)
        risposta = cliente.post(
            "/api/onboarding/squadra", json={**SQUADRA, "nome": "Un'altra"}
        )
        assert risposta.status_code == 422
        assert "gia' una squadra" in risposta.json()["detail"]

    def test_un_nome_gia_preso_si_rifiuta(self, client):
        """Due squadre con lo stesso nome non si distinguono in classifica."""
        codice = self.codice_demo(client)
        client.post("/api/registrazione", json=ISCRIZIONE)
        client.post("/api/onboarding/unisciti", json={"codice": codice})
        risposta = client.post(
            "/api/onboarding/squadra", json={**SQUADRA, "nome": "Tiri Team"}
        )
        assert risposta.status_code == 409
        assert "Esiste gia'" in risposta.json()["detail"]

    def codice_demo(self, client) -> str:
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        codice = client.get("/api/lega").json()["codice_invito"]
        client.post("/api/esci")
        return codice

    def test_un_colore_impossibile_si_rifiuta(self, nuovo):
        cliente = self.dentro_la_lega(nuovo)
        risposta = cliente.post(
            "/api/onboarding/squadra", json={**SQUADRA, "colore_primario": "verde"}
        )
        assert risposta.status_code == 422


class TestLaModalitaEIModuli:
    """Scegliendo Classic i moduli devono seguire, o la lega si rifiuta da se'."""

    def test_una_lega_classic_si_crea(self, nuovo):
        risposta = nuovo.post(
            "/api/onboarding/lega", json={**LEGA, "modalita": "CLASSIC"}
        )
        assert risposta.status_code == 201, risposta.text

    def test_e_tiene_i_moduli_classic(self, nuovo):
        nuovo.post("/api/onboarding/lega", json={**LEGA, "modalita": "CLASSIC"})
        moduli = nuovo.get("/api/lega").json()["regole"]
        testo = str(moduli)
        # Il 4-1-4-1 e' un modulo Mantra: in una lega Classic non deve esserci.
        assert "4-1-4-1" not in testo

    def test_il_predefinito_e_mantra(self, nuovo):
        """E' la modalita' in cui gioca questa lega: partire dall'altra fa
        creare la lega sbagliata a chi non guarda."""
        senza_modalita = {k: v for k, v in LEGA.items() if k != "modalita"}
        nuovo.post("/api/onboarding/lega", json=senza_modalita)
        assert "Mantra" in str(nuovo.get("/api/lega").json())


class TestDireDiQualeSquadraSeiPresidente:
    """La strada normale quando il calendario e' stato caricato prima.

    Le dieci squadre esistono gia' — i nomi stanno nel calendario ufficiale,
    che si carica prima che le persone siano entrate — e chi arriva col codice
    deve dire quale guida, non fondarne un'undicesima che nel campionato non
    gioca.
    """

    def entra_col_codice(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        codice = client.get("/api/lega").json()["codice_invito"]
        client.post("/api/esci")
        client.post("/api/registrazione", json=ISCRIZIONE)
        client.post("/api/onboarding/unisciti", json={"codice": codice})
        return client

    def test_a_chi_entra_il_sito_propone_le_squadre_senza_presidente(
        self, squadre_in_attesa
    ):
        cliente = self.entra_col_codice(squadre_in_attesa)

        stato = cliente.get("/api/onboarding").json()

        assert stato["serve"] == "squadra"
        assert stato["squadre_libere"]
        nomi = [s["nome"] for s in stato["squadre_libere"]]
        assert "Tiri Team" not in nomi  # e' di Marco
        assert all(s["giocatori"] > 0 for s in stato["squadre_libere"])

    def test_chi_non_e_ancora_in_una_lega_non_vede_squadre(self, client):
        """Prima la lega: le squadre di un'altra non lo riguardano."""
        client.post("/api/registrazione", json=ISCRIZIONE)

        stato = client.get("/api/onboarding").json()

        assert stato["serve"] == "lega"
        assert stato["squadre_libere"] == []

    def test_rivendicarla_la_collega_a_chi_l_ha_chiesta(self, squadre_in_attesa):
        cliente = self.entra_col_codice(squadre_in_attesa)
        libera = cliente.get("/api/onboarding").json()["squadre_libere"][0]

        risposta = cliente.post(
            "/api/onboarding/squadra/rivendica", json={"squadra_id": libera["id"]}
        )

        assert risposta.status_code == 200
        assert risposta.json()["nome"] == libera["nome"]
        assert cliente.get("/api/io").json()["squadra_id"] == libera["id"]
        assert cliente.get("/api/onboarding").json()["serve"] == "niente"

    def test_la_squadra_mostra_il_nome_del_suo_presidente(self, squadre_in_attesa):
        """Finche' resta vuoto, la pagina della squadra sembra di nessuno."""
        cliente = self.entra_col_codice(squadre_in_attesa)
        libera = cliente.get("/api/onboarding").json()["squadre_libere"][0]

        cliente.post(
            "/api/onboarding/squadra/rivendica", json={"squadra_id": libera["id"]}
        )

        squadra = cliente.get(f"/api/squadre/{libera['id']}").json()
        assert squadra["presidente"] == "Chiara Rossi"
        assert squadra["e_mia"] is True

    def test_una_squadra_che_ha_gia_un_presidente_non_si_porta_via(
        self, squadre_in_attesa
    ):
        """Il bottone lo premono in due: a fermare il secondo e' il server."""
        cliente = self.entra_col_codice(squadre_in_attesa)
        sua_di_marco = 1

        risposta = cliente.post(
            "/api/onboarding/squadra/rivendica", json={"squadra_id": sua_di_marco}
        )

        assert risposta.status_code == 422
        assert "gia' un presidente" in risposta.json()["detail"]
        assert cliente.get("/api/io").json()["squadra_id"] is None

    def test_chi_ha_gia_la_sua_non_ne_prende_una_seconda(self, client):
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        libere = client.get("/api/squadre").json()

        risposta = client.post(
            "/api/onboarding/squadra/rivendica",
            json={"squadra_id": libere[-1]["id"]},
        )

        assert risposta.status_code == 422
        assert "gia' una squadra" in risposta.json()["detail"]

    def test_una_squadra_che_non_esiste(self, squadre_in_attesa):
        cliente = self.entra_col_codice(squadre_in_attesa)

        risposta = cliente.post(
            "/api/onboarding/squadra/rivendica", json={"squadra_id": 9999}
        )

        assert risposta.status_code == 404

    def test_senza_sessione_non_si_rivendica_niente(self, client):
        client.post("/api/esci")

        risposta = client.post(
            "/api/onboarding/squadra/rivendica", json={"squadra_id": 1}
        )

        assert risposta.status_code == 401

    def test_in_una_lega_nuova_non_c_e_niente_da_rivendicare(self, nuovo):
        """Chi fonda la lega non trova squadre: le crea, o le carica col
        calendario. L'elenco vuoto e' la differenza fra «scegli la tua» e
        «fondala»."""
        nuovo.post("/api/onboarding/lega", json=LEGA)

        stato = nuovo.get("/api/onboarding").json()

        assert stato["serve"] == "squadra"
        assert stato["squadre_libere"] == []


class TestUnaLegaSalvataConIModuliVecchi:
    """Il guasto di chi aveva gia' creato la lega prima del cambio dei moduli.

    La riga nel database porta ancora i sedici moduli. Letta male, la lega
    spariva senza un errore (`carica_leghe` salta le righe illeggibili) e il
    sito rimandava il presidente all'onboarding: «non sei in nessuna lega».
    """

    SEDICI = [
        "3-4-3", "3-4-1-2", "3-4-2-1", "3-5-2", "3-5-1-1", "4-3-3", "4-4-2",
        "4-3-1-2", "4-1-4-1", "4-2-3-1", "4-4-1-1", "4-3-2-1",
        "5-3-2", "5-4-1", "5-2-2-1", "5-3-1-1",
    ]  # fmt: skip

    @pytest.fixture
    def con_la_lega_vecchia(self, monkeypatch, db_demo):
        import json

        with sqlite3.connect(db_demo) as conn:
            (grezzo,) = conn.execute("select opzioni from leghe where id = 1").fetchone()
            opzioni = json.loads(grezzo)
            opzioni["moduli_ammessi"] = self.SEDICI
            conn.execute(
                "update leghe set opzioni = ? where id = 1", (json.dumps(opzioni),)
            )
        return _client(monkeypatch, db_demo)

    def test_il_presidente_e_ancora_dentro_la_sua_lega(self, con_la_lega_vecchia):
        client = con_la_lega_vecchia
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )

        stato = client.get("/api/onboarding").json()

        assert stato["serve"] == "niente"
        assert stato["nome_lega"]

    def test_la_pagina_della_lega_si_apre(self, con_la_lega_vecchia):
        client = con_la_lega_vecchia
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )

        risposta = client.get("/api/lega")

        assert risposta.status_code == 200
        assert risposta.json()["codice_invito"]

    def test_chi_entra_col_codice_trova_la_lega(self, con_la_lega_vecchia):
        client = con_la_lega_vecchia
        client.post(
            "/api/accesso", json={"nome_utente": "marco", "password": "fantanuovo26"}
        )
        codice = client.get("/api/lega").json()["codice_invito"]
        client.post("/api/esci")
        client.post("/api/registrazione", json=ISCRIZIONE)

        risposta = client.post("/api/onboarding/unisciti", json={"codice": codice})

        assert risposta.status_code == 200
