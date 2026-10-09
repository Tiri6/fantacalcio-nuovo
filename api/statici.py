"""Un servizio solo: la stessa app serve l'API **e** le pagine React.

Due servizi separati vorrebbero dire due cose da configurare, due cose che
si rompono, e il CORS da tenere aperto perche' il cookie di sessione deve
attraversare due domini. Qui invece il browser vede un indirizzo solo, il
cookie e' di casa, e quando qualcosa non va c'e' un posto solo dove guardare.

Il prezzo e' che l'API deve sapere che esiste un front-end. E' un prezzo
piccolo e confinato in questo file: `fantacalcio/` non ne sa niente, come
non sapeva di Streamlit.

Senza le pagine costruite (`npm run build`) tutto questo non si monta
proprio: in sviluppo React sta su Vite, e un `web/dist` vecchio servito per
sbaglio sarebbe peggio di nessun sito.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

RADICE = Path(__file__).resolve().parents[1]


def cartella_sito() -> Path:
    """Dove stanno le pagine costruite."""
    indicata = os.environ.get("FANTA_SITO")
    return Path(indicata) if indicata else RADICE / "web" / "dist"


def monta_sito(app: FastAPI) -> bool:
    """Aggiunge le pagine all'app. Dice se c'erano davvero.

    Va chiamata **dopo** `include_router`: le rotte si provano nell'ordine in
    cui sono registrate, e qui dentro ce n'e' una che risponde a tutto.
    """
    cartella = cartella_sito().resolve()
    indice = cartella / "index.html"
    if not indice.is_file():
        return False

    # Anche HEAD, non solo GET: le anteprime dei link (WhatsApp, Telegram)
    # chiedono spesso cosi', e un 405 fa sembrare il sito rotto prima ancora
    # che qualcuno l'abbia aperto.
    @app.api_route("/{percorso:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def pagina(percorso: str) -> FileResponse:
        # Un indirizzo `/api/...` che non esiste deve restare un 404. Se
        # cadesse anche lui sull'index.html, una chiamata sbagliata del
        # front-end tornerebbe una pagina HTML con stato 200: il guasto si
        # vedrebbe solo molto dopo, e in un punto che non c'entra niente.
        if percorso == "api" or percorso.startswith("api/"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Rotta inesistente."
            )

        richiesto = (cartella / percorso).resolve()
        # `..` nell'indirizzo non deve poter uscire dalla cartella del sito,
        # altrimenti si servirebbe qualunque file del server.
        dentro = richiesto == cartella or cartella in richiesto.parents
        if percorso and dentro and richiesto.is_file():
            return FileResponse(richiesto)

        # Tutto il resto e' un indirizzo di React (`/squadre/3`): il server
        # non lo conosce e non deve conoscerlo, manda l'index e ci pensa il
        # front-end. Senza questo, aprire un link o premere F5 darebbe 404.
        #
        # `no-cache` solo qui: i file sotto `assets/` hanno l'impronta del
        # contenuto nel nome e non cambiano mai, ma l'index.html e' quello
        # che dice *quali* file caricare — se il browser tiene il vecchio,
        # dopo un aggiornamento continua a chiedere file che non ci sono piu'.
        return FileResponse(indice, headers={"Cache-Control": "no-cache"})

    return True
