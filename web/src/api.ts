/**
 * L'unico posto da cui si parla con l'API.
 *
 * `credentials: "include"` su ogni chiamata: la sessione sta in un cookie
 * httpOnly, quindi il browser lo manda da solo e il JavaScript non lo vede
 * mai. Niente token in localStorage — un XSS se lo porterebbe via.
 */

export class ErroreApi extends Error {
  stato: number;

  constructor(stato: number, messaggio: string) {
    super(messaggio);
    this.stato = stato;
  }

  /** Vero quando la sessione non c'e' piu': chi chiama rimanda all'accesso. */
  get fuori(): boolean {
    return this.stato === 401;
  }
}

async function chiama<T>(percorso: string, opzioni: RequestInit = {}): Promise<T> {
  const risposta = await fetch(`/api${percorso}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opzioni.headers ?? {}) },
    ...opzioni,
  });

  if (!risposta.ok) {
    // Il dettaglio di FastAPI quando c'e', altrimenti qualcosa di leggibile:
    // «[object Object]» in faccia a un utente non spiega niente.
    let dettaglio = `Errore ${risposta.status}`;
    try {
      const corpo = await risposta.json();
      if (typeof corpo?.detail === "string") dettaglio = corpo.detail;
    } catch {
      /* risposta senza corpo JSON: tengo il messaggio generico */
    }
    throw new ErroreApi(risposta.status, dettaglio);
  }

  if (risposta.status === 204) return undefined as T;
  return risposta.json() as Promise<T>;
}

export type ChiSono = {
  nome_utente: string;
  nome: string;
  ruolo: string;
  squadra_id: number | null;
  lega_id: number | null;
  deve_cambiare_password: boolean;
  puo_importare: boolean;
  puo_svincolare: boolean;
  puo_scrivere_in_bacheca: boolean;
};

export type Squadra = {
  id: number;
  nome: string;
  presidente: string;
  motto: string;
  stadio: string;
  citta: string;
  curva: string;
  anno_fondazione: number | null;
  colori: { primario: string; secondario: string; stile_maglia: string };
  logo: string | null;
  giocatori: number;
  anni_impegnati: number;
  monte_ingaggi: number;
  dead_money: number;
  e_mia: boolean;
};

export const api = {
  entra: (nome_utente: string, password: string) =>
    chiama<ChiSono>("/accesso", {
      method: "POST",
      body: JSON.stringify({ nome_utente, password }),
    }),
  io: () => chiama<ChiSono>("/io"),
  esci: () => chiama<void>("/esci", { method: "POST" }),
  squadre: () => chiama<Squadra[]>("/squadre"),
};
