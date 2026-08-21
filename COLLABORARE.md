# Collaborare a FantaCalcio NuoVo

Benvenuto. Questo documento ti serve una volta sola: dice cosa devi accettare,
come si modifica il progetto e cosa non fare mai.

**Cos'e':** il gestionale della nostra lega di fantacalcio manageriale.
Contratti, monte anni, Salary Cap, draft e scambi stanno qui. Il gioco vero e
proprio (voti, formazioni, risultati) resta su Leghe Fantacalcio: questo sito
non lo sostituisce, gestisce tutto il resto.

**Com'e' fatto:** Python + Streamlit per l'interfaccia, Supabase (PostgreSQL)
per i dati. Il codice sta su GitHub, il sito si aggiorna da solo a ogni push.

---

## I tre livelli di accesso

Non ti serve tutto subito. Guarda cosa vuoi fare e parti da li'.

| Vuoi... | Ti serve | Come |
|---|---|---|
| **Usare il sito** come partecipante | solo l'indirizzo del sito | apri il link, fai login con l'account che ti crea il presidente |
| **Modificare il codice** | account GitHub + invito accettato | vedi "Il ciclo di lavoro" |
| **Gestire il deploy** (riavviare, log, chiavi) | lo stesso invito di sopra | vedi "Streamlit" |

Il secondo e il terzo livello arrivano **insieme**: basta accettare un invito.

---

## Passo 1 — Accetta l'invito su GitHub

Marco ti ha aggiunto come collaboratore con permesso **Write**. Ti arriva una
mail da GitHub, oppure trovi l'invito su
[github.com/notifications](https://github.com/notifications).

Accettalo. Da quel momento vedi
[github.com/Tiri6/fantacalcio-nuovo](https://github.com/Tiri6/fantacalcio-nuovo)
(e' privata: prima dell'invito ti darebbe 404).

> **Perche' Write e non Admin:** Write ti permette di fare tutto il lavoro
> quotidiano — creare branch, pushare, aprire pull request, gestire l'app su
> Streamlit. Admin serve solo per cancellare la repo o cambiarne la
> visibilita', cose che non capitano.

## Passo 2 — Collega Streamlit

Vai su [share.streamlit.io](https://share.streamlit.io) e fai **Sign in with
GitHub**.

Quando GitHub ti chiede l'autorizzazione, **concedi anche l'accesso alle repo
private**. Se salti questo permesso, Streamlit non vede il progetto e ti dice
*"This repository does not exist"* — che e' un messaggio bugiardo: la repo
esiste, e' lui che non la vede.

Fatto questo, nella dashboard ti compare l'app della lega. Non devi
ri-deployarla: e' gia' online, tu ne diventi amministratore.

---

## Il ciclo di lavoro

### Con Claude (il modo in cui lavoriamo)

Apri Claude Code sulla repository e di' direttamente cosa vuoi fare. Non serve
nessun preambolo: `CLAUDE.md` si carica da solo e rimanda a
[MEMORIA.md](MEMORIA.md), che dice a che punto siamo, cosa e' gia' stato deciso
e quali trappole sono gia' costate tempo a qualcun altro.

A fine sessione, prima del push, lancia `/memoria`: aggiorna quel file per chi
viene dopo. E' l'unica cosa che tiene allineate due persone che non lavorano
nello stesso momento.

### A mano

```bash
git clone https://github.com/Tiri6/fantacalcio-nuovo.git
cd fantacalcio-nuovo

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/pytest              # devono passare tutti, in una decina di secondi
.venv/bin/streamlit run app.py
```

Senza credenziali parte in **modalita' demo**: dati inventati, database SQLite
locale, nessun rischio di toccare quelli veri. E' il modo giusto per provare.

### In ogni caso: un branch a testa

```bash
git pull                         # sempre, prima di iniziare
git checkout -b luca/svincoli    # un branch per ogni cosa che fai
# ... lavori ...
.venv/bin/pytest && .venv/bin/ruff check .
git push -u origin luca/svincoli
```

Poi su GitHub apri una **pull request** verso `main`. Marco la guarda e la
unisce. Appena finisce sopra `main`, il sito si riaggiorna da solo in un paio
di minuti.

Se lavorate entrambi su `main` vi pestate i piedi: chi pusha per secondo viene
rifiutato e deve sbrogliare un merge a mano.

---

## Streamlit: cosa puoi fare

Dalla dashboard di [share.streamlit.io](https://share.streamlit.io), menu **⋮**
accanto all'app:

- **Reboot app** — se si e' impallata. E' innocuo, non perde dati: stanno su
  Supabase, non nell'app.
- **Settings → Secrets** — le credenziali del database. Si modificano qui e da
  nessun'altra parte. Al salvataggio l'app si riavvia da sola.
- I **log** in tempo reale, in basso a destra dell'app: e' li' che si legge
  l'errore vero quando qualcosa non va.

Non serve rideployare per pubblicare una modifica: il push su `main` basta.

---

## Le cinque regole

1. **Mai una chiave in un file versionato.** Le credenziali di Supabase vanno
   *solo* nei secret di Streamlit, o nel file locale `.streamlit/secrets.toml`
   che e' in `.gitignore`. Il file `.streamlit/secrets.toml.example` e' un
   modello e finisce su GitHub: contiene segnaposto, non toccarlo. Un test
   (`tests/test_segreti.py`) fallisce apposta se ci finisce dentro una chiave
   vera — se ti si accende quello, non aggirarlo: ha ragione lui.

2. **Nessun numero del regolamento sparso nel codice.** Monte anni 66, Salary
   Cap 100M, rosa 30-33: stanno tutti in `ParametriLega`
   (`fantacalcio/regole.py`) e solo li'. La lega cambia le regole per
   votazione, e devono restare modificabili in un punto solo.

3. **Prima di pushare, `pytest` e `ruff check .` devono passare.** Sono la rete
   che permette a due persone di toccare lo stesso codice senza rompersi a
   vicenda.

4. **Mai due sessioni Claude sullo stesso branch nello stesso momento.** Due
   modelli che riscrivono gli stessi file in parallelo producono conflitti che
   poi tocca sbrogliare a mano.

5. **Fuori dalla repo restano** il PDF del regolamento, il database con i dati
   veri e ogni credenziale. Anche se la repo e' privata.

---

## Se qualcosa va storto

| Sintomo | Cosa e' successo |
|---|---|
| GitHub ti da **404** sulla repo | invito non ancora accettato |
| Streamlit: *"This repository does not exist"* | non gli hai dato il permesso sulle repo private (Passo 2) |
| L'app dice *"Il database e' raggiungibile ma non ha le tabelle"* | manca `db/schema.sql` sul progetto Supabase |
| L'app non riesce a scrivere, o il login non va | nei secret c'e' la chiave `anon` invece della `service_role` |
| `git push` rifiutato | qualcuno ha pushato prima di te: `git pull --rebase` e riprova |
| La sidebar dice **"Modalita' demo"** | nessuna credenziale: e' normale in locale |

Il resto — come e' fatto dentro, chi puo' fare cosa, come funziona uno scambio,
come si caricano le rose — sta nel [README](README.md). Le regole per chi
scrive codice stanno in [CLAUDE.md](CLAUDE.md). Lo stato del progetto, con
quello che manca in ordine di utilita', sta in [MEMORIA.md](MEMORIA.md).
