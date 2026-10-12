"""La sala del draft vista dall'API.

Tre cose si provano qui e non nel dominio, perche' esistono solo quando c'e'
una richiesta HTTP di mezzo:

1. **Il polling.** Chi guarda la sala la interroga ogni paio di secondi: con
   la stessa versione deve ricevere «niente di nuovo» e non la pagina intera,
   altrimenti dieci persone collegate rileggono rose e listone trenta volte al
   minuto.
2. **La chiamata respinta torna 200.** Le violazioni non sono un errore di
   protocollo: chi chiama deve vedere di quanto sfora e correggere senza
   perdere la pagina, con nove persone che aspettano.
3. **Chi puo' cosa.** La sala la apre chi amministra; chiama chi ha il turno;
   gli anni li corregge solo chi ha preso quel giocatore **in quella sala**.

I dati vengono dal database di demo, dove ogni rosa e' al limite: 31
giocatori e 66 anni impegnati, cioe' esattamente il monte anni. E' una
fortuna per questi test — significa che una chiamata in piu' sfora davvero, e
che per provare il caso buono bisogna prima fare spazio, che e' esattamente
l'ordine delle cose a settembre.
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


def entra(client, chi="marco"):
    client.post("/api/esci")
    risposta = client.post(
        "/api/accesso", json={"nome_utente": chi, "password": "fantanuovo26"}
    )
    assert risposta.status_code == 200, risposta.json()
    return risposta.json()


def apri_sala(client, round_totali=2, **extra):
    """Apre e comincia una sala, come fa chi amministra la sera del draft."""
    entra(client)
    risposta = client.post(
        "/api/sala", json={"tipo": "SETTEMBRE", "round_totali": round_totali, **extra}
    )
    assert risposta.status_code == 200, risposta.json()
    cominciata = client.post("/api/sala/comincia")
    assert cominciata.status_code == 200, cominciata.json()
    return cominciata.json()


def fai_spazio(client, squadra_id, quanti=3):
    """Svincola `quanti` giocatori: libera anni e Salary Cap.

    Con `pre-asta` non si genera Dead Money — e' lo svincolo di chi ripulisce
    la rosa **prima** del draft, che e' il momento in cui questo serve.
    """
    entra(client)
    svincolabili = client.get(f"/api/squadre/{squadra_id}/svincoli").json()["giocatori"]
    for voce in svincolabili[:quanti]:
        fatto = client.post(
            f"/api/squadre/{squadra_id}/svincoli",
            json={"giocatore_id": voce["giocatore_id"], "motivo": "pre-asta"},
        )
        assert fatto.status_code == 200, fatto.json()


def utente_della_squadra(squadra_id):
    """Il nome utente di chi gioca quella squadra, letto dal database."""
    from fantacalcio.data import archivio, carica_credenziali

    for nome, cred in carica_credenziali(archivio()).items():
        if cred.utente.squadra_id == squadra_id:
            return nome
    raise AssertionError(f"Nessun utente per la squadra {squadra_id}")


def chiama(client, pagina, anni=1, indice=0):
    """Fa chiamare chi ha il turno, con un giocatore libero qualunque."""
    turno = pagina["turno"]
    entra(client, utente_della_squadra(turno["squadra_id"]))
    scelto = pagina["disponibili"][indice]
    risposta = client.post(
        "/api/sala/chiamate", json={"giocatore_id": scelto["id"], "anni": anni}
    )
    assert risposta.status_code == 200, risposta.json()
    return scelto, risposta.json()


class TestLaPaginaSenzaSala:
    def test_senza_entrare_non_si_vede(self, client):
        assert client.get("/api/sala").status_code == 401

    def test_senza_sala_lo_dice_invece_di_dare_404(self, client):
        """La pagina esiste sempre: e' da li' che chi amministra apre la sala."""
        entra(client)
        pagina = client.get("/api/sala").json()

        assert pagina["c_e_una_sala"] is False
        assert pagina["turno"] is None
        assert pagina["chiamate"] == []
        assert pagina["posso_amministrare"] is True

    def test_porta_i_limiti_del_contratto_dai_parametri(self, client):
        """Il browser non li sa: 1 e 5 stanno in `ParametriLega`."""
        entra(client)
        pagina = client.get("/api/sala").json()

        assert pagina["anni_minimo"] == 1
        assert pagina["anni_massimo"] == 5


class TestAprire:
    def test_chi_non_amministra_non_apre(self, client):
        entra(client, "luca")
        risposta = client.post("/api/sala", json={"tipo": "SETTEMBRE", "round_totali": 2})

        assert risposta.status_code == 403

    def test_apre_con_l_ordine_gia_congelato(self, client):
        entra(client)
        pagina = client.post(
            "/api/sala", json={"tipo": "SETTEMBRE", "round_totali": 3}
        ).json()

        assert pagina["stato"] == "aperta"
        assert pagina["round_totali"] == 3
        assert pagina["chiamate_totali"] == 30  # tre round per dieci squadre
        # Aperta ma non cominciata: nessuno chiama ancora.
        assert pagina["turno"] is None

    def test_un_tipo_inventato_non_passa(self, client):
        entra(client)
        risposta = client.post("/api/sala", json={"tipo": "NATALE", "round_totali": 2})

        assert risposta.status_code == 422
        assert "NATALE" in risposta.json()["detail"]

    def test_due_sale_insieme_no(self, client):
        """Due turni sulla stessa rosa non vogliono dire niente."""
        apri_sala(client)
        risposta = client.post("/api/sala", json={"tipo": "SETTEMBRE", "round_totali": 2})

        assert risposta.status_code == 422
        assert "in corso" in risposta.json()["detail"]

    def test_dopo_una_chiusa_se_ne_apre_un_altra(self, client):
        """I mercati di riparazione sono altre sale, non la stessa riaperta."""
        apri_sala(client)
        client.post("/api/sala/chiudi")

        risposta = client.post(
            "/api/sala", json={"tipo": "RIPARAZIONE", "round_totali": 1}
        )

        assert risposta.status_code == 200
        assert risposta.json()["tipo"] == "RIPARAZIONE"
        assert risposta.json()["chiamate_totali"] == 10

    def test_l_ordine_della_lottery_si_puo_dettare(self, client):
        """A settembre l'ordine lo estrae la Lottery, non la classifica."""
        entra(client)
        pagina = client.post(
            "/api/sala",
            json={
                "tipo": "SETTEMBRE",
                "round_totali": 1,
                "ordine_lottery": [7, 3, 1, 2, 4, 5, 6, 8, 9, 10],
            },
        ).json()
        client.post("/api/sala/comincia")
        turno = client.get("/api/sala").json()["turno"]

        assert pagina["chiamate_totali"] == 10
        assert turno["squadra_id"] == 7

    def test_comincia_solo_da_aperta(self, client):
        apri_sala(client)
        risposta = client.post("/api/sala/comincia")

        assert risposta.status_code == 422
        assert "in corso" in risposta.json()["detail"]

    def test_chiudere_due_volte_no(self, client):
        apri_sala(client)
        assert client.post("/api/sala/chiudi").status_code == 200
        assert client.post("/api/sala/chiudi").status_code == 422


class TestIlPolling:
    def test_con_la_stessa_versione_risponde_che_non_c_e_niente(self, client):
        """Il caso normale: dieci persone che guardano e nessuno che chiama."""
        pagina = apri_sala(client)
        versione = pagina["versione"]

        di_nuovo = client.get("/api/sala", params={"versione": versione}).json()

        assert di_nuovo["aggiornato"] is False
        assert di_nuovo["versione"] == versione
        # La risposta leggera non rilegge il listone: e' il punto.
        assert di_nuovo["disponibili"] == []

    def test_cominciare_la_sala_cambia_la_versione(self, client):
        """Non tutto cio' che cambia in sala e' una chiamata: gli altri nove
        devono vedere che si e' cominciato senza ricaricare a mano."""
        entra(client)
        aperta = client.post(
            "/api/sala", json={"tipo": "SETTEMBRE", "round_totali": 1}
        ).json()

        in_corso = client.post("/api/sala/comincia").json()

        assert in_corso["versione"] != aperta["versione"]
        dopo = client.get("/api/sala", params={"versione": aperta["versione"]}).json()
        assert dopo["aggiornato"] is True
        assert dopo["stato"] == "in corso"

    def test_aprire_la_sala_la_fa_comparire_a_chi_guardava(self, client):
        """Chi aveva davanti la pagina vuota non deve restare a guardarla."""
        entra(client)
        vuota = client.get("/api/sala").json()
        assert vuota["versione"] == "nessuna"

        entra(client, "luca")
        ferma = client.get("/api/sala", params={"versione": "nessuna"}).json()
        apri_sala(client, round_totali=1)
        entra(client, "luca")
        dopo = client.get("/api/sala", params={"versione": "nessuna"}).json()

        assert ferma["aggiornato"] is False
        assert dopo["aggiornato"] is True
        assert dopo["c_e_una_sala"] is True

    def test_senza_versione_torna_la_pagina_intera(self, client):
        apri_sala(client)
        pagina = client.get("/api/sala").json()

        assert pagina["aggiornato"] is True
        assert pagina["disponibili"]
        assert pagina["turno"] is not None

    def test_una_chiamata_cambia_la_versione(self, client):
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()

        chiama(client, pagina)
        dopo = client.get("/api/sala", params={"versione": pagina["versione"]}).json()

        assert dopo["aggiornato"] is True
        assert dopo["versione"] != pagina["versione"]
        assert len(dopo["chiamate"]) == 1

    def test_gli_altri_vedono_la_chiamata_appena_fatta(self, client):
        """E' tutto quel che serve: nessun canale aperto, solo un numero."""
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()
        scelto, _ = chiama(client, pagina)

        entra(client, "marco")
        dopo = client.get("/api/sala").json()

        assert [c["giocatore_id"] for c in dopo["chiamate"]] == [scelto["id"]]
        assert dopo["chiamate"][0]["giocatore"] == scelto["nome"]
        # E non e' piu' chiamabile da nessuno.
        assert scelto["id"] not in [g["id"] for g in dopo["disponibili"]]

    def test_le_chiamate_arrivano_dall_ultima(self, client):
        """In sala si guarda chi ha appena chiamato, non chi ha cominciato."""
        pagina = apri_sala(client)
        for _ in range(2):
            pagina = client.get("/api/sala").json()
            fai_spazio(client, pagina["turno"]["squadra_id"])
            pagina = client.get("/api/sala").json()
            chiama(client, pagina)

        entra(client, "marco")
        chiamate = client.get("/api/sala").json()["chiamate"]

        assert [c["numero"] for c in chiamate] == [2, 1]


class TestChiamare:
    def test_a_sala_aperta_ma_non_cominciata_non_si_chiama(self, client):
        entra(client)
        client.post("/api/sala", json={"tipo": "SETTEMBRE", "round_totali": 1})
        pagina = client.get("/api/sala").json()

        esito = client.post(
            "/api/sala/chiamate",
            json={"giocatore_id": pagina["disponibili"][0]["id"], "anni": 1},
        ).json()

        assert esito["fatta"] is False
        assert [v["codice"] for v in esito["violazioni"]] == ["sala_chiusa"]

    def test_fuori_turno_lo_dice_e_non_e_un_errore_http(self, client):
        """200 con la violazione: chi ha sbagliato turno non perde la pagina."""
        pagina = apri_sala(client)
        tocca_a = pagina["turno"]["squadra_id"]
        altro = next(s for s in range(1, 11) if s != tocca_a)
        entra(client, utente_della_squadra(altro))

        risposta = client.post(
            "/api/sala/chiamate",
            json={"giocatore_id": pagina["disponibili"][0]["id"], "anni": 1},
        )

        assert risposta.status_code == 200
        esito = risposta.json()
        assert esito["fatta"] is False
        codici = [v["codice"] for v in esito["violazioni"]]
        assert "non_e_il_tuo_turno" in codici

    def test_la_rosa_piena_sfora_il_monte_anni_e_lo_dice_col_numero(self, client):
        """«Monte anni superato» senza il numero e' inutile quanto il silenzio."""
        pagina = apri_sala(client)
        entra(client, utente_della_squadra(pagina["turno"]["squadra_id"]))

        esito = client.post(
            "/api/sala/chiamate",
            json={"giocatore_id": pagina["disponibili"][0]["id"], "anni": 3},
        ).json()

        assert esito["fatta"] is False
        monte = next(v for v in esito["violazioni"] if v["codice"] == "monte_anni")
        assert "66" in monte["messaggio"]
        assert monte["bloccante"] is True

    def test_chi_ha_fatto_spazio_chiama(self, client):
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()

        scelto, esito = chiama(client, pagina, anni=2)

        assert esito["fatta"] is True
        assert scelto["nome"] in esito["messaggio"]
        assert "2 anni" in esito["messaggio"]

    def test_un_anno_e_al_singolare(self, client):
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()

        _, esito = chiama(client, pagina, anni=1)

        assert "per 1 anno." in esito["messaggio"]

    def test_la_chiamata_entra_in_rosa_col_suo_contratto(self, client):
        """La sala non e' un verbale: la rosa cambia subito."""
        from fantacalcio.data import archivio, carica_rose

        pagina = apri_sala(client)
        squadra_id = pagina["turno"]["squadra_id"]
        fai_spazio(client, squadra_id)
        prima = carica_rose(archivio())[squadra_id]
        pagina = client.get("/api/sala").json()

        scelto, _ = chiama(client, pagina, anni=4)

        dopo = carica_rose(archivio())[squadra_id]
        assert dopo.dimensione == prima.dimensione + 1
        assert dopo.anni_impegnati == prima.anni_impegnati + 4
        contratto = next(c for c in dopo.contratti if c.giocatore_id == scelto["id"])
        assert contratto.anni_residui == 4

    def test_lo_stesso_giocatore_non_si_chiama_due_volte(self, client):
        pagina = apri_sala(client)
        for squadra in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
            fai_spazio(client, squadra, quanti=2)
        pagina = client.get("/api/sala").json()
        scelto, _ = chiama(client, pagina)

        pagina = client.get("/api/sala").json()
        entra(client, utente_della_squadra(pagina["turno"]["squadra_id"]))
        esito = client.post(
            "/api/sala/chiamate", json={"giocatore_id": scelto["id"], "anni": 1}
        ).json()

        assert esito["fatta"] is False
        codici = [v["codice"] for v in esito["violazioni"]]
        # Preso in questa sala: `gia_chiamato`, non «non disponibile».
        assert "gia_chiamato" in codici

    def test_un_giocatore_che_non_esiste_e_un_422(self, client):
        """Qui non c'e' niente da spiegare all'utente: e' il browser a sbagliare."""
        pagina = apri_sala(client)
        entra(client, utente_della_squadra(pagina["turno"]["squadra_id"]))

        risposta = client.post(
            "/api/sala/chiamate", json={"giocatore_id": 999_999, "anni": 1}
        )

        assert risposta.status_code == 422

    def test_senza_sala_la_chiamata_e_un_404(self, client):
        entra(client)
        assert (
            client.post("/api/sala/chiamate", json={"giocatore_id": 1, "anni": 1})
        ).status_code == 404

    def test_zero_anni_lo_blocca_pydantic(self, client):
        apri_sala(client)
        risposta = client.post("/api/sala/chiamate", json={"giocatore_id": 1, "anni": 0})

        assert risposta.status_code == 422

    def test_sei_anni_li_blocca_il_regolamento(self, client):
        """Il massimo sta in `ParametriLega`, non in un `Field(le=5)`."""
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()
        entra(client, utente_della_squadra(pagina["turno"]["squadra_id"]))

        esito = client.post(
            "/api/sala/chiamate",
            json={"giocatore_id": pagina["disponibili"][0]["id"], "anni": 6},
        ).json()

        assert esito["fatta"] is False
        durata = next(v for v in esito["violazioni"] if v["codice"] == "durata_contratto")
        assert "da 1 a 5" in durata["messaggio"]


class TestDuePersoneCheChiamanoInsieme:
    """Il caso che un draft dal vivo produce davvero: due che premono insieme.

    Chi chiama non sceglie il numero della chiamata — lo conta il registro — e
    il database rifiuta il numero gia' preso. Qui si prova la traduzione:
    quell'errore deve diventare un 409 con scritto cosa fare, non un 500, e
    soprattutto non deve sovrascrivere la chiamata di chi era arrivato primo.

    Si riproduce facendo leggere alla seconda richiesta un registro vecchio,
    che e' esattamente cio' che vede chi ha aperto la pagina un attimo prima.
    """

    def apparecchia(self, client, monkeypatch):
        """Una chiamata fatta, e la richiesta dopo che legge il registro di prima."""
        from api.rotte import sala as rotta

        pagina = apri_sala(client)
        for squadra in range(1, 11):
            fai_spazio(client, squadra, quanti=2)
        pagina = client.get("/api/sala").json()
        chi_tocca = pagina["turno"]["squadra_id"]
        # Spazio per due chiamate, non per una: qui se ne tentano due di fila.
        fai_spazio(client, chi_tocca, quanti=4)
        pagina = client.get("/api/sala").json()
        primo, _ = chiama(client, pagina, indice=-1)

        # Il registro come lo aveva letto chi stava decidendo: vuoto.
        monkeypatch.setattr(rotta, "carica_chiamate", lambda *_: [])
        entra(client, utente_della_squadra(chi_tocca))
        return primo, client.get("/api/sala").json()

    def test_il_numero_gia_preso_torna_409(self, client, monkeypatch):
        primo, pagina = self.apparecchia(client, monkeypatch)
        altro = next(g for g in reversed(pagina["disponibili"]) if g["id"] != primo["id"])

        risposta = client.post(
            "/api/sala/chiamate", json={"giocatore_id": altro["id"], "anni": 1}
        )

        assert risposta.status_code == 409, risposta.json()
        assert "ricarica" in risposta.json()["detail"]

    def test_la_chiamata_di_chi_era_primo_resta(self, client, monkeypatch):
        """Il punto di tutto: la seconda scrittura non sovrascrive la prima."""
        from fantacalcio.data import archivio, carica_chiamate

        primo, pagina = self.apparecchia(client, monkeypatch)
        altro = next(g for g in reversed(pagina["disponibili"]) if g["id"] != primo["id"])
        client.post("/api/sala/chiamate", json={"giocatore_id": altro["id"], "anni": 1})

        registro = carica_chiamate(archivio(), 1)

        assert [s.giocatore_id for s in registro] == [primo["id"]]


class TestIlTurno:
    def test_sa_dire_se_tocca_a_me(self, client):
        """La pagina non deve far dedurre al browser di chi e' il turno."""
        pagina = apri_sala(client, round_totali=1)
        tocca_a = pagina["turno"]["squadra_id"]

        entra(client, utente_della_squadra(tocca_a))
        mio = client.get("/api/sala").json()["turno"]
        entra(client, utente_della_squadra(next(s for s in range(1, 11) if s != tocca_a)))
        altrui = client.get("/api/sala").json()["turno"]

        assert mio["e_mio"] is True
        assert altrui["e_mio"] is False

    def test_porta_round_e_posizione_in_chiaro(self, client):
        pagina = apri_sala(client)

        assert pagina["turno"]["round"] == 1
        assert pagina["turno"]["posizione"] == 1
        assert pagina["turno"]["etichetta"] == "Round 1 · chiamata 1"

    def test_senza_timer_non_scade(self, client):
        """Un turno che passa mentre uno sta decidendo e' peggio di un draft lento."""
        pagina = apri_sala(client)

        assert pagina["turno"]["scade_il"] is None

    def test_col_timer_la_scadenza_arriva_al_browser(self, client):
        pagina = apri_sala(client, secondi_per_chiamata=90)

        assert pagina["turno"]["scade_il"] is not None

    def test_a_sala_chiusa_non_c_e_turno(self, client):
        apri_sala(client)
        pagina = client.post("/api/sala/chiudi").json()

        assert pagina["stato"] == "chiusa"
        assert pagina["turno"] is None


class TestCorreggereGliAnni:
    """Solo i giocatori presi in **questa** sala, e solo fino alla giornata dopo.

    E' la regola che Marco ha dettato: «il contratto cambia soltanto per i
    nuovi acquisti post draft e prima della prima partita. Poi mai piu'».
    """

    def prendi_uno(self, client):
        pagina = apri_sala(client)
        squadra_id = pagina["turno"]["squadra_id"]
        fai_spazio(client, squadra_id)
        pagina = client.get("/api/sala").json()
        scelto, _ = chiama(client, pagina, anni=2)
        entra(client, "marco")
        client.post("/api/sala/chiudi")
        return squadra_id, scelto

    def test_a_sala_in_corso_non_si_correggono(self, client):
        """Prima si finisce di chiamare: a meta' draft la finestra non esiste."""
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()
        scelto, _ = chiama(client, pagina)

        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 3}
        )

        assert risposta.status_code == 422
        assert client.get("/api/sala").json()["anni_correggibili"] is False

    def test_appena_la_sala_chiude_si_correggono(self, client):
        squadra_id, scelto = self.prendi_uno(client)

        entra(client, utente_della_squadra(squadra_id))
        pagina = client.get("/api/sala").json()
        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 3}
        )

        assert pagina["anni_correggibili"] is True
        assert risposta.status_code == 200
        assert "3 anni" in risposta.json()["messaggio"]

    def test_la_correzione_cambia_registro_e_contratto_insieme(self, client):
        """Se divergessero, la rosa direbbe una cosa e la sala un'altra."""
        from fantacalcio.data import archivio, carica_rose

        squadra_id, scelto = self.prendi_uno(client)
        entra(client, utente_della_squadra(squadra_id))
        client.put("/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 5})

        acquisto = next(
            c
            for c in client.get("/api/sala").json()["miei_acquisti"]
            if c["giocatore_id"] == scelto["id"]
        )
        contratto = next(
            c
            for c in carica_rose(archivio())[squadra_id].contratti
            if c.giocatore_id == scelto["id"]
        )

        assert acquisto["anni"] == 5
        assert contratto.anni_residui == 5

    def test_gli_acquisti_altrui_non_si_toccano(self, client):
        squadra_id, scelto = self.prendi_uno(client)

        altro = next(s for s in range(1, 11) if s != squadra_id)
        entra(client, utente_della_squadra(altro))
        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 5}
        )

        assert risposta.status_code == 422
        assert "presi in questa sala" in risposta.json()["detail"]

    def test_un_giocatore_che_avevo_gia_non_si_tocca(self, client):
        """L'articolo 8 protegge esattamente questo: un contratto in corso."""
        from fantacalcio.data import archivio, carica_rose

        squadra_id, scelto = self.prendi_uno(client)
        entra(client, utente_della_squadra(squadra_id))
        gia_mio = next(
            c
            for c in carica_rose(archivio())[squadra_id].contratti
            if c.giocatore_id != scelto["id"]
        )

        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": gia_mio.giocatore_id, "anni": 5}
        )

        assert risposta.status_code == 422

    def test_sei_anni_non_passano_nemmeno_in_correzione(self, client):
        squadra_id, scelto = self.prendi_uno(client)
        entra(client, utente_della_squadra(squadra_id))

        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 6}
        )

        assert risposta.status_code == 422
        assert "da 1 a 5" in risposta.json()["detail"]

    def test_la_lega_puo_spegnere_la_finestra(self, client):
        """Finche' l'articolo 8 non e' votato, decide `OpzioniLega`."""
        from dataclasses import replace

        from fantacalcio.data import archivio, carica_leghe, salva_lega

        squadra_id, scelto = self.prendi_uno(client)
        arch = archivio()
        lega = next(iter(carica_leghe(arch).values()))
        salva_lega(
            arch,
            replace(lega, opzioni=replace(lega.opzioni, modifica_anni_dopo_draft=False)),
        )

        entra(client, utente_della_squadra(squadra_id))
        pagina = client.get("/api/sala").json()
        risposta = client.put(
            "/api/sala/anni", json={"giocatore_id": scelto["id"], "anni": 3}
        )

        assert pagina["anni_correggibili"] is False
        assert risposta.status_code == 422

    def test_la_pagina_dice_entro_quando(self, client):
        """Una scadenza che l'utente scopre solo dall'errore non e' una scadenza."""
        squadra_id, _ = self.prendi_uno(client)
        entra(client, utente_della_squadra(squadra_id))
        pagina = client.get("/api/sala").json()

        assert pagina["anni_correggibili"] is True
        assert pagina["anni_chiudono_il"] or pagina["anni_motivo"]

    def test_miei_acquisti_sono_solo_i_miei(self, client):
        squadra_id, scelto = self.prendi_uno(client)

        entra(client, utente_della_squadra(squadra_id))
        miei = client.get("/api/sala").json()["miei_acquisti"]
        entra(
            client, utente_della_squadra(next(s for s in range(1, 11) if s != squadra_id))
        )
        altrui = client.get("/api/sala").json()["miei_acquisti"]

        assert [c["giocatore_id"] for c in miei] == [scelto["id"]]
        assert altrui == []


class TestDopoDiTe:
    """L'ordine e' congelato, quindi la pagina puo' dire chi chiama dopo."""

    def test_la_pagina_porta_i_prossimi_turni(self, client):
        pagina = apri_sala(client)

        assert len(pagina["prossimi"]) == 5
        assert pagina["prossimi"][0]["numero"] == 2
        assert pagina["prossimi"][0]["squadra"]

    def test_avanzano_quando_qualcuno_chiama(self, client):
        pagina = apri_sala(client)
        fai_spazio(client, pagina["turno"]["squadra_id"])
        pagina = client.get("/api/sala").json()
        dopo_di_me = pagina["prossimi"][0]["squadra_id"]
        chiama(client, pagina)

        dopo = client.get("/api/sala").json()

        assert dopo["turno"]["squadra_id"] == dopo_di_me
        assert dopo["prossimi"][0]["numero"] == 3

    def test_a_sala_chiusa_non_ce_ne_sono(self, client):
        apri_sala(client)
        pagina = client.post("/api/sala/chiudi").json()

        assert pagina["prossimi"] == []


class TestLOrdineIncompleto:
    def test_chi_non_e_stato_estratto_si_accoda(self, client):
        """Un ordine a meta' e' una trascrizione interrotta, non la volonta'
        di far saltare il turno a qualcuno: round piu' corti del numero di
        squadre vorrebbero dire squadre che non chiamano mai."""
        entra(client)
        pagina = client.post(
            "/api/sala",
            json={
                "tipo": "SETTEMBRE",
                "round_totali": 1,
                "ordine_lottery": [7, 3],
            },
        ).json()
        client.post("/api/sala/comincia")
        turno = client.get("/api/sala").json()["turno"]
        prossimi = client.get("/api/sala").json()["prossimi"]

        assert pagina["chiamate_totali"] == 10
        assert turno["squadra_id"] == 7
        assert prossimi[0]["squadra_id"] == 3

    def test_una_squadra_che_non_esiste_si_ignora(self, client):
        entra(client)
        pagina = client.post(
            "/api/sala",
            json={"tipo": "SETTEMBRE", "round_totali": 1, "ordine_lottery": [999]},
        ).json()

        assert pagina["chiamate_totali"] == 10
