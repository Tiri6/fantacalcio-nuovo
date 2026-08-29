# Dati pronti da caricare

File da scaricare e dare in pasto alla pagina **Listone giocatori →
Consolida e carica**. Sono qui, nel repository, perche' cosi' si scaricano da
qualsiasi dispositivo senza dover ripescare un allegato in chat.

| File | Cos'e' |
|---|---|
| `listone-2026_27.csv` | I 518 giocatori del listone ufficiale 2026/27, con ruolo Classic e Mantra, piu' stipendio lordo annuo e nazionalita' per 402 di loro (fonte Capology, colonna *Lordo annuo EUR*). |
| `listone-2026_27-senza-stipendio.csv` | I 116 rimasti senza importo, squadra per squadra. Di questi, 64 non compaiono affatto nella fonte e 52 ci sono con la casella vuota. |

**La data di nascita e' vuota per tutti**: la fonte degli stipendi porta
l'eta', non la data, e da un'eta' non si ricava un compleanno. Finche' manca,
lo status Under 21 non si puo' determinare.

Per completare: si apre il CSV in un foglio di calcolo, si riempiono le
caselle mancanti e si ricarica lo stesso file. Chi ha gia' lo stipendio non
lo perde, e gli id non cambiano mai — quindi le rose restano attaccate ai
loro giocatori.
