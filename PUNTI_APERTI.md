# Punti aperti del regolamento

Il regolamento V2.1 e' molto piu' dettagliato della media, ma per scrivere il
codice ho dovuto prendere una posizione su alcuni punti che il testo non chiude.

Qui c'e' **cosa il gestionale fa oggi** e **cosa serve decidere**. Ogni voce e'
gia' un parametro: cambiare la decisione significa cambiare un valore in
`fantacalcio/regole.py`, non riscrivere il codice.

---

## 1. Fasce di gol: il primo gol scatta a 60 o a 66? ⚠️ importante

L'articolo 1 elenca *"Fasce di gol: di 6 in 6 – 60-66-72-78-84-90"*.

La sequenza e' coerente sia leggendo 60 come "primo gol" sia come "ultima
soglia a zero gol". Su Leghe Fantacalcio — la piattaforma dove giocate — il
primo gol scatta a 66.

**Oggi il codice usa 66**, per allinearsi ai risultati che vedete sulla
piattaforma. Se la lega intende 60, si cambia `soglia_primo_gol`.

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

## 8. Portiere d'emergenza (Lodo Messina)

Il modello prevede gia' il campo (`Rosa.portiere_emergenza_id`) e la regola e'
chiara: non firma contratto, non incide su monte anni ne' su Salary Cap, vota
con malus di −1 (Lodo Messina bis).

**Non c'e' ancora il flusso** per attivarlo e disattivarlo, perche' dipende
dalla disponibilita' dei portieri, che si legge su Leghe Fantacalcio.

## 9. Cose che il regolamento rimanda esplicitamente

- **Stadio di proprieta'** (art. 9): regole da definire.
- **Sponsorship** (art. 10): regole da definire, con l'eccezione
  dell'espansione Under 21 di italiannextgen.it, che e' gia' implementata.
- **Coppa e playoff**: proposta in appendice, da votare.
- **Prestiti**: l'istituto non e' previsto, quindi il codice non li contempla.

## 10. Registro dei lodi

Il principio di tassativita' dell'articolo 1 dice che le decisioni prese a
maggioranza entrano nel regolamento. Lo schema prevede gia' una tabella `lodi`
per tenerne traccia, ma **non c'e' ancora l'interfaccia** per registrarli e
collegarli all'articolo che modificano.

E' probabilmente la cosa piu' utile da aggiungere subito dopo le scritture:
oggi un lodo vive in una chat, e fra due stagioni nessuno ricorda perche'.
