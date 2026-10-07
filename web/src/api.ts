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


export type Violazione = {
  codice: string;
  articolo: string;
  gravita: string;
  messaggio: string;
  valore: number | null;
  limite: number | null;
  bloccante: boolean;
};

export type GiocatoreInRosa = {
  id: number;
  nome: string;
  club: string;
  ruoli: string[];
  nazionalita: string;
  data_nascita: string | null;
  eta: number | null;
  italiano: boolean;
  u21: boolean;
  anni_residui: number;
  ingaggio: number;
  prolungato: boolean;
  in_scadenza: boolean;
  valore_residuo: number;
  dead_money_se_tagliato: number;
};

export type Titolo = {
  competizione: string;
  etichetta: string;
  icona: string;
  stagione: string;
  note: string;
};

export type Conti = {
  giocatori: number;
  limite_dimensione: number;
  slot_u21: number;
  portieri: number;
  anni_impegnati: number;
  monte_anni: number;
  contratti_annuali: number;
  annuali_richiesti: number;
  monte_ingaggi: number;
  dead_money: number;
  limite_cap: number;
  italiani: number;
  u21: number;
};

export type SquadraInDettaglio = Squadra & {
  posso_gestirla: boolean;
  conti: Conti;
  rosa: GiocatoreInRosa[];
  violazioni: Violazione[];
  titoli: Titolo[];
  riferimento_u21: string;
};

export type Giocatore = {
  id: number;
  nome: string;
  club: string;
  ruoli: string[];
  ruolo_classic: string;
  squadra: string;
  anni: number;
  ingaggio: number;
  nazionalita: string;
  data_nascita: string | null;
  eta: number | null;
  italiano: boolean;
  u21: boolean;
  quotazione: number | null;
  fvm: number | null;
};

export type Listone = {
  giocatori: Giocatore[];
  svincolato: string;
  con_stipendio: number;
  con_data_nascita: number;
  riferimento_u21: string;
};


export type SquadraInGalleria = {
  id: number;
  nome: string;
  presidente: string;
  motto: string;
  stadio: string;
  citta: string;
  curva: string;
  anno_fondazione: number | null;
  colore_primario: string;
  colore_secondario: string;
  stile_maglia: string;
  maglia: string;
  logo: string | null;
  modificabile: boolean;
};

export type Galleria = {
  squadre: SquadraInGalleria[];
  stili: { nome: string; etichetta: string }[];
  posso_crearne: boolean;
  nomi_occupati: string[];
};

export type ModificaIdentita = {
  nome: string;
  presidente: string;
  motto: string;
  stadio: string;
  citta: string;
  curva: string;
  colore_primario: string;
  colore_secondario: string;
  stile_maglia: string;
  anno_fondazione: number | null;
  logo?: string | null;
  maglia_caricata?: string | null;
  rimuovi_logo?: boolean;
  rimuovi_maglia?: boolean;
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
  squadra: (id: number) => chiama<SquadraInDettaglio>(`/squadre/${id}`),
  listone: () => chiama<Listone>("/giocatori"),
  identita: () => chiama<Galleria>("/identita"),
  salvaIdentita: (id: number, corpo: ModificaIdentita) =>
    chiama<SquadraInGalleria>(`/squadre/${id}/identita`, {
      method: "PUT",
      body: JSON.stringify(corpo),
    }),
  creaSquadra: (corpo: ModificaIdentita) =>
    chiama<SquadraInGalleria>("/squadre", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  caricaImmagine: (contenuto_base64: string, tipo_mime: string) =>
    chiama<{ data_uri: string }>("/immagini", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, tipo_mime }),
    }),
};
