"""Calcolare una giornata: dai voti al risultato, e da dove arrivano i voti.

Due cose distinte, tenute separate di proposito:

- **leggere i voti**, che oggi entrano da un file o da un copia-incolla, e un
  domani potrebbero arrivare da una fonte in rete senza che cambi altro;
- **calcolare la giornata**, che prende le formazioni salvate, i voti e le
  regole della lega, e scrive gol e punti nel calendario.

Il calcolo non tocca la rete e non importa Streamlit: si prova per intero coi
test, ed e' giusto cosi', perche' e' il pezzo che decide chi vince.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .formazioni import (
    SOSTITUZIONI_MASSIME,
    EsitoPartita,
    Formazione,
    Voto,
    calcola_partita,
)
from .leghe import Bonus, FasciaModificatore, ModalitaSostituzioni
from .regole import ParametriLega


class VotiNonLeggibili(ValueError):
    """Il file dei voti non si lascia leggere, e il messaggio dice perche'."""


# Le colonne accettate, per sinonimi: chi prepara il file non deve indovinare
# la nostra grafia. `voto` vuoto vuol dire senza voto, che non e' zero.
_SINONIMI_VOTI = {
    "giocatore": ("giocatore", "nome", "calciatore", "player", "nomegiocatore"),
    "id": ("id", "idgiocatore", "idufficiale", "playerid"),
    "voto": ("voto", "votobase", "rating", "v"),
    "gol": ("gol", "golfatti", "reti", "goals", "gf"),
    "gol_su_rigore": ("golsurigore", "rigorisegnati", "golrigore"),
    "rigori_sbagliati": ("rigorisbagliati", "rigorifalliti", "errori"),
    "rigori_parati": ("rigoriparati", "parate"),
    "autogol": ("autogol", "autoreti", "og"),
    "assist": ("assist", "assistenze", "ass"),
    "ammonizioni": ("ammonizioni", "gialli", "ammonizione", "cartellinigialli"),
    "espulsioni": ("espulsioni", "rossi", "espulsione", "cartellinirossi"),
    "gol_subiti": ("golsubiti", "gs", "retisubite"),
    "imbattuto": ("imbattuto", "cleansheet", "porta inviolata", "portainviolata"),
}

MODELLO_CSV_VOTI = (
    "giocatore;voto;gol;assist;ammonizioni;espulsioni;gol_subiti\n"
    "Svilar;6.5;0;0;0;0;1\n"
    "Dybala;7;1;1;1;0;0\n"
    "Barella;;0;0;0;0;0\n"
)


def _chiave(testo: str) -> str:
    import re
    import unicodedata

    senza_accenti = "".join(
        c
        for c in unicodedata.normalize("NFD", str(testo))
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]", "", senza_accenti.lower())


def _mappa_colonne(intestazioni) -> dict[str, str]:
    normalizzate = {_chiave(c): c for c in intestazioni if c}
    trovate: dict[str, str] = {}
    for nostro, sinonimi in _SINONIMI_VOTI.items():
        for sinonimo in sinonimi:
            if _chiave(sinonimo) in normalizzate:
                trovate[nostro] = normalizzate[_chiave(sinonimo)]
                break
    return trovate


def _intero(valore) -> int:
    testo = str(valore or "").strip().replace(",", ".")
    if not testo:
        return 0
    try:
        return int(float(testo))
    except ValueError:
        return 0


def _booleano(valore) -> bool:
    return _chiave(valore) in ("1", "si", "s", "true", "vero", "x", "y", "yes")


@dataclass
class EsitoLetturaVoti:
    """Cosa e' stato letto e cosa non si e' saputo abbinare."""

    voti: list[Voto] = field(default_factory=list)
    non_abbinati: list[str] = field(default_factory=list)
    senza_voto: int = 0

    @property
    def quanti(self) -> int:
        return len(self.voti)


def leggi_voti(
    contenuto: bytes | str,
    giornata: int,
    per_nome: dict[str, int],
    per_id_ufficiale: dict[int, int] | None = None,
) -> EsitoLetturaVoti:
    """Legge i voti di una giornata da un CSV o da una tabella incollata.

    `per_nome` va da nome normalizzato a id interno del giocatore; se il file
    porta l'id ufficiale del listone si usa quello, che e' piu' sicuro di un
    nome. Chi non si abbina finisce in `non_abbinati` invece di sparire: un
    voto perso in silenzio e' un punteggio sbagliato che nessuno spiega.
    """
    import csv
    import io

    from .importazione import normalizza_nome_giocatore

    testo = (
        contenuto.decode("utf-8-sig", "replace")
        if isinstance(contenuto, bytes)
        else contenuto
    )
    if not testo.strip():
        raise VotiNonLeggibili("Il file dei voti e' vuoto.")

    prima = testo.splitlines()[0]
    conteggi = {c: prima.count(c) for c in ("\t", ";", ",")}
    separatore = max(conteggi, key=lambda c: conteggi[c])
    if not conteggi[separatore]:
        separatore = ";"

    righe = list(csv.DictReader(io.StringIO(testo), delimiter=separatore))
    if not righe:
        raise VotiNonLeggibili(
            "Il file dei voti non ha righe sotto l'intestazione — o non e' un "
            "CSV. Servono almeno le colonne «giocatore» e «voto»."
        )

    colonne = _mappa_colonne(righe[0].keys())
    if "voto" not in colonne or not ({"giocatore", "id"} & set(colonne)):
        lette = ", ".join(c for c in righe[0] if isinstance(c, str) and c.strip())
        raise VotiNonLeggibili(
            "Nel file dei voti servono la colonna del voto e una che dica di "
            f"chi e' (giocatore o id). Intestazioni lette: {lette or '(nessuna)'}."
        )

    esito = EsitoLetturaVoti()
    per_id_ufficiale = per_id_ufficiale or {}
    for riga in righe:

        def campo(nome: str, riga=riga) -> str:
            colonna = colonne.get(nome)
            return str(riga.get(colonna, "") or "").strip() if colonna else ""

        nome = campo("giocatore")
        identificativo = None
        if "id" in colonne and campo("id"):
            identificativo = per_id_ufficiale.get(_intero(campo("id")))
        if identificativo is None and nome:
            identificativo = per_nome.get(normalizza_nome_giocatore(nome))
        if identificativo is None:
            if nome or campo("id"):
                esito.non_abbinati.append(nome or campo("id"))
            continue

        grezzo = campo("voto").replace(",", ".")
        voto = None
        if grezzo:
            try:
                voto = float(grezzo)
            except ValueError:
                voto = None
        if voto is None:
            esito.senza_voto += 1

        esito.voti.append(
            Voto(
                giocatore_id=identificativo,
                giornata=giornata,
                voto=voto,
                gol=_intero(campo("gol")),
                gol_su_rigore=_intero(campo("gol_su_rigore")),
                rigori_sbagliati=_intero(campo("rigori_sbagliati")),
                rigori_parati=_intero(campo("rigori_parati")),
                autogol=_intero(campo("autogol")),
                assist=_intero(campo("assist")),
                ammonizioni=_intero(campo("ammonizioni")),
                espulsioni=_intero(campo("espulsioni")),
                gol_subiti=_intero(campo("gol_subiti")),
                imbattuto=_booleano(campo("imbattuto")),
            )
        )

    if not esito.voti:
        raise VotiNonLeggibili(
            "Nessuna riga abbinata a un giocatore in rosa. Controlla i nomi, "
            "oppure metti nel file la colonna «id» del listone."
        )
    return esito


# --- il calcolo -------------------------------------------------------------


@dataclass
class RisultatoPartita:
    """Una partita calcolata, pronta da scrivere e da mostrare."""

    partita_id: int
    casa_id: int
    trasferta_id: int
    esito: EsitoPartita
    saltata: str = ""

    @property
    def calcolata(self) -> bool:
        return not self.saltata


@dataclass
class EsitoGiornata:
    """Il conto di una giornata intera."""

    giornata: int
    risultati: list[RisultatoPartita] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)

    @property
    def calcolate(self) -> int:
        return sum(1 for r in self.risultati if r.calcolata)


def calcola_giornata(
    giornata: int,
    partite: list[dict],
    formazioni: dict[int, Formazione],
    voti: dict[int, Voto],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    parametri: ParametriLega,
    bonus: Bonus | None = None,
    fasce_difesa: tuple[FasciaModificatore, ...] = (),
    sostituzioni_massime: int = SOSTITUZIONI_MASSIME,
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
) -> EsitoGiornata:
    """Calcola tutte le partite di una giornata, saltando quelle che non si puo'.

    Una squadra senza formazione non fa perdere l'intera giornata: si salta
    quella partita e lo si dice. Il presidente sistema e ricalcola, invece di
    trovarsi davanti un errore unico che non dice quale squadra manca.
    """
    esito = EsitoGiornata(giornata=giornata)
    if not voti:
        esito.avvisi.append(
            "Non ci sono voti per questa giornata: prima si caricano i voti, "
            "poi si calcola."
        )
        return esito

    for partita in partite:
        casa_id = int(partita["casa_id"])
        trasferta_id = int(partita["trasferta_id"])
        mancanti = [s for s in (casa_id, trasferta_id) if s not in formazioni]
        if mancanti:
            esito.risultati.append(
                RisultatoPartita(
                    partita_id=int(partita["id"]),
                    casa_id=casa_id,
                    trasferta_id=trasferta_id,
                    esito=None,  # type: ignore[arg-type]
                    saltata=(
                        f"{len(mancanti)} squadr"
                        + ("a" if len(mancanti) == 1 else "e")
                        + " senza formazione salvata"
                    ),
                )
            )
            continue

        esito.risultati.append(
            RisultatoPartita(
                partita_id=int(partita["id"]),
                casa_id=casa_id,
                trasferta_id=trasferta_id,
                esito=calcola_partita(
                    formazioni[casa_id],
                    formazioni[trasferta_id],
                    voti,
                    ruoli_per_giocatore,
                    parametri,
                    bonus,
                    fasce_difesa,
                    sostituzioni_massime,
                    modalita,
                ),
            )
        )
    return esito
