"""Chi sei, fra una richiesta e l'altra.

E' il pezzo che Streamlit regalava e che adesso dobbiamo scrivere. Li' la
sessione viveva nel processo del server (`st.session_state`): il browser non
teneva niente, e ricaricare la pagina buttava fuori. Un front-end React non
ha quel filo, quindi serve qualcosa che il browser riporti a ogni chiamata.

**Un token firmato in un cookie httpOnly**, non in `localStorage`: cosi'
nessun JavaScript della pagina puo' leggerlo, e un XSS non si porta via la
sessione di nessuno.

Dentro il token c'e' **solo il nome utente**, mai l'oggetto `Utente`. E' la
stessa regola che vale per il `session_state` di Streamlit, e per la stessa
ragione: appena uno entra in una lega o fonda la squadra la sua riga cambia,
e un utente congelato al momento del login mostrerebbe lo stato vecchio. Il
token dice *chi*, il database dice *com'e' adesso*.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ALGORITMO = "HS256"

# Quanto dura una sessione. Dieci persone che guardano la propria rosa non
# hanno bisogno di restare dentro per sempre, e una settimana evita di dover
# riscrivere la password ogni volta che si apre il sito.
DURATA = timedelta(days=7)

NOME_COOKIE = "fanta_sessione"


class SegretoMancante(RuntimeError):
    """Senza segreto non si firma niente: meglio fermarsi che firmare col vuoto."""


# Sotto questa lunghezza HMAC-SHA256 perde margine contro chi prova a
# indovinare la chiave (RFC 7518, 3.2). PyJWT lo segnala con un warning: qui
# e' un errore, perche' un warning in produzione non lo legge nessuno.
LUNGHEZZA_MINIMA_SEGRETO = 32


def segreto() -> str:
    """La chiave di firma, da `FANTA_SEGRETO_JWT`.

    Non ha un default: un valore di comodo finirebbe in produzione e
    chiunque lo conosca potrebbe fabbricarsi un token da presidente. Meglio
    che l'app non parta.
    """
    valore = (os.environ.get("FANTA_SEGRETO_JWT") or "").strip()
    if not valore:
        raise SegretoMancante(
            "Manca FANTA_SEGRETO_JWT: senza non si possono firmare le sessioni. "
            'Generane uno con `python -c "import secrets; '
            'print(secrets.token_urlsafe(48))"` e mettilo fra le variabili '
            "d'ambiente."
        )
    if len(valore) < LUNGHEZZA_MINIMA_SEGRETO:
        raise SegretoMancante(
            f"FANTA_SEGRETO_JWT e' lungo {len(valore)} caratteri: ne servono "
            f"almeno {LUNGHEZZA_MINIMA_SEGRETO}. Un segreto corto si indovina, "
            "e chi lo indovina entra da presidente."
        )
    return valore


@dataclass(frozen=True)
class Sessione:
    nome_utente: str
    scade_il: datetime


def crea_token(nome_utente: str, adesso: datetime | None = None) -> str:
    """Firma un token per questo nome utente."""
    adesso = adesso or datetime.now(timezone.utc)
    carico = {
        "sub": nome_utente,
        "iat": int(adesso.timestamp()),
        "exp": int((adesso + DURATA).timestamp()),
    }
    return jwt.encode(carico, segreto(), algorithm=ALGORITMO)


def leggi_token(token: str) -> Sessione | None:
    """La sessione dentro il token, o None se non e' valido.

    Scaduto, firmato con un'altra chiave, manomesso o scritto a caso sono lo
    stesso caso per chi chiama: non sei dentro. Distinguerli nella risposta
    direbbe a chi prova quanto c'e' andato vicino.
    """
    try:
        carico = jwt.decode(token, segreto(), algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None

    nome = carico.get("sub")
    if not isinstance(nome, str) or not nome.strip():
        return None

    return Sessione(
        nome_utente=nome,
        scade_il=datetime.fromtimestamp(carico["exp"], tz=timezone.utc),
    )
