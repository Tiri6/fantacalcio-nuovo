"""Utenti, password e permessi.

Dieci persone, un presidente. Ognuno vede tutta la lega ma tocca solo la
propria squadra; il presidente ratifica gli scambi e importa i dati.

Le password si conservano come hash scrypt con sale per utente: mai in chiaro,
mai reversibili. Vedi la nota sui limiti in fondo al modulo.
"""

from __future__ import annotations

import hmac
import re
import secrets
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from hashlib import scrypt

from .anagrafica import Sesso

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
    # Chi il presidente autorizza a scrivere in bacheca, senza dargli il
    # resto dei suoi poteri: non ratifica scambi e non importa dati.
    EDITOR = "editor"
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
    # `nome` e' il nome proprio; per mostrarlo usa `nome_completo`.
    nome: str
    ruolo: Ruolo
    cognome: str = ""
    # L'email e' obbligatoria in registrazione, ma resta opzionale sul modello:
    # gli account creati prima che lo diventasse non hanno smesso di esistere.
    email: str | None = None
    data_nascita: date | None = None
    sesso: Sesso = Sesso.NON_DICHIARATO
    citta: str = ""
    squadra_preferita: str = ""
    squadra_id: int | None = None
    # None = registrato ma non ancora dentro nessuna lega: vede l'onboarding.
    lega_id: int | None = None
    attivo: bool = True
    # Alzato quando la password l'ha scelta qualcun altro (una reimpostazione):
    # al primo accesso il sito obbliga a sostituirla.
    deve_cambiare_password: bool = False

    @property
    def nome_completo(self) -> str:
        """Come va mostrato: «Marco Tirinato», o solo il nome se manca l'altro."""
        return f"{self.nome} {self.cognome}".strip()

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
    def e_editor(self) -> bool:
        return self.ruolo is Ruolo.EDITOR

    @property
    def puo_importare(self) -> bool:
        """Import e ratifiche sono prerogativa del presidente (art. 1)."""
        return self.attivo and self.e_presidente

    @property
    def puo_scrivere_in_bacheca(self) -> bool:
        """Il presidente e chi lui autorizza. Vedi `bacheca.puo_pubblicare`."""
        return self.attivo and (self.e_presidente or self.e_editor)


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
    # Il codice di recupero e' una seconda password, monouso, che serve solo a
    # rientrare quando la prima si e' dimenticata. Si conserva cifrato come
    # l'altra: chi leggesse il database non se ne fa niente. Vuoto = non ne ha.
    hash_recupero: str = ""
    sale_recupero: str = ""

    def corrisponde(self, password: str) -> bool:
        return verifica_password(password, self.hash_password, self.sale)

    @property
    def ha_codice_recupero(self) -> bool:
        return bool(self.hash_recupero and self.sale_recupero)

    def codice_corrisponde(self, codice: str) -> bool:
        """Se quel codice e' il suo. Chi non ne ha non ne indovina nessuno."""
        if not self.ha_codice_recupero:
            return False
        return verifica_password(
            normalizza_codice_recupero(codice), self.hash_recupero, self.sale_recupero
        )


def crea_credenziali(
    id_: int,
    nome_utente: str,
    nome: str,
    password: str,
    ruolo: Ruolo = Ruolo.FANTALLENATORE,
    squadra_id: int | None = None,
    lega_id: int | None = None,
    email: str | None = None,
    cognome: str = "",
    data_nascita: date | None = None,
    sesso: Sesso = Sesso.NON_DICHIARATO,
    citta: str = "",
    squadra_preferita: str = "",
) -> Credenziali:
    """Costruisce un utente nuovo, validando nome e password."""
    hash_password, sale = cifra_password(password)
    return Credenziali(
        utente=Utente(
            id=id_,
            nome_utente=normalizza_nome_utente(nome_utente),
            nome=nome.strip() or nome_utente,
            cognome=(cognome or "").strip(),
            ruolo=ruolo,
            squadra_id=squadra_id,
            lega_id=lega_id,
            email=email,
            data_nascita=data_nascita,
            sesso=sesso,
            citta=(citta or "").strip(),
            squadra_preferita=(squadra_preferita or "").strip(),
        ),
        hash_password=hash_password,
        sale=sale,
    )


class NomeUtenteOccupato(UtenteNonValido):
    """Nome utente gia' preso: e' l'unico errore di registrazione da mostrare.

    Al contrario del login, qui *bisogna* dire che il nome esiste: senza,
    chi si registra non saprebbe come sbloccarsi. E' un'asimmetria voluta.
    """


class EmailGiaUsata(UtenteNonValido):
    """Due account con la stessa email sono due modi di essere la stessa persona."""


def registra(
    credenziali_esistenti: dict[str, Credenziali],
    id_: int,
    nome_utente: str,
    nome: str,
    password: str,
    conferma: str | None = None,
    email: str | None = None,
    ruolo: Ruolo = Ruolo.FANTALLENATORE,
    cognome: str = "",
    data_nascita: date | None = None,
    sesso: Sesso = Sesso.NON_DICHIARATO,
    citta: str = "",
    squadra_preferita: str = "",
) -> Credenziali:
    """Registra un utente nuovo, rifiutando nomi utente ed email gia' presi.

    L'email e' **obbligatoria**: e' l'unico dato che lega un account a una
    persona reale, e serve a far combaciare chi si iscrive con l'invito che lo
    attende. La conferma password si controlla qui e non nell'interfaccia:
    e' una regola, non una decorazione della schermata.
    """
    from .leghe import normalizza_email

    chiave = normalizza_nome_utente(nome_utente)
    if chiave in credenziali_esistenti:
        raise NomeUtenteOccupato(
            f"Il nome utente «{chiave}» e' gia' preso. Scegline un altro."
        )

    pulita = normalizza_email(email or "")
    gia_usata = {c.utente.email for c in credenziali_esistenti.values() if c.utente.email}
    if pulita in gia_usata:
        raise EmailGiaUsata(
            f"L'indirizzo {pulita} e' gia' registrato. Entra con quell'account, "
            f"oppure fai reimpostare la password al presidente di lega."
        )

    if conferma is not None and password != conferma:
        raise PasswordNonValida("Le due password non coincidono")

    return crea_credenziali(
        id_=id_,
        nome_utente=chiave,
        nome=nome,
        password=password,
        ruolo=ruolo,
        email=pulita,
        cognome=cognome,
        data_nascita=data_nascita,
        sesso=sesso,
        citta=citta,
        squadra_preferita=squadra_preferita,
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


# ---------------------------------------------------------------------------
# Cambio e reimpostazione della password
# ---------------------------------------------------------------------------
#
# Non c'e' recupero via email: l'app non ha un server di posta, e montarne uno
# per una lega di amici non si giustifica. Al suo posto ci sono due strade che
# non richiedono di spedire niente:
#
#   1. chi conosce la propria password se la cambia da solo;
#   2. chi l'ha dimenticata la fa reimpostare a chi amministra, che gli
#      consegna a voce una password temporanea. Al primo accesso il sito
#      obbliga a sostituirla, cosi' quella temporanea vive pochi minuti.
#
# La differenza rispetto al link via email e' che serve fidarsi di chi
# amministra. In una lega di dieci amici e' un requisito gia' soddisfatto.

# Alfabeto senza caratteri confondibili: la password temporanea viene dettata
# a voce o scritta su WhatsApp, e O/0 e I/1 sono il modo classico di sbagliarla.
ALFABETO_TEMPORANEA = "ABCDEFGHJKMNPQRSTWXYZabcdefghjkmnpqrstwxyz23456789"
LUNGHEZZA_TEMPORANEA = 12


class PermessoNegato(PermissionError):
    """Solo chi amministra la lega reimposta le password altrui."""


def genera_password_temporanea() -> str:
    """Password usa e getta per una reimpostazione."""
    return "".join(
        secrets.choice(ALFABETO_TEMPORANEA) for _ in range(LUNGHEZZA_TEMPORANEA)
    )


# Il codice di recupero si legge ad alta voce e si ricopia da uno screenshot:
# niente caratteri che si confondono, e si scrive a gruppi di quattro.
ALFABETO_RECUPERO = "ABCDEFGHJKMNPQRSTWXYZ23456789"
GRUPPI_RECUPERO = 3
LETTERE_PER_GRUPPO = 4


def genera_codice_recupero() -> str:
    """Un codice tipo «H7KP-2MQX-9TBW», da conservare adesso per dopo."""
    gruppi = [
        "".join(secrets.choice(ALFABETO_RECUPERO) for _ in range(LETTERE_PER_GRUPPO))
        for _ in range(GRUPPI_RECUPERO)
    ]
    return "-".join(gruppi)


def normalizza_codice_recupero(valore: str) -> str:
    """Accetta «h7kp 2mqx9tbw» e ne fa «H7KP2MQX9TBW».

    Chi lo ricopia a mano sbaglia i trattini e le maiuscole, non il codice:
    farlo fallire per quello sarebbe solo un dispetto.
    """
    return re.sub(r"[^A-Z0-9]", "", str(valore or "").upper())


def con_codice_recupero(
    credenziali: Credenziali, codice: str | None = None
) -> tuple[Credenziali, str]:
    """Genera un codice di recupero e lo lega all'utente.

    Restituisce anche il codice in chiaro, che e' l'unico momento in cui
    esiste leggibile: da qui in poi resta solo il suo hash, esattamente come
    per la password. Se se ne genera un altro, il precedente smette di valere.
    """
    codice = codice or genera_codice_recupero()
    pulito = normalizza_codice_recupero(codice)
    if len(pulito) < GRUPPI_RECUPERO * LETTERE_PER_GRUPPO:
        raise PasswordNonValida(
            f"Un codice di recupero ha almeno "
            f"{GRUPPI_RECUPERO * LETTERE_PER_GRUPPO} caratteri."
        )
    hash_recupero, sale_recupero = cifra_password(pulito)
    return (
        replace(credenziali, hash_recupero=hash_recupero, sale_recupero=sale_recupero),
        codice,
    )


def recupera_con_codice(
    credenziali: Credenziali,
    codice: str,
    nuova: str,
    conferma: str | None = None,
) -> Credenziali:
    """Rientra con il codice di recupero e sceglie subito una password nuova.

    Il codice **si consuma**: chi rientra ne genera un altro se lo vuole. Un
    codice che resta valido per sempre e' una seconda password che nessuno
    cambia mai.
    """
    if not credenziali.codice_corrisponde(codice):
        raise PasswordNonValida("Il codice di recupero non e' corretto")
    if conferma is not None and nuova != conferma:
        raise PasswordNonValida("Le due password non coincidono")
    controlla_password(nuova)
    aggiornate = con_nuova_password(credenziali, nuova)
    return replace(
        aggiornate,
        hash_recupero="",
        sale_recupero="",
        utente=replace(aggiornate.utente, deve_cambiare_password=False),
    )


def cambia_password(
    credenziali: Credenziali,
    password_attuale: str,
    nuova: str,
    conferma: str | None = None,
) -> Credenziali:
    """Cambio autonomo: serve conoscere la password attuale.

    Richiederla non e' una formalita': senza, chiunque trovasse una sessione
    aperta potrebbe prendersi l'account per sempre.
    """
    if not credenziali.corrisponde(password_attuale):
        raise PasswordNonValida("La password attuale non e' corretta")
    if conferma is not None and nuova != conferma:
        raise PasswordNonValida("Le due password non coincidono")
    controlla_password(nuova)
    if credenziali.corrisponde(nuova):
        raise PasswordNonValida("La password nuova e' uguale a quella attuale")
    aggiornate = con_nuova_password(credenziali, nuova)
    return replace(
        aggiornate,
        utente=replace(aggiornate.utente, deve_cambiare_password=False),
    )


# --- la richiesta di aiuto --------------------------------------------------
#
# Chi ha dimenticato la password e non ha un codice di recupero ha bisogno del
# presidente. Prima doveva scrivergli su WhatsApp e sperare che se lo
# ricordasse; adesso la richiesta resta scritta nel sito, e il presidente la
# vede dov'e' gia' il pulsante per reimpostare.


class StatoRichiesta(Enum):
    APERTA = "aperta"
    EVASA = "evasa"
    ANNULLATA = "annullata"

    @property
    def etichetta(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True)
class RichiestaPassword:
    """Qualcuno dice «non riesco a entrare» e lascia detto chi e'."""

    id: int
    lega_id: int | None
    utente_id: int | None
    nome_utente: str
    chiesta_il: str = ""
    stato: StatoRichiesta = StatoRichiesta.APERTA
    chiusa_il: str = ""
    chiusa_da: int | None = None
    nota: str = ""

    @property
    def aperta(self) -> bool:
        return self.stato is StatoRichiesta.APERTA


def apri_richiesta_password(
    credenziali: dict[str, Credenziali],
    nome_utente: str,
    aperte: list[RichiestaPassword] | None = None,
    quando: str = "",
    prossimo_id: int = 1,
) -> RichiestaPassword | None:
    """Registra la richiesta, se c'e' qualcosa da registrare.

    Torna `None` quando il nome non esiste o ha gia' una richiesta aperta —
    e chi chiama **non deve dirlo**: la pagina risponde sempre allo stesso
    modo, altrimenti si trasforma in un modo comodo per scoprire chi e'
    iscritto.
    """
    nome = normalizza_nome_utente(nome_utente)
    trovato = credenziali.get(nome)
    if trovato is None or not trovato.utente.attivo:
        return None
    if any(r.aperta and r.nome_utente == nome for r in (aperte or [])):
        return None
    return RichiestaPassword(
        id=prossimo_id,
        lega_id=trovato.utente.lega_id,
        utente_id=trovato.utente.id,
        nome_utente=nome,
        chiesta_il=quando,
    )


def chiudi_richiesta(
    richiesta: RichiestaPassword,
    chi: Utente,
    stato: StatoRichiesta = StatoRichiesta.EVASA,
    quando: str = "",
    nota: str = "",
) -> RichiestaPassword:
    """Segna la richiesta come evasa o annullata."""
    return replace(richiesta, stato=stato, chiusa_il=quando, chiusa_da=chi.id, nota=nota)


def puo_reimpostare(chi: Utente | None, bersaglio: Utente | None) -> bool:
    """Chi amministra reimposta le password della propria lega, non di altre."""
    if chi is None or bersaglio is None or not chi.attivo:
        return False
    if not chi.e_presidente:
        return False
    return chi.lega_id is not None and chi.lega_id == bersaglio.lega_id


def reimposta_password(
    credenziali: Credenziali,
    chi_reimposta: Utente,
    password: str | None = None,
) -> tuple[Credenziali, str]:
    """Reimpostazione fatta da chi amministra.

    Restituisce le credenziali nuove **e** la password in chiaro: e' l'unico
    momento in cui esiste leggibile, perche' va consegnata alla persona. Da
    quel momento in poi resta solo l'hash.
    """
    if not puo_reimpostare(chi_reimposta, credenziali.utente):
        raise PermessoNegato(
            "Solo il presidente della lega puo' reimpostare le password."
        )
    temporanea = password or genera_password_temporanea()
    controlla_password(temporanea)
    aggiornate = con_nuova_password(credenziali, temporanea)
    return (
        replace(
            aggiornate,
            utente=replace(aggiornate.utente, deve_cambiare_password=True),
        ),
        temporanea,
    )


# LIMITI, detti chiaramente
# ---------------------------------------------------------------------------
# Questo login e' proporzionato a una lega di dieci amici, non a un servizio
# pubblico. In particolare:
#   - la sessione vive nel session_state di Streamlit: chi ha accesso al server
#     ha accesso alle sessioni;
#   - non c'e' recupero password via email: si rientra con il codice di
#     recupero, oppure chiedendo al presidente, che vede la richiesta nel sito;
#   - su Streamlit Community Cloud l'indirizzo dell'app e' pubblico, quindi la
#     pagina di login e' raggiungibile da chiunque abbia il link.
# Le password restano comunque protette da scrypt con sale: anche chi ottenesse
# il database non le ricava.
#
# Il codice di recupero non ha un contatore di tentativi come il login, e va
# bene cosi': dodici caratteri su un alfabeto di ventinove fanno circa 3*10^17
# combinazioni, e ogni prova costa una verifica scrypt. Indovinarlo a forza
# bruta richiederebbe piu' tempo di quanto duri la lega.
