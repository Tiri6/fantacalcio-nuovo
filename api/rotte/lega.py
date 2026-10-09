"""Impostazioni della lega: come si entra, chi c'e', con che regole si gioca.

La pagina risponde a due domande — «come si entra qui dentro?» e «con che
regole giochiamo?» — e aggiunge i pochi comandi che servono a chi amministra:
delegare la bacheca, riservare un posto, rimettere in piedi chi non riesce
piu' ad accedere.

**Chi amministra lo decide il dominio**, due volte e in due modi diversi:
`puo_modificare_regole` guarda `admin_id` (chi la lega l'ha creata), mentre
`puo_reimpostare` guarda il ruolo di presidente. Non sono la stessa cosa e
non vanno confuse: il presidente di un'altra lega qui dentro e' un
fantallenatore qualunque.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio import diagnostica
from fantacalcio.autenticazione import (
    PermessoNegato,
    Ruolo,
    StatoRichiesta,
    chiudi_richiesta,
    puo_reimpostare,
    reimposta_password,
)
from fantacalcio.data import (
    carica_credenziali,
    carica_inviti,
    carica_richieste_password,
    carica_rose,
    prossimo_id,
    salva_credenziali,
    salva_invito,
    salva_richiesta_password,
)
from fantacalcio.leghe import (
    EmailNonValida,
    crea_invito,
    moduli_disponibili,
    puo_modificare_regole,
)

from ..contesto import Contesto, contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["lega"])

NON_ELABORABILE = 422

# Chi puo' essere assegnato da qui. Il presidente non e' nell'elenco: non si
# cede la lega con una tendina.
RUOLI_ASSEGNABILI = (Ruolo.FANTALLENATORE, Ruolo.EDITOR)


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Partecipante(BaseModel):
    id: int
    nome_utente: str
    nome_completo: str
    ruolo: str
    ruolo_etichetta: str
    squadra: str
    sono_io: bool


class InvitoLetto(BaseModel):
    email: str
    stato: str


class RichiestaLetta(BaseModel):
    id: int
    nome_utente: str
    chiesta_il: str


class ProblemaSchema(BaseModel):
    messaggio: str


class Voce(BaseModel):
    """Una regola come si legge: etichetta, valore, e una riga di contesto."""

    etichetta: str
    valore: str
    nota: str = ""


class GruppoRegole(BaseModel):
    titolo: str
    voci: list[Voce]


class FasciaGol(BaseModel):
    da: str
    gol: int


class Lega(BaseModel):
    nome: str
    stagione: str
    modalita: str
    # Il codice lo vedono tutti i membri: e' quello che si gira agli amici.
    codice_invito: str
    partecipanti: list[Partecipante]
    posti: int
    squadre_fondate: int
    regole: list[GruppoRegole]
    fasce_gol: list[FasciaGol]
    moduli_ammessi: list[str]
    moduli_possibili: int
    bonus: list[Voce]
    modificatori: list[str]
    spiegazione_sostituzioni: str
    # I due permessi, distinti di proposito: vedi la nota in cima al file.
    posso_amministrare: bool
    posso_cambiare_regole: bool
    posso_reimpostare_password: bool
    inviti: list[InvitoLetto]
    richieste_password: list[RichiestaLetta]
    ruoli_assegnabili: list[dict[str, str]]
    problemi_schema: list[ProblemaSchema]
    sql_di_riparazione: str


def _si(valore: bool) -> str:
    return "Sì" if valore else "No"


def _regole(opzioni) -> list[GruppoRegole]:
    """Le regole raggruppate come su Streamlit: generali, rosa, punteggio.

    Nessun numero si scrive qui: si legge da `OpzioniLega`, che e' il posto
    dove la lega li cambia per votazione.
    """
    if opzioni.limiti_per_ruolo:
        rosa = str(opzioni.rosa_totale) if opzioni.rosa_totale else "—"
        nota_rosa = " · ".join(
            f"{limite if limite is not None else '∞'} {sigla}"
            for limite, sigla in (
                (opzioni.rosa_portieri, "Por"),
                (opzioni.rosa_difensori, "Dif"),
                (opzioni.rosa_centrocampisti, "Cen"),
                (opzioni.rosa_attaccanti, "Att"),
            )
        )
    else:
        rosa, nota_rosa = "Libera", "nessun tetto per ruolo"

    return [
        GruppoRegole(
            titolo="Generali",
            voci=[
                Voce(etichetta="Modalità", valore=opzioni.modalita.etichetta),
                Voce(etichetta="Formato", valore=opzioni.formato.etichetta),
                Voce(etichetta="Giornate", valore=str(opzioni.giornate_totali)),
                Voce(etichetta="Assegnazione", valore=opzioni.tipo_asta.etichetta),
                Voce(
                    etichetta="Punti",
                    valore=f"{opzioni.punti_vittoria} / {opzioni.punti_pareggio}",
                    nota="vittoria / pareggio",
                ),
                Voce(
                    etichetta="Contratti",
                    valore=f"fino a {opzioni.anni_contratto_massimi} anni",
                ),
            ],
        ),
        GruppoRegole(
            titolo="Rosa e formazione",
            voci=[
                Voce(etichetta="Rosa", valore=rosa, nota=nota_rosa),
                Voce(etichetta="Panchinari", valore=str(opzioni.panchinari)),
                Voce(
                    etichetta="Sostituzioni",
                    valore=opzioni.modalita_sostituzioni.etichetta,
                    nota=(
                        f"massimo {opzioni.sostituzioni_massime} a giornata"
                        if opzioni.sostituzioni_automatiche
                        else "non automatiche"
                    ),
                ),
                Voce(
                    etichetta="Capitano",
                    valore=_si(opzioni.capitano),
                    nota="vice attivo" if opzioni.vice_capitano else "",
                ),
                Voce(
                    etichetta="Minimo italiani",
                    valore=str(opzioni.minimo_italiani or "—"),
                    nota="nessun vincolo" if not opzioni.minimo_italiani else "in rosa",
                ),
                Voce(
                    etichetta="Minimo U21 italiani",
                    valore=str(opzioni.minimo_u21_italiani or "—"),
                    nota=(
                        "nessun vincolo"
                        if not opzioni.minimo_u21_italiani
                        else "contano anche come italiani"
                    ),
                ),
                Voce(
                    etichetta="Scambi a stagione",
                    valore=(
                        "Illimitati"
                        if opzioni.scambi_illimitati
                        else str(opzioni.scambi_per_stagione)
                    ),
                    nota="per squadra",
                ),
            ],
        ),
    ]


def _fasce(opzioni) -> list[FasciaGol]:
    return [
        FasciaGol(da=f"{opzioni.soglia_primo_gol + opzioni.passo_gol * n:g}+", gol=n + 1)
        for n in range(6)
    ]


def _bonus(opzioni) -> list[Voce]:
    b = opzioni.bonus
    return [
        Voce(etichetta=nome, valore=f"{valore:+g}" if valore else "0")
        for nome, valore in (
            ("Gol segnato", b.gol_segnato),
            ("Gol subito", b.gol_subito),
            ("Assist", b.assist),
            ("Rigore parato", b.rigore_parato),
            ("Rigore sbagliato", b.rigore_sbagliato),
            ("Autogol", b.autogol),
            ("Ammonizione", b.ammonizione),
            ("Espulsione", b.espulsione),
            ("Portiere imbattuto", b.portiere_imbattuto),
        )
    ]


def _lega_o_422(ctx: Contesto):
    if ctx.lega is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Non sei dentro nessuna lega.",
        )
    return ctx.lega


def _costruisci(utente) -> Lega:
    ctx = contesto_di(utente)
    lega = _lega_o_422(ctx)
    opzioni = lega.opzioni

    rose = carica_rose(ctx.arch)
    nomi_squadra = {id_: r.squadra.nome for id_, r in rose.items()}

    tutte = carica_credenziali(ctx.arch)
    dentro = [c.utente for c in tutte.values() if c.utente.lega_id == lega.id]
    partecipanti = [
        Partecipante(
            id=u.id,
            nome_utente=u.nome_utente,
            nome_completo=u.nome_completo,
            ruolo=u.ruolo.name,
            ruolo_etichetta=u.ruolo.etichetta,
            squadra=nomi_squadra.get(u.squadra_id, "— nessuna —"),
            sono_io=u.id == utente.id,
        )
        for u in sorted(dentro, key=lambda u: u.nome_completo.lower())
    ]

    amministra = utente.id == lega.admin_id or utente.puo_importare
    problemi = diagnostica.verifica(ctx.arch)

    richieste = [
        RichiestaLetta(id=r.id, nome_utente=r.nome_utente, chiesta_il=r.chiesta_il)
        for r in carica_richieste_password(ctx.arch, lega.id)
        if r.aperta
    ]

    modificatori = [
        nome
        for nome, acceso in (
            ("Difesa", opzioni.modificatore_difesa),
            ("Centrocampo", opzioni.modificatore_centrocampo),
            ("Attacco", opzioni.modificatore_attacco),
        )
        if acceso
    ]

    return Lega(
        nome=lega.nome,
        stagione=lega.stagione,
        modalita=opzioni.modalita.etichetta,
        codice_invito=lega.codice_invito,
        partecipanti=partecipanti,
        posti=opzioni.partecipanti,
        squadre_fondate=sum(1 for u in dentro if u.ha_squadra),
        regole=_regole(opzioni),
        fasce_gol=_fasce(opzioni),
        moduli_ammessi=list(opzioni.moduli_ammessi),
        moduli_possibili=len(moduli_disponibili(opzioni.modalita)),
        bonus=_bonus(opzioni),
        modificatori=modificatori,
        spiegazione_sostituzioni=opzioni.modalita_sostituzioni.spiegazione,
        posso_amministrare=amministra,
        posso_cambiare_regole=puo_modificare_regole(utente, lega),
        posso_reimpostare_password=utente.e_presidente,
        inviti=(
            [
                InvitoLetto(email=i.email, stato=i.stato.etichetta)
                for i in carica_inviti(ctx.arch, lega.id)
            ]
            if amministra
            else []
        ),
        richieste_password=richieste if amministra else [],
        ruoli_assegnabili=[
            {"nome": r.name, "etichetta": r.etichetta} for r in RUOLI_ASSEGNABILI
        ],
        problemi_schema=[ProblemaSchema(messaggio=p.messaggio) for p in problemi],
        # Il rimedio lo si da' solo a chi puo' applicarlo: a chiunque altro
        # sarebbe una query da incollare in un posto a cui non ha accesso.
        sql_di_riparazione=(
            diagnostica.sql_di_riparazione(problemi) if problemi and amministra else ""
        ),
    )


@rotte.get("/lega", response_model=Lega)
def lega(utente: UtenteDentro) -> Lega:
    return _costruisci(utente)


class Invitato(BaseModel):
    email: str = Field(min_length=1, max_length=200)


@rotte.post("/lega/inviti", response_model=Lega, status_code=status.HTTP_201_CREATED)
def invita(richiesta: Invitato, utente: UtenteDentro) -> Lega:
    """Riserva un posto a un indirizzo. **Non manda nessuna mail.**

    L'app non ha un server di posta, e montarne uno per dieci persone non si
    giustifica: l'invito registra chi e' atteso, il codice si gira a mano.
    """
    ctx = contesto_di(utente)
    lega_corrente = _lega_o_422(ctx)
    if not (utente.id == lega_corrente.admin_id or utente.puo_importare):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo chi amministra la lega puo' invitare.",
        )

    try:
        invito = crea_invito(
            id_=prossimo_id(ctx.arch, "inviti"),
            lega=lega_corrente,
            email=richiesta.email,
            creato_da=utente.id,
        )
    except EmailNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    if any(i.email == invito.email for i in carica_inviti(ctx.arch, lega_corrente.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{invito.email} e' gia' nella lista degli invitati.",
        )

    salva_invito(ctx.arch, invito)
    return _costruisci(utente)


class CambioRuolo(BaseModel):
    nome_utente: str
    ruolo: str


@rotte.put("/lega/ruoli", response_model=Lega)
def assegna_ruolo(richiesta: CambioRuolo, utente: UtenteDentro) -> Lega:
    """L'editor scrive in bacheca e basta: una delega stretta, non una
    seconda presidenza."""
    ctx = contesto_di(utente)
    lega_corrente = _lega_o_422(ctx)
    if not (utente.id == lega_corrente.admin_id or utente.puo_importare):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo chi amministra la lega puo' cambiare i ruoli.",
        )

    try:
        nuovo = Ruolo[richiesta.ruolo]
    except KeyError:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail=f"Ruolo sconosciuto: {richiesta.ruolo}"
        ) from None
    if nuovo not in RUOLI_ASSEGNABILI:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"«{nuovo.etichetta}» non si assegna da qui.",
        )

    credenziali = carica_credenziali(ctx.arch).get(richiesta.nome_utente)
    if credenziali is None or credenziali.utente.lega_id != lega_corrente.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questo partecipante non e' in questa lega.",
        )
    if credenziali.utente.id == utente.id:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail="Il tuo ruolo non te lo cambi da solo."
        )
    if credenziali.utente.ruolo is Ruolo.PRESIDENTE:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="E' il presidente della lega: il ruolo non si cambia da qui.",
        )

    from dataclasses import replace

    salva_credenziali(
        ctx.arch,
        replace(credenziali, utente=replace(credenziali.utente, ruolo=nuovo)),
    )
    return _costruisci(utente)


class PasswordReimpostata(BaseModel):
    """La password temporanea in chiaro: si vede **una volta sola**."""

    nome_utente: str
    password: str


@rotte.post("/lega/reimposta/{nome_utente}", response_model=PasswordReimpostata)
def reimposta(nome_utente: str, utente: UtenteDentro) -> PasswordReimpostata:
    """Genera una password temporanea e chiude la richiesta aperta.

    Non parte nessuna mail: la password si consegna a voce o in privato. Chi
    la riceve e' obbligato a sostituirla al primo accesso, quindi vive pochi
    minuti.
    """
    ctx = contesto_di(utente)
    lega_corrente = _lega_o_422(ctx)

    credenziali = carica_credenziali(ctx.arch).get(nome_utente)
    if credenziali is None or credenziali.utente.lega_id != lega_corrente.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questo partecipante non e' in questa lega.",
        )
    if not puo_reimpostare(utente, credenziali.utente):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo il presidente della lega puo' reimpostare le password.",
        )

    try:
        aggiornate, temporanea = reimposta_password(credenziali, utente)
    except PermessoNegato as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore

    salva_credenziali(ctx.arch, aggiornate)

    # La richiesta aperta di quella persona si chiude da sola: lasciarla li'
    # vorrebbe dire che il presidente la rivede domani e reimposta due volte.
    for richiesta in carica_richieste_password(ctx.arch, lega_corrente.id):
        if richiesta.aperta and richiesta.nome_utente == credenziali.utente.nome_utente:
            salva_richiesta_password(
                ctx.arch,
                chiudi_richiesta(richiesta, utente, quando=_adesso()),
            )

    return PasswordReimpostata(
        nome_utente=credenziali.utente.nome_utente, password=temporanea
    )


@rotte.delete("/lega/richieste/{richiesta_id}", response_model=Lega)
def annulla_richiesta(richiesta_id: int, utente: UtenteDentro) -> Lega:
    """Archivia una richiesta senza reimpostare niente: capita che chi
    l'ha aperta si ricordi la password da solo."""
    ctx = contesto_di(utente)
    lega_corrente = _lega_o_422(ctx)
    if not utente.e_presidente:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo il presidente puo' archiviare una richiesta.",
        )

    for richiesta in carica_richieste_password(ctx.arch, lega_corrente.id):
        if richiesta.id == richiesta_id and richiesta.aperta:
            salva_richiesta_password(
                ctx.arch,
                chiudi_richiesta(
                    richiesta, utente, StatoRichiesta.ANNULLATA, quando=_adesso()
                ),
            )
            return _costruisci(utente)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Richiesta inesistente."
    )
