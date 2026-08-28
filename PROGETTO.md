# FantaCalcio NuoVo — il progetto, per intero

Questo file raccoglie **tutto quello che e' stato deciso e costruito**: cosa
fa il sito, con quali regole, come e' fatto dentro e cosa manca ancora.

E' il documento da leggere per capire il progetto senza ricostruirlo dalla
cronologia. Gli altri file hanno scopi piu' stretti:

| File | A cosa serve |
|---|---|
| [MEMORIA.md](MEMORIA.md) | Lo stato corrente e le trappole gia' pagate. Lo legge Claude a ogni sessione |
| [CLAUDE.md](CLAUDE.md) | Le regole per chi scrive codice |
| [COLLABORARE.md](COLLABORARE.md) | Come entrare nel progetto, per chi arriva |
| [README.md](README.md) | Come si usa il sito, schermata per schermata |
| [PUNTI_APERTI.md](PUNTI_APERTI.md) | Le ambiguita' del regolamento ancora da sciogliere |

---

## 1. Cos'e'

Il **gestionale** della lega FantaCalcio NuoVo: contratti, monte anni, Salary
Cap, draft, scambi e competizioni.

Il gioco vero e proprio — voti, formazioni, risultati di giornata — resta su
**Leghe Fantacalcio**. Questo sito non lo sostituisce: gestisce tutto cio' che
un fantacalcio manageriale ha in piu' e che quella piattaforma non prevede.

**Indirizzo**: https://fantacalcio-nuovo.streamlit.app
**Codice**: https://github.com/Tiri6/fantacalcio-nuovo (privato)

---

## 2. Le decisioni prese

Non si riaprono senza un motivo nuovo.

| Decisione | Perche' |
|---|---|
| **Primo gol a 66**, poi uno ogni 6 | Confermato dalla lega. L'art. 1 cita anche 60: e' la formulazione del regolamento a essere imprecisa, non il codice |
| Il **draft si fa offline**, i risultati si caricano | Il sito non conduce l'asta: registra chi si e' preso chi |
| Stack **Streamlit + Supabase** | La logica e' Python puro senza Streamlit: cambiare frontend non la tocca |
| **Registrazione autonoma**, email obbligatoria e unica | L'email e' l'unico dato che lega un account a una persona |
| Si entra con un **codice d'invito** di 8 caratteri | Alfabeto senza `O`/`0` e `I`/`1`: si ricopia da uno screenshot senza sbagliare |
| Gli **inviti per email non spediscono niente** | Non c'e' un server di posta, e montarne uno per dieci persone non si giustifica |
| Le **opzioni di lega** stanno in JSON, non in colonne | Cambiano ogni stagione: una migrazione per casella sarebbe un costo continuo |
| **Under 21 al 31 agosto**, non alla data del draft | Lo status si cristallizza li' e vale per l'annata, come nei campionati veri |
| **Niente recupero password via email** | Lo reimposta il presidente e lo consegna a voce. Serve fidarsi di una persona invece che di un link |
| La **squadra si puo' rimandare** | Chi amministra e basta non deve restare chiuso fuori |
| **Si resta su Streamlit** per la stagione di prova | La migrazione a un'autenticazione vera si valuta dopo aver giocato |

---

## 3. Come si entra

Quattro cancelli, ognuno una volta sola. Ognuno ferma la pagina finche' non e'
superato, quindi dal menu in giu' c'e' sempre un utente dentro una lega.

### 1. Registrazione

Nome, cognome, data di nascita (gg/mm/aaaa), sesso, citta', squadra del cuore,
nome utente, **email** e password (almeno 8 caratteri, scritto nel modulo).

L'elenco delle squadre del cuore si ricava dai club presenti nel listone
caricato: cosi' e' quello vero della stagione, e nessuno deve aggiornarlo a
settembre. In coda Serie B e le voci «Altro (Italia)», «Altro (Estero)».

**Il primo che si registra su un database vuoto diventa presidente**: senza,
non ci sarebbe nessuno a creare la lega.

### 2. Password (solo dopo una reimpostazione)

Chi ha ricevuto una password temporanea deve sostituirla prima di entrare.

### 3. Crea una lega o unisciti

*Crea*: tutte le opzioni (sotto). Alla fine ricevi il **codice d'invito**.
*Unisciti*: incolli il codice che ti hanno passato.

### 4. Fonda la squadra

Nome, citta', stadio, nome della curva, motto, colori sociali, con la maglia
disegnata in anteprima. Rimandabile.

---

## 4. Le opzioni di lega

Si scelgono creando la lega e si vedono in «Impostazioni lega» e «Regolamento».

**Generali** — modalita' (Mantra o Classic), partecipanti, formato del
campionato, giornate, punti per vittoria e pareggio.

**Rosa e mercato** — come si assegnano i giocatori, **anni di contratto
massimi**, **budget cap annuale in milioni**, stagione.

**Limite di giocatori per ruolo** — o quattro numeri, o **nessun limite**.
Nessun limite non e' un numero grande: i campi diventano assenti, e il totale
di rosa non esiste. Sommare ignorando i ruoli liberi darebbe un numero che non
vincola nulla.

**Vincoli** — minimo di giocatori italiani, minimo di Under 21 italiani,
scambi permessi a stagione. Zero significa nessun vincolo. I due minimi si
controllano a vicenda: non si possono chiedere piu' Under 21 italiani che
italiani, perche' un Under 21 italiano e' gia' un italiano.

**Competizioni** — il campionato c'e' sempre; **Coppa Italia** e
**Supercoppa** si accendono qui, e solo allora compaiono nel menu.

**Formazione** — moduli ammessi (16 in Mantra, 7 in Classic), panchinari,
sostituzioni automatiche, capitano.

**Punteggio** — nove bonus e malus, voto d'ufficio a chi non gioca, fasce di
gol (soglia del primo gol e passo), modificatori di difesa, centrocampo e
attacco.

---

## 5. Le competizioni

### Campionato
Sempre attivo. Classifica, calendario e andamento.

### Coppa Italia
Formato, squadre ammesse (**una potenza di due**, altrimenti il tabellone non
si chiude), teste di serie dalla classifica, ogni quante giornate si gioca un
turno, spareggio ai fantapunti in caso di parita'.

### Supercoppa
Vincitrice campionato contro vincitrice di coppa, oppure contro la seconda,
oppure a scelta. **Il primo anno le due squadre si scelgono a mano** perche'
l'albo d'oro e' vuoto; dall'anno dopo si ricavano da sole.

### Albo d'oro
Storicizza i vincitori. Il nome della squadra si **copia** nella riga invece di
tenere solo l'id: una squadra puo' sparire, il titolo resta suo.

### Calendario dei weekend
La corrispondenza fra giornata di Serie A e giornata di lega:

| Weekend | Serie A | Nella lega |
|---|---|---|
| 4 | 8ª giornata | 🏆 4ª giornata |
| 5 | 9ª giornata | 🥇 Quarti di finale |
| 6 | 10ª giornata | 🏆 5ª giornata |

Un turno di coppa occupa un weekend e fa **slittare** il campionato di una
settimana: non lo salta. E' questo slittamento che disallinea le due
numerazioni, ed e' cio' che la pagina esiste per mostrare.

---

## 6. Il menu

**Lega · <nome della lega>**
Bacheca · Cruscotto · Campionato · *Coppa Italia* · *Supercoppa* · Calendario ·
Albo d'oro · Regolamento

**Squadre e giocatori**
Squadre · Lista giocatori · Identita' squadre

**Mercato**
Draft · *Assegnazioni* · Scambi · Componi scambio

**Impostazioni**
Impostazioni profilo · *Importa dati* · Impostazioni lega

*In corsivo cio' che compare solo a chi ne ha diritto o se la lega lo prevede.*

---

## 7. Chi puo' fare cosa

| | Presidente | Editor | Fantallenatore |
|---|---|---|---|
| Vedere tutta la lega | si | si | si |
| Modificare la propria squadra | si | si | si |
| Modificare le altre squadre | si | no | no |
| **Scrivere in bacheca** | si | **si** | no |
| Proporre scambi | per chiunque | per la sua | per la sua |
| **Ratificare** uno scambio | si | no | no |
| **Importare** dati e assegnazioni | si | no | no |
| Reimpostare le password | si | no | no |

L'**editor** e' una delega stretta: scrive in bacheca e basta.

I permessi non sono grafici: `Utente.puo_gestire()`, `bacheca.puo_pubblicare()`
e le transizioni in `scambi.py` rifiutano l'operazione anche se qualcuno
arrivasse alla funzione per altre strade. Nascondere un bottone non e' un
controllo.

---

## 8. Le regole del gioco applicate

### Rosa (art. 2)
Rosa 30–33, fino a 36 con l'espansione Under 21. Massimo 3 portieri. Monte
anni 66. Contratti da 1 a 5 anni. Regola «1/3»: 10 contratti annuali con rosa
da 30, 11 fino a 33, 12 fino a 36.

**Under 21**: italiano che al **31 agosto** della stagione non ha 21 anni.

### Economia (art. 4 e 7)
Salary Cap 100M, Salary Floor 80M. Fonte degli stipendi: **Capology**.
**Dead Money** (Lodo Origi): svincolando, il 50% del valore residuo si addebita
alla prima sessione utile e non concorre al Floor.

### Scambi (art. 8)
Proposta → accettazione → **ratifica del presidente**, con ri-validazione al
momento della ratifica. Senza 24 ore di preavviso lo scambio vale dalla
giornata dopo.

I tre lodi sui prolungamenti:

- **Lodo Longoni** — chi riceve un giocatore puo' allungargli il contratto, se
  ha anni liberi nel monte. Dybala arriva con 1 anno e lo porti a 3: i due anni
  in piu' si scalano dal tuo monte. Massimo **2 per squadra a stagione**.
- **Lodo Corti** — una volta sola nell'arco della vita residua del contratto di
  quel giocatore.
- **Lodo Bono** — in sede di scambio il contratto non si accorcia.

Il limite di scambi a stagione conta solo i **ratificati**: una proposta in
attesa o rifiutata non ha spostato nessuno.

### Draft (art. 3)
Draft Lottery a due fasce, ordine di chiamata con la deroga dei round multipli
di 3, probabilita' delle pick stimate per simulazione.

---

## 9. Com'e' fatto

```
app.py            i quattro cancelli e la navigazione
fantacalcio/      la logica: non importa Streamlit (tranne ui e schermate)
viste/            una pagina per file, eseguite da st.navigation
db/schema.sql     lo schema Postgres, rieseguibile
tests/            542 test, sotto i dieci secondi
```

### Le regole che tengono in piedi il progetto

- **Nessun numero del regolamento fuori da `ParametriLega`.** La lega cambia le
  regole per votazione: devono essere modificabili in un punto solo.
- **La logica non importa Streamlit.** Solo `ui.py`, `schermate.py` e `viste/`.
  E' quello che tiene i test veloci. `tema.py` produce stringhe di CSS e HTML:
  non importa Streamlit nemmeno lui.
- **Le verifiche restituiscono violazioni, non booleani.** Ogni controllo
  produce una `Violazione` con articolo, valore e limite: chi la subisce deve
  sapere *di quanto* sfora.
- **I permessi si controllano nel dominio.**
- **Il testo scritto dagli utenti non finisce mai in `unsafe_allow_html`** senza
  passare da `tema._scudo()`. Gli annunci della bacheca si rendono con
  `st.markdown`, che scuda l'HTML da solo.

### Le trappole gia' pagate

- **Streamlit ricarica `app.py` e le viste, non i moduli importati.** Dopo un
  aggiornamento senza riavvio il primo campo nuovo alza un AttributeError. La
  guardia sta in `app.py` e usa solo `streamlit`: una guardia dentro il modulo
  che protegge manca proprio quando serve.
- **SQLite e PostgREST rispondono diversamente al «non c'e' niente».** SQLite
  da' una tabella vuota con le colonne, PostgREST un DataFrame senza colonne.
  `data.con_colonne()` normalizza; `tests/test_backend_vuoto.py` simula la
  forma di PostgREST, perche' provare su SQLite non basta.
- **Nelle cache di Streamlit vanno solo DataFrame**, mai oggetti di dominio: un
  oggetto in cache conserva la forma che aveva quando e' entrato.
- **`st.cache_data.clear()` provoca un rerun** che cancella il messaggio appena
  mostrato. Si usa `ui.invalida_dati()`.
- **I messaggi prima di `st.rerun()` non si vedono.**
- **`st.stop()` dentro una scheda ferma tutto lo script.**
- **Oltre la decina di pagine `st.navigation` tronca il menu**: serve
  `expanded=True`.
- **Una regola di validazione non scritta nel modulo e' una trappola.** La
  password minima non era dichiarata: chi ne scriveva una corta non veniva
  creato e non capiva perche'.

---

## 10. Cosa manca

In ordine di utilita'.

1. **Assegnazioni, contratti e ingaggi veri.** Il listone e' caricato ma non
   dice chi appartiene a chi. Finche' mancano, Salary Cap e Floor sono a zero.
2. **Date di nascita e nazionalita'** dei giocatori: senza, lo status Under 21
   non si determina.
3. **I vincoli sono dichiarati ma non applicati.** Minimo italiani, minimo
   Under 21 e limite scambi si vedono ma nessuno impedisce di violarli.
4. **Risultati di coppa e supercoppa** non si importano separatamente.
5. **Svincoli registrati**: il Dead Money si calcola ma non si scrive.
6. **Dati anagrafici non modificabili** dopo l'iscrizione.
7. **Registro dei lodi**: la tabella c'e', manca la pagina.
8. **Tabellone del draft** da proiettare durante l'asta.

---

## 11. Manutenzione

**Aggiornare il database** — `db/schema.sql` e' rieseguibile e contiene gli
`alter table ... add column if not exists`. Se qualcosa manca, la pagina
«Impostazioni lega» lo dice e mostra la query da incollare.

**Se il sito da' errore dopo un aggiornamento** — ⋮ → *Reboot app*. I dati
stanno su Supabase, non si perde niente.

**Prima di ogni push** — `pytest` e `ruff check .` devono passare puliti.
