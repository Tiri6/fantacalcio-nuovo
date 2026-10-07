"""L'API che espone il dominio a React.

Sta sopra `fantacalcio/`, non dentro: la logica non deve sapere che esiste un
HTTP, cosi' come non sapeva che esisteva Streamlit. Qui si traduce soltanto —
dal dominio al JSON e ritorno.

**Nessuna regola di gioco vive qui.** Conformita', Mantra, Dead Money, draft
e scambi restano in `fantacalcio/`, con i loro test. Una regola riscritta in
questo strato sarebbe la copia che diverge, e il regolamento tornerebbe a
stare in due posti.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .rotte import (
    accesso,
    albo,
    bacheca,
    campionato,
    cruscotto,
    giocatori,
    identita,
    squadre,
)
from .statici import monta_sito

registro = logging.getLogger("fantacalcio")


@asynccontextmanager
async def avvio(app: FastAPI) -> AsyncIterator[None]:
    """Urla se in produzione sta girando sul database di demo.

    Senza `SUPABASE_URL` l'app parte lo stesso, sul SQLite di demo: e' quello
    che la rende sempre avviabile in CI e nelle sessioni cloud. In produzione
    pero' e' una trappola silenziosa — la gente entrerebbe con utenti finti e
    ogni riavvio cancellerebbe quello che ha scritto. Meglio dirlo forte.
    """
    from fantacalcio.config import carica_impostazioni

    if os.environ.get("FANTA_AMBIENTE") != "sviluppo" and not (
        carica_impostazioni().usa_supabase
    ):
        registro.warning(
            "ATTENZIONE: mancano SUPABASE_URL/SUPABASE_KEY, sto girando sul "
            "database di DEMO. Gli utenti sono finti e tutto quello che viene "
            "scritto sparisce al prossimo riavvio."
        )
    yield


app = FastAPI(
    title="FantaCalcio NuoVo",
    description="Contratti, monte anni, Salary Cap, draft e scambi.",
    version="0.1.0",
    lifespan=avvio,
)

# In produzione React e API stanno sullo stesso dominio e il CORS non serve.
# In sviluppo Vite gira su un'altra porta, quindi va aperto a quella sola:
# `allow_credentials` con origine `*` il browser lo rifiuta comunque, ed e'
# giusto cosi' — il cookie di sessione non deve viaggiare verso chiunque.
if os.environ.get("FANTA_AMBIENTE") == "sviluppo":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(accesso.rotte, prefix="/api")
app.include_router(albo.rotte, prefix="/api")
app.include_router(campionato.rotte, prefix="/api")
app.include_router(bacheca.rotte, prefix="/api")
app.include_router(cruscotto.rotte, prefix="/api")
app.include_router(giocatori.rotte, prefix="/api")
app.include_router(identita.rotte, prefix="/api")
app.include_router(squadre.rotte, prefix="/api")


@app.get("/api/salute", tags=["servizio"])
def salute() -> dict[str, str]:
    """Dice che l'API risponde e su quale backend sta leggendo."""
    from fantacalcio.config import carica_impostazioni

    return {"stato": "ok", "backend": carica_impostazioni().backend}


# Le pagine si montano per ultime: qui sotto c'e' una rotta che risponde a
# qualunque indirizzo, e le rotte si provano nell'ordine di registrazione.
if not monta_sito(app):
    registro.info(
        "Nessun sito in web/dist: servo solo l'API. In sviluppo e' normale "
        "(React sta su Vite); in produzione vuol dire che `npm run build` "
        "non e' stato eseguito."
    )
