"""Confronta il database con quello che il codice si aspetta.

Serve a trasformare un muro di errori rossi in una frase sola: «manca la
colonna X, incolla questa query». Senza, chi usa il sito vede un messaggio di
PostgREST e non ha modo di sapere che basta un `alter table`.

Non importa Streamlit: produce dati e stringhe, li mostra `viste/lega.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Cosa il codice si aspetta di trovare. Le colonne elencate sono quelle
# **scritte** dall'app: se manca una di queste, un salvataggio fallisce.
ATTESO: dict[str, tuple[str, ...]] = {
    "leghe": ("id", "nome", "codice_invito", "admin_id", "stagione", "opzioni"),
    "inviti": ("id", "lega_id", "email", "codice", "stato"),
    "annunci": (
        "id",
        "lega_id",
        "titolo",
        "testo",
        "tipo",
        "autore_id",
        "autore_nome",
        "giornata",
        "pubblicato",
        "in_evidenza",
    ),
    "squadre": (
        "id",
        "nome",
        "presidente",
        "motto",
        "stadio",
        "citta",
        "curva",
        "colore_primario",
        "colore_secondario",
        "stile_maglia",
        "lega_id",
    ),
    "utenti": (
        "id",
        "nome_utente",
        "nome",
        "hash_password",
        "sale",
        "ruolo",
        "email",
        "squadra_id",
        "lega_id",
        "attivo",
        "deve_cambiare_password",
        "cognome",
        "data_nascita",
        "sesso",
        "citta",
        "squadra_preferita",
    ),
    "giocatori": ("id", "nome", "club", "ruoli", "ingaggio", "nazionalita"),
    "contratti": ("giocatore_id", "squadra_id", "anni_residui"),
    "calendario": ("id", "giornata", "casa_id", "trasferta_id"),
}

# Il tipo con cui ricreare una colonna mancante. Serve a scrivere l'ALTER
# giusto invece di lasciare che se lo inventi chi legge.
TIPI = {
    "citta": "text not null default ''",
    "curva": "text not null default ''",
    "cognome": "text not null default ''",
    "squadra_preferita": "text not null default ''",
    "sesso": "text not null default 'NON_DICHIARATO'",
    "email": "text",
    "data_nascita": "date",
    "lega_id": "bigint",
    "deve_cambiare_password": "boolean not null default false",
    "autore_nome": "text not null default ''",
    "giornata": "integer",
    "pubblicato": "boolean not null default true",
    "in_evidenza": "boolean not null default false",
    "stagione": "text not null default '2026/27'",
    "opzioni": "text not null default '{}'",
}


@dataclass(frozen=True)
class Problema:
    tabella: str
    colonne_mancanti: tuple[str, ...] = ()
    tabella_mancante: bool = False

    @property
    def messaggio(self) -> str:
        if self.tabella_mancante:
            return f"La tabella `{self.tabella}` non esiste."
        elenco = ", ".join(f"`{c}`" for c in self.colonne_mancanti)
        quante = "la colonna" if len(self.colonne_mancanti) == 1 else "le colonne"
        return f"A `{self.tabella}` mancano {quante} {elenco}."


def verifica(arch) -> list[Problema]:
    """Cosa manca, tabella per tabella. Lista vuota = tutto a posto.

    Le colonne si deducono da una riga letta: un backend REST non espone lo
    schema, ma espone i dati. Su una tabella vuota non si puo' dire niente, e
    infatti non si dice: meglio nessun allarme che uno falso.
    """
    problemi: list[Problema] = []
    for tabella, colonne in ATTESO.items():
        try:
            righe = arch.tabella(tabella)
        except Exception:  # noqa: BLE001 - ogni backend segnala a modo suo
            problemi.append(Problema(tabella, tabella_mancante=True))
            continue

        if righe.empty:
            continue  # nessuna riga: le colonne non si possono dedurre

        mancanti = tuple(c for c in colonne if c not in righe.columns)
        if mancanti:
            problemi.append(Problema(tabella, colonne_mancanti=mancanti))
    return problemi


def sql_di_riparazione(problemi: list[Problema]) -> str:
    """La query da incollare nel SQL Editor per rimettere a posto lo schema."""
    if not problemi:
        return ""

    righe: list[str] = []
    tabelle_da_creare = [p.tabella for p in problemi if p.tabella_mancante]
    if tabelle_da_creare:
        righe.append(
            "-- Mancano tabelle intere: incolla il contenuto di db/schema.sql,\n"
            "-- che le crea tutte ed e' rieseguibile senza cancellare niente.\n"
            f"-- Tabelle assenti: {', '.join(tabelle_da_creare)}"
        )

    for problema in problemi:
        if problema.tabella_mancante:
            continue
        for colonna in problema.colonne_mancanti:
            tipo = TIPI.get(colonna, "text")
            righe.append(
                f"alter table {problema.tabella} "
                f"add column if not exists {colonna} {tipo};"
            )

    if any(not p.tabella_mancante for p in problemi):
        righe.append("")
        righe.append("-- I privilegi non si ereditano da soli:")
        righe.append(
            "grant all privileges on all tables in schema public to service_role;"
        )
        righe.append(
            "grant all privileges on all sequences in schema public to service_role;"
        )
    return "\n".join(righe)


def riepilogo(problemi: list[Problema]) -> str:
    if not problemi:
        return "Il database ha tutto quello che il sito si aspetta."
    quante = len(problemi)
    return (
        f"{quante} "
        + ("problema" if quante == 1 else "problemi")
        + " nello schema: "
        + " ".join(p.messaggio for p in problemi)
    )
