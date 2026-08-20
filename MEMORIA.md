# Memoria del progetto

Stato corrente di FantaCalcio NuoVo. **Chi apre una sessione nuova legge questo
file per primo**: dice dove siamo, cosa e' gia' deciso e cosa non va rifatto.

Claude Code carica `CLAUDE.md` da solo a ogni avvio, e da li' arriva qui: non
serve chiedere "leggi la memoria", basta dire cosa si vuole fare.

> Aggiornare con `/memoria` a fine sessione, prima del push.

---

## In una riga

Gestionale della lega: contratti, monte anni, Salary Cap/Floor, draft, scambi.
Il gioco (voti, formazioni, risultati) resta su Leghe Fantacalcio.

**Ultimo aggiornamento:** 20 agosto 2026 — listone ufficiale (509 giocatori veri) e script di migrazione.

---

## Decisioni prese (non riaprirle senza motivo)

| Decisione | Quando | Nota |
|---|---|---|
| Fasce di gol: **primo gol a 66**, poi uno ogni 6 | confermata dalla lega | L'art. 1 cita anche 60: e' la formulazione del regolamento a essere imprecisa, non il codice |
| Il **draft si fa offline** e si carica via CSV | confermata | Il sito non conduce l'asta: serve l'import, che c'e' |
| Stack **Streamlit + Supabase** | scelta iniziale | La logica e' Python puro senza Streamlit: un cambio di frontend non la tocca |
| Il campo squadra si chiama **presidente** | rinominato da `fantallenatore` | |
| Maglie **disegnate dai colori sociali** in SVG | | Chi vuole carica un'immagine propria |
| Le cache si invalidano con **`ui.invalida_dati()`** | | Vedi le trappole sotto |

## Cosa c'e' (funziona e ha i test)

- **Motore di regole**: monte anni 66, rosa 30-33 (36 con Under 21), max 3
  portieri, regola "1/3", Salary Cap 100M, Salary Floor 80M, Dead Money al 50%.
- **Draft Lottery** a due fasce, ordine di chiamata con la deroga dei round
  multipli di 3, probabilita' delle pick stimate per simulazione.
- **Import CSV** di rose e risultati, con anteprima di conformita' *prima* di
  scrivere.
- **Identita' squadre**: presidente, motto, stadio, colori, maglia, logo.
- **Login** con ruoli: il presidente ratifica e importa, gli altri gestiscono
  solo la propria squadra.
- **Registro scambi**: proposta → accettazione → ratifica, con ri-validazione
  al momento della ratifica e applicazione ai contratti.

## Cosa manca (in ordine di utilita')

1. **Assegnazioni, contratti e ingaggi**: il listone e' caricato (509 giocatori
   con ruoli Mantra e quotazioni) ma non dice chi appartiene a quale squadra,
   con quanti anni e con quale ingaggio. Gli ingaggi vanno da Capology
   (art. 4). Finche' mancano, Salary Cap e Floor sono a zero.
2. **Data di nascita e nazionalita'**: senza, lo status Under 21 non si puo'
   determinare e l'espansione rosa non si applica.
3. **Svincoli registrati**: oggi il Dead Money si calcola ma non si scrive.
   Serve un flusso come quello degli scambi.
4. **Gestione utenti** dall'interfaccia: creare partecipanti, assegnare
   squadre, reimpostare password. Oggi gli utenti esistono solo nella demo.
5. **Registro dei lodi**: la tabella c'e' nello schema, manca la pagina.
6. **Tabellone del draft** da proiettare durante l'asta.

## Punti aperti del regolamento

Stanno in `PUNTI_APERTI.md`. I due che contano: quando si **chiudono** le
finestre di mercato (il regolamento dice solo quando aprono) e se il campionato
sara' di 18 o 27 giornate.

## Trappole gia' pagate (non ripeterle)

- **`st.html` non renderizza l'SVG inline.** Passa da un data URI e `st.image`.
- **`st.cache_data.clear()` provoca un rerun** che cancella il messaggio di
  conferma appena mostrato. Usa `ui.invalida_dati()`.
- **I messaggi prima di `st.rerun()` non si vedono.** Mettili nel
  `session_state` e mostrali in cima alla pagina al giro dopo.
- **Il contatore di versione deve essere globale**, non nel session_state: le
  cache di Streamlit sono condivise fra sessioni, e con dieci persone collegate
  chi entra dopo leggerebbe dati vecchi.
- **Il ruolo Mantra `B` (braccetto) esisteva nel listone vero e non nel mio
  modello.** Trovato solo caricando il file ufficiale: i dati veri scoprono
  buchi che i dati inventati non mostrano.
- **Nei CSV separati da `;` i ruoli non vanno scritti `M;C`** ma `M/C`. Il
  lettore ora lo riconosce e lo spiega.
- **Ricaricare la pagina fa uscire dal login** (session_state di Streamlit).
  Navigando col menu non succede. Scelta consapevole: un token in cookie
  aggiungerebbe superficie d'attacco per poco guadagno.

## Come si lavora

- Branch: `claude/fantacalcio-github-setup-j3e4ly` su `Tiri6/virtual-nutritionist`.
  Il progetto vive nella sottocartella `fantacalcio/`.
- Prima di ogni push: `.venv/bin/pytest` e `.venv/bin/ruff check .` devono
  passare puliti.
- Le regole del progetto stanno in `CLAUDE.md`: leggile prima di toccare il
  codice.

## Attenzione

`Tiri6/virtual-nutritionist` e' un repository **pubblico**. Non committare il
PDF del regolamento, i dati veri della lega, ne' credenziali.
