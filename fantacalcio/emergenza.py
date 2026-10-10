"""Portiere d'emergenza: il Lodo Messina dell'articolo 8.

Se i portieri sotto contratto risultano indisponibili **tutti insieme** —
infortunati e nemmeno in panchina — la squadra puo' pescare un portiere fra
gli svincolati per non scendere in campo senza. Non firma contratto: non pesa
sul monte anni ne' sul Salary Cap, e proprio per questo non passa dal mercato.

Tre cose che il regolamento dice e che qui diventano codice:

- **la scelta e' unica**: un portiere d'emergenza alla volta, non due;
- **dura finche' serve**: appena uno dei portieri di ruolo torna disponibile,
  anche solo in panchina, l'emergenza si chiude;
- **vota col malus** di chi gioca fuori ruolo (Lodo Messina bis). Il malus non
  e' un numero nuovo: e' lo stesso `malus_adattamento` dei parametri, perche'
  il regolamento lo definisce per rinvio («come un giocatore schierato fuori
  ruolo»). Se la lega cambia quello, questo segue.

Il modulo non sa **dove** si leggano le indisponibilita': gliele si passa. Oggi
le segna il presidente guardando Leghe Fantacalcio; se un giorno ci fosse una
API, cambierebbe solo chi riempie quel set, non queste regole.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from .modelli import Giocatore, Rosa
from .regole import ParametriLega


class EmergenzaNonAmmessa(ValueError):
    """L'emergenza non si puo' aprire (o chiudere), e il messaggio dice perche'."""


@dataclass(frozen=True)
class PortiereInRosa:
    """Un portiere sotto contratto e se questa settimana c'e'."""

    id: int
    nome: str
    disponibile: bool


@dataclass(frozen=True)
class StatoEmergenza:
    """Com'e' la porta di una squadra: chi c'e', chi manca, cosa si puo' fare.

    E' la fotografia che serve a decidere, e la stessa che la pagina mostra:
    senza di lei il bottone «attiva» comparirebbe o sparirebbe senza spiegare
    niente a chi lo guarda.
    """

    squadra_id: int
    squadra: str
    portieri: tuple[PortiereInRosa, ...]
    # Chi e' in carica adesso, se c'e'. Il nome e' separato perche' non e' in
    # rosa: l'anagrafica va cercata nel listone, non fra i contratti.
    in_carica_id: int | None = None
    in_carica_nome: str = ""

    @property
    def indisponibili(self) -> tuple[PortiereInRosa, ...]:
        return tuple(p for p in self.portieri if not p.disponibile)

    @property
    def disponibili(self) -> tuple[PortiereInRosa, ...]:
        return tuple(p for p in self.portieri if p.disponibile)

    @property
    def attiva(self) -> bool:
        return self.in_carica_id is not None

    @property
    def tutti_fuori(self) -> bool:
        """Nessun portiere di ruolo disponibile — e almeno uno in rosa.

        La seconda condizione non e' pedanteria: una rosa senza portieri non e'
        in emergenza, e' incompleta, e si sistema al mercato (art. 2).
        """
        return bool(self.portieri) and not self.disponibili

    @property
    def ammessa(self) -> bool:
        """Se adesso si puo' attivare un portiere d'emergenza."""
        return self.tutti_fuori and not self.attiva

    @property
    def va_revocata(self) -> bool:
        """Emergenza aperta mentre un portiere di ruolo e' tornato: va chiusa."""
        return self.attiva and not self.tutti_fuori

    @property
    def motivo(self) -> str:
        """Perche' il sito permette o non permette l'emergenza, in una frase."""
        if not self.portieri:
            return (
                "In rosa non c'e' nessun portiere: non e' un'emergenza, e' una "
                "rosa da completare al mercato (art. 2)."
            )
        if self.va_revocata:
            uno = len(self.disponibili) == 1
            tornati = ", ".join(p.nome for p in self.disponibili)
            return (
                f"{tornati} {'e' if uno else 'sono'} di nuovo "
                f"{'disponibile' if uno else 'disponibili'}: il portiere "
                f"d'emergenza va revocato (art. 8, Lodo Messina)."
            )
        if self.attiva:
            return (
                f"{self.in_carica_nome} e' in porta come portiere d'emergenza: "
                f"vota con il malus del fuori ruolo (Lodo Messina bis)."
            )
        if self.ammessa:
            fuori = ", ".join(p.nome for p in self.indisponibili)
            return (
                f"Tutti i portieri sono indisponibili ({fuori}): si puo' "
                f"pescare un portiere fra gli svincolati."
            )
        uno = len(self.disponibili) == 1
        chi = ", ".join(p.nome for p in self.disponibili)
        return (
            f"{chi} {'e' if uno else 'sono'} ancora "
            f"{'disponibile' if uno else 'disponibili'}: il portiere "
            f"d'emergenza spetta solo a chi li ha indisponibili tutti."
        )


def stato_emergenza(
    rosa: Rosa,
    indisponibili: Collection[int] | None = None,
    in_carica_nome: str = "",
) -> StatoEmergenza:
    """La fotografia della porta, dalla rosa e dagli indisponibili dichiarati.

    `indisponibili` sono id di giocatori: quelli che su Leghe Fantacalcio non
    sono nemmeno in panchina. Chi non e' nell'elenco si considera disponibile,
    che e' l'ipotesi giusta per difetto — l'emergenza e' l'eccezione.

    Lasciandolo fuori si usano quelli che la squadra ha dichiarato e che sono
    scritti nella rosa: e' il caso normale quando si apre una pagina. Passarlo
    serve a chi sta **valutando** una dichiarazione nuova prima di salvarla.
    """
    fuori = set(rosa.portieri_indisponibili if indisponibili is None else indisponibili)
    portieri = tuple(
        PortiereInRosa(id=g.id, nome=g.nome, disponibile=g.id not in fuori)
        for g in sorted(rosa.portieri, key=lambda g: g.nome)
    )
    return StatoEmergenza(
        squadra_id=rosa.squadra.id,
        squadra=rosa.squadra.nome,
        portieri=portieri,
        in_carica_id=rosa.portiere_emergenza_id,
        in_carica_nome=in_carica_nome,
    )


def verifica_attivazione(
    stato: StatoEmergenza, candidato: Giocatore, svincolati: Collection[int]
) -> None:
    """Solleva `EmergenzaNonAmmessa` se quel portiere non si puo' attivare.

    I controlli stanno qui e non nella pagina: nascondere un bottone non e' un
    controllo, e la stessa regola serve all'API e alla vista Streamlit.
    """
    if stato.attiva:
        raise EmergenzaNonAmmessa(
            f"{stato.squadra} ha gia' {stato.in_carica_nome} come portiere "
            f"d'emergenza: la scelta e' unica (art. 8, Lodo Messina). Revoca "
            f"quello prima di cambiarlo."
        )
    if not stato.ammessa:
        raise EmergenzaNonAmmessa(stato.motivo)
    if not candidato.portiere:
        raise EmergenzaNonAmmessa(
            f"{candidato.nome} non e' un portiere: l'emergenza copre la porta, "
            f"non un posto qualsiasi."
        )
    if candidato.id in {p.id for p in stato.portieri}:
        raise EmergenzaNonAmmessa(
            f"{candidato.nome} e' gia' un portiere di questa rosa: il portiere "
            f"d'emergenza si pesca fra gli svincolati."
        )
    if candidato.id not in set(svincolati):
        raise EmergenzaNonAmmessa(
            f"{candidato.nome} non e' svincolato: ha un contratto con una "
            f"squadra della lega, e per averlo serve uno scambio (art. 8)."
        )


def verifica_revoca(stato: StatoEmergenza) -> None:
    """Solleva `EmergenzaNonAmmessa` se non c'e' niente da revocare.

    Revocare **si puo' sempre**, anche con i portieri ancora fuori: e' una
    facolta' del fantallenatore, non un obbligo, e rinunciarci non viola
    nulla. Quel che non si puo' e' revocare quando non c'e' nessuno.
    """
    if not stato.attiva:
        raise EmergenzaNonAmmessa(
            f"{stato.squadra} non ha nessun portiere d'emergenza da revocare."
        )


def malus_emergenza(parametri: ParametriLega) -> float:
    """Il malus del portiere d'emergenza: quello del fuori ruolo, per rinvio.

    Esiste come funzione e non come costante perche' il Lodo Messina bis lo
    definisce rinviando («come un giocatore schierato fuori ruolo»): scriverlo
    a parte vorrebbe dire due numeri da tenere allineati a mano.
    """
    return abs(parametri.malus_adattamento)
