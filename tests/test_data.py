"""Il backend di demo si costruisce e produce una lega conforme al regolamento."""

import pytest

from fantacalcio.conformita import Momento, verifica_rosa
from fantacalcio.data import (
    ArchivioSQLite,
    calendario_dettagliato,
    carica_credenziali,
    carica_inviti,
    carica_leghe,
    carica_rose,
    carica_squadre,
    salva_invito,
    salva_lega,
    salva_squadra,
)
from fantacalcio.demo_data import (
    DATA_DRAFT,
    GIORNATE_GIOCATE,
    SQUADRE,
    SQUADRE_CON_DEAD_MONEY,
)
from fantacalcio.identita import IdentitaSquadra
from fantacalcio.leghe import (
    Modalita,
    OpzioniLega,
    crea_invito,
    crea_lega,
    trova_per_codice,
)
from fantacalcio.modelli import Squadra
from fantacalcio.regole import ParametriLega


@pytest.fixture(scope="module")
def archivio(tmp_path_factory):
    return ArchivioSQLite(tmp_path_factory.mktemp("db") / "nuovo.db")


@pytest.fixture(scope="module")
def rose(archivio):
    return carica_rose(archivio)


def test_dieci_squadre(archivio):
    squadre = archivio.squadre()
    assert len(squadre) == len(SQUADRE) == 10
    assert squadre["nome"].is_unique


def test_ogni_squadra_ha_una_rosa_conforme(rose):
    """La demo deve essere un banco di prova valido, non una lega irregolare."""
    for rosa in rose.values():
        stato = verifica_rosa(rosa, DATA_DRAFT, momento=Momento.ASTA_SETTEMBRE)
        assert stato.conforme, f"{rosa.squadra.nome}: {stato.violazioni}"


def test_nessun_giocatore_in_due_rose(archivio):
    assert archivio.contratti()["giocatore_id"].is_unique


def test_i_contratti_stanno_nel_monte_anni(rose):
    parametri = ParametriLega()
    for rosa in rose.values():
        assert rosa.anni_impegnati <= parametri.monte_anni
        assert all(
            1 <= c.anni_residui <= parametri.contratto_anni_massimo
            for c in rosa.contratti
        )


def test_gli_ingaggi_stanno_nella_forbice(rose):
    parametri = ParametriLega()
    for rosa in rose.values():
        assert parametri.salary_floor <= rosa.monte_ingaggi <= parametri.salary_cap


def test_almeno_una_rosa_e_ampliata_dagli_under21(rose):
    parametri = ParametriLega()
    ampliate = [
        rosa for rosa in rose.values() if rosa.dimensione > parametri.rosa_massimo_base
    ]
    assert ampliate, "la demo deve mostrare l'espansione Under 21"
    for rosa in ampliate:
        slot = rosa.slot_u21(DATA_DRAFT, parametri)
        assert rosa.dimensione <= parametri.rosa_massimo(slot)


def test_il_dead_money_e_presente_dove_previsto(rose):
    con_dead_money = {id_ for id_, rosa in rose.items() if rosa.dead_money_totale > 0}
    assert con_dead_money == set(SQUADRE_CON_DEAD_MONEY)


def test_calendario_andata_e_ritorno(archivio):
    partite = calendario_dettagliato(archivio)
    assert partite["giornata"].max() == 18  # (10 - 1) * 2
    assert len(partite) == 90

    giocate = partite[partite["giornata"] <= GIORNATE_GIOCATE]
    assert giocate["gol_casa"].notna().all()
    assert giocate["punti_casa"].gt(0).all()

    future = partite[partite["giornata"] > GIORNATE_GIOCATE]
    assert future["gol_casa"].isna().all()


def test_db_non_viene_rigenerato_se_esiste(tmp_path):
    percorso = tmp_path / "lega.db"
    ArchivioSQLite(percorso)
    modificato = percorso.stat().st_mtime_ns
    ArchivioSQLite(percorso)
    assert percorso.stat().st_mtime_ns == modificato


def test_tabella_sconosciuta(archivio):
    with pytest.raises(ValueError, match="non prevista"):
        archivio.tabella("segreti_del_presidente")


def test_i_giocatori_hanno_ruoli_mantra(archivio):
    from fantacalcio.regole import RUOLI_MANTRA

    for ruoli in archivio.giocatori()["ruoli"]:
        assert all(r in RUOLI_MANTRA for r in ruoli.split(";"))


class TestLegheEInviti:
    """La lega deve sopravvivere al giro completo attraverso il database."""

    def test_salva_e_rilegge_una_lega(self, archivio):
        lega = crea_lega(
            id_=90,
            nome="Lega di Prova",
            admin_id=1,
            opzioni=OpzioniLega(modalita=Modalita.CLASSIC, moduli_ammessi=("4-4-2",)),
        )
        salva_lega(archivio, lega)
        riletta = carica_leghe(archivio)[90]
        assert riletta.nome == "Lega di Prova"
        assert riletta.codice_invito == lega.codice_invito
        assert riletta.opzioni.modalita is Modalita.CLASSIC
        assert riletta.opzioni.moduli_ammessi == ("4-4-2",)

    def test_la_lega_di_demo_esiste_gia(self, archivio):
        """Senza, gli utenti di demo resterebbero fermi sull'onboarding."""
        leghe = carica_leghe(archivio)
        assert leghe, "la demo deve contenere una lega"
        assert all(u.utente.lega_id for u in carica_credenziali(archivio).values())

    def test_si_ritrova_dal_codice(self, archivio):
        lega = crea_lega(91, "Cercami", 1, codice="abcd2345")
        salva_lega(archivio, lega)
        trovata = trova_per_codice(carica_leghe(archivio), "  AbCd 2345 ")
        assert trovata is not None and trovata.id == 91

    def test_riscrivere_la_stessa_lega_non_la_duplica(self, archivio):
        lega = crea_lega(92, "Una sola", 1)
        salva_lega(archivio, lega)
        salva_lega(archivio, lega.con_opzioni(OpzioniLega(partecipanti=12)))
        leghe = carica_leghe(archivio)
        assert len([id_ for id_ in leghe if id_ == 92]) == 1
        assert leghe[92].opzioni.partecipanti == 12

    def test_salva_e_rilegge_un_invito(self, archivio):
        lega = crea_lega(93, "Con inviti", 1)
        salva_lega(archivio, lega)
        salva_invito(archivio, crea_invito(50, lega, "Luca@Esempio.IT", creato_da=1))
        inviti = carica_inviti(archivio, 93)
        assert len(inviti) == 1
        assert inviti[0].email == "luca@esempio.it"
        assert inviti[0].codice == lega.codice_invito
        assert inviti[0].in_attesa

    def test_gli_inviti_si_filtrano_per_lega(self, archivio):
        prima = crea_lega(94, "Prima", 1)
        seconda = crea_lega(95, "Seconda", 1)
        salva_lega(archivio, prima)
        salva_lega(archivio, seconda)
        salva_invito(archivio, crea_invito(60, prima, "a@esempio.it"))
        salva_invito(archivio, crea_invito(61, seconda, "b@esempio.it"))
        assert [i.email for i in carica_inviti(archivio, 94)] == ["a@esempio.it"]

    def test_una_riga_malformata_non_impedisce_di_leggere_le_altre(self, archivio):
        """Una lega scritta male non deve chiudere fuori chi gioca nelle altre."""
        buona = crea_lega(96, "Buona", 1)
        salva_lega(archivio, buona)
        archivio.scrivi(
            "leghe",
            [{"id": 97, "nome": "x", "codice_invito": "TROPPOCORTO", "admin_id": 1}],
            chiave="id",
        )
        leghe = carica_leghe(archivio)
        assert 96 in leghe
        assert 97 not in leghe


class TestIdentitaEstesa:
    def test_citta_e_curva_sopravvivono_al_salvataggio(self, archivio):
        squadra = Squadra(
            id=80,
            nome="Nuovi Colori",
            presidente="Luca",
            identita=IdentitaSquadra(
                presidente="Luca",
                citta="Ginevra",
                curva="Curva Nord",
                stadio="Arena",
                colore_primario="#123456",
                colore_secondario="#fedcba",
            ),
            lega_id=1,
        )
        salva_squadra(archivio, squadra)
        riletta = carica_squadre(archivio)[80]
        assert riletta.citta == "Ginevra"
        assert riletta.curva == "Curva Nord"
        assert riletta.lega_id == 1


def test_un_database_di_demo_vecchio_si_ricostruisce(tmp_path):
    """Un file creato prima delle leghe non deve far fallire l'app all'avvio."""
    import sqlite3

    from fantacalcio.demo_data import costruisci_db

    percorso = tmp_path / "vecchio.db"
    with sqlite3.connect(percorso) as conn:
        conn.execute("create table squadre (id integer primary key, nome text)")

    costruisci_db(percorso)

    with sqlite3.connect(percorso) as conn:
        tabelle = {
            r[0]
            for r in conn.execute("select name from sqlite_master where type='table'")
        }
        colonne = {r[1] for r in conn.execute("pragma table_info(squadre)")}
    assert "leghe" in tabelle and "inviti" in tabelle
    assert {"citta", "curva", "lega_id"} <= colonne


def test_un_database_gia_aggiornato_non_si_rigenera(tmp_path):
    """Rigenerare a ogni avvio cancellerebbe i dati di chi prova in locale."""
    from fantacalcio.demo_data import costruisci_db

    percorso = costruisci_db(tmp_path / "buono.db")
    impronta = percorso.stat().st_mtime_ns
    costruisci_db(percorso)
    assert percorso.stat().st_mtime_ns == impronta


class TestBachecaPersistita:
    def test_salva_e_rilegge_un_annuncio(self, archivio):
        from types import SimpleNamespace

        from fantacalcio.bacheca import TipoAnnuncio, crea_annuncio
        from fantacalcio.data import carica_annunci, salva_annuncio

        lega = SimpleNamespace(id=1, admin_id=1)
        admin = SimpleNamespace(
            id=1,
            nome="Marco",
            nome_completo="Marco Tirinato",
            attivo=True,
            e_presidente=True,
        )
        nuovo = crea_annuncio(
            id_=500,
            lega=lega,
            utente=admin,
            titolo="Recap 3a giornata",
            testo="**Sorpresa** a Cuneo.",
            tipo=TipoAnnuncio.RECAP,
            giornata=3,
            in_evidenza=True,
        )
        salva_annuncio(archivio, nuovo)

        riletto = next(a for a in carica_annunci(archivio, 1) if a.id == 500)
        assert riletto.titolo == "Recap 3a giornata"
        assert riletto.testo == "**Sorpresa** a Cuneo."
        assert riletto.tipo is TipoAnnuncio.RECAP
        assert riletto.giornata == 3
        assert riletto.in_evidenza
        assert riletto.pubblicato
        assert riletto.autore_nome == "Marco Tirinato"

    def test_una_bozza_resta_bozza_dopo_il_giro(self, archivio):
        from types import SimpleNamespace

        from fantacalcio.bacheca import crea_annuncio
        from fantacalcio.data import carica_annunci, salva_annuncio

        lega = SimpleNamespace(id=1, admin_id=1)
        admin = SimpleNamespace(
            id=1,
            nome="Marco",
            nome_completo="Marco Tirinato",
            attivo=True,
            e_presidente=True,
        )
        salva_annuncio(
            archivio,
            crea_annuncio(501, lega, admin, "Bozza", "Non pronta", pubblicato=False),
        )
        riletto = next(a for a in carica_annunci(archivio, 1) if a.id == 501)
        assert riletto.e_bozza

    def test_eliminare_un_annuncio(self, archivio):
        from types import SimpleNamespace

        from fantacalcio.bacheca import crea_annuncio
        from fantacalcio.data import carica_annunci, elimina_annuncio, salva_annuncio

        lega = SimpleNamespace(id=1, admin_id=1)
        admin = SimpleNamespace(
            id=1,
            nome="Marco",
            nome_completo="Marco Tirinato",
            attivo=True,
            e_presidente=True,
        )
        salva_annuncio(archivio, crea_annuncio(502, lega, admin, "Da togliere", "x"))
        elimina_annuncio(archivio, 502)
        assert not [a for a in carica_annunci(archivio, 1) if a.id == 502]

    def test_una_riga_malformata_non_impedisce_di_leggere_le_altre(self, archivio):
        from fantacalcio.data import carica_annunci

        archivio.scrivi(
            "annunci",
            [{"id": 503, "lega_id": 1, "titolo": "x", "testo": ""}],
            chiave="id",
        )
        # titolo troppo corto e testo vuoto: la riga si salta, le altre no.
        assert not [a for a in carica_annunci(archivio, 1) if a.id == 503]
        assert carica_annunci(archivio, 1)


class TestAlboPersistito:
    def test_salva_e_rilegge_un_titolo(self, archivio):
        from fantacalcio.competizioni import TipoCompetizione, crea_titolo
        from fantacalcio.data import carica_albo, salva_titolo

        salva_titolo(
            archivio,
            crea_titolo(600, 1, TipoCompetizione.CAMPIONATO, "2026/27", "Tiri Team", 1),
        )
        riletto = next(t for t in carica_albo(archivio, 1) if t.id == 600)
        assert riletto.competizione is TipoCompetizione.CAMPIONATO
        assert riletto.squadra_nome == "Tiri Team"
        assert riletto.stagione == "2026/27"

    def test_eliminare_un_titolo(self, archivio):
        from fantacalcio.competizioni import TipoCompetizione, crea_titolo
        from fantacalcio.data import carica_albo, elimina_titolo, salva_titolo

        salva_titolo(
            archivio,
            crea_titolo(601, 1, TipoCompetizione.COPPA_ITALIA, "2026/27", "Padel"),
        )
        elimina_titolo(archivio, 601)
        assert not [t for t in carica_albo(archivio, 1) if t.id == 601]

    def test_una_competizione_sconosciuta_si_salta(self, archivio):
        """Una riga scritta da una versione futura non deve rompere l'albo."""
        from fantacalcio.data import carica_albo

        archivio.scrivi(
            "albo",
            [
                {
                    "id": 602,
                    "lega_id": 1,
                    "competizione": "MONDIALE_PER_CLUB",
                    "stagione": "2026/27",
                    "squadra_nome": "Tiri Team",
                }
            ],
            chiave="id",
        )
        assert not [t for t in carica_albo(archivio, 1) if t.id == 602]


def test_il_ruolo_editor_scrive_in_bacheca_ma_non_importa():
    """Il presidente delega la bacheca senza cedere il resto dei suoi poteri."""
    from types import SimpleNamespace

    from fantacalcio.autenticazione import Ruolo, Utente
    from fantacalcio.bacheca import puo_pubblicare

    editor = Utente(id=5, nome_utente="ed", nome="Ed", ruolo=Ruolo.EDITOR, lega_id=1)
    lega = SimpleNamespace(id=1, admin_id=1)
    assert puo_pubblicare(editor, lega)
    assert editor.puo_scrivere_in_bacheca
    assert not editor.puo_importare

    normale = Utente(id=6, nome_utente="lu", nome="Lu", ruolo=Ruolo.FANTALLENATORE)
    assert not puo_pubblicare(normale, lega)


class TestCancellazioni:
    """Togliere giocatori dal listone, e i contratti che li nominano."""

    def archivio(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite

        arch = ArchivioSQLite(tmp_path / "cancella.db")
        arch.svuota("contratti")
        arch.svuota("giocatori")
        arch.scrivi(
            "giocatori",
            [
                {
                    "id": i,
                    "id_ufficiale": 1000 + i,
                    "nome": f"Tale {i}",
                    "club": "Roma",
                    "ruoli": "A",
                    "ruolo_classic": "A",
                    "ingaggio": 1_000_000,
                    "nazionalita": "Italia",
                    "data_nascita": None,
                    "quotazione": 10,
                    "fvm": 20,
                }
                for i in (1, 2, 3)
            ],
            chiave="id",
        )
        arch.scrivi(
            "contratti",
            [
                {
                    "giocatore_id": 1,
                    "squadra_id": 7,
                    "anni_residui": 2,
                    "prolungato": False,
                    "stagione_prolungamento": None,
                }
            ],
            chiave="giocatore_id",
        )
        return arch

    def test_elimina_giocatori_porta_via_anche_i_contratti(self, tmp_path):
        from fantacalcio.data import elimina_giocatori

        arch = self.archivio(tmp_path)
        assert elimina_giocatori(arch, [1]) == 1
        assert sorted(arch.giocatori()["id"]) == [2, 3]
        # Il contratto non resta appeso a un giocatore che non c'e' piu'.
        assert arch.contratti().empty

    def test_eliminare_niente_non_fa_niente(self, tmp_path):
        from fantacalcio.data import elimina_giocatori

        arch = self.archivio(tmp_path)
        assert elimina_giocatori(arch, []) == 0
        assert len(arch.giocatori()) == 3

    def test_svuota_listone_dice_quanto_ha_cancellato(self, tmp_path):
        from fantacalcio.data import svuota_listone

        arch = self.archivio(tmp_path)
        assert svuota_listone(arch) == {"giocatori": 3, "contratti": 1}
        assert arch.giocatori().empty
        assert arch.contratti().empty

    def test_su_supabase_i_contratti_si_svuotano_sulla_loro_chiave(self):
        # `contratti` non ha la colonna `id`: filtrare su quella fallirebbe.
        from fantacalcio.data import ArchivioSupabase

        chiamate = []

        class FintaTabella:
            def __init__(self, nome):
                self.nome = nome

            def delete(self):
                return self

            def neq(self, colonna, valore):
                chiamate.append((self.nome, colonna))
                return self

            def execute(self):
                return None

        class FintoClient:
            def table(self, nome):
                return FintaTabella(nome)

        arch = ArchivioSupabase.__new__(ArchivioSupabase)
        arch._client = FintoClient()
        arch.svuota("contratti")
        arch.svuota("giocatori")
        assert chiamate == [("contratti", "giocatore_id"), ("giocatori", "id")]


class TestRecuperoPassword:
    """Andata e ritorno su database: il codice di recupero e le richieste.

    Sono test noiosi e servono proprio per quello. La prima versione di
    `carica_richieste_password` importava la sua dataclass solo per i type
    checker: i test del dominio passavano tutti, e il presidente non vedeva
    nessuna richiesta perche' la lettura falliva a runtime.
    """

    def test_il_codice_di_recupero_sopravvive_al_salvataggio(self, archivio):
        from fantacalcio.autenticazione import con_codice_recupero, registra
        from fantacalcio.data import salva_credenziali

        credenziali = registra(
            {}, 900, "tizio", "Tizio", "password1", email="tizio@esempio.it"
        )
        con_codice, codice = con_codice_recupero(credenziali)
        salva_credenziali(archivio, con_codice)

        rilette = carica_credenziali(archivio)["tizio"]
        assert rilette.ha_codice_recupero
        assert rilette.codice_corrisponde(codice)
        assert rilette.corrisponde("password1")

    def test_chi_non_ha_il_codice_si_rilegge_senza(self, archivio):
        from fantacalcio.autenticazione import registra
        from fantacalcio.data import salva_credenziali

        salva_credenziali(
            archivio,
            registra({}, 901, "caio", "Caio", "password1", email="caio@esempio.it"),
        )
        assert not carica_credenziali(archivio)["caio"].ha_codice_recupero

    def test_una_richiesta_si_salva_e_si_rilegge(self, archivio):
        from fantacalcio.autenticazione import RichiestaPassword, StatoRichiesta
        from fantacalcio.data import (
            carica_richieste_password,
            salva_richiesta_password,
        )

        salva_richiesta_password(
            archivio,
            RichiestaPassword(
                id=1,
                lega_id=1,
                utente_id=7,
                nome_utente="sempronio",
                chiesta_il="2026-09-19T10:00:00",
            ),
        )
        riletta = carica_richieste_password(archivio, 1)
        assert [r.nome_utente for r in riletta] == ["sempronio"]
        assert riletta[0].aperta
        assert riletta[0].stato is StatoRichiesta.APERTA

    def test_chiuderla_si_vede_alla_rilettura(self, archivio):
        from fantacalcio.autenticazione import (
            RichiestaPassword,
            Ruolo,
            StatoRichiesta,
            Utente,
            chiudi_richiesta,
        )
        from fantacalcio.data import (
            carica_richieste_password,
            salva_richiesta_password,
        )

        richiesta = RichiestaPassword(id=2, lega_id=1, utente_id=7, nome_utente="tizio")
        salva_richiesta_password(archivio, richiesta)
        presidente = Utente(
            id=1, nome_utente="marco", nome="Marco", ruolo=Ruolo.PRESIDENTE
        )
        salva_richiesta_password(
            archivio,
            chiudi_richiesta(richiesta, presidente, StatoRichiesta.EVASA, "2026-09-19"),
        )

        riletta = [r for r in carica_richieste_password(archivio, 1) if r.id == 2]
        assert len(riletta) == 1, "chiudere una richiesta non deve duplicarla"
        assert not riletta[0].aperta
        assert riletta[0].chiusa_da == 1

    def test_le_richieste_di_un_altra_lega_non_si_vedono(self, archivio):
        from fantacalcio.autenticazione import RichiestaPassword
        from fantacalcio.data import (
            carica_richieste_password,
            salva_richiesta_password,
        )

        salva_richiesta_password(
            archivio, RichiestaPassword(id=3, lega_id=99, utente_id=8, nome_utente="x")
        )
        assert all(r.lega_id != 99 for r in carica_richieste_password(archivio, 1))


class TestTabellaCheNonEsiste:
    """Una migrazione non lanciata non deve uccidere la pagina.

    E' successo davvero: su Supabase mancava la tabella `formazioni` e la
    pagina Formazione moriva con un errore che Streamlit oscura («original
    error message is redacted»). Da fuori sembrava un guasto del sito, mentre
    bastava eseguire un file SQL — e la pagina che elenca i problemi dello
    schema non guardava nemmeno quella tabella.
    """

    def archivio_che_non_ha(self, mancanti, codice="PGRST205"):
        """Un finto Supabase a cui certe tabelle non esistono."""
        from fantacalcio.data import ArchivioSupabase

        class ErroreFinto(Exception):
            def __init__(self, nome):
                super().__init__(
                    f"Could not find the table 'public.{nome}' in the schema cache"
                )
                self.code = codice
                self.message = f"Could not find the table 'public.{nome}'"

        class FintaTabella:
            def __init__(self, nome):
                self.nome = nome

            def select(self, *_):
                return self

            def execute(self):
                if self.nome in mancanti:
                    raise ErroreFinto(self.nome)
                return type("Risposta", (), {"data": []})()

        class FintoClient:
            def table(self, nome):
                return FintaTabella(nome)

        arch = ArchivioSupabase.__new__(ArchivioSupabase)
        arch._client = FintoClient()
        return arch

    def test_si_legge_come_vuota_invece_di_esplodere(self):
        from fantacalcio.data import COLONNE_ATTESE

        arch = self.archivio_che_non_ha({"formazioni"})
        righe = arch.tabella("formazioni")
        assert righe.empty
        # Vuota ma con le sue colonne, come per ogni tabella senza righe.
        assert list(righe.columns) == list(COLONNE_ATTESE["formazioni"])

    def test_anche_col_codice_di_postgres(self):
        arch = self.archivio_che_non_ha({"voti"}, codice="42P01")
        assert arch.tabella("voti").empty

    def test_si_ricorda_quale_mancava(self):
        arch = self.archivio_che_non_ha({"formazioni", "voti"})
        arch.tabella("formazioni")
        arch.tabella("voti")
        arch.tabella("squadre")
        assert {"formazioni", "voti"} <= arch.assenti
        assert "squadre" not in arch.assenti

    def test_quando_la_tabella_arriva_smette_di_dirlo(self):
        senza = self.archivio_che_non_ha({"formazioni"})
        senza.tabella("formazioni")
        assert "formazioni" in senza.assenti
        # Migrazione lanciata: la lettura riesce e l'allarme si spegne.
        senza.tabella("squadre")
        con = self.archivio_che_non_ha(set())
        con.tabella("formazioni")
        assert "formazioni" not in con.assenti

    def test_due_archivi_non_si_scambiano_le_assenze(self):
        # L'elenco descrive un database, non il programma: tenerlo globale
        # faceva credere a un archivio sano di avere i guasti di un altro.
        malato = self.archivio_che_non_ha({"formazioni"})
        malato.tabella("formazioni")
        sano = self.archivio_che_non_ha(set())
        sano.tabella("formazioni")
        assert malato.assenti == {"formazioni"}
        assert sano.assenti == set()

    def test_un_errore_diverso_deve_farsi_sentire(self):
        """Chiave sbagliata, rete, permessi: la cura e' un'altra, e si deve vedere."""
        from fantacalcio.data import ArchivioSupabase

        class Ostile:
            def table(self, nome):
                raise RuntimeError("Invalid API key")

        arch = ArchivioSupabase.__new__(ArchivioSupabase)
        arch._client = Ostile()
        with pytest.raises(RuntimeError, match="Invalid API key"):
            arch.tabella("formazioni")

    def test_anche_sqlite_lo_dice_a_modo_suo(self, tmp_path):
        """SQLite scrive «no such table», PostgREST scrive altro: valgono entrambi."""
        import sqlite3

        from fantacalcio.data import ArchivioSQLite

        percorso = tmp_path / "vecchio.db"
        arch = ArchivioSQLite(percorso)
        with sqlite3.connect(percorso) as conn:
            conn.execute("drop table if exists formazioni")
        assert arch.tabella("formazioni").empty
        assert "formazioni" in arch.assenti

    def test_le_formazioni_si_caricano_vuote(self):
        """Il pezzo che si rompeva: `carica_formazioni` su una tabella assente."""
        from fantacalcio.data import carica_formazioni

        arch = self.archivio_che_non_ha({"formazioni"})
        assert carica_formazioni(arch, giornata=1) == {}
