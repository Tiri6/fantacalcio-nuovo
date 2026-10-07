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

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .rotte import accesso, squadre

app = FastAPI(
    title="FantaCalcio NuoVo",
    description="Contratti, monte anni, Salary Cap, draft e scambi.",
    version="0.1.0",
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
app.include_router(squadre.rotte, prefix="/api")


@app.get("/api/salute", tags=["servizio"])
def salute() -> dict[str, str]:
    """Dice che l'API risponde e su quale backend sta leggendo."""
    from fantacalcio.config import carica_impostazioni

    return {"stato": "ok", "backend": carica_impostazioni().backend}
