"""Le fonti pubbliche del listone, provate senza rete.

Qui non si verifica che Fantacalcio.it e Capology rispondano — quello lo dira'
il pulsante «Aggiorna» in produzione — ma che, **dato** quel che rispondono,
il consolidamento faccia la cosa giusta: abbini i nomi scritti in due modi
diversi, non inventi abbinamenti ambigui, e soprattutto non azzeri gli
ingaggi quando una delle due fonti manca.
"""

import io
import json
from datetime import date

import pytest
from openpyxl import Workbook

from fantacalcio.fonti_web import (
    EsitoAggiornamento,
    FonteNonRaggiungibile,
    RigaListone,
    Stipendio,
    a_csv,
    a_righe_archivio,
    abbina,
    aggiorna_da_web,
    annata,
    consolida,
    etichetta_stagione,
    leggi_importo,
    leggi_stipendi,
    normalizza_club,
    stagione,
    url_capology,
    url_quotazioni,
)

INTESTAZIONI_LISTONE = (
    "Id",
    "R",
    "RM",
    "Nome",
    "Squadra",
    "Qt.A",
    "Qt.I",
    "Diff.",
    "Qt.A M",
    "Qt.I M",
    "Diff.M",
    "FVM",
    "FVM M",
)


def listone_xlsx(righe: list[tuple]) -> bytes:
    """Un listone col formato vero: titolo in riga 1, intestazioni in riga 2."""
    cartella = Workbook()
    foglio = cartella.active
    foglio.title = "Tutti"
    foglio.append(("Quotazioni Fantacalcio Stagione 2026 27",))
    foglio.append(INTESTAZIONI_LISTONE)
    for riga in righe:
        foglio.append(riga)
    buffer = io.BytesIO()
    cartella.save(buffer)
    return buffer.getvalue()


LISTONE = [
    (2071, "A", "A;Pc", "Dybala", "Roma", 24, 24, 0, 26, 26, 0, 60, 70),
    (486, "A", "Pc", "Lautaro Martinez", "Inter", 34, 34, 0, 36, 36, 0, 120, 140),
    (555, "C", "M;C", "Barella", "Inter", 18, 18, 0, 19, 19, 0, 40, 45),
    (999, "P", "Por", "Svilar", "Roma", 18, 18, 0, 18, 18, 0, 30, 33),
]


class TestStagione:
    def test_da_luglio_comincia_la_stagione_nuova(self):
        assert stagione(date(2026, 8, 29)) == "2026_27"
        assert stagione(date(2026, 7, 1)) == "2026_27"

    def test_a_giugno_si_gioca_ancora_quella_di_prima(self):
        assert stagione(date(2026, 6, 30)) == "2025_26"
        assert stagione(date(2027, 1, 15)) == "2026_27"

    def test_le_due_scritture_della_stessa_stagione(self):
        assert annata("2026_27") == "2026-2027"
        assert etichetta_stagione("2026_27") == "2026/27"

    def test_indirizzi(self):
        assert url_quotazioni("2026_27").endswith(
            "Quotazioni_Fantacalcio_Stagione_2026_27.xlsx"
        )
        assert url_capology("2026_27").endswith("/serie-a/salaries/2026-2027/")


class TestNormalizzazioneClub:
    def test_le_sigle_non_contano(self):
        assert normalizza_club("Bologna FC 1909") == normalizza_club("Bologna")
        assert normalizza_club("ACF Fiorentina") == normalizza_club("Fiorentina")
        assert normalizza_club("US Lecce") == normalizza_club("Lecce")

    def test_i_nomi_davvero_diversi_stanno_in_tabella(self):
        assert normalizza_club("Internazionale") == normalizza_club("Inter")
        assert normalizza_club("Hellas Verona") == normalizza_club("Verona")

    def test_squadre_diverse_restano_diverse(self):
        assert normalizza_club("Milan") != normalizza_club("Inter")


class TestImporti:
    @pytest.mark.parametrize(
        ("scritto", "atteso"),
        [
            ("€ 4.500.000", 4_500_000),
            ("4,500,000", 4_500_000),
            ("1.2M", 1_200_000),
            ("850K", 850_000),
            (3_000_000, 3_000_000),
            ("4.5", 4.5),
        ],
    )
    def test_legge_i_modi_in_cui_si_scrive_un_milione(self, scritto, atteso):
        assert leggi_importo(scritto) == pytest.approx(atteso)

    def test_quel_che_non_e_un_numero_e_niente(self):
        assert leggi_importo("") is None
        assert leggi_importo(None) is None
        assert leggi_importo("n/d") is None


class TestLetturaStipendi:
    def pagina_json(self, righe: list[dict]) -> str:
        return (
            "<html><head><script>window.__DATA__ = "
            + json.dumps(righe)
            + ";</script></head><body></body></html>"
        )

    def test_legge_i_dati_incapsulati_nello_script(self):
        stipendi = leggi_stipendi(
            self.pagina_json(
                [
                    {
                        "player": "Paulo Dybala",
                        "team": "Roma",
                        "gross_annual": "€ 6.000.000",
                        "country": "Argentina",
                        "dob": "1993-11-15",
                        "age": 32,
                    },
                    {
                        "player": "Nicolò Barella",
                        "team": "Inter",
                        "gross_annual": 9_000_000,
                        "country": "Italia",
                        "dob": "1997-02-07",
                        "age": 29,
                    },
                ]
            )
        )
        assert [s.nome for s in stipendi] == ["Paulo Dybala", "Nicolò Barella"]
        assert stipendi[0].lordo_annuo == 6_000_000
        assert stipendi[0].nazionalita == "Argentina"
        assert stipendi[1].data_nascita == date(1997, 2, 7)

    def test_scarta_gli_array_che_non_sono_la_tabella(self):
        pagina = (
            '<script>var menu = [{"label":"Home","href":"/"}];</script>'
            + self.pagina_json([{"player": "Svilar", "gross_annual": 3_000_000}])
        )
        stipendi = leggi_stipendi(pagina)
        assert [s.nome for s in stipendi] == ["Svilar"]

    def test_ripiega_sulla_tabella_html(self):
        pagina = """
        <html><body>
          <table>
            <tr><th>Giocatore</th><th>Squadra</th><th>Lordo Annuale</th>
                <th>Nazionalita</th></tr>
            <tr><td>Paulo Dybala</td><td>Roma</td><td>€ 6.000.000</td>
                <td>Argentina</td></tr>
            <tr><td>Mile Svilar</td><td>Roma</td><td>€ 3.000.000</td>
                <td>Serbia</td></tr>
          </table>
        </body></html>
        """
        stipendi = leggi_stipendi(pagina)
        assert len(stipendi) == 2
        assert stipendi[0].lordo_annuo == 6_000_000
        assert stipendi[1].nazionalita == "Serbia"

    def test_un_formato_irriconoscibile_si_dichiara(self):
        # Silenzio e lista vuota direbbero «nessuno guadagna niente»: falso.
        with pytest.raises(FonteNonRaggiungibile, match="formato"):
            leggi_stipendi("<html><body><p>Manutenzione</p></body></html>")

    def test_accetta_i_byte(self):
        pagina = self.pagina_json([{"player": "Svilar", "salary": 3_000_000}])
        assert leggi_stipendi(pagina.encode("utf-8"))[0].nome == "Svilar"


class TestAbbinamento:
    def indici(self, *stipendi: Stipendio):
        from fantacalcio.fonti_web import _indicizza_stipendi

        return _indicizza_stipendi(stipendi)

    def test_nome_intero_contro_cognome(self):
        indici = self.indici(Stipendio("Nicolò Barella", "Inter", 9_000_000))
        trovato = abbina("Barella", "Inter", indici)
        assert trovato is not None and trovato.lordo_annuo == 9_000_000

    def test_gli_accenti_non_fermano_l_abbinamento(self):
        indici = self.indici(Stipendio("Nicolò Barella", "FC Internazionale", 9_000_000))
        assert abbina("Barella", "Inter", indici) is not None

    def test_due_omonimi_nella_stessa_squadra_non_si_abbinano(self):
        # Meglio un ingaggio mancante, che si vede, di uno sbagliato in rosa.
        indici = self.indici(
            Stipendio("Thiago Motta", "Genoa", 1_000_000),
            Stipendio("Juan Motta", "Genoa", 2_000_000),
        )
        assert abbina("Motta", "Genoa", indici) is None

    def test_omonimi_in_squadre_diverse_si_risolvono_col_club(self):
        indici = self.indici(
            Stipendio("Marco Rossi", "Torino", 1_000_000),
            Stipendio("Luca Rossi", "Lecce", 2_000_000),
        )
        trovato = abbina("Rossi", "Lecce", indici)
        assert trovato is not None and trovato.lordo_annuo == 2_000_000

    def test_chi_non_c_e_non_c_e(self):
        indici = self.indici(Stipendio("Paulo Dybala", "Roma", 6_000_000))
        assert abbina("Vlahovic", "Juventus", indici) is None

    def test_un_cognome_piu_corto_non_ruba_lo_stipendio(self):
        # Caso vero, trovato sul listone 2026/27: «Martin» del Genoa si
        # prendeva lo stipendio di «Josep Martinez» dell'Inter, perche'
        # m-a-r-t-i-n sta dentro «martinez». Il confronto e' per parole
        # intere proprio per questo.
        indici = self.indici(Stipendio("Josep Martinez", "Inter", 2_000_000))
        assert abbina("Martin", "Genoa", indici) is None
        assert abbina("Martin", "Inter", indici) is None

    def test_l_iniziale_abbreviata_distingue_gli_omonimi(self):
        # Il listone scrive «Martinez Jo.» e «Martinez L.» per Josep e Lautaro.
        indici = self.indici(
            Stipendio("Josep Martinez", "Inter", 2_000_000),
            Stipendio("Lautaro Martinez", "Inter", 11_000_000),
        )
        primo = abbina("Martinez Jo.", "Inter", indici)
        secondo = abbina("Martinez L.", "Inter", indici)
        assert primo is not None and primo.lordo_annuo == 2_000_000
        assert secondo is not None and secondo.lordo_annuo == 11_000_000

    def test_senza_iniziale_due_omonimi_restano_ambigui(self):
        indici = self.indici(
            Stipendio("Josep Martinez", "Inter", 2_000_000),
            Stipendio("Lautaro Martinez", "Inter", 11_000_000),
        )
        assert abbina("Martinez", "Inter", indici) is None

    def test_il_cognome_staccato_o_attaccato_e_lo_stesso(self):
        indici = self.indici(Stipendio("Charles De Ketelaere", "Atalanta", 4_000_000))
        assert abbina("De Ketelaere", "Atalanta", indici) is not None

    def test_scomposizione_del_nome_del_listone(self):
        from fantacalcio.fonti_web import scomponi_nome_listone

        assert scomponi_nome_listone("Martinez Jo.") == (("martinez",), "jo")
        assert scomponi_nome_listone("Barella") == (("barella",), "")
        assert scomponi_nome_listone("De Ketelaere") == (("de", "ketelaere"), "")


class TestConsolidamento:
    def test_mette_insieme_listone_e_stipendi(self):
        righe, senza = consolida(
            listone_xlsx(LISTONE),
            [
                Stipendio("Paulo Dybala", "Roma", 6_000_000, "Argentina"),
                Stipendio("Lautaro Martínez", "Inter", 11_000_000, "Argentina"),
                Stipendio("Nicolò Barella", "Inter", 9_000_000, "Italia"),
                Stipendio("Mile Svilar", "Roma", 3_000_000, "Serbia"),
            ],
        )
        per_nome = {r.nome: r for r in righe}
        assert len(righe) == 4
        assert per_nome["Dybala"].ingaggio == 6_000_000
        assert per_nome["Dybala"].nazionalita == "Argentina"
        assert per_nome["Barella"].ruoli == ("M", "C")
        assert per_nome["Lautaro Martinez"].ingaggio == 11_000_000
        assert senza == []

    def test_senza_stipendi_i_ruoli_si_aggiornano_lo_stesso(self):
        righe, senza = consolida(listone_xlsx(LISTONE), [])
        assert len(righe) == 4
        assert all(r.ingaggio == 0 for r in righe)
        # Nessuna fonte stipendi: non ha senso elencare «mancanti».
        assert senza == []

    def test_chi_non_ha_riscontro_tiene_l_ingaggio_che_aveva(self):
        righe, senza = consolida(
            listone_xlsx(LISTONE),
            [Stipendio("Paulo Dybala", "Roma", 6_000_000)],
            ingaggi_correnti={555: 8_000_000},
        )
        per_nome = {r.nome: r for r in righe}
        assert per_nome["Barella"].ingaggio == 8_000_000  # conservato
        assert per_nome["Svilar"].ingaggio == 0
        assert "Svilar (Roma)" in senza
        assert not any(s.startswith("Barella") for s in senza)

    def test_un_listone_illeggibile_si_dichiara(self):
        with pytest.raises(FonteNonRaggiungibile, match="Listone non leggibile"):
            consolida(b"non sono un xlsx", [])


class TestAggiornamentoCompleto:
    def finto_web(self, stipendi_ok: bool = True, listone_ok: bool = True):
        pagina = json.dumps(
            [
                {"player": "Paulo Dybala", "team": "Roma", "gross_annual": 6_000_000},
                {"player": "Nicolò Barella", "team": "Inter", "gross_annual": 9_000_000},
            ]
        )

        def apri(url: str) -> bytes:
            if url.endswith(".xlsx"):
                if not listone_ok:
                    raise FonteNonRaggiungibile("404")
                return listone_xlsx(LISTONE)
            if not stipendi_ok:
                raise FonteNonRaggiungibile("503")
            return f"<script>var d = {pagina};</script>".encode()

        return apri

    def test_va_a_buon_fine(self):
        esito = aggiorna_da_web(apri=self.finto_web(), stagione_="2026_27")
        assert esito.riuscito
        assert len(esito.righe) == 4
        assert esito.con_stipendio == 2
        assert all(f.ok for f in esito.fonti)
        assert esito.fonti[0].nome.startswith("Listone")

    def test_stipendi_giu_ma_listone_su(self):
        esito = aggiorna_da_web(
            apri=self.finto_web(stipendi_ok=False),
            stagione_="2026_27",
            ingaggi_correnti={2071: 5_000_000},
        )
        assert esito.riuscito  # i ruoli si aggiornano lo stesso
        assert len(esito.righe) == 4
        assert {r.nome: r.ingaggio for r in esito.righe}["Dybala"] == 5_000_000
        assert [f.ok for f in esito.fonti] == [True, False]

    def test_listone_giu_non_alza_ma_racconta(self):
        esito = aggiorna_da_web(apri=self.finto_web(listone_ok=False))
        assert not esito.riuscito
        assert esito.righe == []
        assert esito.fonti[0].ok is False
        assert "404" in esito.fonti[0].dettaglio


class TestFileUnico:
    def test_csv_con_una_riga_per_giocatore(self):
        righe = [
            RigaListone(
                id_ufficiale=2071,
                nome="Dybala",
                club="Roma",
                ruoli=("A", "Pc"),
                ruolo_classic="A",
                quotazione=24,
                fvm=70,
                ingaggio=6_000_000,
                nazionalita="Argentina",
                data_nascita=date(1993, 11, 15),
            )
        ]
        testo = a_csv(righe)
        intestazioni, prima = testo.strip().split("\n")
        assert intestazioni.startswith("id_ufficiale;nome;club;ruolo_classic;ruoli")
        assert "2071;Dybala;Roma;A;A/Pc" in prima
        assert "6000000" in prima
        assert "1993-11-15" in prima

    def test_le_righe_per_l_archivio_tengono_gli_id_interni(self):
        import pandas as pd

        esistenti = pd.DataFrame(
            [
                {
                    "id": 7,
                    "id_ufficiale": 2071,
                    "nome": "Dybala",
                    "club": "Roma",
                    "ruoli": "A",
                    "ingaggio": 5_000_000,
                    "nazionalita": "Argentina",
                    "data_nascita": "1993-11-15",
                    "quotazione": 24,
                    "fvm": 70,
                }
            ]
        )
        righe = [
            RigaListone(2071, "Dybala", "Roma", ("A", "Pc"), ingaggio=6_000_000),
            RigaListone(555, "Barella", "Inter", ("M", "C")),
        ]
        fuori = a_righe_archivio(righe, esistenti)
        per_ufficiale = {r["id_ufficiale"]: r for r in fuori}
        # L'id interno non cambia: i contratti ci puntano.
        assert per_ufficiale[2071]["id"] == 7
        assert per_ufficiale[555]["id"] == 8
        # Nazionalita' e nascita note non si perdono se la fonte non le porta.
        assert per_ufficiale[2071]["nazionalita"] == "Argentina"
        assert per_ufficiale[2071]["data_nascita"] == "1993-11-15"
        assert per_ufficiale[2071]["ruoli"] == "A;Pc"

    def test_su_archivio_vuoto_parte_da_uno(self):
        import pandas as pd

        fuori = a_righe_archivio(
            [RigaListone(555, "Barella", "Inter", ("M",))], pd.DataFrame()
        )
        assert fuori[0]["id"] == 1
        assert fuori[0]["nazionalita"] == "Italia"


class TestScritturaInArchivio:
    def test_applica_scrive_e_conta(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite
        from fantacalcio.fonti_web import applica

        arch = ArchivioSQLite(tmp_path / "listone.db")
        arch.svuota("giocatori")
        conteggio = applica(
            arch,
            [
                RigaListone(2071, "Dybala", "Roma", ("A", "Pc"), ingaggio=6_000_000),
                RigaListone(555, "Barella", "Inter", ("M", "C")),
            ],
        )
        assert conteggio == {
            "totali": 2,
            "nuovi": 2,
            "rimossi": 0,
            "con_stipendio": 1,
        }
        salvati = arch.giocatori()
        assert set(salvati["nome"]) == {"Dybala", "Barella"}

    def test_riapplicare_non_duplica(self, tmp_path):
        from fantacalcio.data import ArchivioSQLite
        from fantacalcio.fonti_web import applica

        arch = ArchivioSQLite(tmp_path / "listone2.db")
        arch.svuota("giocatori")
        righe = [RigaListone(2071, "Dybala", "Roma", ("A",), ingaggio=6_000_000)]
        applica(arch, righe)
        applica(arch, [RigaListone(2071, "Dybala", "Roma", ("A", "Pc"), ingaggio=7e6)])
        salvati = arch.giocatori()
        assert len(salvati) == 1
        assert salvati.iloc[0]["ruoli"] == "A;Pc"
        assert salvati.iloc[0]["ingaggio"] == 7_000_000


def test_esito_vuoto_non_e_riuscito():
    assert not EsitoAggiornamento().riuscito


class TestIntestazioniDaBrowser:
    """Il 403 di un CDN si evita somigliando a un visitatore, non insistendo."""

    def test_il_referer_si_deduce_dal_dominio(self):
        from fantacalcio.fonti_web import (
            RIFERIMENTO_CAPOLOGY,
            RIFERIMENTO_QUOTAZIONI,
            riferimento_per,
        )

        assert (
            riferimento_per("https://content.fantacalcio.it/statico/x.xlsx")
            == RIFERIMENTO_QUOTAZIONI
        )
        assert (
            riferimento_per("https://www.capology.com/it/serie-a/salaries/")
            == RIFERIMENTO_CAPOLOGY
        )
        assert riferimento_per("https://esempio.it/file.xlsx") == ""

    def test_la_richiesta_porta_referer_e_user_agent(self, monkeypatch):
        from fantacalcio import fonti_web

        viste = {}

        class FintaRisposta:
            headers = {"Content-Encoding": ""}

            def read(self):
                return b"contenuto"

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def finto_urlopen(richiesta, timeout=None):
            viste["headers"] = dict(richiesta.headers)
            viste["url"] = richiesta.full_url
            return FintaRisposta()

        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", finto_urlopen)
        assert fonti_web.scarica(fonti_web.url_quotazioni("2026_27")) == b"contenuto"
        # urllib normalizza i nomi delle intestazioni in Camel-Case.
        intestazioni = {k.lower(): v for k, v in viste["headers"].items()}
        assert "fantacalcio.it" in intestazioni["referer"]
        assert "Mozilla" in intestazioni["user-agent"]
        assert intestazioni["accept-language"].startswith("it-IT")

    def test_una_risposta_gzip_viene_scompattata(self, monkeypatch):
        import gzip
        import urllib.request

        from fantacalcio import fonti_web

        class FintaRisposta:
            headers = {"Content-Encoding": "gzip"}

            def read(self):
                return gzip.compress(b"<html>ciao</html>")

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FintaRisposta())
        assert fonti_web.scarica("https://esempio.it/x") == b"<html>ciao</html>"

    def test_un_403_diventa_un_messaggio_leggibile(self, monkeypatch):
        import urllib.error
        import urllib.request

        from fantacalcio import fonti_web

        def rifiuta(*_a, **_k):
            raise urllib.error.HTTPError(
                "https://esempio.it/x", 403, "Forbidden", {}, None
            )

        monkeypatch.setattr(urllib.request, "urlopen", rifiuta)
        with pytest.raises(FonteNonRaggiungibile, match="403"):
            fonti_web.scarica("https://esempio.it/x")

    def test_il_messaggio_dice_anche_come_si_e_chiesto(self, monkeypatch):
        # Un 403 identico puo' venire da un CDN che ci rifiuta o da un sito
        # rimasto al codice di prima: la coda del messaggio distingue i due.
        import urllib.error
        import urllib.request

        from fantacalcio import fonti_web

        def rifiuta(*_a, **_k):
            raise urllib.error.HTTPError(
                fonti_web.url_quotazioni("2026_27"), 403, "Forbidden", {}, None
            )

        monkeypatch.setattr(urllib.request, "urlopen", rifiuta)
        with pytest.raises(FonteNonRaggiungibile) as caduta:
            fonti_web.scarica(fonti_web.url_quotazioni("2026_27"))
        messaggio = str(caduta.value)
        assert "intestazioni da browser" in messaggio
        assert "Referer https://www.fantacalcio.it/quotazioni-fantacalcio" in messaggio


class TestStipendiDaFile:
    """Quando il CDN dice di no, gli stipendi si caricano a mano."""

    def test_legge_un_csv_col_punto_e_virgola(self):
        from fantacalcio.fonti_web import MODELLO_CSV_STIPENDI, leggi_stipendi_csv

        stipendi = leggi_stipendi_csv(MODELLO_CSV_STIPENDI)
        assert [s.nome for s in stipendi] == ["Paulo Dybala", "Nicolo Barella"]
        assert stipendi[0].lordo_annuo == 6_000_000
        assert stipendi[0].club == "Roma"
        assert stipendi[1].data_nascita == date(1997, 2, 7)

    def test_legge_anche_con_la_virgola_e_in_inglese(self):
        from fantacalcio.fonti_web import leggi_stipendi_csv

        stipendi = leggi_stipendi_csv(
            "player,team,gross,country\nMile Svilar,Roma,€ 3.000.000,Serbia\n"
        )
        assert stipendi[0].lordo_annuo == 3_000_000
        assert stipendi[0].nazionalita == "Serbia"

    def test_colonne_sbagliate_lo_dicono(self):
        from fantacalcio.fonti_web import leggi_stipendi_csv

        with pytest.raises(FonteNonRaggiungibile, match="colonne"):
            leggi_stipendi_csv("pippo;pluto\n1;2\n")

    def test_file_vuoto(self):
        from fantacalcio.fonti_web import leggi_stipendi_csv

        with pytest.raises(FonteNonRaggiungibile, match="vuoto"):
            leggi_stipendi_csv("")


class TestAggiornamentoDaFile:
    """La via che non passa dalla rete, quindi non puo' fallire per colpa sua."""

    def test_listone_piu_stipendi_caricati_a_mano(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(
            listone_xlsx(LISTONE),
            stipendi_csv=(
                "giocatore;squadra;lordo;nazionalita\n"
                "Paulo Dybala;Roma;6000000;Argentina\n"
                "Nicolo Barella;Inter;9000000;Italia\n"
            ),
        )
        assert esito.riuscito
        assert len(esito.righe) == 4
        assert esito.con_stipendio == 2
        assert [f.ok for f in esito.fonti] == [True, True]
        assert esito.fonti[0].nome == "Listone (file caricato)"

    def test_il_solo_listone_basta(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(listone_xlsx(LISTONE))
        assert esito.riuscito
        assert esito.con_stipendio == 0
        assert len(esito.fonti) == 1

    def test_un_xlsx_che_non_e_il_listone(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        # Comincia per PK come uno zip, quindi si prova a leggerlo da Excel.
        esito = aggiorna_da_file(b"PK\x03\x04 e poi spazzatura")
        assert not esito.riuscito
        assert esito.fonti[0].ok is False
        assert "Listone non leggibile" in esito.fonti[0].dettaglio

    def test_un_file_che_non_e_ne_xlsx_ne_csv(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(b"questo e' un pdf, non un listone")
        assert not esito.riuscito
        assert esito.fonti[0].ok is False
        # Il messaggio dice quali colonne cercava: e' quello che serve sapere.
        assert "colonne" in esito.fonti[0].dettaglio.lower()

    def test_stipendi_illeggibili_non_fermano_il_listone(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(listone_xlsx(LISTONE), stipendi_csv="pippo;pluto\n1;2\n")
        assert esito.riuscito
        assert len(esito.righe) == 4
        assert [f.ok for f in esito.fonti] == [True, False]


class TestIndirizziAlternativi:
    def test_si_puo_puntare_altrove_senza_toccare_il_codice(self):
        chiamati = []

        def apri(url: str) -> bytes:
            chiamati.append(url)
            if url.endswith(".xlsx"):
                return listone_xlsx(LISTONE)
            raise FonteNonRaggiungibile("non serve")

        esito = aggiorna_da_web(
            apri=apri,
            stagione_="2026_27",
            url_listone="https://esempio.it/mio_listone.xlsx",
            url_stipendi="https://esempio.it/stipendi.html",
        )
        assert chiamati == [
            "https://esempio.it/mio_listone.xlsx",
            "https://esempio.it/stipendi.html",
        ]
        assert esito.riuscito


class TestListoneInUnFileSolo:
    """Il CSV con tutto dentro: quel che si prepara in Excel e si carica."""

    def test_legge_il_modello(self):
        from fantacalcio.fonti_web import MODELLO_CSV_LISTONE, leggi_listone_csv

        righe = leggi_listone_csv(MODELLO_CSV_LISTONE)
        assert [r.nome for r in righe] == ["Paulo Dybala", "Nicolo Barella"]
        primo = righe[0]
        assert primo.id_ufficiale == 2071
        assert primo.club == "Roma"
        assert primo.ruolo_classic == "A"
        assert primo.ruoli == ("A", "Pc")
        assert primo.data_nascita == date(1993, 11, 15)
        assert primo.nazionalita == "Argentina"
        assert primo.ingaggio == 6_000_000

    def test_il_cognome_da_solo_basta(self):
        from fantacalcio.fonti_web import leggi_listone_csv

        righe = leggi_listone_csv(
            "id;cognome;ruolo mantra;stipendio lordo\n555;Barella;M/C;9000000\n"
        )
        assert righe[0].nome == "Barella"
        assert righe[0].ruoli == ("M", "C")

    def test_senza_id_non_si_puo_procedere(self):
        # Senza id i contratti non saprebbero piu' a chi puntano.
        from fantacalcio.fonti_web import leggi_listone_csv

        with pytest.raises(FonteNonRaggiungibile, match="id giocatore"):
            leggi_listone_csv("nome;ruolo mantra\nBarella;M\n")

    def test_senza_ruolo_mantra_nemmeno(self):
        from fantacalcio.fonti_web import leggi_listone_csv

        with pytest.raises(FonteNonRaggiungibile, match="ruolo mantra"):
            leggi_listone_csv("id;nome\n555;Barella\n")

    def test_un_ruolo_inventato_si_dichiara(self):
        from fantacalcio.fonti_web import leggi_listone_csv

        with pytest.raises(FonteNonRaggiungibile, match="Nessuna riga leggibile"):
            leggi_listone_csv("id;nome;ruolo mantra\n555;Barella;Mediano\n")

    def test_una_riga_rotta_non_butta_via_le_altre(self):
        from fantacalcio.fonti_web import leggi_listone_csv

        righe = leggi_listone_csv(
            "id;nome;ruolo mantra\n555;Barella;M/C\nxx;Rotto;M\n999;Svilar;Por\n"
        )
        assert [r.nome for r in righe] == ["Barella", "Svilar"]

    def test_passa_da_aggiorna_da_file(self):
        from fantacalcio.fonti_web import MODELLO_CSV_LISTONE, aggiorna_da_file

        esito = aggiorna_da_file(MODELLO_CSV_LISTONE.encode("utf-8"))
        assert esito.riuscito
        assert esito.con_stipendio == 2
        assert esito.fonti[0].nome == "Listone (CSV caricato)"

    def test_un_ingaggio_a_zero_tiene_quello_che_c_era(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(
            b"id;nome;ruolo mantra;stipendio lordo\n555;Barella;M/C;\n",
            ingaggi_correnti={555: 8_000_000},
        )
        assert esito.righe[0].ingaggio == 8_000_000
        assert esito.senza_stipendio == []


class TestConteggioNuovi:
    """«Nuovi» conta chi non c'era, non la differenza fra due totali."""

    def archivio(self, tmp_path, nome="conteggio.db"):
        from fantacalcio.data import ArchivioSQLite

        arch = ArchivioSQLite(tmp_path / nome)
        arch.svuota("giocatori")
        return arch

    def test_su_un_catalogo_gia_pieno(self, tmp_path):
        from fantacalcio.fonti_web import applica

        arch = self.archivio(tmp_path)
        applica(
            arch,
            [
                RigaListone(i, f"Tale {i}", "Roma", ("A",), ingaggio=1_000_000)
                for i in range(1, 21)
            ],
        )
        # Ne ricarico sei, di cui uno solo mai visto prima.
        conteggio = applica(
            arch,
            [RigaListone(i, f"Tale {i}", "Roma", ("A",)) for i in (1, 2, 3, 4, 5, 99)],
        )
        assert conteggio["totali"] == 6
        assert conteggio["nuovi"] == 1


class TestTabellaIncollata:
    """Capology non esporta: si copia la tabella e si incolla. Deve bastare."""

    def test_colonne_separate_da_tabulazione(self):
        from fantacalcio.fonti_web import leggi_stipendi_incollati

        incollato = (
            "Giocatore\tSquadra\tLordo annuale\tNazionalita\n"
            "Paulo Dybala\tRoma\t€ 6.000.000\tArgentina\n"
            "Nicolo Barella\tInter\t€ 9.000.000\tItalia\n"
        )
        stipendi = leggi_stipendi_incollati(incollato)
        assert [s.nome for s in stipendi] == ["Paulo Dybala", "Nicolo Barella"]
        assert stipendi[0].lordo_annuo == 6_000_000
        assert stipendi[1].club == "Inter"

    def test_html_della_tabella(self):
        from fantacalcio.fonti_web import leggi_stipendi_incollati

        incollato = (
            "<table><tr><th>Player</th><th>Gross</th></tr>"
            "<tr><td>Mile Svilar</td><td>3000000</td></tr></table>"
        )
        stipendi = leggi_stipendi_incollati(incollato)
        assert stipendi[0].nome == "Mile Svilar"
        assert stipendi[0].lordo_annuo == 3_000_000

    def test_il_csv_di_un_foglio_di_calcolo(self):
        from fantacalcio.fonti_web import leggi_stipendi_incollati

        stipendi = leggi_stipendi_incollati("giocatore;lordo\nSvilar;3000000\n")
        assert stipendi[0].lordo_annuo == 3_000_000

    def test_html_rotto_ripiega_sul_testo(self):
        from fantacalcio.fonti_web import leggi_stipendi_incollati

        # C'e' un <tr> ma la tabella non e' leggibile: si prova come testo,
        # e li' l'intestazione e' quella giusta.
        incollato = "<tr></tr>\ngiocatore;lordo\nSvilar;3000000\n"
        stipendi = leggi_stipendi_incollati("giocatore;lordo\nSvilar;3000000\n")
        assert stipendi[0].nome == "Svilar"
        # Con la riga di troppo in testa non si indovina: si dice cosa si e'
        # letto, invece di scoppiare mentre si spiega l'errore.
        with pytest.raises(FonteNonRaggiungibile, match="Intestazioni lette"):
            leggi_stipendi_incollati(incollato)


class TestListoneVeroDiSerieA:
    """Il file vero di Fantacalcio.it, non uno costruito su misura."""

    def listone(self):
        from pathlib import Path

        percorso = Path(__file__).parent / "dati" / "listone_2026_27.xlsx"
        if not percorso.exists():
            pytest.skip("il listone vero non e' nel repository")
        return percorso.read_bytes()

    def test_si_legge_per_intero(self):
        from fantacalcio.fonti_web import aggiorna_da_file

        esito = aggiorna_da_file(self.listone())
        assert esito.riuscito
        assert len(esito.righe) > 400
        assert len({r.club for r in esito.righe}) == 20
        assert all(r.ruoli for r in esito.righe)
        assert all(r.ruolo_classic in ("P", "D", "C", "A") for r in esito.righe)

    def test_il_file_da_completare_ritorna_indietro_uguale(self):
        from fantacalcio.fonti_web import (
            a_csv_da_completare,
            aggiorna_da_file,
            leggi_listone_csv,
        )

        righe = aggiorna_da_file(self.listone()).righe
        tornate = leggi_listone_csv(a_csv_da_completare(righe))
        assert len(tornate) == len(righe)
        assert [r.id_ufficiale for r in tornate] == [r.id_ufficiale for r in righe]
        assert [r.ruoli for r in tornate] == [r.ruoli for r in righe]
        assert [r.ruolo_classic for r in tornate] == [r.ruolo_classic for r in righe]


class TestSostituzioneDelListone:
    """Unire e sostituire sono due cose diverse, e si scelgono."""

    def archivio(self, tmp_path, nome):
        from fantacalcio.data import ArchivioSQLite
        from fantacalcio.fonti_web import applica

        arch = ArchivioSQLite(tmp_path / nome)
        arch.svuota("contratti")
        arch.svuota("giocatori")
        applica(
            arch,
            [
                RigaListone(2071, "Dybala", "Roma", ("A",), ingaggio=6_000_000),
                RigaListone(555, "Barella", "Inter", ("M",), ingaggio=9_000_000),
                RigaListone(999, "Svilar", "Roma", ("Por",), ingaggio=3_000_000),
            ],
        )
        return arch

    def test_unire_lascia_stare_chi_non_c_e_nel_file(self, tmp_path):
        from fantacalcio.fonti_web import applica

        arch = self.archivio(tmp_path, "unisci.db")
        conteggio = applica(arch, [RigaListone(2071, "Dybala", "Roma", ("A", "Pc"))])
        assert conteggio["rimossi"] == 0
        assert len(arch.giocatori()) == 3

    def test_sostituire_cancella_chi_non_c_e_nel_file(self, tmp_path):
        from fantacalcio.fonti_web import applica

        arch = self.archivio(tmp_path, "sostituisci.db")
        conteggio = applica(
            arch,
            [RigaListone(2071, "Dybala", "Roma", ("A", "Pc"), ingaggio=6_000_000)],
            sostituisci=True,
        )
        assert conteggio["totali"] == 1
        assert conteggio["rimossi"] == 2
        rimasti = arch.giocatori()
        assert list(rimasti["nome"]) == ["Dybala"]

    def test_sostituire_porta_via_anche_i_contratti(self, tmp_path):
        from fantacalcio.data import assegna_contratto
        from fantacalcio.fonti_web import applica

        arch = self.archivio(tmp_path, "sostituisci2.db")
        elenco = arch.giocatori()
        interno = int(elenco.loc[elenco["id_ufficiale"] == 555, "id"].iloc[0])
        assegna_contratto(arch, interno, squadra_id=1, anni_residui=3)
        assert len(arch.contratti()) == 1

        applica(arch, [RigaListone(2071, "Dybala", "Roma", ("A",))], sostituisci=True)
        # Barella non c'e' piu': il suo contratto non puo' restare appeso.
        assert arch.contratti().empty


class TestColonnaDelloStipendio:
    """Quale colonna e' «lo stipendio», quando ce ne sono quattro simili."""

    def intestazioni(self, *nomi):
        from fantacalcio.fonti_web import _mappa_campi

        return _mappa_campi(nomi)

    def test_riconosce_il_suffisso_della_valuta(self):
        # Il file vero di Capology scrive «Lordo annuo EUR».
        campi = self.intestazioni("Giocatore", "Lordo annuo EUR")
        assert campi["lordo"] == "Lordo annuo EUR"

    def test_preferisce_il_lordo_al_totale_col_bonus(self):
        campi = self.intestazioni(
            "Giocatore",
            "Lordo settimanale EUR",
            "Lordo annuo EUR",
            "Bonus lordo annuo EUR",
            "Totale lordo annuo EUR",
            "Residuo contratto lordo EUR",
        )
        assert campi["lordo"] == "Lordo annuo EUR"

    def test_non_scambia_il_settimanale_per_l_annuo(self):
        campi = self.intestazioni("Giocatore", "Lordo settimanale EUR")
        assert "lordo" not in campi

    def test_capisce_anche_l_inglese(self):
        campi = self.intestazioni("Player", "Annual Gross Salary (EUR)")
        assert campi["lordo"] == "Annual Gross Salary (EUR)"

    def test_il_totale_da_solo_non_vale(self):
        # Comprende i bonus: non e' lo stipendio dell'articolo 4.
        campi = self.intestazioni("Giocatore", "Totale lordo annuo EUR")
        assert "lordo" not in campi


class TestPaesiInItaliano:
    """«Italy» non e' «Italia», e il sito decide da quella parola chi e' italiano."""

    def test_traduce_i_paesi_noti(self):
        from fantacalcio.fonti_web import traduci_paese

        assert traduci_paese("Italy") == "Italia"
        assert traduci_paese("France") == "Francia"
        assert traduci_paese("Turkey") == "Turchia"
        assert traduci_paese("Netherlands") == "Paesi Bassi"

    def test_lascia_stare_quel_che_non_conosce(self):
        from fantacalcio.fonti_web import traduci_paese

        assert traduci_paese("Argentina") == "Argentina"
        assert traduci_paese("Wakanda") == "Wakanda"
        assert traduci_paese("") == ""

    def test_un_italiano_registrato_come_Italy_resta_italiano(self):
        from fantacalcio.fonti_web import leggi_stipendi_csv
        from fantacalcio.modelli import Giocatore

        stipendi = leggi_stipendi_csv("giocatore;lordo;nazionalita\nRossi;1;Italy\n")
        # E' la stringa su cui `Giocatore.italiano` fa il confronto: se
        # restasse «Italy», il minimo italiani in rosa lo conterebbe straniero.
        giocatore = Giocatore(
            id=1,
            nome="Rossi",
            club="Roma",
            ruoli=("C",),
            ingaggio=1,
            nazionalita=stipendi[0].nazionalita,
        )
        assert giocatore.italiano

    def test_anche_nel_listone_caricato_a_mano(self):
        from fantacalcio.fonti_web import leggi_listone_csv

        righe = leggi_listone_csv("id;nome;ruolo mantra;nazionalita\n1;Rossi;C;Italy\n")
        assert righe[0].nazionalita == "Italia"


class TestClubAllInglese:
    def test_inter_milan_e_l_inter(self):
        assert normalizza_club("Inter Milan") == normalizza_club("Inter")

    def test_ac_milan_resta_il_milan(self):
        assert normalizza_club("AC Milan") == normalizza_club("Milan")
        assert normalizza_club("AC Milan") != normalizza_club("Inter Milan")


class TestCognomiStaccati:
    def indici(self, *stipendi: Stipendio):
        from fantacalcio.fonti_web import _indicizza_stipendi

        return _indicizza_stipendi(stipendi)

    def test_delprato_e_del_prato(self):
        # Caso vero: il listone scrive «Delprato», Capology «Enrico Del Prato».
        indici = self.indici(Stipendio("Enrico Del Prato", "Parma", 1_200_000))
        trovato = abbina("Delprato", "Parma", indici)
        assert trovato is not None and trovato.lordo_annuo == 1_200_000

    def test_non_incastra_pezzi_di_nome(self):
        # Le parole devono essere consecutive: «martin» non e' «josep martinez».
        indici = self.indici(Stipendio("Josep Martinez", "Inter", 2_000_000))
        assert abbina("Martin", "Genoa", indici) is None
        assert abbina("Sepmar", "Inter", indici) is None
