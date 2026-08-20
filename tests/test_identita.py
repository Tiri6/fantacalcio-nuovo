import pytest

from fantacalcio.identita import (
    PESO_MASSIMO_IMMAGINE,
    ColoreNonValido,
    IdentitaSquadra,
    ImmagineNonValida,
    StileMaglia,
    contrasto_sufficiente,
    immagine_a_data_uri,
    maglia_data_uri,
    maglia_svg,
    normalizza_colore,
)


class TestNormalizzaColore:
    @pytest.mark.parametrize(
        "valore,atteso",
        [
            ("#aabbcc", "#aabbcc"),
            ("aabbcc", "#aabbcc"),
            ("#ABC", "#aabbcc"),
            ("abc", "#aabbcc"),
            ("  #2E7D32  ", "#2e7d32"),
        ],
    )
    def test_forme_accettate(self, valore, atteso):
        assert normalizza_colore(valore) == atteso

    @pytest.mark.parametrize("valore", ["", "   ", "rosso", "#12345", "#gggggg", None])
    def test_valori_rifiutati(self, valore):
        with pytest.raises(ColoreNonValido):
            normalizza_colore(valore)

    def test_il_messaggio_nomina_il_campo(self):
        with pytest.raises(ColoreNonValido, match="colore primario"):
            normalizza_colore("banana", "colore primario")


class TestContrasto:
    def test_nero_e_bianco_si_distinguono(self):
        assert contrasto_sufficiente("#000000", "#ffffff")

    def test_due_bianchi_no(self):
        assert not contrasto_sufficiente("#ffffff", "#fefefe")

    def test_e_simmetrico(self):
        assert contrasto_sufficiente("#c62828", "#ffffff") == contrasto_sufficiente(
            "#ffffff", "#c62828"
        )


class TestMaglia:
    @pytest.mark.parametrize("stile", list(StileMaglia))
    def test_ogni_stile_produce_un_svg_valido(self, stile):
        svg = maglia_svg("#c62828", "#ffffff", stile)
        assert svg.startswith("<svg") and svg.endswith("</svg>")
        assert "#c62828" in svg

    def test_i_colori_sono_normalizzati(self):
        assert "#aabbcc" in maglia_svg("ABC", "#fff")

    def test_la_tinta_unita_non_usa_pattern(self):
        assert "pattern" not in maglia_svg("#c62828", "#fff", StileMaglia.TINTA_UNITA)

    def test_le_strisce_usano_un_pattern(self):
        svg = maglia_svg("#c62828", "#ffffff", StileMaglia.STRISCE)
        assert "<pattern" in svg and "url(#riempimento)" in svg

    def test_numero_di_maglia(self):
        assert ">10<" in maglia_svg("#000", "#fff", numero="10")
        assert "<text" not in maglia_svg("#000", "#fff")

    def test_larghezza_personalizzata(self):
        assert 'width="90"' in maglia_svg("#000", "#fff", larghezza=90)

    def test_data_uri(self):
        assert maglia_data_uri("#000", "#fff").startswith("data:image/svg+xml;base64,")

    def test_colore_non_valido_propaga(self):
        with pytest.raises(ColoreNonValido):
            maglia_svg("verde acqua", "#fff")


class TestIdentitaSquadra:
    def test_valori_predefiniti_sensati(self):
        identita = IdentitaSquadra()
        assert identita.colore_primario.startswith("#")
        assert identita.stile_maglia is StileMaglia.TINTA_UNITA
        assert identita.colori_distinguibili

    def test_normalizza_i_colori_alla_costruzione(self):
        identita = IdentitaSquadra(colore_primario="ABC", colore_secondario="#FFF")
        assert identita.colore_primario == "#aabbcc"
        assert identita.colore_secondario == "#ffffff"

    def test_colore_non_valido_blocca_la_creazione(self):
        with pytest.raises(ColoreNonValido):
            IdentitaSquadra(colore_primario="viola pastello")

    def test_maglia_disegnata_se_non_ne_e_stata_caricata_una(self):
        assert IdentitaSquadra().maglia().startswith("<svg")

    def test_maglia_caricata_ha_la_precedenza(self):
        identita = IdentitaSquadra(maglia_caricata="data:image/png;base64,AAA")
        assert identita.maglia() == "data:image/png;base64,AAA"

    def test_colori_indistinguibili_segnalati(self):
        identita = IdentitaSquadra(colore_primario="#ffffff", colore_secondario="#fdfdfd")
        assert not identita.colori_distinguibili


class TestImmagineCaricata:
    def test_png_valido(self):
        uri = immagine_a_data_uri(b"\\x89PNG fittizio", "image/png")
        assert uri.startswith("data:image/png;base64,")

    def test_formato_non_supportato(self):
        with pytest.raises(ImmagineNonValida, match="non supportato"):
            immagine_a_data_uri(b"dati", "application/pdf")

    def test_file_vuoto(self):
        with pytest.raises(ImmagineNonValida, match="vuoto"):
            immagine_a_data_uri(b"", "image/png")

    def test_file_troppo_grande(self):
        with pytest.raises(ImmagineNonValida, match="KB"):
            immagine_a_data_uri(b"x" * (PESO_MASSIMO_IMMAGINE + 1), "image/png")

    def test_al_limite_passa(self):
        uri = immagine_a_data_uri(b"x" * PESO_MASSIMO_IMMAGINE, "image/webp")
        assert uri.startswith("data:image/webp;base64,")
