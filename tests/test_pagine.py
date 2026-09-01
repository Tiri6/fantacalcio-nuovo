"""Le pagine del menu esistono e si compilano.

Non e' un test dell'interfaccia — quello lo si fa col browser — ma dei due
guasti che con Streamlit si scoprono solo aprendo il sito: una voce di menu
che punta a un file che non c'e', e un errore di sintassi in una pagina che
nessun altro test importa.
"""

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
VISTE = RADICE / "viste"


def pagine_dichiarate() -> list[str]:
    testo = (RADICE / "app.py").read_text(encoding="utf-8")
    return re.findall(r'st\.Page\(\s*"([^"]+)"', testo)


def test_il_menu_dichiara_delle_pagine():
    assert len(pagine_dichiarate()) > 10


def test_ogni_voce_di_menu_punta_a_un_file_che_esiste():
    mancanti = [p for p in pagine_dichiarate() if not (RADICE / p).is_file()]
    assert mancanti == []


def test_le_pagine_della_settimana_sono_nel_menu():
    # Formazione e Giornata sono la funzione base: se sparissero dal menu il
    # sito resterebbe pieno di tabelle e senza il fantacalcio.
    dichiarate = pagine_dichiarate()
    assert "viste/formazione.py" in dichiarate
    assert "viste/giornata.py" in dichiarate


def test_tutte_le_viste_si_compilano():
    for pagina in sorted(VISTE.glob("*.py")):
        compile(pagina.read_text(encoding="utf-8"), str(pagina), "exec")
