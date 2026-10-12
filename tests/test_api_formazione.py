"""La formazione vista dall'API: chi puo' schierare, e fino a quando.

Le regole del Mantra hanno i loro test in `test_formazioni.py`. Qui si prova
quello che l'API aggiunge: che le caselle arrivino con dentro chi le puo'
occupare — perche' e' il modo in cui la tabella Mantra resta in Python invece
di finire riscritta in TypeScript — e che il blocco valga anche sulla rotta.

Il blocco e' il confine fra «schierata in tempo» e «schierata dopo aver visto
le formazioni degli altri»: un bottone nascosto non e' un controllo.
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


def pagina(client, **parametri):
    return client.get("/api/formazione", params=parametri).json()


def da_schierare(dati: dict) -> dict:
    """La proposta che il server stesso suggerisce, pronta da rimandare."""
    return {
        "giornata": dati["giornata"],
        "competizione": dati["competizione"],
        "modulo": dati["modulo"],
        "titolari": dati["titolari"],
        "panchina": dati["panchina"],
    }


class TestLaPagina:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/formazione").status_code == 401

    def test_propone_la_prima_giornata_non_disputata(self, client):
        entra(client)
        dati = pagina(client)
        assert dati["giornata"] >= 1
        assert dati["competizione"] == "CAMPIONATO"
        assert dati["totali"] == 10

    def test_porta_una_proposta_gia_valida(self, client):
        """Chi apre la pagina non deve trovare undici caselle vuote."""
        entra(client)
        dati = pagina(client)
        assert len(dati["titolari"]) == dati["titolari_richiesti"] == 11
        assert len(set(dati["titolari"])) == 11
        assert len(dati["panchina"]) <= dati["panchinari"]

    def test_la_panchina_non_ripete_i_titolari(self, client):
        entra(client)
        dati = pagina(client)
        assert not set(dati["panchina"]) & set(dati["titolari"])

    def test_dice_le_regole_dell_adattamento_prima_di_schierare(self, client):
        entra(client)
        dati = pagina(client)
        assert dati["adattamento_ammesso"] is True
        assert dati["malus_adattamento"] > 0
        assert dati["modalita_sostituzioni"]


class TestLeCaselle:
    """La tabella Mantra arriva risolta, non da ricalcolare nella pagina."""

    def test_ogni_casella_dice_chi_la_occupa_di_diritto_e_chi_adattandosi(self, client):
        entra(client)
        caselle = pagina(client)["caselle"]
        assert len(caselle) == 11
        assert all(c["liberi"] for c in caselle)
        # I due elenchi non si sovrappongono: chi entra gratis non e' adattato.
        for casella in caselle:
            assert not set(casella["liberi"]) & set(casella["adattati"])

    def test_in_porta_non_ci_si_adatta(self, client):
        """Nessun ruolo si adatta a fare il portiere: la casella lo dice."""
        entra(client)
        porta = pagina(client)["caselle"][0]
        assert porta["reparto"] == "Porta"
        assert porta["adattati"] == []
        assert porta["liberi"]

    def test_cambiare_modulo_cambia_le_caselle(self, client):
        entra(client)
        dati = pagina(client)
        altro = next(m for m in dati["moduli"] if m != dati["modulo"])

        nuovo = pagina(client, modulo=altro)

        assert nuovo["modulo"] == altro
        etichette = [c["etichetta"] for c in nuovo["caselle"]]
        assert etichette != [c["etichetta"] for c in dati["caselle"]]
        assert len(nuovo["titolari"]) == 11

    def test_un_modulo_che_la_lega_non_ammette_si_ignora(self, client):
        """Non un errore: si ricade sul modulo buono, invece di una pagina rotta."""
        entra(client)
        dati = pagina(client, modulo="9-0-1")
        assert dati["modulo"] in dati["moduli"]


class TestSchierare:
    def test_la_proposta_del_server_si_salva_com_e(self, client):
        entra(client)
        dati = pagina(client)

        risposta = client.post("/api/formazione", json=da_schierare(dati))

        assert risposta.status_code == 200
        assert "salvata" in risposta.json()["messaggio"]

    def test_dopo_il_salvataggio_la_vedono_tutti(self, client):
        entra(client)
        dati = pagina(client)
        client.post("/api/formazione", json=da_schierare(dati))

        entra(client, "Luca")
        viste = pagina(client, giornata=dati["giornata"])
        assert viste["schierate"] == 1
        schierata = viste["squadre"][0]
        assert schierata["squadra"] == "Tiri Team"
        # Gia' divisa per reparti, pronta da disegnare sul campo.
        assert [len(r) for r in schierata["reparti"]] == [1, 3, 4, 3]
        assert all(g["nome"] for riga in schierata["reparti"] for g in riga)

    def test_chi_non_ha_schierato_e_nell_elenco(self, client):
        entra(client)
        dati = pagina(client)
        client.post("/api/formazione", json=da_schierare(dati))

        dopo = pagina(client, giornata=dati["giornata"])
        assert "Tiri Team" not in dopo["mancanti"]
        assert len(dopo["mancanti"]) == 9

    def test_rileggendola_torna_quella_salvata(self, client):
        entra(client)
        dati = pagina(client)
        proposta = da_schierare(dati)
        # Scambio due titolari dello stesso reparto: resta valida ed e'
        # diversa da quella suggerita.
        proposta["titolari"][5], proposta["titolari"][6] = (
            proposta["titolari"][6],
            proposta["titolari"][5],
        )
        client.post("/api/formazione", json=proposta)

        riletta = pagina(client, giornata=dati["giornata"])
        assert riletta["titolari"] == proposta["titolari"]

    def test_dieci_titolari_non_si_salvano(self, client):
        entra(client)
        proposta = da_schierare(pagina(client))
        proposta["titolari"] = proposta["titolari"][:10]

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "11 titolari" in risposta.json()["detail"]

    def test_un_giocatore_non_in_rosa_non_si_schiera(self, client):
        entra(client)
        proposta = da_schierare(pagina(client))
        proposta["titolari"][10] = 999_999

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "non sono in rosa" in risposta.json()["detail"]

    def test_lo_stesso_giocatore_due_volte_non_si_schiera(self, client):
        entra(client)
        proposta = da_schierare(pagina(client))
        proposta["titolari"][1] = proposta["titolari"][2]

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "due volte" in risposta.json()["detail"]

    def test_i_problemi_arrivano_tutti_insieme(self, client):
        """Chi schiera vuole sapere quante cose deve sistemare, non una alla volta."""
        entra(client)
        proposta = da_schierare(pagina(client))
        proposta["titolari"] = proposta["titolari"][:9] + [999_998, 999_999]

        dettaglio = client.post("/api/formazione", json=proposta).json()["detail"]

        assert "non sono in rosa" in dettaglio

    def test_senza_squadra_non_si_schiera(self, client):
        """Il presidente di un'altra lega qui dentro non ha niente da schierare."""
        from fantacalcio.data import archivio, carica_credenziali, salva_credenziali

        entra(client)
        proposta = da_schierare(pagina(client))

        arch = archivio()
        credenziali = carica_credenziali(arch)["luca"]
        from dataclasses import replace

        salva_credenziali(
            arch,
            replace(credenziali, utente=replace(credenziali.utente, squadra_id=None)),
        )

        entra(client, "Luca")
        risposta = client.post("/api/formazione", json=proposta)
        assert risposta.status_code == 403
        assert "squadra" in risposta.json()["detail"]


class TestIlBlocco:
    """Si chiude un minuto prima del calcio d'inizio, e vale anche sulla rotta."""

    @staticmethod
    def _programma(giornata: int, quando: str) -> None:
        """Mette un orario d'inizio alle partite di una giornata."""
        from fantacalcio.data import archivio

        arch = archivio()
        calendario = arch.calendario()
        righe = [
            {**r, "inizio_previsto": quando}
            for r in calendario.to_dict("records")
            if int(r["giornata"]) == giornata
        ]
        arch.scrivi("calendario", righe, "id")

    def test_senza_orario_in_calendario_resta_aperta(self, client):
        """Una giornata non programmata non blocca: peggio il contrario."""
        entra(client)
        blocco = pagina(client)["blocco"]
        assert blocco["modificabile"] is True
        assert blocco["inizio"] is None

    def test_una_giornata_cominciata_e_chiusa(self, client):
        entra(client)
        giornata = pagina(client)["giornata"]
        self._programma(giornata, "2020-01-01T15:00:00")

        dati = pagina(client, giornata=giornata)

        assert dati["blocco"]["modificabile"] is False
        assert dati["posso_schierare"] is False
        assert "bloccano" in dati["blocco"]["motivo"]

    def test_a_giornata_chiusa_la_rotta_rifiuta(self, client):
        entra(client)
        dati = pagina(client)
        proposta = da_schierare(dati)
        self._programma(dati["giornata"], "2020-01-01T15:00:00")

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "bloccano" in risposta.json()["detail"]

    def test_una_giornata_futura_dice_quanto_manca(self, client):
        from datetime import datetime, timedelta

        entra(client)
        giornata = pagina(client)["giornata"]
        fra_due_ore = (datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds")
        self._programma(giornata, fra_due_ore)

        blocco = pagina(client, giornata=giornata)["blocco"]

        assert blocco["modificabile"] is True
        assert 6000 < blocco["mancano_secondi"] <= 7200


class TestCosaLaLegaAmmette:
    """Modulo e competizione si controllano anche sulla rotta.

    `valida` guarda se il modulo e' **leggibile**, non se e' **consentito**:
    un 4-4-2 in una lega che ammette solo moduli a tre difensori passerebbe
    tutti i controlli del Mantra. La tendina non e' il controllo.
    """

    def test_un_modulo_che_la_lega_non_ammette_non_si_salva(self, client):
        entra(client)
        dati = pagina(client)
        proposta = da_schierare(dati)
        # Leggibile e con undici giocatori, ma fuori dall'elenco della lega.
        fuori = "4-5-1"
        assert fuori not in dati["moduli"]
        proposta["modulo"] = fuori

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "non e' fra quelli ammessi" in risposta.json()["detail"]

    def test_una_competizione_che_la_lega_non_gioca_non_si_salva(self, client):
        entra(client)
        proposta = da_schierare(pagina(client))
        proposta["competizione"] = "CHAMPIONS"

        risposta = client.post("/api/formazione", json=proposta)

        assert risposta.status_code == 422
        assert "non gioca" in risposta.json()["detail"]
