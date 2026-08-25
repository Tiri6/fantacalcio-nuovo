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
        admin = SimpleNamespace(id=1, nome="Marco", attivo=True, e_presidente=True)
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
        assert riletto.autore_nome == "Marco"

    def test_una_bozza_resta_bozza_dopo_il_giro(self, archivio):
        from types import SimpleNamespace

        from fantacalcio.bacheca import crea_annuncio
        from fantacalcio.data import carica_annunci, salva_annuncio

        lega = SimpleNamespace(id=1, admin_id=1)
        admin = SimpleNamespace(id=1, nome="Marco", attivo=True, e_presidente=True)
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
        admin = SimpleNamespace(id=1, nome="Marco", attivo=True, e_presidente=True)
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
