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
        "hash_recupero",
        "sale_recupero",
    ),
    "richieste_password": ("id", "nome_utente", "stato", "chiesta_il"),
    "giocatori": ("id", "nome", "club", "ruoli", "ingaggio", "nazionalita"),
    "contratti": ("giocatore_id", "squadra_id", "anni_residui"),
    "calendario": ("id", "giornata", "casa_id", "trasferta_id", "inizio_previsto"),
    "formazioni": ("id", "squadra_id", "giornata", "competizione", "modulo"),
    "voti": ("id", "giocatore_id", "giornata", "voto"),
    "albo": ("id", "lega_id", "competizione", "stagione", "squadra_nome"),
    "dead_money": ("id", "squadra_id", "importo"),
    "scambi": ("id", "squadra_a_id", "squadra_b_id", "stato"),
    "scambi_movimenti": ("id", "scambio_id", "giocatore_id"),
}

# Da quale file di migrazione nasce ogni tabella. Serve a dire «esegui
# quello», invece di «manca una tabella, arrangiati».
MIGRAZIONE: dict[str, str] = {
    "formazioni": "db/aggiornamento_giornata.sql",
    "voti": "db/aggiornamento_giornata.sql",
    "richieste_password": "db/aggiornamento_recupero_password.sql",
    "annunci": "db/aggiornamento_bacheca.sql",
    "leghe": "db/aggiornamento_leghe.sql",
    "inviti": "db/aggiornamento_leghe.sql",
}


def migrazione_per(tabella: str) -> str:
    """Il file da eseguire per avere quella tabella. Vuoto se non si sa."""
    return MIGRAZIONE.get(tabella, "")


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
    "hash_recupero": "text not null default ''",
    "sale_recupero": "text not null default ''",
    "nome_utente": "text not null default ''",
    "stato": "text not null default 'aperta'",
    "chiesta_il": "text",
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
            dove = migrazione_per(self.tabella)
            return f"La tabella `{self.tabella}` non esiste." + (
                f" La crea `{dove}`." if dove else ""
            )
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

        # Una tabella che non esiste non alza piu' un errore: si legge vuota,
        # cosi' le pagine restano in piedi. Chi l'ha letta pero' se l'e'
        # segnato, ed e' li' che bisogna guardare — altrimenti una tabella
        # assente passerebbe per una tabella semplicemente senza righe, e
        # questa pagina direbbe «tutto a posto» mentre il sito non funziona.
        if tabella in getattr(arch, "assenti", ()):
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
        files = sorted(
            {migrazione_per(t) for t in tabelle_da_creare if migrazione_per(t)}
        )
        righe.append(
            "-- Mancano tabelle intere: incolla il contenuto di db/schema.sql,\n"
            "-- che le crea tutte ed e' rieseguibile senza cancellare niente.\n"
            f"-- Tabelle assenti: {', '.join(tabelle_da_creare)}"
            + (
                "\n-- In alternativa basta il file che le introduce: " + ", ".join(files)
                if files
                else ""
            )
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
