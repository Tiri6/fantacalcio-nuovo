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

async function chiama<T>(
  percorso: string,
  opzioni: RequestInit = {},
): Promise<T> {
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

export type PortiereDellaRosa = {
  id: number;
  nome: string;
  disponibile: boolean;
};

export type PortiereLibero = {
  id: number;
  nome: string;
  club: string;
  ingaggio: number;
};

/**
 * Lo stato del Lodo Messina, deciso dal server.
 *
 * `motivo` si mostra, non si ricostruisce: la regola di quando l'emergenza
 * spetta sta nel dominio Python, e una seconda copia qui direbbe prima o poi
 * una cosa diversa da quella che il server poi applica.
 */
export type Emergenza = {
  portieri: PortiereDellaRosa[];
  attiva: boolean;
  ammessa: boolean;
  va_revocata: boolean;
  motivo: string;
  in_carica_id: number | null;
  in_carica_nome: string;
  malus: number;
  candidati: PortiereLibero[];
};

export type SquadraInDettaglio = Squadra & {
  posso_gestirla: boolean;
  conti: Conti;
  rosa: GiocatoreInRosa[];
  violazioni: Violazione[];
  titoli: Titolo[];
  riferimento_u21: string;
  emergenza: Emergenza;
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

export type AnnuncioLetto = {
  id: number;
  titolo: string;
  /** Markdown grezzo. Si rende con `<Markdown>`, mai con dangerouslySetInnerHTML. */
  testo: string;
  tipo: string;
  tipo_etichetta: string;
  tipo_icona: string;
  autore_nome: string;
  giornata: number | null;
  pubblicato: boolean;
  in_evidenza: boolean;
  data_leggibile: string;
};

export type Bacheca = {
  annunci: AnnuncioLetto[];
  tipi: { nome: string; etichetta: string; icona: string }[];
  posso_scrivere: boolean;
  nome_lega: string;
  titolo_minimo: number;
  titolo_massimo: number;
  testo_massimo: number;
};

export type Scritto = {
  titolo: string;
  testo: string;
  tipo: string;
  giornata: number | null;
  pubblicato: boolean;
  in_evidenza: boolean;
};

/** Solo i campi mandati cambiano: due bottoni premuti insieme non si sovrascrivono. */
export type Correzione = Partial<Scritto>;

export type Conteggio = {
  etichetta: string;
  valore: string;
  nota: string;
  quota: number | null;
  stato: string;
};

export type RigaCruscotto = {
  squadra_id: number;
  squadra: string;
  dimensione: number;
  limite_dimensione: number;
  slot_u21: number;
  portieri: number;
  anni_impegnati: number;
  monte_anni: number;
  anni_disponibili: number;
  contratti_annuali: number;
  annuali_richiesti: number;
  monte_ingaggi: number;
  dead_money: number;
  spesa_salariale: number;
  limite_cap: number;
  spazio_salariale: number;
  conforme: boolean;
  violazioni: Violazione[];
};

export type Cruscotto = {
  momento: string;
  momenti: { nome: string; etichetta: string }[];
  conteggi: Conteggio[];
  righe: RigaCruscotto[];
  monte_anni: number;
  salary_cap: number;
  salary_floor: number;
  mercato_bloccato: boolean;
  finestra_piu_recente: string;
};

export type RigaClassifica = {
  posizione: number;
  squadra: string;
  giocate: number;
  vinte: number;
  pareggiate: number;
  perse: number;
  gol_fatti: number;
  gol_subiti: number;
  differenza_reti: number;
  punti: number;
  punti_fantacalcio: number;
};

export type Partita = {
  giornata: number;
  casa: string;
  trasferta: string;
  gol_casa: number | null;
  gol_trasferta: number | null;
  punti_casa: number | null;
  punti_trasferta: number | null;
};

export type AndamentoSquadra = {
  squadra: string;
  punti: { giornata: number; punti: number }[];
};

export type Campionato = {
  classifica: RigaClassifica[];
  partite: Partita[];
  andamento: AndamentoSquadra[];
  giornate_disputate: number;
  giornate_totali: number;
  giornate_in_calendario: number;
  calendario_importato: boolean;
};

export type TitoloLetto = {
  id: number;
  competizione: string;
  competizione_etichetta: string;
  competizione_icona: string;
  stagione: string;
  squadra_nome: string;
  squadra_id: number | null;
  note: string;
};

export type Albo = {
  titoli: TitoloLetto[];
  bacheche: {
    squadra: string;
    titoli: Record<string, number>;
    totale: number;
  }[];
  competizioni: { nome: string; etichetta: string; icona: string }[];
  squadre: string[];
  stagione_corrente: string;
  nome_lega: string;
  posso_registrare: boolean;
};

export type Registrazione = {
  competizione: string;
  stagione: string;
  squadra_nome: string;
  note: string;
};

export type Profilo = {
  nome_utente: string;
  nome_completo: string;
  ruolo: string;
  ruolo_etichetta: string;
  squadra: string;
  nome_lega: string;
  email: string;
  data_nascita: string;
  eta: number | null;
  sesso: string;
  citta: string;
  squadra_preferita: string;
  ha_codice_recupero: boolean;
};

export type Voce = { etichetta: string; valore: string; nota: string };

export type Partecipante = {
  id: number;
  nome_utente: string;
  nome_completo: string;
  ruolo: string;
  ruolo_etichetta: string;
  squadra: string;
  sono_io: boolean;
};

export type DatiLega = {
  nome: string;
  stagione: string;
  modalita: string;
  codice_invito: string;
  partecipanti: Partecipante[];
  posti: number;
  squadre_fondate: number;
  regole: { titolo: string; voci: Voce[] }[];
  fasce_gol: { da: string; gol: number }[];
  moduli_ammessi: string[];
  moduli_possibili: number;
  bonus: Voce[];
  modificatori: string[];
  spiegazione_sostituzioni: string;
  posso_amministrare: boolean;
  posso_cambiare_regole: boolean;
  posso_reimpostare_password: boolean;
  inviti: { email: string; stato: string }[];
  richieste_password: { id: number; nome_utente: string; chiesta_il: string }[];
  ruoli_assegnabili: { nome: string; etichetta: string }[];
  problemi_schema: { messaggio: string }[];
  sql_di_riparazione: string;
};

export type VoceModulo = {
  nome: string;
  etichetta: string;
};

/**
 * Quel che serve a disegnare il modulo di registrazione.
 *
 * Le tendine arrivano dal server e non si scrivono qui: le squadre del cuore
 * sono quelle vere della stagione quando il listone e' caricato, e i minimi
 * (password, eta') sono gli stessi numeri che il dominio poi applica. Una
 * copia nel front-end direbbe una cosa e il server ne farebbe un'altra.
 */
export type ModuloRegistrazione = {
  primo_utente: boolean;
  sessi: VoceModulo[];
  squadre_preferite: string[];
  password_minima: number;
  eta_minima: number;
};

export type Iscrizione = {
  nome: string;
  cognome: string;
  data_nascita: string;
  sesso: string;
  citta: string;
  squadra_preferita: string;
  nome_utente: string;
  email: string;
  password: string;
  conferma: string;
};

export type InvitoTrovato = {
  lega_nome: string;
  codice: string;
};

/** Cosa manca a questa persona prima di poter usare il sito. */
export type StatoOnboarding = {
  serve: "lega" | "squadra" | "niente";
  nome: string;
  nome_lega: string;
  codice_invito: string;
  esistono_leghe: boolean;
  invito: InvitoTrovato | null;
  modalita: VoceModulo[];
  formati: VoceModulo[];
  stili_maglia: VoceModulo[];
};

export type NuovaLega = {
  nome: string;
  stagione: string;
  modalita: string;
  formato: string;
  partecipanti: number;
  coppa_italia: boolean;
  f1_rush: boolean;
};

export type NuovaSquadra = {
  nome: string;
  citta: string;
  stadio: string;
  curva: string;
  motto: string;
  colore_primario: string;
  colore_secondario: string;
  stile_maglia: string;
};

export type LegaCreata = {
  nome: string;
  codice_invito: string;
};

export type MovimentoScambio = {
  giocatore_id: number;
  nome_giocatore: string;
  da_squadra_id: number;
  da_squadra: string;
  a_squadra_id: number;
  a_squadra: string;
  anni: number;
};

export type ViolazioneScambio = {
  codice: string;
  articolo: string;
  messaggio: string;
  bloccante: boolean;
};

export type ScambioLetto = {
  id: number;
  stato: string;
  stato_etichetta: string;
  aperto: boolean;
  squadra_a_id: number;
  squadra_a: string;
  squadra_b_id: number;
  squadra_b: string;
  movimenti: MovimentoScambio[];
  note: string;
  creato_il: string;
  giornata_efficacia: number | null;
  /** Cosa puo' fare chi guarda: lo decide il dominio, non il browser. */
  posso_accettare: boolean;
  posso_rifiutare: boolean;
  posso_annullare: boolean;
  posso_ratificare: boolean;
  violazioni: ViolazioneScambio[];
};

export type PaginaScambi = {
  scambi: ScambioLetto[];
  mia_squadra_id: number | null;
  conclusi: number;
  residui: number | null;
  mercato_aperto: boolean;
  finestra: string;
  squadre: { id: number; nome: string }[];
};

export type EsitoProposta = {
  scambio: ScambioLetto | null;
  violazioni: ViolazioneScambio[];
  inviata: boolean;
};

// --- Importazione -----------------------------------------------------------
//
// Le colonne non sono scritte qui: le manda il server, che le prende dallo
// stesso modulo che legge i file. Una tabella scritta nella pagina sarebbe la
// copia che diverge al primo sinonimo nuovo.

export type CampoFile = {
  nome: string;
  obbligatorio: boolean;
  esempio: string;
  nota: string;
};

export type FormatiImport = {
  posso_importare: boolean;
  giocatori_in_catalogo: number;
  nota_formato: string;
  campi_listone: CampoFile[];
  campi_rose: CampoFile[];
  campi_risultati: CampoFile[];
  modello_rose: string;
  modello_risultati: string;
  soglia_primo_gol: number;
  passo_gol: number;
};

export type ProblemaFile = {
  riga: number;
  colonna: string;
  valore: string;
  messaggio: string;
};

export type EsitoFile = {
  lette: number;
  errori: ProblemaFile[];
  avvisi: ProblemaFile[];
  intestazioni_ignorate: string[];
  importabile: boolean;
};

export type ViolazioneImport = {
  codice: string;
  articolo: string;
  messaggio: string;
  bloccante: boolean;
};

export type StatoRosaImport = {
  squadra: string;
  dimensione: number;
  limite_dimensione: number;
  slot_u21: number;
  portieri: number;
  anni_impegnati: number;
  monte_anni: number;
  contratti_annuali: number;
  annuali_richiesti: number;
  spesa_salariale: number;
  limite_cap: number;
  spazio_salariale: number;
  conforme: boolean;
  violazioni: ViolazioneImport[];
};

export type RigaRosaImport = {
  riga: number;
  squadra: string;
  giocatore: string;
  club: string;
  ruoli: string[];
  anni: number;
  ingaggio: number;
};

export type EsitoRoseImport = EsitoFile & {
  righe: RigaRosaImport[];
  squadre: StatoRosaImport[];
};

export type RigaListoneImport = {
  id_ufficiale: number;
  nome: string;
  club: string;
  ruoli: string[];
  quotazione: number | null;
  fvm: number | null;
};

export type EsitoListoneImport = EsitoFile & {
  righe: RigaListoneImport[];
  club: number;
};

export type RigaRisultatoImport = {
  giornata: number;
  casa: string;
  trasferta: string;
  punti_casa: number;
  punti_trasferta: number;
};

export type EsitoRisultatiImport = EsitoFile & {
  righe: RigaRisultatoImport[];
};

export type RiepilogoImport = { messaggio: string };

export const api = {
  entra: (nome_utente: string, password: string) =>
    chiama<ChiSono>("/accesso", {
      method: "POST",
      body: JSON.stringify({ nome_utente, password }),
    }),
  io: () => chiama<ChiSono>("/io"),
  moduloRegistrazione: () => chiama<ModuloRegistrazione>("/registrazione"),
  iscriviti: (corpo: Iscrizione) =>
    chiama<ChiSono>("/registrazione", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  esci: () => chiama<void>("/esci", { method: "POST" }),
  squadre: () => chiama<Squadra[]>("/squadre"),
  squadra: (id: number) => chiama<SquadraInDettaglio>(`/squadre/${id}`),
  listone: () => chiama<Listone>("/giocatori"),
  onboarding: () => chiama<StatoOnboarding>("/onboarding"),
  scambi: () => chiama<PaginaScambi>("/scambi"),
  proponiScambio: (corpo: {
    squadra_b_id: number;
    da_me: number[];
    da_loro: number[];
    note: string;
  }) =>
    chiama<EsitoProposta>("/scambi", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  decidiScambio: (
    id: number,
    azione: "accetta" | "rifiuta" | "annulla" | "ratifica",
    giornata_efficacia?: number | null,
  ) =>
    chiama<ScambioLetto>(`/scambi/${id}`, {
      method: "POST",
      body: JSON.stringify({
        azione,
        giornata_efficacia: giornata_efficacia ?? null,
      }),
    }),
  creaLega: (corpo: NuovaLega) =>
    chiama<LegaCreata>("/onboarding/lega", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  unisciti: (codice: string) =>
    chiama<LegaCreata>("/onboarding/unisciti", {
      method: "POST",
      body: JSON.stringify({ codice }),
    }),
  fondaSquadra: (corpo: NuovaSquadra) =>
    chiama<{ id: number; nome: string }>("/onboarding/squadra", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  attivaPortiereEmergenza: (
    squadra: number,
    giocatore_id: number,
    indisponibili: number[],
  ) =>
    chiama<Emergenza>(`/squadre/${squadra}/portiere-emergenza`, {
      method: "POST",
      body: JSON.stringify({ giocatore_id, indisponibili }),
    }),
  revocaPortiereEmergenza: (squadra: number) =>
    chiama<Emergenza>(`/squadre/${squadra}/portiere-emergenza`, {
      method: "DELETE",
    }),
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
  bacheca: () => chiama<Bacheca>("/bacheca"),
  scriviInBacheca: (corpo: Scritto) =>
    chiama<AnnuncioLetto>("/bacheca", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  correggiAnnuncio: (id: number, corpo: Correzione) =>
    chiama<AnnuncioLetto>(`/bacheca/${id}`, {
      method: "PUT",
      body: JSON.stringify(corpo),
    }),
  cancellaAnnuncio: (id: number) =>
    chiama<void>(`/bacheca/${id}`, { method: "DELETE" }),
  profilo: () => chiama<Profilo>("/profilo"),
  cambiaPassword: (attuale: string, nuova: string, conferma: string) =>
    chiama<void>("/profilo/password", {
      method: "PUT",
      body: JSON.stringify({ attuale, nuova, conferma }),
    }),
  generaCodiceRecupero: () =>
    chiama<{ codice: string }>("/profilo/codice-recupero", { method: "POST" }),
  lega: () => chiama<DatiLega>("/lega"),
  invita: (email: string) =>
    chiama<DatiLega>("/lega/inviti", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  assegnaRuolo: (nome_utente: string, ruolo: string) =>
    chiama<DatiLega>("/lega/ruoli", {
      method: "PUT",
      body: JSON.stringify({ nome_utente, ruolo }),
    }),
  reimpostaPassword: (nome_utente: string) =>
    chiama<{ nome_utente: string; password: string }>(
      `/lega/reimposta/${encodeURIComponent(nome_utente)}`,
      { method: "POST" },
    ),
  archiviaRichiesta: (id: number) =>
    chiama<DatiLega>(`/lega/richieste/${id}`, { method: "DELETE" }),
  campionato: () => chiama<Campionato>("/campionato"),
  albo: () => chiama<Albo>("/albo"),
  registraTitolo: (corpo: Registrazione) =>
    chiama<TitoloLetto>("/albo", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  cancellaTitolo: (id: number) =>
    chiama<void>(`/albo/${id}`, { method: "DELETE" }),
  cruscotto: (momento: string) =>
    chiama<Cruscotto>(`/cruscotto?momento=${encodeURIComponent(momento)}`),
  formatiImport: () => chiama<FormatiImport>("/importazione"),
  anteprimaListone: (contenuto_base64: string, nome: string) =>
    chiama<EsitoListoneImport>("/importazione/listone/anteprima", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  importaListone: (contenuto_base64: string, nome: string) =>
    chiama<RiepilogoImport>("/importazione/listone", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  anteprimaRose: (contenuto_base64: string, nome: string) =>
    chiama<EsitoRoseImport>("/importazione/rose/anteprima", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  importaRose: (contenuto_base64: string, nome: string, sostituisci: boolean) =>
    chiama<RiepilogoImport>("/importazione/rose", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome, sostituisci }),
    }),
  anteprimaRisultati: (contenuto_base64: string, nome: string) =>
    chiama<EsitoRisultatiImport>("/importazione/risultati/anteprima", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  importaRisultati: (contenuto_base64: string, nome: string) =>
    chiama<RiepilogoImport>("/importazione/risultati", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  caricaImmagine: (contenuto_base64: string, tipo_mime: string) =>
    chiama<{ data_uri: string }>("/immagini", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, tipo_mime }),
    }),
};
