"""Nessuna credenziale vera deve finire in un file versionato.

Questo test esiste perche' e' successo: una chiave `service_role` di Supabase
e' stata scritta per errore in `secrets.toml.example`, che e' un modello
tracciato da Git, ed e' finita su GitHub. Toglierla dal file non basta —
resta nella cronologia — quindi va rigenerata. Meglio accorgersene qui.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[1]

# Un JWT ha tre parti separate da punti; quelli di Supabase iniziano per eyJ.
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")

# Sottodominio Supabase reale: 20 lettere minuscole. I segnaposto (IL-TUO-...,
# xxxx) non corrispondono.
URL_SUPABASE = re.compile(r"https://[a-z]{20}\.supabase\.co")

ESTENSIONI_DA_IGNORARE = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".xlsx", ".db"}


def file_versionati() -> list[Path]:
    esito = subprocess.run(
        ["git", "ls-files"],
        cwd=RADICE,
        capture_output=True,
        text=True,
        check=True,
    )
    return [RADICE / riga for riga in esito.stdout.splitlines() if riga]


@pytest.fixture(scope="module")
def tracciati() -> list[Path]:
    return file_versionati()


def test_nessun_token_jwt_nei_file_versionati(tracciati):
    colpevoli = []
    for percorso in tracciati:
        if percorso.suffix.lower() in ESTENSIONI_DA_IGNORARE or not percorso.exists():
            continue
        # Il test stesso contiene le espressioni regolari: si salta.
        if percorso.name == "test_segreti.py":
            continue
        try:
            testo = percorso.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if JWT.search(testo):
            colpevoli.append(percorso.relative_to(RADICE))

    assert not colpevoli, (
        "Token JWT trovati in file versionati: "
        + ", ".join(str(c) for c in colpevoli)
        + ". Se e' una chiave vera, RIGENERALA da Supabase: toglierla dal file "
        "non la toglie dalla cronologia di Git."
    )


def test_nessun_url_supabase_reale_nei_file_versionati(tracciati):
    colpevoli = []
    for percorso in tracciati:
        if percorso.suffix.lower() in ESTENSIONI_DA_IGNORARE or not percorso.exists():
            continue
        if percorso.name == "test_segreti.py":
            continue
        try:
            testo = percorso.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if URL_SUPABASE.search(testo):
            colpevoli.append(percorso.relative_to(RADICE))

    assert not colpevoli, (
        "URL di un progetto Supabase reale in file versionati: "
        + ", ".join(str(c) for c in colpevoli)
    )


def test_il_file_delle_credenziali_vere_non_e_tracciato(tracciati):
    """`secrets.toml` deve restare fuori da Git; il `.example` e' il modello."""
    nomi = {p.name for p in tracciati}
    assert "secrets.toml" not in nomi
    assert "secrets.toml.example" in nomi
