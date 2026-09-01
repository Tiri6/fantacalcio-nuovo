"""Il tema produce stringhe: si prova senza far girare Streamlit."""

import pytest

from fantacalcio import tema


class TestContrasto:
    @pytest.mark.parametrize(
        "fondo,atteso",
        [
            ("#ffffff", "#10141c"),
            ("#ffeb3b", "#10141c"),
            ("#000000", "#ffffff"),
            ("#1a237e", "#ffffff"),
            ("#2e7d32", "#ffffff"),
        ],
    )
    def test_testo_leggibile_sul_fondo(self, fondo, atteso):
        assert tema.testo_su(fondo) == atteso

    def test_bianco_e_nero_stanno_agli_estremi(self):
        assert tema.luminanza("#ffffff") > tema.luminanza("#808080")
        assert tema.luminanza("#808080") > tema.luminanza("#000000")

    def test_trasparenza(self):
        assert tema.con_trasparenza("#2e7d32", 0.5) == "rgba(46, 125, 50, 0.50)"

    @pytest.mark.parametrize("alfa,atteso", [(-1, "0.00"), (2, "1.00")])
    def test_alfa_fuori_scala_viene_riportata_dentro(self, alfa, atteso):
        assert tema.con_trasparenza("#000000", alfa).endswith(f"{atteso})")


class TestFrammenti:
    def test_la_testata_contiene_il_titolo(self):
        assert "Cruscotto" in tema.testata("Cruscotto")

    def test_l_occhiello_compare_solo_se_dato(self):
        assert "fanta-occhiello" not in tema.testata("Titolo")
        assert "fanta-occhiello" in tema.testata("Titolo", occhiello="Lega")

    def test_la_barra_riflette_la_quota(self):
        assert "width:50%" in tema.dato("Rosa", "15", quota=0.5)

    @pytest.mark.parametrize("quota,atteso", [(-0.5, "0%"), (3.0, "100%")])
    def test_quota_fuori_scala(self, quota, atteso):
        assert f"width:{atteso}" in tema.dato("X", "1", quota=quota)

    def test_stato_sconosciuto_ricade_su_ok(self):
        assert "fanta-dato ok" in tema.dato("X", "1", stato="celeste")

    def test_pastiglia_squadra_usa_i_due_colori(self):
        html = tema.pastiglia_squadra("Tiri Team", "#2e7d32", "#ffffff")
        assert "#2e7d32" in html and "#ffffff" in html


class TestSicurezza:
    """Nome squadra, motto e curva li scrivono gli utenti e finiscono in HTML."""

    @pytest.mark.parametrize(
        "frammento",
        [
            "<script>alert(1)</script>",
            '"><img src=x onerror=alert(1)>',
            "<b>grassetto</b>",
        ],
    )
    def test_l_html_degli_utenti_non_viene_eseguito(self, frammento):
        """Il testo puo' *contenere* `onerror=`; non deve essere un attributo.

        Cio' che rende innocuo il frammento e' che `<`, `>` e `"` arrivino al
        browser scudati: allora resta testo visibile, non markup.
        """
        for prodotto in (
            tema.testata(frammento),
            tema.scheda(frammento, frammento),
            tema.dato(frammento, frammento),
            tema.pastiglia(frammento),
            tema.pastiglia_squadra(frammento, "#000000", "#ffffff"),
            tema.codice_invito(frammento),
        ):
            # La proprieta' e' una sola: il testo grezzo dell'utente non
            # compare mai tale e quale. Cercare singoli tag non funziona,
            # perche' `">` sta legittimamente nel markup del contenitore.
            assert frammento not in prodotto
            assert "&lt;" in prodotto or "&quot;" in prodotto

    def test_le_e_commerciali_si_scudano_per_prime(self):
        """Scudare & dopo < produrrebbe &amp;lt; invece di &lt;."""
        assert "&amp;lt;" not in tema.pastiglia("a & b < c")
        assert "&amp;" in tema.pastiglia("a & b")


def test_il_css_definisce_tutte_le_variabili_che_usa():
    """Una variabile usata ma mai definita rende invisibile un pezzo di pagina."""
    import re

    definite = set(re.findall(r"(--fanta-[a-z-]+):", tema.CSS))
    usate = set(re.findall(r"var\((--fanta-[a-z-]+)\)", tema.CSS))
    assert usate <= definite, f"variabili non definite: {sorted(usate - definite)}"


class TestCampo:
    """Il campo e' HTML costruito a mano: qui si controlla che sia sano."""

    def test_una_riga_per_reparto(self):
        from fantacalcio.tema import campo, maglia_in_campo

        html = campo([[maglia_in_campo("Svilar")], [maglia_in_campo("Mancini")]])
        assert html.count('class="fanta-reparto"') == 2
        assert "Svilar" in html and "Mancini" in html

    def test_il_nome_del_giocatore_e_scudato(self):
        # Un nome con dentro dell'HTML non deve finire nella pagina come tale.
        from fantacalcio.tema import maglia_in_campo

        html = maglia_in_campo("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_la_casella_vuota_si_riconosce(self):
        from fantacalcio.tema import maglia_in_campo

        assert "vuota" in maglia_in_campo("")
        assert "vuota" not in maglia_in_campo("Dybala")

    def test_chi_e_entrato_si_vede(self):
        from fantacalcio.tema import maglia_in_campo

        assert "entrato" in maglia_in_campo("Dybala", entrato=True)

    def test_i_punti_compaiono_solo_se_ci_sono(self):
        from fantacalcio.tema import maglia_in_campo

        assert "punti" not in maglia_in_campo("Dybala")
        assert "7.5" in maglia_in_campo("Dybala", punti=7.5)
