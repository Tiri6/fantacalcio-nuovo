"""Registro degli scambi: dalla proposta alla ratifica.

Fino a ieri lo scambio si poteva solo simulare. Qui diventa un atto con una
storia: chi l'ha proposto, chi l'ha accettato, quando il presidente l'ha
ratificato e da quale giornata ha effetto (art. 8).

La validazione contro il regolamento resta in `mercato.valida_scambio`: qui si
governa solo il ciclo di vita e la scrittura.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .autenticazione import Utente
from .conformita import Gravita, Violazione
from .mercato import PropostaScambio, applica_scambio, valida_scambio
from .modelli import Rosa
from .regole import ParametriLega


class StatoScambio(Enum):
    PROPOSTO = "proposto"
    ACCETTATO = "accettato"
    RATIFICATO = "ratificato"
    RIFIUTATO = "rifiutato"
    ANNULLATO = "annullato"

    @property
    def etichetta(self) -> str:
        return self.value.capitalize()

    @property
    def aperto(self) -> bool:
        """Uno scambio aperto e' ancora in gioco: si puo' agire su di lui."""
        return self in (StatoScambio.PROPOSTO, StatoScambio.ACCETTATO)


class TransizioneNonAmmessa(Exception):
    """L'operazione non e' consentita in questo stato o a questo utente."""


@dataclass(frozen=True)
class Movimento:
    """Un giocatore che cambia squadra dentro uno scambio."""

    giocatore_id: int
    nome_giocatore: str
    da_squadra_id: int
    a_squadra_id: int
    anni_prima: int
    anni_dopo: int

    @property
    def prolungato(self) -> bool:
        return self.anni_dopo > self.anni_prima


@dataclass(frozen=True)
class Scambio:
    """Uno scambio proposto tra due squadre."""

    id: int
    squadra_a_id: int
    squadra_b_id: int
    proposto_da: int
    stato: StatoScambio
    creato_il: datetime
    movimenti: tuple[Movimento, ...] = ()
    note: str = ""
    aggiornato_il: datetime | None = None
    deciso_da: int | None = None
    ratificato_da: int | None = None
    giornata_efficacia: int | None = None

    @property
    def squadre(self) -> tuple[int, int]:
        return (self.squadra_a_id, self.squadra_b_id)

    def coinvolge(self, squadra_id: int | None) -> bool:
        return squadra_id in self.squadre

    def altra_squadra(self, squadra_id: int) -> int:
        if squadra_id == self.squadra_a_id:
            return self.squadra_b_id
        if squadra_id == self.squadra_b_id:
            return self.squadra_a_id
        raise ValueError(f"La squadra {squadra_id} non fa parte dello scambio")

    def in_uscita_da(self, squadra_id: int) -> tuple[Movimento, ...]:
        return tuple(m for m in self.movimenti if m.da_squadra_id == squadra_id)

    def a_proposta(self) -> PropostaScambio:
        """Riconverte lo scambio nella forma che sa validare `mercato`."""
        return PropostaScambio(
            da_squadra_a=tuple(
                m.giocatore_id
                for m in self.movimenti
                if m.da_squadra_id == self.squadra_a_id
            ),
            da_squadra_b=tuple(
                m.giocatore_id
                for m in self.movimenti
                if m.da_squadra_id == self.squadra_b_id
            ),
            prolungamenti={
                m.giocatore_id: m.anni_dopo for m in self.movimenti if m.prolungato
            },
        )


# ---------------------------------------------------------------------------
# Ciclo di vita
# ---------------------------------------------------------------------------


def costruisci_movimenti(
    rosa_a: Rosa, rosa_b: Rosa, proposta: PropostaScambio
) -> tuple[Movimento, ...]:
    """Espande la proposta nei movimenti da registrare."""
    movimenti: list[Movimento] = []
    for giocatori, origine, destinazione in (
        (proposta.da_squadra_a, rosa_a, rosa_b),
        (proposta.da_squadra_b, rosa_b, rosa_a),
    ):
        for giocatore_id in giocatori:
            contratto = origine.contratto_di(giocatore_id)
            if contratto is None:
                raise ValueError(
                    f"{origine.squadra.nome} non ha in rosa il giocatore {giocatore_id}"
                )
            movimenti.append(
                Movimento(
                    giocatore_id=giocatore_id,
                    nome_giocatore=origine.giocatore(giocatore_id).nome,
                    da_squadra_id=origine.squadra.id,
                    a_squadra_id=destinazione.squadra.id,
                    anni_prima=contratto.anni_residui,
                    anni_dopo=proposta.prolungamenti.get(
                        giocatore_id, contratto.anni_residui
                    ),
                )
            )
    return tuple(movimenti)


def proponi(
    identificativo: int,
    rosa_a: Rosa,
    rosa_b: Rosa,
    proposta: PropostaScambio,
    utente: Utente,
    stagione: str,
    quando: datetime | None = None,
    note: str = "",
    parametri: ParametriLega | None = None,
) -> tuple[Scambio, list[Violazione]]:
    """Crea la proposta e la valida. Le violazioni bloccanti impediscono l'invio.

    Restituisce comunque lo scambio, cosi' la pagina puo' mostrare *cosa* non
    va senza perdere quello che l'utente aveva composto.
    """
    if not utente.puo_gestire(rosa_a.squadra.id):
        raise TransizioneNonAmmessa(
            f"{utente.nome} non puo' proporre scambi per {rosa_a.squadra.nome}"
        )

    violazioni = valida_scambio(rosa_a, rosa_b, proposta, stagione, parametri)
    movimenti = costruisci_movimenti(rosa_a, rosa_b, proposta)

    scambio = Scambio(
        id=identificativo,
        squadra_a_id=rosa_a.squadra.id,
        squadra_b_id=rosa_b.squadra.id,
        proposto_da=utente.id,
        stato=StatoScambio.PROPOSTO,
        creato_il=quando or datetime.now(),
        movimenti=movimenti,
        note=note.strip(),
    )
    return scambio, violazioni


def _esigi_stato(scambio: Scambio, ammessi: tuple[StatoScambio, ...], azione: str):
    if scambio.stato not in ammessi:
        raise TransizioneNonAmmessa(
            f"Non si puo' {azione} uno scambio nello stato «{scambio.stato.etichetta}»"
        )


def accetta(scambio: Scambio, utente: Utente, quando: datetime | None = None) -> Scambio:
    """La squadra che riceve la proposta la accetta."""
    _esigi_stato(scambio, (StatoScambio.PROPOSTO,), "accettare")
    if not utente.e_presidente and not utente.puo_gestire(scambio.squadra_b_id):
        raise TransizioneNonAmmessa(
            "Solo la squadra che ha ricevuto la proposta puo' accettarla"
        )
    return replace(
        scambio,
        stato=StatoScambio.ACCETTATO,
        deciso_da=utente.id,
        aggiornato_il=quando or datetime.now(),
    )


def rifiuta(scambio: Scambio, utente: Utente, quando: datetime | None = None) -> Scambio:
    _esigi_stato(scambio, (StatoScambio.PROPOSTO,), "rifiutare")
    if not utente.e_presidente and not utente.puo_gestire(scambio.squadra_b_id):
        raise TransizioneNonAmmessa(
            "Solo la squadra che ha ricevuto la proposta puo' rifiutarla"
        )
    return replace(
        scambio,
        stato=StatoScambio.RIFIUTATO,
        deciso_da=utente.id,
        aggiornato_il=quando or datetime.now(),
    )


def annulla(scambio: Scambio, utente: Utente, quando: datetime | None = None) -> Scambio:
    """Il proponente ritira la proposta finche' non e' ratificata."""
    _esigi_stato(scambio, (StatoScambio.PROPOSTO, StatoScambio.ACCETTATO), "annullare")
    if not utente.e_presidente and not utente.puo_gestire(scambio.squadra_a_id):
        raise TransizioneNonAmmessa("Solo chi ha proposto lo scambio puo' ritirarlo")
    return replace(
        scambio,
        stato=StatoScambio.ANNULLATO,
        deciso_da=utente.id,
        aggiornato_il=quando or datetime.now(),
    )


def giornata_di_efficacia(
    scambio: Scambio,
    prossima_giornata: int,
    inizio_prossima_giornata: datetime | None,
    parametri: ParametriLega | None = None,
) -> int:
    """Articolo 8: serve un preavviso di 24 ore sull'inizio della giornata.

    Se la proposta e' stata comunicata piu' tardi, lo scambio non vale per la
    giornata imminente ma da quella successiva.
    """
    from .mercato import scambio_ratificabile

    if inizio_prossima_giornata is None:
        return prossima_giornata
    if scambio_ratificabile(scambio.creato_il, inizio_prossima_giornata, parametri):
        return prossima_giornata
    return prossima_giornata + 1


def ratifica(
    scambio: Scambio,
    rosa_a: Rosa,
    rosa_b: Rosa,
    utente: Utente,
    stagione: str,
    giornata_efficacia: int | None = None,
    quando: datetime | None = None,
    parametri: ParametriLega | None = None,
) -> tuple[Scambio, Rosa, Rosa]:
    """Il presidente ratifica: si ri-valida e si applicano le rose.

    La ri-validazione non e' pignoleria: tra la proposta e la ratifica le rose
    possono essere cambiate (un altro scambio, uno svincolo), e uno scambio
    valido ieri puo' non esserlo piu' oggi.
    """
    _esigi_stato(scambio, (StatoScambio.ACCETTATO,), "ratificare")
    if not utente.puo_importare:
        raise TransizioneNonAmmessa("Solo il presidente puo' ratificare uno scambio")

    proposta = scambio.a_proposta()
    violazioni = valida_scambio(rosa_a, rosa_b, proposta, stagione, parametri)
    bloccanti = [v for v in violazioni if v.gravita is Gravita.BLOCCO]
    if bloccanti:
        raise TransizioneNonAmmessa(
            "Lo scambio non e' piu' valido: " + "; ".join(v.messaggio for v in bloccanti)
        )

    nuova_a, nuova_b = applica_scambio(rosa_a, rosa_b, proposta, stagione)
    ratificato = replace(
        scambio,
        stato=StatoScambio.RATIFICATO,
        ratificato_da=utente.id,
        aggiornato_il=quando or datetime.now(),
        giornata_efficacia=giornata_efficacia,
    )
    return ratificato, nuova_a, nuova_b


# ---------------------------------------------------------------------------
# Persistenza
# ---------------------------------------------------------------------------


def _testo_data(valore: datetime | None) -> str | None:
    return valore.isoformat(timespec="seconds") if valore else None


def salva_scambio(arch, scambio: Scambio) -> None:
    """Scrive lo scambio e i suoi movimenti."""
    arch.scrivi(
        "scambi",
        [
            {
                "id": scambio.id,
                "squadra_a_id": scambio.squadra_a_id,
                "squadra_b_id": scambio.squadra_b_id,
                "proposto_da": scambio.proposto_da,
                "stato": scambio.stato.value,
                "note": scambio.note,
                "creato_il": _testo_data(scambio.creato_il),
                "aggiornato_il": _testo_data(scambio.aggiornato_il),
                "deciso_da": scambio.deciso_da,
                "ratificato_da": scambio.ratificato_da,
                "giornata_efficacia": scambio.giornata_efficacia,
            }
        ],
        chiave="id",
    )
    if scambio.movimenti:
        arch.scrivi(
            "scambi_movimenti",
            [
                {
                    "id": scambio.id * 1000 + indice,
                    "scambio_id": scambio.id,
                    "giocatore_id": m.giocatore_id,
                    "nome_giocatore": m.nome_giocatore,
                    "da_squadra_id": m.da_squadra_id,
                    "a_squadra_id": m.a_squadra_id,
                    "anni_prima": m.anni_prima,
                    "anni_dopo": m.anni_dopo,
                }
                for indice, m in enumerate(scambio.movimenti)
            ],
            chiave="id",
        )


def carica_scambi(arch) -> list[Scambio]:
    """Tutti gli scambi registrati, dal piu' recente."""
    import pandas as pd

    righe = arch.tabella("scambi")
    if righe.empty:
        return []

    movimenti_df = arch.tabella("scambi_movimenti")
    per_scambio: dict[int, list[Movimento]] = {}
    if not movimenti_df.empty:
        for _, m in movimenti_df.iterrows():
            per_scambio.setdefault(int(m["scambio_id"]), []).append(
                Movimento(
                    giocatore_id=int(m["giocatore_id"]),
                    nome_giocatore=str(m["nome_giocatore"]),
                    da_squadra_id=int(m["da_squadra_id"]),
                    a_squadra_id=int(m["a_squadra_id"]),
                    anni_prima=int(m["anni_prima"]),
                    anni_dopo=int(m["anni_dopo"]),
                )
            )

    def data(valore) -> datetime | None:
        if valore is None or pd.isna(valore):
            return None
        return datetime.fromisoformat(str(valore))

    def intero(valore) -> int | None:
        return None if valore is None or pd.isna(valore) else int(valore)

    scambi = [
        Scambio(
            id=int(r["id"]),
            squadra_a_id=int(r["squadra_a_id"]),
            squadra_b_id=int(r["squadra_b_id"]),
            proposto_da=int(r["proposto_da"]),
            stato=StatoScambio(str(r["stato"])),
            creato_il=data(r["creato_il"]) or datetime.min,
            movimenti=tuple(per_scambio.get(int(r["id"]), ())),
            note=str(r["note"]) if r["note"] and not pd.isna(r["note"]) else "",
            aggiornato_il=data(r["aggiornato_il"]),
            deciso_da=intero(r["deciso_da"]),
            ratificato_da=intero(r["ratificato_da"]),
            giornata_efficacia=intero(r["giornata_efficacia"]),
        )
        for _, r in righe.iterrows()
    ]
    return sorted(scambi, key=lambda s: (s.creato_il, s.id), reverse=True)


def applica_alle_rose(arch, nuova_a: Rosa, nuova_b: Rosa) -> None:
    """Riscrive i contratti delle due squadre dopo una ratifica."""
    righe = [
        {
            "giocatore_id": c.giocatore_id,
            "squadra_id": rosa.squadra.id,
            "anni_residui": c.anni_residui,
            "prolungato": int(c.prolungato),
            "stagione_prolungamento": c.stagione_prolungamento,
        }
        for rosa in (nuova_a, nuova_b)
        for c in rosa.contratti
    ]
    arch.scrivi("contratti", righe, chiave="giocatore_id")
