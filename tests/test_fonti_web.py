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
                quotazione=24,
                fvm=70,
                ingaggio=6_000_000,
                nazionalita="Argentina",
                data_nascita=date(1993, 11, 15),
            )
        ]
        testo = a_csv(righe)
        intestazioni, prima = testo.strip().split("\n")
        assert intestazioni.startswith("id_ufficiale;nome;club;ruoli")
        assert "2071;Dybala;Roma;A/Pc" in prima
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
        assert conteggio == {"totali": 2, "nuovi": 2, "con_stipendio": 1}
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
