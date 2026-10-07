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

**Un servizio solo**: la stessa app serve l'API *e* le pagine React, allo
stesso indirizzo.

Due servizi separati sarebbero stati due cose da configurare, due cose che si
rompono, e il CORS da tenere aperto perché il cookie di sessione avrebbe
dovuto attraversare due domini. Così invece il browser vede un indirizzo solo,
il cookie è di casa, e quando qualcosa non va c'è un posto solo dove guardare.

Il prezzo è che l'API deve sapere che esiste un front-end. È un prezzo piccolo
e sta tutto in `api/statici.py`: `fantacalcio/` non ne sa niente, come non
sapeva di Streamlit.

Quel file fa tre cose che vale la pena conoscere:

- **Un indirizzo `/api/...` che non esiste resta un 404 JSON.** Se cadesse
  sulle pagine, una chiamata sbagliata del front-end tornerebbe `200` con
  dentro dell'HTML, e il guasto salterebbe fuori molto dopo.
- **Qualunque altro indirizzo serve l'index.html.** Gli indirizzi come
  `/squadre/3` li conosce React, non il server: senza questo, aprire un link
  o premere F5 darebbe 404.
- **L'index.html non si tiene in cache**, i file sotto `assets/` sì. Quelli
  hanno l'impronta del contenuto nel nome e non cambiano mai; l'index invece
  dice *quali* file caricare, e se il browser tiene il vecchio dopo un
  aggiornamento il sito resta bianco.

Senza `web/dist` tutto questo non si monta proprio, e l'app serve solo l'API:
in sviluppo è giusto così, perché React sta su Vite.

### Il contenitore

Il `Dockerfile` in cima al repository costruisce le due cose insieme: prima
fase con Node che costruisce le pagine, seconda fase con Python che si porta
via solo il risultato. Nell'immagine finale Node non c'è: niente
`node_modules`, niente compilatore. E non gira da root.

Si prova in locale senza pubblicare niente:

```bash
docker build -t fantacalcio-nuovo .
docker run --rm -p 8000:8000 \
  -e FANTA_SEGRETO_JWT="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  fantacalcio-nuovo
```

Poi **http://localhost:8000**. Senza `SUPABASE_URL` parte sul database di
demo e lo dice nei log, forte: utenti finti, e tutto cancellato al riavvio.

Come pubblicarlo davvero sta in [README.md](../README.md), sezione
*Pubblicare il sito*.
