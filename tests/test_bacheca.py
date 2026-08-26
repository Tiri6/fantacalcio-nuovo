"""Bacheca: validazione, permessi, ordinamento e visibilita' delle bozze."""

from types import SimpleNamespace

import pytest

from fantacalcio.bacheca import (
    TESTO_MASSIMO,
    TITOLO_MASSIMO,
    Annuncio,
    AnnuncioNonValido,
    NonAutorizzato,
    TipoAnnuncio,
    crea_annuncio,
    filtra_per_tipo,
    formatta_data,
    modifica,
    ordina,
    pubblica,
    puo_pubblicare,
    ritira,
    visibili_per,
)

LEGA = SimpleNamespace(id=1, admin_id=10, nome="Lega di Prova")
ALTRA_LEGA = SimpleNamespace(id=2, admin_id=99, nome="Altra")


def finto_utente(id_, nome, cognome, presidente=False, attivo=True):
    """Un doppio con la stessa superficie di `Utente`, `nome_completo` compreso."""
    return SimpleNamespace(
        id=id_,
        nome=nome,
        cognome=cognome,
        nome_completo=f"{nome} {cognome}".strip(),
        attivo=attivo,
        e_presidente=presidente,
    )


ADMIN = finto_utente(10, "Marco", "Tirinato")
PRESIDENTE = finto_utente(11, "Sara", "Bianchi", presidente=True)
GIOCATORE = finto_utente(12, "Luca", "Verdi")
SOSPESO = finto_utente(13, "Ex", "Socio", presidente=True, attivo=False)


def annuncio(id_=1, **campi) -> Annuncio:
    predefiniti = {
        "lega_id": 1,
        "titolo": "Titolo",
        "testo": "Testo dell'annuncio",
        "autore_id": 10,
        "autore_nome": "Marco",
        "creato_il": "2026-08-20T10:00:00+00:00",
        "aggiornato_il": "2026-08-20T10:00:00+00:00",
    }
    return Annuncio(id=id_, **{**predefiniti, **campi})


class TestPermessi:
    def test_l_admin_della_lega_pubblica(self):
        assert puo_pubblicare(ADMIN, LEGA)

    def test_il_presidente_pubblica(self):
        assert puo_pubblicare(PRESIDENTE, LEGA)

    def test_un_fantallenatore_qualsiasi_no(self):
        assert not puo_pubblicare(GIOCATORE, LEGA)

    def test_un_utente_disattivato_no(self):
        """Anche se e' presidente: `attivo` viene prima del ruolo."""
        assert not puo_pubblicare(SOSPESO, LEGA)

    def test_nessun_utente_no(self):
        assert not puo_pubblicare(None, LEGA)

    def test_l_admin_di_un_altra_lega_no(self):
        assert not puo_pubblicare(ADMIN, ALTRA_LEGA)

    def test_il_permesso_e_nel_dominio_non_nella_pagina(self):
        """Nascondere un bottone non e' un controllo: crea_annuncio rifiuta."""
        with pytest.raises(NonAutorizzato):
            crea_annuncio(1, LEGA, GIOCATORE, "Titolo", "Testo")

    def test_anche_modificare_richiede_il_permesso(self):
        esistente = annuncio()
        with pytest.raises(NonAutorizzato):
            modifica(esistente, GIOCATORE, LEGA, titolo="Dirottato")


class TestValidazione:
    @pytest.mark.parametrize("titolo", ["", "  ", "ab", None])
    def test_titolo_troppo_corto(self, titolo):
        with pytest.raises(AnnuncioNonValido, match="titolo"):
            annuncio(titolo=titolo)

    def test_titolo_troppo_lungo(self):
        with pytest.raises(AnnuncioNonValido, match="titolo"):
            annuncio(titolo="x" * (TITOLO_MASSIMO + 1))

    @pytest.mark.parametrize("testo", ["", "   ", "\n\n", None])
    def test_testo_vuoto(self, testo):
        with pytest.raises(AnnuncioNonValido, match="testo"):
            annuncio(testo=testo)

    def test_testo_troppo_lungo(self):
        with pytest.raises(AnnuncioNonValido, match="testo"):
            annuncio(testo="x" * (TESTO_MASSIMO + 1))

    def test_gli_spazi_ai_bordi_si_perdono(self):
        assert annuncio(titolo="  Titolo  ", testo="  Testo  ").titolo == "Titolo"

    def test_campo_non_modificabile_rifiutato(self):
        with pytest.raises(AnnuncioNonValido, match="autore_id"):
            modifica(annuncio(), ADMIN, LEGA, autore_id=999)


class TestCiclo:
    def test_creazione_registra_autore_e_data(self):
        nuovo = crea_annuncio(5, LEGA, ADMIN, "Recap", "La giornata", TipoAnnuncio.RECAP)
        assert nuovo.autore_id == 10
        assert nuovo.autore_nome == "Marco Tirinato"
        assert nuovo.tipo is TipoAnnuncio.RECAP
        assert nuovo.creato_il and nuovo.aggiornato_il
        assert nuovo.pubblicato

    def test_bozza_e_pubblicazione(self):
        bozza = crea_annuncio(5, LEGA, ADMIN, "Titolo", "Testo", pubblicato=False)
        assert bozza.e_bozza
        assert pubblica(bozza, ADMIN, LEGA).pubblicato
        assert ritira(annuncio(), ADMIN, LEGA).e_bozza

    def test_modificare_non_muta_l_originale(self):
        originale = annuncio()
        modifica(originale, ADMIN, LEGA, titolo="Nuovo")
        assert originale.titolo == "Titolo"

    def test_modificare_aggiorna_la_data(self):
        originale = annuncio()
        assert modifica(originale, ADMIN, LEGA, titolo="Nuovo").aggiornato_il != (
            originale.aggiornato_il
        )


class TestOrdinamento:
    def test_in_evidenza_prima_poi_i_piu_recenti(self):
        vecchio = annuncio(1, titolo="Vecchio", aggiornato_il="2026-08-01T10:00:00+00:00")
        nuovo = annuncio(2, titolo="Nuovo", aggiornato_il="2026-08-20T10:00:00+00:00")
        fissato = annuncio(
            3,
            titolo="Fissato",
            in_evidenza=True,
            aggiornato_il="2026-07-01T10:00:00+00:00",
        )
        assert [a.titolo for a in ordina([vecchio, nuovo, fissato])] == [
            "Fissato",
            "Nuovo",
            "Vecchio",
        ]

    def test_una_data_illeggibile_non_fa_esplodere_l_ordinamento(self):
        rotto = annuncio(1, titolo="Rotto", aggiornato_il="non una data")
        buono = annuncio(2, titolo="Buono")
        assert len(ordina([rotto, buono])) == 2

    def test_ordinamento_stabile_a_parita_di_data(self):
        a = annuncio(1, titolo="Primo")
        b = annuncio(2, titolo="Secondo")
        assert [x.titolo for x in ordina([a, b])] == ["Secondo", "Primo"]


class TestVisibilita:
    def test_chi_legge_non_vede_le_bozze(self):
        elenco = [
            annuncio(1, titolo="Pubblico"),
            annuncio(2, titolo="Bozza", pubblicato=False),
        ]
        visti = visibili_per(elenco, GIOCATORE, LEGA)
        assert [a.titolo for a in visti] == ["Pubblico"]

    def test_chi_amministra_vede_anche_le_bozze(self):
        elenco = [
            annuncio(1, titolo="Pubblico"),
            annuncio(2, titolo="Bozza", pubblicato=False),
        ]
        assert len(visibili_per(elenco, ADMIN, LEGA)) == 2

    def test_gli_annunci_di_un_altra_lega_non_si_vedono(self):
        elenco = [annuncio(1, lega_id=1), annuncio(2, lega_id=2)]
        assert len(visibili_per(elenco, ADMIN, LEGA)) == 1

    def test_filtro_per_tipo(self):
        elenco = [
            annuncio(1, tipo=TipoAnnuncio.RECAP),
            annuncio(2, tipo=TipoAnnuncio.MERCATO),
        ]
        assert len(filtra_per_tipo(elenco, TipoAnnuncio.RECAP)) == 1
        assert len(filtra_per_tipo(elenco, None)) == 2


class TestPresentazione:
    def test_data_in_italiano(self):
        assert formatta_data("2026-08-22T14:09:00+00:00") == "22 agosto 2026, 14:09"

    @pytest.mark.parametrize("grezza", ["", "non una data", "2026-13-45"])
    def test_data_illeggibile_torna_com_era(self, grezza):
        assert formatta_data(grezza) == grezza

    def test_anteprima_salta_le_intestazioni_markdown(self):
        testo = "# Titolo grosso\n\nLa prima riga vera."
        assert annuncio(testo=testo).anteprima == "Titolo grosso"

    def test_anteprima_troncata(self):
        assert annuncio(testo="x" * 300).anteprima.endswith("...")

    def test_ogni_tipo_ha_un_icona(self):
        assert all(t.icona for t in TipoAnnuncio)
