# FantaCalcio NuoVo — il gestionale della lega

Il gioco (voti, formazioni, risultati) si svolge su **Leghe Fantacalcio**.
Questo progetto governa tutto quello che la piattaforma non sa fare, ed e' cio'
che rende "gestionale" la vostra lega:

- contratti pluriennali e **monte anni** (66 anni da distribuire);
- **Salary Cap** (100M) e **Salary Floor** (80M) su ingaggi reali da Capology;
- **Dead Money** da svincolo (Lodo Origi);
- **regola "1/3"** sui contratti in scadenza;
- **espansione Under 21** che allarga la rosa;
- **draft con lottery** a due fasce e ordine di chiamata variabile per round;
- **scambi** validati contro i lodi Bono, Corti e Longoni.

Base: regolamento **V2.1 di Agosto 2026**, versione post-redline.

> I punti del regolamento che ho dovuto interpretare sono elencati in
> [PUNTI_APERTI.md](PUNTI_APERTI.md), con l'ipotesi che il codice applica oggi.
> Le fasce di gol sono chiuse: **primo gol a 66**, poi uno ogni 6.

---

## Avvio rapido

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/streamlit run app.py
```

Parte **senza credenziali**: se non trova Supabase genera una lega di demo in
SQLite, con 10 squadre, rose contrattualizzate e 11 giornate disputate. Tutte
le rose della demo sono conformi al regolamento, quindi sono un banco di prova
valido per le regole.

```bash
.venv/bin/pytest        # 143 test
.venv/bin/ruff check .
```

---

## Le schermate

| Pagina | A cosa serve |
|---|---|
| **Cruscotto** | Chi e' in regola e chi no: rosa, monte anni, annuali, cap e floor di tutte e 10 le squadre in una tabella. |
| **Rose e contratti** | La rosa di una squadra con anni residui, ingaggi, status U21 e quanto costerebbe tagliare ciascun giocatore. |
| **Mercato** | Componi uno scambio, verifica contro i lodi e invialo alla controparte. Calcolo del Dead Money prima di svincolare. |
| **Identita' squadre** | Presidente, motto, stadio, colori sociali, maglia e logo. La maglia si disegna dai colori: nessuno resta senza. |
| **Importa dati** | Il CSV del draft e i risultati di giornata, con anteprima ed errori riga per riga prima di scrivere. |
| **Draft** | Draft Lottery riproducibile, ordine di chiamata round per round, probabilita' delle pick, draft list delle scadenze. |
| **Campionato** | Classifica e risultati importati da Leghe: servono a determinare l'ordine del draft. |
| **Scambi** | Proposte ricevute e inviate, ratifica del presidente, storico di chi ha fatto cosa. |
| **Regolamento** | I valori che il gestionale applica davvero, articolo per articolo. |

---

## Com'e' fatto

```
app.py                    router: st.navigation, monta le viste
viste/                    una schermata per file
fantacalcio/
  regole.py               TUTTI i numeri del regolamento (ParametriLega)
  modelli.py              Giocatore, Contratto, Rosa, Dead Money
  identita.py             colori sociali, maglia disegnata in SVG, logo
  conformita.py           verifica una rosa -> elenco di violazioni
  draft.py                Draft Lottery e ordine di chiamata (art. 3)
  mercato.py              finestre, svincoli, scambi e lodi (art. 5-8)
  importazione.py         lettura e validazione dei CSV
  autenticazione.py       utenti, password (scrypt) e permessi
  scambi.py               ciclo di vita di uno scambio e persistenza
  standings.py            calendario e classifica
  data.py                 accesso ai dati: Supabase o SQLite demo
  vista.py                dai dati grezzi alle tabelle a schermo
  ui.py                   helper Streamlit (l'unico modulo che importa st)
  demo_data.py            genera la lega di demo
db/schema.sql             schema Postgres da incollare in Supabase
tests/                    143 test sulle regole, i dati e le viste
```

Due regole tengono insieme il progetto:

**Il regolamento sta in un posto solo.** Ogni soglia — 66 anni, 100M, 33
giocatori, 3 portieri, 50% di Dead Money — e' un campo di `ParametriLega`.
Quando la lega vota un lodo si cambia quel valore, non la logica. E' anche il
motivo per cui la pagina Regolamento puo' stampare i parametri veri invece di
una copia scritta a mano che prima o poi diverge.

**La logica non conosce Streamlit.** `regole`, `modelli`, `conformita`,
`draft`, `mercato` e `vista` sono Python puro. I 143 test girano in poco piu'
di un secondo senza avviare nulla — ed e' il motivo per cui questa parte
sopravvivrebbe intatta a un cambio di tecnologia del sito.

### La verifica non e' un si'/no

`verifica_rosa()` restituisce sempre **l'elenco completo** delle violazioni,
ciascuna con l'articolo, la gravita', il valore attuale e il limite. A un
fantallenatore non serve sapere che la rosa e' irregolare: serve sapere che gli
mancano 2 contratti annuali e che sfora il cap di 1,4M.

Le stesse regole non sono vincolanti sempre allo stesso modo, e il codice lo
rispecchia con il parametro `Momento`:

| | Asta di Settembre / riparazione | Stagione in corso |
|---|---|---|
| Salary Cap | blocca | avviso (art. 8b: si sana prima dell'asta) |
| Salary Floor | blocca | non si verifica |
| Rosa minima, regola 1/3 | blocca | avviso |
| Rosa massima, portieri, monte anni | blocca | blocca |

---

## Caricare i giocatori (listone ufficiale)

Prima delle rose si carica il **listone** di Fantacalcio.it, il file
`Quotazioni_Fantacalcio_Stagione_*.xlsx`: 509 giocatori con ruoli Mantra,
squadra di Serie A e quotazioni. Pagina **Importa dati → Listone giocatori**.

Cosa il listone **non** contiene, e va quindi da altrove:

| Serve per | Da dove |
|---|---|
| A quale squadra della lega appartiene | il vostro file del draft |
| Anni di contratto | il vostro file del draft |
| **Ingaggio** (Salary Cap e Floor) | Capology, come dice l'art. 4 |
| Data di nascita e nazionalita' (status Under 21) | da aggiungere a mano |

Finche' mancano gli ingaggi, Salary Cap e Floor risulteranno a zero: non e' un
errore del programma, e' un dato che non c'e' ancora.

Il vantaggio del listone e' che dopo averlo caricato il file delle rose diventa
minimo: bastano `squadra`, `giocatore`, `anni`, `ingaggio`. Ruoli e club si
ricavano dal nome, e un nome che non esiste viene segnalato con un
suggerimento (`Svilarr` → «Forse intendevi: Svilar»).

---

## Caricare i dati dopo il draft

Il draft si fa di persona e poi si carica il risultato dalla pagina **Importa
dati**. Il CSV vuole una riga per giocatore:

Con il listone gia' caricato bastano quattro colonne:

```csv
squadra;giocatore;anni;ingaggio
Tiri Team;Svilar;3;4.500.000
Padel United;Dimarco;2;6,2M
```

Senza listone servono anche ruoli e club:

```csv
squadra;giocatore;club;ruoli;ingaggio;anni;nazionalita;data_nascita
Tiri Team;Rossi Marco;Juventus;Dc;2.500.000;3;Italia;17/04/2001
Padel United;Silva Joao;Napoli;W/T;4,2M;2;Brasile;30/06/1999
```

Il lettore e' volutamente tollerante, perche' i fogli veri non arrivano mai
puliti:

- **intestazioni**: riconosce i sinonimi piu' comuni (`Fantasquadra`,
  `Calciatore`, `Stipendio`, `Durata`, `RM`, `Nazionalità`...), senza badare a
  maiuscole e accenti;
- **separatore**: `;` o `,`, riconosciuto da solo;
- **importi**: `3.500.000`, `1500000`, `3,5M`, `4 mln`, `€ 2.100.000`;
- **date**: `17/04/2001`, `2001-04-17`, `17-04-2001`;
- **ruoli multipli**: separali con `/` — per esempio `Dc/Dd`. Non usare `;`
  dentro la cella se il CSV e' separato da `;`: e' l'errore piu' comune, e il
  programma lo riconosce e te lo dice.

Le colonne obbligatorie sono `squadra`, `giocatore`, `ruoli`, `ingaggio` e
`anni`. Le altre migliorano i controlli: senza `data_nascita`, per esempio, non
si puo' stabilire chi e' Under 21.

**Niente viene scritto finche' non confermi.** Prima vedi gli errori riga per
riga, l'anteprima delle rose e — la parte utile — la verifica di conformita':
se il draft ha lasciato qualcuno oltre il Salary Cap o sotto i 30 giocatori, lo
scopri prima di importare, non dopo.

Stessa cosa per i **risultati di giornata**: carichi giornata, squadre e punti,
e i gol vengono calcolati dalle fasce della lega.

---

## Chi puo' fare cosa

Si entra con nome utente e password. Ci sono due ruoli:

| | Presidente | Fantallenatore |
|---|---|---|
| Vedere tutta la lega | si | si |
| Modificare la propria squadra | si | si |
| Modificare le altre squadre | si | no |
| Proporre scambi | per chiunque | solo per la sua squadra |
| Accettare o rifiutare | si | solo le proposte ricevute |
| **Ratificare** uno scambio | si | no |
| **Importare** i CSV | si | no |

In modalita' demo esistono dieci utenti di prova (`marco` e' il presidente),
con una password comune mostrata nella pagina di accesso. Sono generati solo
nel database di demo: **con i dati veri su Supabase quegli utenti non esistono**.

I permessi non sono solo grafici: `Utente.puo_gestire()` e le transizioni in
`scambi.py` rifiutano l'operazione anche se qualcuno arrivasse alla funzione
per altre strade. Nascondere un bottone non e' un controllo.

> Onesta' sui limiti: questo login e' proporzionato a dieci amici, non a un
> servizio pubblico.
>
> - **Ricaricare la pagina fa uscire.** La sessione vive nel session_state di
>   Streamlit: navigando con il menu tutto resta com'e', ma un F5 riporta al
>   login. Tenerla viva richiederebbe un token in un cookie, che aggiunge
>   superficie d'attacco per un guadagno modesto: meglio ri-entrare.
> - Non c'e' recupero password via email: la reimposta il presidente.
> - Su Streamlit Community Cloud l'indirizzo dell'app e' pubblico, quindi la
>   pagina di accesso e' raggiungibile da chiunque abbia il link.
>
> Le password restano protette da scrypt con sale: anche chi ottenesse il
> database non le ricava.

---

## Come funziona uno scambio

1. **Componi** la proposta dal Mercato: scegli i giocatori, eventualmente
   prolunghi i contratti. La validazione contro i lodi Bono, Corti e Longoni
   e' immediata.
2. **Invia**: la controparte la trova nella pagina Scambi, sezione *Ricevute*.
3. **Accetta o rifiuta**. Chi ha proposto puo' ritirare fino alla ratifica.
4. **Il presidente ratifica**. Qui lo scambio viene **ri-validato**: tra la
   proposta e la ratifica le rose possono essere cambiate, e uno scambio valido
   ieri puo' non esserlo oggi. Solo allora i contratti passano davvero.
5. La **giornata di efficacia** segue l'art. 8: con meno di 24 ore di preavviso
   sull'inizio della giornata, lo scambio vale da quella successiva.

Ogni passaggio resta nello storico, con chi l'ha fatto e quando.

---

## Cosa manca per essere "la piattaforma vera"

Il gestionale **legge, valida e scrive**: identita', import CSV, login e
scambi. Manca, nell'ordine in cui lo farei:

1. **I dati veri**: appena arriva il CSV della lega, tarare i sinonimi delle
   intestazioni sul formato reale.
2. **Svincoli registrati**, che scrivano davvero il Dead Money invece di
   limitarsi a calcolarlo: stesso flusso degli scambi.
3. **Gestione utenti** dall'interfaccia: creare i partecipanti, assegnare le
   squadre, reimpostare le password. Oggi gli utenti esistono solo nella demo.
4. **Registro dei lodi**, collegato all'articolo che modificano.
5. **Tabellone del draft** da proiettare durante l'asta al Centro Padel.

Il punto 1 e' anche il momento in cui va deciso se restare su Streamlit: per
dieci persone che consultano e propongono scambi puo' bastare, ma per un'asta
in tempo reale e per l'uso quotidiano da telefono un frontend vero renderebbe
molto meglio. La logica di regole non andrebbe comunque riscritta.

---

## Lavorare in due (o in dieci)

Il repository e' privato: chi collabora va aggiunto da **Settings →
Collaborators**, con permesso *Write*. Quel permesso vale anche per il deploy:
su Streamlit Community Cloud e' l'accesso in scrittura alla repo a decidere chi
puo' amministrare l'app, non un'impostazione di Streamlit.

Da girare a chi entra: **[COLLABORARE.md](COLLABORARE.md)**, che ripercorre
l'invito, il collegamento a Streamlit e il ciclo di lavoro dal suo punto di
vista.

Tre regole che evitano il 90% dei problemi:

**Un branch a testa.** `marco/qualcosa`, `luca/qualcosa`. Se lavorate entrambi
su `main` vi pestate i piedi: chi pusha per secondo viene rifiutato e deve
sbrogliare un merge.

```bash
git pull                        # sempre, prima di iniziare
git checkout -b marco/svincoli  # un branch per ogni cosa che fai
# ... lavori ...
git push -u origin marco/svincoli
```

Poi su GitHub apri una **pull request** verso `main`.

**Mai due sessioni Claude sullo stesso branch nello stesso momento.** Due
Claude che modificano gli stessi file in parallelo producono conflitti che poi
tocca risolvere a mano.

**Prima di pushare, i test devono passare.** `pytest` e `ruff check .`: sono la
rete che permette a due persone di toccare lo stesso codice senza rompersi a
vicenda.

### Riprendere il progetto da una sessione nuova

Apri Claude Code su questo repository e di' direttamente cosa vuoi fare.
`CLAUDE.md` si carica da solo e rimanda a [MEMORIA.md](MEMORIA.md), che dice a
che punto siamo, cosa e' gia' stato deciso e quali trappole sono gia' costate
tempo. A fine sessione, `/memoria` per aggiornarla.

---

## Pubblicare il sito

Il sito e' online su Streamlit Community Cloud: ogni push su `main` lo
riaggiorna da solo, senza rideploy. Chi lo pubblica da zero fa due passaggi.

**1. Supabase — il database vero.** Crea il progetto su
[supabase.com](https://supabase.com) (piano free), apri il SQL Editor e incolla
tutto `db/schema.sql`. Crea 10 tabelle ed e' rieseguibile: se lo lanci due
volte non rompe niente.

Senza questo passo l'app gira in modalita' demo: dati inventati, e ogni riavvio
azzera tutto.

Poi da *Project Settings → API* copia l'URL e la chiave **`service_role`**.

> **Serve la `service_role`, non la `anon`.** L'app non legge soltanto: crea
> utenti, importa rose, ratifica scambi. Con la `anon` la Row Level Security
> blocca ogni scrittura e la tabella `utenti` non e' nemmeno leggibile — non
> riusciresti neanche a fare login.
>
> La `service_role` bypassa la RLS. Qui va bene perche' **Streamlit gira sul
> server**: la chiave resta nel backend e non raggiunge mai il browser di chi
> usa il sito. A proteggere le scritture ci pensa il sistema di permessi
> dell'app.
>
> **Non incollarla mai in un file versionato.** Le chiavi legacy non si
> possono rigenerare: se ne compromettessi una, l'unico rimedio e' creare una
> chiave `secret` nuova da *Settings → API Keys* e disattivare le legacy dalla
> stessa pagina. Chi parte oggi puo' usare direttamente una chiave
> `sb_secret_...`, che invece si puo' revocare singolarmente.

Per provarlo prima in locale: `cp .streamlit/secrets.toml.example
.streamlit/secrets.toml` e compilalo. Al riavvio la sidebar passa da "Modalita'
demo" a "Dati live da Supabase" — `config.py` sceglie da solo il backend, il
codice non cambia.

**Il primo accesso.** Un database appena creato non ha utenti: gli account di
prova esistono solo nella lega di demo. Alla prima apertura l'app se ne accorge
e mostra una schermata di **prima configurazione** per creare il presidente di
lega. Da li' in poi si entra normalmente, e sara' il presidente a creare gli
altri partecipanti.

**2. Streamlit Community Cloud — il sito.** Su
[share.streamlit.io](https://share.streamlit.io) collega il repository, indica
`app.py` come main file, e in *Settings → Secrets* incolla:

```toml
NOME_LEGA = "FantaCalcio NuoVo"
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "..."
```

Esce un indirizzo tipo `https://fantacalcio-nuovo.streamlit.app`: **quello e'
il link da dare ai partecipanti.** Ogni push su `main` ridispiega da solo.

Due cose da sapere sul piano gratuito: l'app **va in letargo** quando non la usa
nessuno, e il primo che apre il link aspetta qualche decina di secondi; e
l'indirizzo e' pubblico, quindi la pagina di accesso e' raggiungibile da
chiunque ce l'abbia (senza credenziali, pero', non si entra).
