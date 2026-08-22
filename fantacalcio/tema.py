"""Aspetto grafico: CSS, componenti HTML e colori derivati dall'identita'.

Questo modulo **non importa Streamlit**: produce stringhe. E' `ui.py` a
iniettarle. Cosi' il tema resta testabile senza far girare un server e la
regola del progetto ("la logica non importa Streamlit") vale anche qui.

L'ispirazione e' Leghe Fantacalcio e Fantalab: fondo scuro, verde campo,
schede con bordo colorato, numeri grandi. Il contrasto e' calcolato, non
scelto a occhio: ogni squadra ha colori suoi e il testo ci deve stare sopra.
"""

from __future__ import annotations

from .identita import normalizza_colore

# --- Palette ----------------------------------------------------------------

VERDE = "#31a354"
VERDE_CHIARO = "#54d17f"
VERDE_SCURO = "#1d6b36"
FONDO = "#0e1117"
FONDO_ALTO = "#161b26"
SUPERFICIE = "#1a1f2b"
SUPERFICIE_ALTA = "#222836"
BORDO = "#2c3444"
TESTO = "#f2f5f7"
TESTO_TENUE = "#9aa7b8"
AMBRA = "#e8b33c"
ROSSO = "#e05252"
AZZURRO = "#4aa8e0"


def luminanza(colore: str) -> float:
    """Luminanza relativa WCAG di un colore esadecimale."""
    esa = normalizza_colore(colore)
    canali = []
    for componente in (esa[1:3], esa[3:5], esa[5:7]):
        c = int(componente, 16) / 255
        canali.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canali[0] + 0.7152 * canali[1] + 0.0722 * canali[2]


def testo_su(colore: str) -> str:
    """Bianco o nero, quello che si legge meglio su quel fondo.

    Serve per le pastiglie colorate con i colori sociali: una squadra gialla e
    una squadra blu non possono avere lo stesso colore di testo.
    """
    return "#10141c" if luminanza(colore) > 0.42 else "#ffffff"


def con_trasparenza(colore: str, alfa: float) -> str:
    """Da '#rrggbb' a 'rgba(r, g, b, alfa)', per i fondi tenui."""
    esa = normalizza_colore(colore)
    r, g, b = (int(esa[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, alfa)):.2f})"


# --- Foglio di stile --------------------------------------------------------

CSS = f"""
<style>
:root {{
  --fanta-verde: {VERDE};
  --fanta-verde-chiaro: {VERDE_CHIARO};
  --fanta-verde-scuro: {VERDE_SCURO};
  --fanta-fondo: {FONDO};
  --fanta-fondo-alto: {FONDO_ALTO};
  --fanta-superficie: {SUPERFICIE};
  --fanta-superficie-alta: {SUPERFICIE_ALTA};
  --fanta-bordo: {BORDO};
  --fanta-testo: {TESTO};
  --fanta-tenue: {TESTO_TENUE};
  --fanta-ambra: {AMBRA};
  --fanta-rosso: {ROSSO};
  --fanta-azzurro: {AZZURRO};
}}

/* --- respiro generale --------------------------------------------------- */

.block-container {{
  padding-top: 2.2rem;
  padding-bottom: 4rem;
  max-width: 1280px;
}}

h1, h2, h3 {{ letter-spacing: -0.015em; }}
h1 {{ font-weight: 800; }}

/* --- intestazione di pagina --------------------------------------------- */

.fanta-testata {{
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.5rem;
  background:
    radial-gradient(1200px 220px at 12% -40%,
      {con_trasparenza(VERDE, 0.28)}, transparent 70%),
    linear-gradient(135deg, {FONDO_ALTO} 0%, {SUPERFICIE} 100%);
  border: 1px solid var(--fanta-bordo);
}}

/* Le righe del campo: decorazione, ma discreta. */
.fanta-testata::after {{
  content: "";
  position: absolute;
  inset: 0;
  background-image: repeating-linear-gradient(
    90deg, {con_trasparenza(VERDE, 0.05)} 0 2px, transparent 2px 64px);
  pointer-events: none;
}}

.fanta-testata h1 {{
  margin: 0;
  font-size: 1.95rem;
  line-height: 1.15;
  color: var(--fanta-testo);
}}

.fanta-testata p {{
  margin: .45rem 0 0;
  color: var(--fanta-tenue);
  font-size: .96rem;
  max-width: 62ch;
}}

.fanta-occhiello {{
  display: inline-block;
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--fanta-verde-chiaro);
  margin-bottom: .5rem;
}}

/* --- schede -------------------------------------------------------------- */

.fanta-scheda {{
  background: var(--fanta-superficie);
  border: 1px solid var(--fanta-bordo);
  border-radius: 14px;
  padding: 1.1rem 1.25rem;
  height: 100%;
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
}}

.fanta-scheda:hover {{
  transform: translateY(-2px);
  border-color: {con_trasparenza(VERDE, 0.55)};
  box-shadow: 0 10px 28px rgba(0, 0, 0, .35);
}}

.fanta-scheda h4 {{
  margin: 0 0 .35rem;
  font-size: 1.02rem;
  color: var(--fanta-testo);
}}

.fanta-scheda p {{
  margin: 0;
  color: var(--fanta-tenue);
  font-size: .9rem;
  line-height: 1.55;
}}

/* --- riquadro numerico --------------------------------------------------- */

.fanta-dato {{
  background: linear-gradient(160deg,
    var(--fanta-superficie-alta), var(--fanta-superficie));
  border: 1px solid var(--fanta-bordo);
  border-left: 3px solid var(--fanta-verde);
  border-radius: 12px;
  padding: .85rem 1rem;
}}

.fanta-dato .etichetta {{
  font-size: .68rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--fanta-tenue);
}}

.fanta-dato .valore {{
  font-size: 1.65rem;
  font-weight: 800;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  color: var(--fanta-testo);
}}

.fanta-dato .nota {{ font-size: .78rem; color: var(--fanta-tenue); }}
.fanta-dato.ok    {{ border-left-color: var(--fanta-verde); }}
.fanta-dato.avviso {{ border-left-color: var(--fanta-ambra); }}
.fanta-dato.male  {{ border-left-color: var(--fanta-rosso); }}

/* --- pastiglie ----------------------------------------------------------- */

.fanta-pastiglia {{
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .18rem .6rem;
  border-radius: 999px;
  font-size: .76rem;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}}

.fanta-codice {{
  display: inline-block;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: .22em;
  padding: .7rem 1.2rem;
  border-radius: 12px;
  color: var(--fanta-verde-chiaro);
  background: {con_trasparenza(VERDE, 0.1)};
  border: 1px dashed {con_trasparenza(VERDE, 0.5)};
}}

/* --- barra di riempimento ------------------------------------------------ */

.fanta-barra {{
  height: 8px;
  border-radius: 999px;
  background: var(--fanta-superficie-alta);
  overflow: hidden;
  margin-top: .5rem;
}}

.fanta-barra span {{
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--fanta-verde-scuro), var(--fanta-verde-chiaro));
}}

/* --- controlli Streamlit ------------------------------------------------- */

.stButton > button {{
  border-radius: 10px;
  font-weight: 600;
  border: 1px solid var(--fanta-bordo);
  transition: transform .12s ease, border-color .12s ease;
}}

.stButton > button:hover {{
  transform: translateY(-1px);
  border-color: var(--fanta-verde);
}}

.stTabs [data-baseweb="tab-list"] {{
  gap: .35rem;
  border-bottom: 1px solid var(--fanta-bordo);
}}

.stTabs [data-baseweb="tab"] {{
  border-radius: 10px 10px 0 0;
  padding: .5rem 1rem;
  font-weight: 600;
}}

.stTabs [aria-selected="true"] {{
  background: {con_trasparenza(VERDE, 0.14)};
  color: var(--fanta-verde-chiaro);
}}

[data-testid="stMetric"] {{
  background: var(--fanta-superficie);
  border: 1px solid var(--fanta-bordo);
  border-radius: 12px;
  padding: .85rem 1rem;
}}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {FONDO_ALTO}, {FONDO});
  border-right: 1px solid var(--fanta-bordo);
}}

div[data-testid="stExpander"] details {{
  border: 1px solid var(--fanta-bordo);
  border-radius: 12px;
  background: var(--fanta-superficie);
}}

/* Il focus da tastiera deve restare visibile: il tema non lo cancella. */
.stButton > button:focus-visible,
.stTabs [data-baseweb="tab"]:focus-visible {{
  outline: 2px solid var(--fanta-verde-chiaro);
  outline-offset: 2px;
}}

@media (prefers-reduced-motion: reduce) {{
  .fanta-scheda, .stButton > button {{ transition: none; }}
  .fanta-scheda:hover, .stButton > button:hover {{ transform: none; }}
}}
</style>
"""


# --- Frammenti HTML ---------------------------------------------------------


def _scudo(valore: str) -> str:
    """Neutralizza l'HTML nei testi che arrivano dagli utenti.

    Nome squadra, motto e curva li scrivono i partecipanti e finiscono dentro
    `unsafe_allow_html`: senza questa, chi scrive `<script>` come motto lo
    farebbe eseguire agli altri.
    """
    return (
        str(valore)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def testata(titolo: str, sottotitolo: str = "", occhiello: str = "") -> str:
    parti = ['<div class="fanta-testata">']
    if occhiello:
        parti.append(f'<div class="fanta-occhiello">{_scudo(occhiello)}</div>')
    parti.append(f"<h1>{_scudo(titolo)}</h1>")
    if sottotitolo:
        parti.append(f"<p>{_scudo(sottotitolo)}</p>")
    parti.append("</div>")
    return "".join(parti)


def scheda(titolo: str, testo: str, icona: str = "") -> str:
    intestazione = f"{icona} {_scudo(titolo)}" if icona else _scudo(titolo)
    return (
        f'<div class="fanta-scheda"><h4>{intestazione}</h4><p>{_scudo(testo)}</p></div>'
    )


def dato(
    etichetta: str,
    valore: str,
    nota: str = "",
    stato: str = "ok",
    quota: float | None = None,
) -> str:
    """Riquadro con un numero grande. `quota` disegna la barra di riempimento."""
    classe = stato if stato in ("ok", "avviso", "male") else "ok"
    parti = [
        f'<div class="fanta-dato {classe}">',
        f'<div class="etichetta">{_scudo(etichetta)}</div>',
        f'<div class="valore">{_scudo(valore)}</div>',
    ]
    if nota:
        parti.append(f'<div class="nota">{_scudo(nota)}</div>')
    if quota is not None:
        percento = max(0.0, min(1.0, quota)) * 100
        parti.append(
            f'<div class="fanta-barra"><span style="width:{percento:.0f}%"></span></div>'
        )
    parti.append("</div>")
    return "".join(parti)


def pastiglia(testo: str, colore: str = VERDE) -> str:
    """Etichetta colorata. Il colore del testo si calcola dal fondo."""
    fondo = normalizza_colore(colore)
    return (
        f'<span class="fanta-pastiglia" style="background:{fondo};'
        f'color:{testo_su(fondo)}">{_scudo(testo)}</span>'
    )


def pastiglia_squadra(nome: str, primario: str, secondario: str) -> str:
    """Nome squadra nei suoi colori sociali, con il secondario come bordo."""
    fondo = normalizza_colore(primario)
    bordo = normalizza_colore(secondario)
    return (
        f'<span class="fanta-pastiglia" style="background:{fondo};'
        f'color:{testo_su(fondo)};box-shadow:inset 0 0 0 2px {bordo}">'
        f"{_scudo(nome)}</span>"
    )


def codice_invito(codice: str) -> str:
    return f'<div class="fanta-codice">{_scudo(codice)}</div>'
