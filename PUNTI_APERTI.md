# Punti aperti del regolamento

Il regolamento V2.1 e' molto piu' dettagliato della media, ma per scrivere il
codice ho dovuto prendere una posizione su alcuni punti che il testo non chiude.

Qui c'e' **cosa il gestionale fa oggi** e **cosa serve decidere**. Ogni voce e'
gia' un parametro: cambiare la decisione significa cambiare un valore in
`fantacalcio/regole.py`, non riscrivere il codice.

---

## 1. Fasce di gol — ✅ CHIUSO

L'articolo 1 elenca *"Fasce di gol: di 6 in 6 – 60-66-72-78-84-90"*, che si
prestava a due letture.

**Deciso dalla lega: il primo gol e' a 66**, poi uno ogni 6. E' quello che il
codice applica (`soglia_primo_gol = 66`, `passo_gol = 6`), ed e' anche il
comportamento di Leghe Fantacalcio. Conviene correggere la formulazione
nell'articolo 1 alla prossima revisione del regolamento, togliendo il 60
dall'elenco per evitare che la domanda si riapra fra un anno.

## 2. Draft Lottery: come si assegnano le pick dalla 2ª alla 5ª?

L'articolo 3 fissa le probabilita' per fascia: *50% alla peggio classificata,
quindi 20% – 15% – 10% – 5% a scalare*. Sono cinque pesi per cinque squadre,
il che descrive bene **la prima estrazione**, ma non dice cosa succede dopo.

**Oggi il codice** estrae senza reimmissione: chi esce viene tolto e i pesi
restanti si rinormalizzano sulle squadre ancora in gioco (lo stesso meccanismo
della lottery NBA). La pagina Draft mostra le probabilita' risultanti per ogni
pick, stimate per simulazione.

Alternativa possibile: sorteggiare solo la pick 1 con quei pesi e assegnare le
pick 2-5 per ordine di classifica inversa.

Nota pratica: il draft si svolge di persona e il risultato si carica dopo via
CSV, quindi questa scelta incide sul sorteggio della Lottery ma non sulla
conduzione dell'asta.

## 3. Quando si chiudono le finestre di mercato?

L'articolo 5 dice quando ogni finestra **apre** (dopo la 9ª e dopo la 18ª
giornata) ma non per quanto resti aperta.

**Oggi il codice** considera il mercato bloccato dopo la giornata di apertura
dell'ultima finestra. Serve stabilire una durata esplicita: un numero di
giorni, oppure "fino allo svolgimento del draft di riparazione".

## 4. Lodo Longoni: chi conta i due prolungamenti?

*"non consentita per piu' di 2 giocatori per squadra per stagione sportiva"*.

**Oggi il codice** li conta sulla **squadra che riceve** il giocatore, perche'
e' lei a beneficiare del contratto piu' lungo. Se invece il limite va contato
su chi cede, o sullo scambio nel suo complesso, e' una riga da cambiare.

## 5. Quante giornate ha il campionato?

Con 10 squadre, andata e ritorno fanno **18 giornate**, e i gironcini da 9
partite dell'articolo 5 tornano perfettamente. L'appendice pero' propone un
campionato su **27 giornate** (ancora da votare), che darebbe tre gironcini.

**Oggi il codice** genera 18 giornate. Se passa la proposta a 27, cambiano
anche le giornate di apertura delle finestre (9 / 18 / 27?).

## 6. Sforamento del Salary Cap: quali punizioni?

L'articolo 4 dice che le punizioni *"sono ancora da definire"*.

**Oggi il codice** segnala lo sforamento e lo qualifica come bloccante a fine
asta e come avviso durante la stagione (art. 8b), ma non applica sanzioni.
Quando le deciderete, diventano un calcolo in piu'.

## 7. Penalita' per mancata consegna della formazione

L'appendice propone: nessuna sanzione la prima volta, poi riduzione
progressiva del Salary Cap della stagione successiva (–1M, –3M, –5M).

**Non implementata**: e' una proposta da votare. Quando passa, diventa un
Salary Cap per squadra invece che uno unico di lega — una modifica piccola ma
che tocca la struttura, quindi meglio farla dopo il voto.

## 8. Il draft si gestisce offline — ✅ CHIARITO

Il draft si svolge di persona e poi si carica il CSV con l'esito. Il sito non
deve quindi condurre l'asta in tempo reale: gli serve la pagina **Importa
dati**, che c'e', con la verifica di conformita' fatta *prima* di scrivere.

Resta utile la sala draft come tabellone da proiettare durante l'asta, ma non
e' piu' un requisito bloccante.

## 9. Portiere d'emergenza (Lodo Messina)

Il modello prevede gia' il campo (`Rosa.portiere_emergenza_id`) e la regola e'
chiara: non firma contratto, non incide su monte anni ne' su Salary Cap, vota
con malus di −1 (Lodo Messina bis).

**Non c'e' ancora il flusso** per attivarlo e disattivarlo, perche' dipende
dalla disponibilita' dei portieri, che si legge su Leghe Fantacalcio.

## 10. Cose che il regolamento rimanda esplicitamente

- **Stadio di proprieta'** (art. 9): regole da definire.
- **Sponsorship** (art. 10): regole da definire, con l'eccezione
  dell'espansione Under 21 di italiannextgen.it, che e' gia' implementata.
- **Coppa e playoff**: proposta in appendice, da votare.
- **Prestiti**: l'istituto non e' previsto, quindi il codice non li contempla.

## 11. Registro dei lodi

Il principio di tassativita' dell'articolo 1 dice che le decisioni prese a
maggioranza entrano nel regolamento. Lo schema prevede gia' una tabella `lodi`
per tenerne traccia, ma **non c'e' ancora l'interfaccia** per registrarli e
collegarli all'articolo che modificano.

E' probabilmente la cosa piu' utile da aggiungere subito dopo le scritture:
oggi un lodo vive in una chat, e fra due stagioni nessuno ricorda perche'.

## 7. Soglie dei modificatori di reparto

La creazione lega permette di accendere i modificatori di **difesa**,
**centrocampo** e **attacco**, come fa Leghe Fantacalcio. Quello che il
regolamento non dice — e che io non ho potuto verificare, perche' da questo
ambiente il sito della lega non e' raggiungibile — sono **le soglie esatte**:
a quale media voto scatta quale bonus.

**Oggi il codice** parte da queste tabelle (`FASCE_DIFESA`,
`FASCE_CENTROCAMPO`, `FASCE_ATTACCO` in `fantacalcio/leghe.py`):

| Media difesa | Bonus | | Media centrocampo | Bonus | | Media attacco | Bonus |
|---|---|---|---|---|---|---|---|
| 6,00 | +1 | | 6,50 | +1 | | 7,00 | +1 |
| 6,25 | +2 | | 7,00 | +2 | | 7,50 | +2 |
| 6,50 | +3 | | 7,50 | +3 | | 8,00 | +3 |
| 6,75 | +4 | | | | | | |
| 7,00 | +5 | | | | | | |
| 7,25 | +6 | | | | | | |

**Da decidere:** confermare o correggere queste soglie confrontandole con
quelle in vigore sulla piattaforma. Sono `FasciaModificatore(soglia, bonus)`,
quindi si cambiano modificando una riga: `bonus_modificatore()` ordina le fasce
da sola, e l'ordine in cui le si scrive non conta.

Finche' i voti di giornata non entrano nel gestionale (oggi arrivano gia'
aggregati da Leghe Fantacalcio), la scelta non cambia nessun risultato: e' una
scheda di configurazione che il sito conserva, non un calcolo che esegue.

## 8. Numero di giornate

`OpzioniLega.giornate_totali` parte da 27, come `CalendarioStagione`. Resta il
punto aperto gia' annotato altrove: 18 o 27. Ora che e' un'opzione di lega, la
decisione si applica dalla schermata di creazione senza toccare il codice.
