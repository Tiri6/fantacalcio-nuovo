/**
 * Leggere un file scelto dall'utente, per mandarlo all'API.
 *
 * Il contenuto viaggia in base64 dentro il JSON, come le immagini della
 * maglia: `python-multipart` non e' fra le dipendenze dell'API, e un formato
 * di trasporto in meno e' una cosa in meno che si rompe in produzione.
 *
 * `readAsDataURL` e non `btoa`: il listone e' un .xlsx, cioe' byte veri.
 * `btoa` vuole una stringa di caratteri sotto 256 e su un file binario
 * solleva, oppure — se glielo si passa dopo un `readAsText` — restituisce
 * byte diversi da quelli del file, perche' la decodifica UTF-8 ha gia'
 * sostituito quello che non sapeva leggere.
 */

/** Il contenuto del file in base64, senza il prefisso `data:`. */
export function leggiBase64(file: File): Promise<string> {
  return new Promise((risolvi, rifiuta) => {
    const lettore = new FileReader();
    lettore.onerror = () =>
      rifiuta(new Error("Non riesco a leggere il file dal tuo computer."));
    lettore.onload = () => {
      const risultato = String(lettore.result ?? "");
      const virgola = risultato.indexOf(",");
      if (virgola < 0) {
        rifiuta(new Error("Il file risulta vuoto."));
        return;
      }
      risolvi(risultato.slice(virgola + 1));
    };
    lettore.readAsDataURL(file);
  });
}

/** Fa scaricare un testo come file, senza passare dal server. */
export function scarica(nome: string, contenuto: string, tipo = "text/csv") {
  const indirizzo = URL.createObjectURL(new Blob([contenuto], { type: tipo }));
  const collegamento = document.createElement("a");
  collegamento.href = indirizzo;
  collegamento.download = nome;
  collegamento.click();
  // Senza, il Blob resta in memoria per tutta la visita.
  URL.revokeObjectURL(indirizzo);
}
