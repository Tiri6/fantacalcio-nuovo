"""Utenti, password e permessi.

Dieci persone, un presidente. Ognuno vede tutta la lega ma tocca solo la
propria squadra; il presidente ratifica gli scambi e importa i dati.

Le password si conservano come hash scrypt con sale per utente: mai in chiaro,
mai reversibili. Vedi la nota sui limiti in fondo al modulo.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import scrypt

# Parametri scrypt: n=2^14 tiene il costo sotto i ~100ms per verifica, che per
# un login manuale e' impercettibile e per chi tenta a forza bruta e' caro.
COSTO_N = 2**14
COSTO_R = 8
COSTO_P = 1
LUNGHEZZA_CHIAVE = 32
BYTE_SALE = 16

LUNGHEZZA_MINIMA_PASSWORD = 8


class Ruolo(Enum):
    PRESIDENTE = "presidente"
    FANTALLENATORE = "fantallenatore"

    @property
    def etichetta(self) -> str:
        return self.value.capitalize()


class PasswordNonValida(ValueError):
    pass


class UtenteNonValido(ValueError):
    pass


@dataclass(frozen=True)
class Utente:
    """Un partecipante alla lega. `squadra_id` a None = nessuna squadra assegnata."""

    id: int
    nome_utente: str
    nome: str
    ruolo: Ruolo
    squadra_id: int | None = None
    # None = registrato ma non ancora dentro nessuna lega: vede l'onboarding.
    lega_id: int | None = None
    email: str | None = None
    attivo: bool = True

    @property
    def e_presidente(self) -> bool:
        return self.ruolo is Ruolo.PRESIDENTE

    @property
    def ha_lega(self) -> bool:
        return self.lega_id is not None

    @property
    def ha_squadra(self) -> bool:
        return self.squadra_id is not None

    def puo_gestire(self, squadra_id: int | None) -> bool:
        """Il presidente gestisce tutte le squadre, gli altri solo la propria."""
        if not self.attivo:
            return False
        if self.e_presidente:
            return True
        return squadra_id is not None and squadra_id == self.squadra_id

    @property
    def puo_importare(self) -> bool:
        """Import e ratifiche sono prerogativa del presidente (art. 1)."""
        return self.attivo and self.e_presidente


def normalizza_nome_utente(valore: str) -> str:
    """Il nome utente si confronta senza maiuscole e spazi ai bordi."""
    if not isinstance(valore, str) or not valore.strip():
        raise UtenteNonValido("Il nome utente non puo' essere vuoto")
    pulito = valore.strip().lower()
    if len(pulito) < 3:
        raise UtenteNonValido("Il nome utente deve avere almeno 3 caratteri")
    return pulito


def controlla_password(password: str) -> None:
    """Solleva PasswordNonValida se la password e' troppo debole."""
    if not isinstance(password, str) or not password:
        raise PasswordNonValida("La password non puo' essere vuota")
    if len(password) < LUNGHEZZA_MINIMA_PASSWORD:
        raise PasswordNonValida(
            f"La password deve avere almeno {LUNGHEZZA_MINIMA_PASSWORD} caratteri"
        )


def cifra_password(password: str, sale: bytes | None = None) -> tuple[str, str]:
    """Restituisce (hash esadecimale, sale esadecimale)."""
    controlla_password(password)
    sale = sale or secrets.token_bytes(BYTE_SALE)
    digest = scrypt(
        password.encode("utf-8"),
        salt=sale,
        n=COSTO_N,
        r=COSTO_R,
        p=COSTO_P,
        dklen=LUNGHEZZA_CHIAVE,
    )
    return digest.hex(), sale.hex()


def verifica_password(password: str, hash_atteso: str, sale_hex: str) -> bool:
    """Confronto a tempo costante: non rivela quanto era vicina la password."""
    if not password or not hash_atteso or not sale_hex:
        return False
    try:
        sale = bytes.fromhex(sale_hex)
        digest = scrypt(
            password.encode("utf-8"),
            salt=sale,
            n=COSTO_N,
            r=COSTO_R,
            p=COSTO_P,
            dklen=LUNGHEZZA_CHIAVE,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_atteso)


@dataclass(frozen=True)
class Credenziali:
    """Riga della tabella `utenti`: l'utente piu' i segreti."""

    utente: Utente
    hash_password: str
    sale: str

    def corrisponde(self, password: str) -> bool:
        return verifica_password(password, self.hash_password, self.sale)


def crea_credenziali(
    id_: int,
    nome_utente: str,
    nome: str,
    password: str,
    ruolo: Ruolo = Ruolo.FANTALLENATORE,
    squadra_id: int | None = None,
    lega_id: int | None = None,
    email: str | None = None,
) -> Credenziali:
    """Costruisce un utente nuovo, validando nome e password."""
    hash_password, sale = cifra_password(password)
    return Credenziali(
        utente=Utente(
            id=id_,
            nome_utente=normalizza_nome_utente(nome_utente),
            nome=nome.strip() or nome_utente,
            ruolo=ruolo,
            squadra_id=squadra_id,
            lega_id=lega_id,
            email=email,
        ),
        hash_password=hash_password,
        sale=sale,
    )


class NomeUtenteOccupato(UtenteNonValido):
    """Nome utente gia' preso: e' l'unico errore di registrazione da mostrare.

    Al contrario del login, qui *bisogna* dire che il nome esiste: senza,
    chi si registra non saprebbe come sbloccarsi. E' un'asimmetria voluta.
    """


def registra(
    credenziali_esistenti: dict[str, Credenziali],
    id_: int,
    nome_utente: str,
    nome: str,
    password: str,
    conferma: str | None = None,
    email: str | None = None,
    ruolo: Ruolo = Ruolo.FANTALLENATORE,
) -> Credenziali:
    """Registra un utente nuovo, rifiutando i nomi gia' presi.

    La conferma password si controlla qui e non nell'interfaccia: e' una
    regola, non una decorazione della schermata.
    """
    chiave = normalizza_nome_utente(nome_utente)
    if chiave in credenziali_esistenti:
        raise NomeUtenteOccupato(
            f"Il nome utente «{chiave}» e' gia' preso. Scegline un altro."
        )
    if conferma is not None and password != conferma:
        raise PasswordNonValida("Le due password non coincidono")
    return crea_credenziali(
        id_=id_,
        nome_utente=chiave,
        nome=nome,
        password=password,
        ruolo=ruolo,
        email=email,
    )


def entra_in_lega(
    credenziali: Credenziali, lega_id: int, ruolo: Ruolo | None = None
) -> Credenziali:
    """Associa l'utente a una lega, eventualmente promuovendolo ad admin."""
    utente = replace(
        credenziali.utente,
        lega_id=lega_id,
        ruolo=ruolo or credenziali.utente.ruolo,
    )
    return replace(credenziali, utente=utente)


def assegna_squadra(credenziali: Credenziali, squadra_id: int) -> Credenziali:
    return replace(credenziali, utente=replace(credenziali.utente, squadra_id=squadra_id))


def con_nuova_password(credenziali: Credenziali, password: str) -> Credenziali:
    hash_password, sale = cifra_password(password)
    return replace(credenziali, hash_password=hash_password, sale=sale)


def autentica(
    credenziali: dict[str, Credenziali], nome_utente: str, password: str
) -> Utente | None:
    """Restituisce l'utente se le credenziali combaciano, altrimenti None.

    Il messaggio d'errore a monte deve restare generico: dire "utente
    inesistente" rivelerebbe quali nomi utente esistono.
    """
    try:
        chiave = normalizza_nome_utente(nome_utente)
    except UtenteNonValido:
        return None

    trovato = credenziali.get(chiave)
    if trovato is None:
        # Si calcola comunque un hash: senza, il tempo di risposta direbbe
        # se il nome utente esiste.
        verifica_password(password or "x" * 8, "00" * 32, "00" * BYTE_SALE)
        return None

    if not trovato.utente.attivo or not trovato.corrisponde(password):
        return None
    return trovato.utente


# LIMITI, detti chiaramente
# ---------------------------------------------------------------------------
# Questo login e' proporzionato a una lega di dieci amici, non a un servizio
# pubblico. In particolare:
#   - la sessione vive nel session_state di Streamlit: chi ha accesso al server
#     ha accesso alle sessioni;
#   - non c'e' recupero password via email: la reimposta il presidente;
#   - su Streamlit Community Cloud l'indirizzo dell'app e' pubblico, quindi la
#     pagina di login e' raggiungibile da chiunque abbia il link.
# Le password restano comunque protette da scrypt con sale: anche chi ottenesse
# il database non le ricava.
