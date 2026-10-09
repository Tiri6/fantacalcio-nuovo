# Il sito intero in un contenitore solo: le pagine React e l'API che le serve.
#
# Due fasi. La prima ha Node e costruisce le pagine; la seconda ha Python e
# si porta via solo il risultato. Cosi' nell'immagine finale Node non c'e'
# proprio: niente `node_modules`, niente compilatore, meno roba che gira sul
# server di quanta ne serva.
#
# E' anche il motivo per cui si usa Docker invece della configurazione
# "Python" preconfezionata degli hosting: quella Node non ce l'ha, e le
# pagine qualcuno le deve pur costruire. Il prezzo e' questo file; il
# guadagno e' che gira identico qui, sul portatile e in produzione.

# --- fase 1: si costruiscono le pagine ------------------------------------
FROM node:22-alpine AS pagine

WORKDIR /pagine

# Prima solo i file delle dipendenze: finche' non cambiano, Docker riusa
# l'installazione gia' fatta e la ricostruzione dura secondi invece di minuti.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# --- fase 2: il server ----------------------------------------------------
FROM python:3.11-slim AS servizio

# PYTHONDONTWRITEBYTECODE: i .pyc in un contenitore che muore a ogni riavvio
# sono solo peso. PYTHONUNBUFFERED: senza, i log restano nel buffer e quando
# il servizio muore ci si perde proprio le righe che dicevano perche'.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Solo le dipendenze dell'API: niente Streamlit, che si porta dietro 156 MB
# di pyarrow e qui non serve a nessuno.
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY fantacalcio/ ./fantacalcio/
COPY api/ ./api/
COPY --from=pagine /pagine/dist/ ./web/dist/

# Non da root: se un giorno qualcuno trova un buco in questo servizio, che
# almeno non si trovi in mano la macchina.
RUN useradd --create-home --uid 1000 fanta && chown -R fanta:fanta /app
USER fanta

# L'hosting dice su che porta ascoltare con $PORT; in locale vale 8000.
ENV PORT=8000
EXPOSE 8000

# `sh -c` perche' $PORT va espansa, ma con `exec` davanti: cosi' uvicorn
# prende il posto della shell e riceve lui il segnale di spegnimento. Senza,
# il segnale arriverebbe alla shell, uvicorn verrebbe ammazzato di forza e
# chi sta caricando una pagina in quel momento vedrebbe la connessione cadere.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
