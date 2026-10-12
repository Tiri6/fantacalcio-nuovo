"""La sezione Lega vista dall'API: bacheca e cruscotto.

Due pezzi molto diversi. Il cruscotto **non calcola niente**: ripete quello
che dice `conformita.verifica_rosa`, e i test qui servono a dire che non si e'
messo a dedurre numeri per conto suo. La bacheca invece scrive, e li' quello
che conta sono i permessi e il fatto che una correzione parziale non si porti
via il resto dell'annuncio.
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


class TestCruscotto:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/cruscotto").status_code == 401

    def test_una_riga_per_squadra(self, client):
        entra(client)
        dati = client.get("/api/cruscotto").json()
        assert len(dati["righe"]) == 10
        assert len({r["squadra_id"] for r in dati["righe"]}) == 10

    def test_i_limiti_arrivano_accanto_ai_valori(self, client):
        """«31 giocatori» da solo non dice niente: serve il limite accanto.

        E' la stessa ragione per cui le violazioni portano valore e limite:
        chi guarda deve sapere **di quanto** sta sforando, non solo che sfora.
        """
        entra(client)
        riga = client.get("/api/cruscotto").json()["righe"][0]
        for valore, limite in (
            ("dimensione", "limite_dimensione"),
            ("anni_impegnati", "monte_anni"),
            ("contratti_annuali", "annuali_richiesti"),
            ("spesa_salariale", "limite_cap"),
        ):
            assert riga[valore] is not None
            assert riga[limite] is not None

    def test_il_monte_anni_e_quello_dei_parametri(self, client):
        """Il totale non si scrive a mano da nessuna parte: viene dal dominio."""
        from fantacalcio.regole import ParametriLega

        entra(client)
        dati = client.get("/api/cruscotto").json()
        assert dati["monte_anni"] == ParametriLega().monte_anni
        assert all(r["monte_anni"] == dati["monte_anni"] for r in dati["righe"])

    def test_le_violazioni_dicono_articolo_valore_e_limite(self, client):
        entra(client)
        for riga in client.get("/api/cruscotto").json()["righe"]:
            for violazione in riga["violazioni"]:
                assert violazione["articolo"]
                assert violazione["messaggio"]
                assert "bloccante" in violazione

    def test_chi_ha_qualcosa_da_sistemare_sta_in_cima(self, client):
        """E' la riga che si cerca entrando: non deve toccare scorrere."""
        entra(client)
        conformi = [r["conforme"] for r in client.get("/api/cruscotto").json()["righe"]]
        assert conformi == sorted(conformi)

    @pytest.mark.parametrize("momento", ["ASTA_SETTEMBRE", "RIPARAZIONE", "STAGIONE"])
    def test_ogni_lente_risponde(self, client, momento):
        entra(client)
        risposta = client.get(f"/api/cruscotto?momento={momento}")
        assert risposta.status_code == 200
        assert risposta.json()["momento"] == momento

    def test_una_lente_inventata_non_passa(self, client):
        entra(client)
        assert client.get("/api/cruscotto?momento=DOMANI").status_code == 422

    def test_il_cruscotto_concorda_con_il_dominio(self, client):
        """Se qui comparisse un numero diverso, vorrebbe dire che l'API calcola.

        E l'API non deve calcolare niente: traduce e basta.
        """
        from api.contesto import contesto_di
        from fantacalcio.conformita import Momento
        from fantacalcio.data import archivio, carica_credenziali, carica_rose
        from fantacalcio.regole import ParametriLega
        from fantacalcio.vista import stati_rose

        entra(client)
        righe = client.get("/api/cruscotto?momento=STAGIONE").json()["righe"]

        utente = carica_credenziali(archivio())["marco"].utente
        ctx = contesto_di(utente)
        attesi = stati_rose(
            carica_rose(ctx.arch), ctx.riferimento_u21, ParametriLega(), Momento.STAGIONE
        )

        for riga in righe:
            stato = attesi[riga["squadra_id"]]
            assert riga["anni_impegnati"] == stato.anni_impegnati
            assert riga["monte_ingaggi"] == pytest.approx(stato.monte_ingaggi)
            assert riga["spesa_salariale"] == pytest.approx(stato.spesa_salariale)
            assert riga["conforme"] is stato.conforme
            assert len(riga["violazioni"]) == len(stato.violazioni)


class TestBachecaLettura:
    def test_senza_entrare_non_si_legge(self, client):
        assert client.get("/api/bacheca").status_code == 401

    def test_il_presidente_puo_scrivere_il_fantallenatore_no(self, client):
        entra(client, "marco")
        assert client.get("/api/bacheca").json()["posso_scrivere"] is True
        entra(client, "luca")
        assert client.get("/api/bacheca").json()["posso_scrivere"] is False

    def test_le_bozze_le_vede_solo_chi_amministra(self, client):
        """Serve a preparare il recap prima che la giornata sia chiusa."""
        entra(client, "marco")
        tutti = client.get("/api/bacheca").json()["annunci"]
        bozze = [a for a in tutti if not a["pubblicato"]]
        # Senza una bozza nella demo questo test non proverebbe niente.
        assert bozze

        entra(client, "luca")
        visti = client.get("/api/bacheca").json()["annunci"]
        assert all(a["pubblicato"] for a in visti)
        assert not any(a["id"] == bozze[0]["id"] for a in visti)

    def test_quello_in_evidenza_sta_in_cima(self, client):
        entra(client)
        annunci = client.get("/api/bacheca").json()["annunci"]
        evidenza = [a["in_evidenza"] for a in annunci]
        assert evidenza == sorted(evidenza, reverse=True)

    def test_il_testo_resta_markdown_grezzo(self, client):
        """Non deve uscire HTML da qui.

        Se l'API restituisse markup gia' pronto, il front-end dovrebbe
        piazzarlo con `dangerouslySetInnerHTML` — e da li' chi scrive un
        annuncio potrebbe infilare uno `<script>` nella pagina di tutti.
        """
        entra(client)
        for annuncio in client.get("/api/bacheca").json()["annunci"]:
            assert "<p>" not in annuncio["testo"]
            assert "<script" not in annuncio["testo"].lower()

    def test_porta_i_limiti_che_servono_al_modulo(self, client):
        entra(client)
        dati = client.get("/api/bacheca").json()
        assert dati["titolo_minimo"] >= 1
        assert dati["titolo_massimo"] > dati["titolo_minimo"]
        assert dati["testo_massimo"] > 0


class TestBachecaScrittura:
    def scrivi(self, client, **campi):
        corpo = {"titolo": "Un titolo valido", "testo": "Un testo."} | campi
        return client.post("/api/bacheca", json=corpo)

    def test_il_fantallenatore_non_scrive(self, client):
        entra(client, "luca")
        assert self.scrivi(client).status_code == 403

    def test_il_presidente_scrive(self, client):
        entra(client, "marco")
        risposta = self.scrivi(client, titolo="Novita'", testo="**Grassetto**")
        assert risposta.status_code == 201
        nuovo = risposta.json()
        assert nuovo["autore_nome"] == "Marco"
        assert nuovo["testo"] == "**Grassetto**"
        assert nuovo["data_leggibile"]

    def test_un_titolo_troppo_corto_non_passa(self, client):
        entra(client, "marco")
        assert self.scrivi(client, titolo="ab").status_code == 422

    def test_un_tipo_inventato_non_passa(self, client):
        entra(client, "marco")
        assert self.scrivi(client, tipo="PETTEGOLEZZO").status_code == 422

    def test_la_correzione_parziale_non_cancella_il_resto(self, client):
        """I bottoni rapidi mandano un campo solo, non tutto l'annuncio.

        Se mandassero tutto, due persone che premono due bottoni diversi
        nello stesso minuto si sovrascriverebbero il testo a vicenda.
        """
        entra(client, "marco")
        nuovo = self.scrivi(client, titolo="Resta intero", testo="Il testo lungo").json()

        corretto = client.put(
            f"/api/bacheca/{nuovo['id']}", json={"in_evidenza": True}
        ).json()
        assert corretto["in_evidenza"] is True
        assert corretto["titolo"] == "Resta intero"
        assert corretto["testo"] == "Il testo lungo"

    def test_il_fantallenatore_non_corregge(self, client):
        entra(client, "marco")
        nuovo = self.scrivi(client).json()
        entra(client, "luca")
        risposta = client.put(f"/api/bacheca/{nuovo['id']}", json={"in_evidenza": True})
        assert risposta.status_code == 403

    def test_il_fantallenatore_non_cancella(self, client):
        entra(client, "marco")
        nuovo = self.scrivi(client).json()
        entra(client, "luca")
        assert client.delete(f"/api/bacheca/{nuovo['id']}").status_code == 403

    def test_il_presidente_cancella_e_sparisce(self, client):
        entra(client, "marco")
        nuovo = self.scrivi(client).json()
        assert client.delete(f"/api/bacheca/{nuovo['id']}").status_code == 204
        rimasti = client.get("/api/bacheca").json()["annunci"]
        assert not any(a["id"] == nuovo["id"] for a in rimasti)

    def test_cancellare_due_volte_da_404(self, client):
        entra(client, "marco")
        nuovo = self.scrivi(client).json()
        client.delete(f"/api/bacheca/{nuovo['id']}")
        assert client.delete(f"/api/bacheca/{nuovo['id']}").status_code == 404

    def test_giornata_zero_vuol_dire_nessuna_giornata(self, client):
        """Lo zero del modulo e' «non riguarda una giornata in particolare»."""
        entra(client, "marco")
        nuovo = self.scrivi(client, giornata=5).json()
        corretto = client.put(f"/api/bacheca/{nuovo['id']}", json={"giornata": 0}).json()
        assert corretto["giornata"] is None


class TestCambiareLeRegole:
    """Il modulo delle regole, che il sito disegna dalla descrizione.

    Su Streamlit si cambiavano le regole senza rifare la lega; qui la pagina
    le mostrava e basta. Chi aveva votato un lodo doveva tornare sul vecchio
    sito, che e' il motivo per cui il vecchio sito non si poteva spegnere.
    """

    def test_senza_entrare_non_si_vedono(self, client):
        assert client.get("/api/lega/regole").status_code == 401

    def test_arrivano_in_gruppi_con_dentro_i_valori(self, client):
        entra(client)

        regole = client.get("/api/lega/regole").json()

        titoli = [g["titolo"] for g in regole["gruppi"]]
        assert "Generali" in titoli and "Punteggio" in titoli
        campi = {c["nome"]: c for g in regole["gruppi"] for c in g["campi"]}
        assert campi["partecipanti"]["valore"] == 10
        assert campi["modalita"]["tipo"] == "scelta"
        assert campi["bonus.assist"]["etichetta"] == "Assist"

    def test_dicono_chi_puo_cambiarle(self, client):
        entra(client)
        da_presidente = client.get("/api/lega/regole").json()
        entra(client, "luca")
        da_fantallenatore = client.get("/api/lega/regole").json()

        assert da_presidente["posso_modificare"] is True
        assert da_fantallenatore["posso_modificare"] is False

    def test_dicono_anche_cosa_non_si_tocca_e_perche(self, client):
        """Un'opzione che esiste e non si vede sembra un pezzo rotto."""
        entra(client)

        escluse = client.get("/api/lega/regole").json()["escluse"]

        assert {e["nome"] for e in escluse} >= {"ordine_draft", "fasce_difesa"}
        assert all(e["motivo"] for e in escluse)

    def test_l_anteprima_dice_cosa_cambia(self, client):
        entra(client)

        esito = client.post(
            "/api/lega/regole/anteprima",
            json={"valori": {"partecipanti": 12, "bonus.assist": 2.0}},
        ).json()

        assert "Partecipanti: 10 → 12" in esito["cambia"]
        assert "Assist: 1 → 2" in esito["cambia"]
        assert esito["errore"] == ""

    def test_l_anteprima_avvisa_senza_rifiutare(self, client):
        """Togliere moduli e' legittimo, ma chi li aveva usati si ritrova la
        formazione da rifare: meglio dirlo prima."""
        entra(client)

        esito = client.post(
            "/api/lega/regole/anteprima",
            json={"valori": {"moduli_ammessi": ["4-4-2"]}},
        ).json()

        assert any("Moduli tolti" in a for a in esito["avvisi"])

    def test_un_valore_impossibile_torna_200_con_l_errore_dentro(self, client):
        """Chi sta compilando non deve perdere il resto del modulo."""
        entra(client)

        risposta = client.post(
            "/api/lega/regole/anteprima",
            json={"valori": {"modalita": "SUBBUTEO"}},
        )

        assert risposta.status_code == 200
        assert "non e' un valore ammesso" in risposta.json()["errore"]

    def test_salvare_cambia_davvero_le_regole(self, client):
        entra(client)

        risposta = client.put(
            "/api/lega/regole",
            json={"valori": {"punti_vittoria": 2, "coppa_italia": True}},
        )

        assert risposta.status_code == 200
        campi = {c["nome"]: c for g in risposta.json()["gruppi"] for c in g["campi"]}
        assert campi["punti_vittoria"]["valore"] == 2
        assert campi["coppa_italia"]["valore"] is True
        # E la lega riletta dice la stessa cosa, non solo la risposta.
        assert (
            client.get("/api/lega/regole").json()["gruppi"][0]["campi"][4]["valore"] == 2
        )

    def test_un_lodo_che_cambia_il_cap_arriva_al_cruscotto(self, client):
        """Il giro completo: si cambia la regola e il conto che ne dipende
        cambia con lei, senza rifare la lega."""
        entra(client)

        client.put("/api/lega/regole", json={"valori": {"budget_cap": 50_000_000}})

        regolamento = client.get("/api/regolamento").json()
        assert "50" in str(regolamento)

    def test_chi_non_ha_creato_la_lega_non_le_cambia(self, client):
        entra(client, "luca")

        risposta = client.put("/api/lega/regole", json={"valori": {"punti_vittoria": 2}})

        assert risposta.status_code == 403

    def test_non_si_scende_sotto_le_squadre_iscritte(self, client):
        """Dieci squadre dentro e il tetto a otto lascerebbe fuori due che
        stanno giocando. E' l'unico controllo che `OpzioniLega` da sola non
        puo' fare: non sa come sta messa **questa** lega."""
        entra(client)
        # Prima si toglie la coppa: con dieci squadre ammesse sarebbe lei a
        # protestare per prima, e il controllo che si vuole provare e' l'altro.
        client.put("/api/lega/regole", json={"valori": {"coppa_italia": False}})

        risposta = client.put("/api/lega/regole", json={"valori": {"partecipanti": 8}})

        assert risposta.status_code == 422
        assert "iscritte" in risposta.json()["detail"]

    def test_una_regola_assurda_in_se_la_ferma_la_dataclass(self, client):
        """Due controlli diversi, tutti e due a monte del salvataggio."""
        entra(client)

        risposta = client.put("/api/lega/regole", json={"valori": {"passo_gol": 0}})

        assert risposta.status_code == 422
        assert risposta.json()["detail"]

    def test_la_stagione_si_cambia_da_qui(self, client):
        entra(client)

        risposta = client.put(
            "/api/lega/regole", json={"valori": {}, "stagione": "2027/28"}
        )

        assert risposta.status_code == 200
        assert risposta.json()["stagione"] == "2027/28"
