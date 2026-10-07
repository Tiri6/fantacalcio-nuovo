# L'API, e il front-end React che ci sta sopra

Il passaggio da Streamlit a React, fatto a pezzi. Streamlit **resta in piedi
e funzionante** finché il nuovo non è in pari: finché `app.py` c'è, la lega
continua a usare quello.

## Perché un'API in mezzo

React non può chiamare Python. Le strade erano due:

1. React parla direttamente a Supabase — e allora conformità, Mantra, Dead
   Money, draft e scambi andrebbero riscritti in TypeScript. Vuol dire
   buttare 1095 test e tenere il regolamento in due copie che divergono.
2. React parla a un'API che espone il dominio Python — e il dominio resta
   uno solo, con i suoi test.

È la seconda. **Qui dentro non vive nessuna regola di gioco**: questo strato
traduce e basta, dal dominio al JSON e ritorno. Una regola scritta qui
sarebbe la copia che diverge.

## Come si avvia, in locale

Servono due processi. L'API:

```bash
export FANTA_SEGRETO_JWT="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export FANTA_AMBIENTE=sviluppo
.venv/bin/python -m uvicorn api.main:app --reload --port 8000
```

E il front-end, in un altro terminale:

```bash
cd web && npm install && npm run dev
```

Poi si apre **http://localhost:5173**. Vite gira su 5173 e inoltra `/api` a
8000, così in sviluppo sembrano lo stesso dominio come saranno in produzione:
è quello che fa funzionare il cookie di sessione qui esattamente come lì.

La documentazione interattiva dell'API sta su http://localhost:8000/docs.

## Le due variabili d'ambiente

| Variabile | A cosa serve |
|---|---|
| `FANTA_SEGRETO_JWT` | Firma le sessioni. **Obbligatoria**, almeno 32 caratteri: senza, l'app non parte di proposito. Un default di comodo finirebbe in produzione, e chi lo conosce si fabbrica un token da presidente. |
| `FANTA_AMBIENTE` | A `sviluppo` apre il CORS verso Vite e toglie `Secure` dal cookie (su `http://localhost` un cookie Secure non tornerebbe mai indietro, e il login sembrerebbe rotto). In produzione **non si imposta**. |

`SUPABASE_URL` e `SUPABASE_KEY` restano quelle di sempre: senza, si cade sul
database di demo SQLite, esattamente come fa Streamlit.

## La sessione

È il pezzo che Streamlit regalava e che qui si scrive a mano.

Lì la sessione viveva nel processo del server (`st.session_state`): il browser
non teneva niente, e **ricaricare la pagina buttava fuori**. Qui c'è un token
firmato in un **cookie httpOnly** — nessun JavaScript della pagina lo legge,
quindi un XSS non se lo porta via — e ricaricare non butta più fuori.

Dentro il token c'è **solo il nome utente**, mai l'oggetto `Utente`. È la
stessa regola del `session_state`, per la stessa ragione: appena uno entra in
una lega o fonda la squadra la sua riga cambia, e un utente congelato al
momento dell'accesso mostrerebbe lo stato vecchio. Il token dice *chi*, il
database dice *com'è adesso*.

Le password non si toccano: restano gli stessi hash scrypt di prima, quindi
nessuno deve reimpostare niente.

## I permessi

Stanno nel dominio, come prima: `Utente.puo_gestire()`, `puo_svincolare`,
le transizioni di `scambi.py`. Le rotte chiedono «puoi?» e il dominio
risponde. Un controllo riscritto in questo strato sarebbe la seconda copia
della regola — e nascondere un bottone in React è ancora meno un controllo di
quanto lo fosse nasconderlo in Streamlit.

## Dove gira, una volta pubblicato

React è statico e sta su un hosting gratuito. L'API è una funzione
serverless: pesa ~120 MB (pandas 71 + numpy 45 + supabase), **sotto il limite
di 250 MB** — e ci sta perché non si porta dietro Streamlit, che da solo
aggiunge 156 MB di `pyarrow`. È il motivo per cui `requirements-api.txt` è
separato da `requirements.txt`.
