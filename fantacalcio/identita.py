"""Identita' di una squadra: colori sociali, maglia, logo, stadio, motto.

La maglia si disegna dai colori sociali invece di richiedere un file: cosi'
ogni squadra ne ha una fin dal primo giorno, e chi vuole puo' comunque
caricare un'immagine propria.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from enum import Enum

ESAGONALE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Un logo o una maglia caricati non devono gonfiare il database: sono
# immagini da mostrare a 200px, non da stampare.
PESO_MASSIMO_IMMAGINE = 512 * 1024  # 512 KB
TIPI_IMMAGINE = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")


class StileMaglia(Enum):
    """Come si combinano i due colori sociali sulla maglia."""

    TINTA_UNITA = "Tinta unita"
    STRISCE = "Strisce verticali"
    BANDE = "Bande orizzontali"
    META = "Meta' e meta'"
    BANDA_TRASVERSALE = "Banda trasversale"


class ColoreNonValido(ValueError):
    pass


class ImmagineNonValida(ValueError):
    pass


def normalizza_colore(valore: str, campo: str = "colore") -> str:
    """Accetta '#abc', '#aabbcc' o 'aabbcc' e restituisce sempre '#aabbcc'."""
    if not isinstance(valore, str) or not valore.strip():
        raise ColoreNonValido(f"Il {campo} non puo' essere vuoto")

    pulito = valore.strip()
    if not pulito.startswith("#"):
        pulito = f"#{pulito}"
    if not ESAGONALE.match(pulito):
        raise ColoreNonValido(
            f"Il {campo} '{valore}' non e' un colore esadecimale valido "
            f"(atteso #rgb o #rrggbb)"
        )

    if len(pulito) == 4:  # #abc -> #aabbcc
        pulito = "#" + "".join(c * 2 for c in pulito[1:])
    return pulito.lower()


def contrasto_sufficiente(primario: str, secondario: str) -> bool:
    """Due colori troppo simili rendono la maglia illeggibile da lontano.

    Usa la differenza di luminanza relativa (WCAG): sotto 1.6 le strisce non
    si distinguono in un elenco di dieci squadre.
    """

    def luminanza(colore: str) -> float:
        r, g, b = (int(colore[i : i + 2], 16) / 255 for i in (1, 3, 5))
        canali = []
        for c in (r, g, b):
            canali.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * canali[0] + 0.7152 * canali[1] + 0.0722 * canali[2]

    a = luminanza(normalizza_colore(primario))
    b = luminanza(normalizza_colore(secondario))
    chiaro, scuro = max(a, b), min(a, b)
    return (chiaro + 0.05) / (scuro + 0.05) >= 1.6


@dataclass(frozen=True)
class IdentitaSquadra:
    """Tutto cio' che identifica una squadra oltre al nome."""

    presidente: str = ""
    motto: str = ""
    stadio: str = ""
    citta: str = ""
    curva: str = ""
    colore_primario: str = "#2e7d32"
    colore_secondario: str = "#ffffff"
    stile_maglia: StileMaglia = StileMaglia.TINTA_UNITA
    logo: str | None = None
    maglia_caricata: str | None = None
    anno_fondazione: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "colore_primario",
            normalizza_colore(self.colore_primario, "colore primario"),
        )
        object.__setattr__(
            self,
            "colore_secondario",
            normalizza_colore(self.colore_secondario, "colore secondario"),
        )

    @property
    def colori_distinguibili(self) -> bool:
        return contrasto_sufficiente(self.colore_primario, self.colore_secondario)

    def maglia(self, larghezza: int = 180) -> str:
        """La maglia da mostrare: quella caricata se c'e', altrimenti disegnata."""
        if self.maglia_caricata:
            return self.maglia_caricata
        return maglia_svg(
            self.colore_primario,
            self.colore_secondario,
            self.stile_maglia,
            larghezza,
        )


# ---------------------------------------------------------------------------
# Disegno della maglia
# ---------------------------------------------------------------------------

# Sagoma di una maglia da calcio: corpo con collo a V e due maniche.
_SAGOMA = (
    "M60,18 L92,8 A28,28 0 0,0 148,8 L180,18 "
    "L196,66 L166,78 L166,196 A6,6 0 0,1 160,202 "
    "L80,202 A6,6 0 0,1 74,196 L74,78 L44,66 Z"
)


def _riempimento(primario: str, secondario: str, stile: StileMaglia) -> tuple[str, str]:
    """Restituisce (definizioni svg, valore dell'attributo fill)."""
    if stile is StileMaglia.TINTA_UNITA:
        return "", primario

    if stile is StileMaglia.STRISCE:
        definizione = (
            '<pattern id="riempimento" width="32" height="8" '
            'patternUnits="userSpaceOnUse">'
            f'<rect width="16" height="8" fill="{primario}"/>'
            f'<rect x="16" width="16" height="8" fill="{secondario}"/>'
            "</pattern>"
        )
        return definizione, "url(#riempimento)"

    if stile is StileMaglia.BANDE:
        definizione = (
            '<pattern id="riempimento" width="8" height="44" '
            'patternUnits="userSpaceOnUse">'
            f'<rect width="8" height="22" fill="{primario}"/>'
            f'<rect y="22" width="8" height="22" fill="{secondario}"/>'
            "</pattern>"
        )
        return definizione, "url(#riempimento)"

    if stile is StileMaglia.META:
        definizione = (
            '<linearGradient id="riempimento" x1="0" x2="1" y1="0" y2="0">'
            f'<stop offset="50%" stop-color="{primario}"/>'
            f'<stop offset="50%" stop-color="{secondario}"/>'
            "</linearGradient>"
        )
        return definizione, "url(#riempimento)"

    # Banda trasversale
    definizione = (
        '<linearGradient id="riempimento" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="38%" stop-color="{primario}"/>'
        f'<stop offset="38%" stop-color="{secondario}"/>'
        f'<stop offset="62%" stop-color="{secondario}"/>'
        f'<stop offset="62%" stop-color="{primario}"/>'
        "</linearGradient>"
    )
    return definizione, "url(#riempimento)"


def maglia_svg(
    colore_primario: str,
    colore_secondario: str,
    stile: StileMaglia = StileMaglia.TINTA_UNITA,
    larghezza: int = 180,
    numero: str = "",
) -> str:
    """SVG della maglia, come stringa pronta da incorporare nella pagina."""
    primario = normalizza_colore(colore_primario, "colore primario")
    secondario = normalizza_colore(colore_secondario, "colore secondario")
    definizioni, riempimento = _riempimento(primario, secondario, stile)

    # Collo e bordo manica prendono sempre il colore opposto al corpo, cosi'
    # restano visibili anche sulla tinta unita.
    dettaglio = secondario if stile is StileMaglia.TINTA_UNITA else primario
    altezza = int(larghezza * 220 / 240)

    testo = ""
    if numero:
        testo = (
            f'<text x="120" y="150" text-anchor="middle" font-size="64" '
            f'font-family="Helvetica, Arial, sans-serif" font-weight="700" '
            f'fill="{dettaglio}" opacity="0.9">{numero}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 220" '
        f'width="{larghezza}" height="{altezza}" role="img" '
        f'aria-label="Maglia {primario} e {secondario}">'
        f"<defs>{definizioni}</defs>"
        f'<path d="{_SAGOMA}" fill="{riempimento}" stroke="#00000055" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'<path d="M92,8 A28,28 0 0,0 148,8" fill="none" stroke="{dettaglio}" '
        f'stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M44,66 L60,18" fill="none" stroke="{dettaglio}" '
        f'stroke-width="5"/>'
        f'<path d="M196,66 L180,18" fill="none" stroke="{dettaglio}" '
        f'stroke-width="5"/>'
        f"{testo}"
        "</svg>"
    )


def maglia_data_uri(*args, **kwargs) -> str:
    """La maglia come data URI, per usarla dove serve un `src` di immagine."""
    svg = maglia_svg(*args, **kwargs)
    codificato = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{codificato}"


# ---------------------------------------------------------------------------
# Immagini caricate
# ---------------------------------------------------------------------------


def immagine_a_data_uri(contenuto: bytes, tipo_mime: str) -> str:
    """Converte un file caricato in data URI, con i controlli del caso.

    Si tengono le immagini dentro il database invece che su uno storage
    esterno: sono dieci loghi piccoli, e cosi' il backend di demo e quello
    Supabase si comportano allo stesso modo.
    """
    if tipo_mime not in TIPI_IMMAGINE:
        raise ImmagineNonValida(
            f"Formato '{tipo_mime}' non supportato. Ammessi: {', '.join(TIPI_IMMAGINE)}"
        )
    if not contenuto:
        raise ImmagineNonValida("Il file e' vuoto")
    if len(contenuto) > PESO_MASSIMO_IMMAGINE:
        raise ImmagineNonValida(
            f"Immagine di {len(contenuto) // 1024} KB: il massimo e' "
            f"{PESO_MASSIMO_IMMAGINE // 1024} KB. Ridimensionala prima di caricarla."
        )

    codificato = base64.b64encode(contenuto).decode("ascii")
    return f"data:{tipo_mime};base64,{codificato}"
