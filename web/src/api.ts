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
  /** Le voci di menu di Coppa e F1 Rush dipendono da questi due. */
  gioca_coppa: boolean;
  gioca_f1_rush: boolean;
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

export type ContoTitoli = { etichetta: string; icona: string; quanti: number };

export type SquadraInDettaglio = Squadra & {
  posso_gestirla: boolean;
  conti: Conti;
  rosa: GiocatoreInRosa[];
  violazioni: Violazione[];
  titoli: Titolo[];
  /** Quanti per competizione: contare le pastiglie smette di funzionare a venti. */
  titoli_per_competizione: ContoTitoli[];
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
  italiano: boolean;
  u21: boolean;
  quotazione: number | null;
  fvm: number | null;
};

export type Listone = {
  giocatori: Giocatore[];
  svincolato: string;
  con_stipendio: number;
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

/** Una squadra della lega che nessuno guida ancora. */
export type SquadraLibera = {
  id: number;
  nome: string;
  giocatori: number;
};

/** Cosa manca a questa persona prima di poter usare il sito. */
export type StatoOnboarding = {
  serve: "lega" | "squadra" | "niente";
  nome: string;
  nome_lega: string;
  codice_invito: string;
  esistono_leghe: boolean;
  /** Quando ce ne sono, la domanda e' «quale di queste guidi», non «come la chiami». */
  squadre_libere: SquadraLibera[];
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
  /** Da che giornata avrebbe effetto ratificando adesso (art. 8). */
  efficacia_proposta: number;
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
  /** Il V3 li ha aboliti, ma è un parametro: la lega può rivotarlo. */
  prolungamenti_ammessi: boolean;
  anni_contratto_massimo: number;
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
  campi_calendario: CampoFile[];
  modello_listone: string;
  modello_rose: string;
  modello_risultati: string;
  soglia_primo_gol: number;
  passo_gol: number;
};

/* --- le regole di lega, come modulo ------------------------------------- */

export type ValoreRegola = string | number | boolean | string[] | null;

export type SceltaRegola = { valore: string; etichetta: string };

export type CampoRegola = {
  nome: string;
  etichetta: string;
  /** intero | decimale | booleano | scelta | multi | testo */
  tipo: string;
  valore: ValoreRegola;
  scelte: SceltaRegola[];
  /** Vero quando «nessun limite» è una risposta ammessa. */
  opzionale: boolean;
  /** "" o "milioni": come si legge il numero, già convertito. */
  unita: string;
};

export type GruppoRegole = { titolo: string; campi: CampoRegola[] };

export type PaginaRegole = {
  posso_modificare: boolean;
  stagione: string;
  squadre_iscritte: number;
  gruppi: GruppoRegole[];
  /** Quel che da qui non si tocca, col motivo. */
  escluse: { nome: string; motivo: string }[];
};

export type RigaU21 = {
  squadra_id: number;
  squadra: string;
  in_rosa: number;
  /** `null` finché nessuno ha mai ricalcolato: prima si contano dal vivo. */
  congelati: number | null;
  limite_rosa: number;
};

export type PaginaUnder21 = {
  riferimento: string;
  massimi: number;
  posso_ricalcolare: boolean;
  mai_ricalcolato: boolean;
  righe: RigaU21[];
};

export type CambiamentiRegole = {
  cambia: string[];
  avvisi: string[];
  errore: string;
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
  /** I tre che l'xlsx ufficiale non ha e il CSV completo sì. */
  ingaggio: number;
  nazionalita: string;
  data_nascita: string | null;
};

export type EsitoListoneImport = EsitoFile & {
  righe: RigaListoneImport[];
  club: number;
  con_stipendio: number;
  con_data_nascita: number;
  con_nazionalita: number;
  senza_stipendio: string[];
  /** Cosa ha riconosciuto il lettore: si accettano due formati. */
  fonti: string[];
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

export type RigaCalendarioImport = {
  giornata: number;
  giornata_serie_a: number | null;
  casa: string;
  trasferta: string;
  /** Vuoti dove non si e' giocato: uno 0-0 in classifica vale un punto. */
  punti_casa: number | null;
  punti_trasferta: number | null;
};

export type EsitoCalendarioImport = EsitoFile & {
  righe: RigaCalendarioImport[];
  giornate: number;
  giocate: number;
  squadre: string[];
  squadre_nuove: string[];
  senza_giornata_serie_a: number;
};

export type PartitaTabellino = {
  casa: string;
  trasferta: string;
  modulo_casa: string;
  modulo_trasferta: string;
  punti_casa: number;
  punti_trasferta: number;
  gol_casa: number | null;
  gol_trasferta: number | null;
};

/** Il tabellino di giornata di Leghe: non ha le righe e gli avvisi degli
 *  altri import, perche' non e' un file di righe ma una giornata intera. */
export type EsitoTabellinoImport = {
  leggibile: boolean;
  giornata: number;
  partite: PartitaTabellino[];
  problemi: string[];
  squadre_mancanti: string[];
  non_abbinati: string[];
  senza_partita: string[];
  voti: number;
  scrivibile: boolean;
};

export type RiepilogoImport = { messaggio: string };

// --- Formazione -------------------------------------------------------------
//
// Le caselle arrivano gia' risolte: per ognuna, chi la occupa di diritto e chi
// ci si adatterebbe pagando il malus. La tabella Mantra resta in Python.

export type GiocatoreScelta = {
  id: number;
  nome: string;
  ruoli: string[];
  // P, D, C o A: il reparto di casa, deciso dal server.
  sigla: string;
  // Calcolati dal server dalla storia della lega: la pagina li stampa e basta.
  // `null` = mai preso voto (si scrive un trattino, non uno zero).
  media_voto: number | null;
  fantamedia: number | null;
  presenze: number;
  titolare_pct: number | null;
};

export type CasellaFormazione = {
  indice: number;
  etichetta: string;
  reparto: string;
  sigla: string;
  liberi: number[];
  adattati: number[];
};

export type BloccoFormazioni = {
  modificabile: boolean;
  motivo: string;
  inizio: string | null;
  mancano_secondi: number | null;
};

export type SquadraInCampo = {
  squadra_id: number;
  squadra: string;
  modulo: string;
  reparti: GiocatoreScelta[][];
  panchina: GiocatoreScelta[];
};

export type PaginaFormazione = {
  giornata: number;
  giornate_totali: number;
  competizione: string;
  competizioni: string[];
  blocco: BloccoFormazioni;
  mia_squadra_id: number | null;
  posso_schierare: boolean;
  avviso: string | null;
  moduli: string[];
  modulo: string;
  modulo_ufficiale: boolean;
  difensori: number;
  centrocampisti: number;
  attaccanti: number;
  caselle: CasellaFormazione[];
  titolari_richiesti: number;
  panchinari: number;
  adattamento_ammesso: boolean;
  malus_adattamento: number;
  modalita_sostituzioni: string;
  rosa: GiocatoreScelta[];
  titolari: number[];
  panchina: number[];
  squadre: SquadraInCampo[];
  mancanti: string[];
  schierate: number;
  totali: number;
};

// --- Giornata ---------------------------------------------------------------

export type InCampoLetto = {
  id: number;
  nome: string;
  ruoli: string[];
  punti: number | null;
  entrato: boolean;
  senza_voto: boolean;
  adattato: boolean;
};

export type TabellinoLetto = {
  totale: number;
  gol: number;
  modificatore_difesa: number;
  malus_adattamento: number;
  malus_emergenza: number;
  adattati: number;
  sostituzioni: string[];
  senza_voto_rimasti: string[];
};

export type SquadraDellaPartita = {
  squadra_id: number;
  squadra: string;
  modulo: string | null;
  ha_schierato: boolean;
  reparti: InCampoLetto[][];
  panchina: string[];
  tabellino: TabellinoLetto | null;
};

export type PartitaLetta = {
  id: number;
  stato: "salvata" | "provvisoria" | "da giocare";
  gol_casa: number | null;
  gol_trasferta: number | null;
  punti_casa: number | null;
  punti_trasferta: number | null;
  casa: SquadraDellaPartita;
  trasferta: SquadraDellaPartita;
};

export type PaginaGiornata = {
  giornata: number;
  giornate: number[];
  competizione: string;
  competizioni: string[];
  partite: PartitaLetta[];
  formazioni_salvate: number;
  voti_caricati: number;
  calendario_vuoto: boolean;
  posso_calcolare: boolean;
  modello_voti: string;
  senza_formazione: string[];
};

export type VotiLetti = {
  messaggio: string;
  salvati: number;
  senza_voto: number;
  non_abbinati: string[];
};

export type GiornataCalcolata = {
  messaggio: string;
  calcolate: number;
  saltate: number;
  avvisi: string[];
};

// --- Calendario, Coppa, F1 Rush ---------------------------------------------

export type PartitaInCalendario = {
  giornata: number;
  casa: string;
  trasferta: string;
  gol_casa: number | null;
  gol_trasferta: number | null;
  punti_casa: number | null;
  punti_trasferta: number | null;
};

export type Weekend = {
  numero: number;
  serie_a: number;
  nella_lega: string;
};

export type PaginaCalendario = {
  squadre: string[];
  giornate_disputate: number;
  giornate_totali: number;
  partite_giocate: number;
  partite: PartitaInCalendario[];
  senza_partite: boolean;
  weekend: Weekend[];
  gioca_coppa: boolean;
  // Opzione della lega; `posso_modificare` lo calcola il server.
  prima_serie_a: number;
  serie_a_totali: number;
  posso_modificare: boolean;
};

export type FaseDiCoppa = { fase: string; quando: string; stato: string };

export type PaginaCoppa = {
  si_gioca: boolean;
  formato: string;
  squadre_ammesse: number;
  a_gironi: boolean;
  gironi: number;
  squadre_per_girone: number;
  giornate_di_girone: number;
  qualificate_per_girone: number;
  squadre_a_eliminazione: number;
  turni: number;
  nomi_turni: string[];
  prima_giornata: number;
  ogni_quante_giornate: number;
  teste_di_serie: boolean;
  spareggio_ai_fantapunti: boolean;
  tabellone: FaseDiCoppa[];
  ammesse: string[];
  accoppiamenti: [string, string][];
};

export type RigaF1 = {
  posizione: number;
  squadra: string;
  punti: number;
  vittorie_di_tappa: number;
  fantapunti: number;
};

export type TappaF1 = { titolo: string; podio: string[] };

export type PaginaF1 = {
  si_gioca: boolean;
  giornate_serie_a: number;
  prima_giornata: number;
  ultima_giornata: number;
  criterio: string;
  punti_per_posizione: number[];
  classifica: RigaF1[];
  tappe: TappaF1[];
  senza_giornate_serie_a: boolean;
  vincitrice: string | null;
  posso_assegnare: boolean;
  squadre: string[];
};

// --- Regolamento e chat -----------------------------------------------------

export type VoceRegolamento = { voce: string; valore: string };

export type GruppoRegolamento = {
  titolo: string;
  nota: string;
  voci: VoceRegolamento[];
};

export type PaginaRegolamento = {
  gruppi: GruppoRegolamento[];
  ruoli_mantra: { sigla: string; nome: string }[];
  coppa: string | null;
  f1_rush: string | null;
  chat_attiva: boolean;
};

export type StatoChat = {
  attiva: boolean;
  scheda: string;
  domande_di_esempio: string[];
  limite_domanda: number;
  posso_configurare: boolean;
  nome_secret: string;
};

/** Un turno di conversazione. Lo storico lo tiene il browser. */
export type MessaggioChat = { ruolo: "utente" | "assistente"; testo: string };

export type Svincolabile = {
  giocatore_id: number;
  nome: string;
  anni_residui: number;
  anni_oltre_quello_in_corso: number;
  ingaggio: number;
  valore_residuo: number;
  dead_money: number;
  a_carico_quest_anno: number;
};

export type Svincoli = {
  posso_svincolare: boolean;
  quota_dead_money: number;
  giocatori: Svincolabile[];
};

export type MotivoSvincolo = "riparazione" | "pre-asta" | "correzione";

/* --- la sala del draft ---------------------------------------------------- */

export type GiocatoreLibero = {
  id: number;
  nome: string;
  club: string;
  ruoli: string[];
  ingaggio: number;
};

export type ChiamataLetta = {
  numero: number;
  squadra_id: number;
  squadra: string;
  giocatore_id: number;
  giocatore: string;
  ruoli: string[];
  anni: number;
  quando: string;
};

export type TurnoLetto = {
  numero: number;
  squadra_id: number;
  squadra: string;
  round: number;
  posizione: number;
  etichetta: string;
  scade_il: string | null;
  /** Deciso dal server: la pagina non deve dedurre di chi e' il turno. */
  e_mio: boolean;
};

export type ViolazioneDiSala = {
  codice: string;
  articolo: string;
  messaggio: string;
  bloccante: boolean;
};

/**
 * Lo stato della sala, con la **versione** per interrogarla a vuoto.
 *
 * `versione` e' l'impronta di quel che la pagina mostra: quale sala, in che
 * stato, quante chiamate. Chi fa polling la rimanda, e se non e' cambiata il
 * server risponde `aggiornato: false` senza rileggere rose e listone: dieci
 * persone collegate diventano dieci confronti fra due stringhe invece di
 * dieci letture complete ogni due secondi.
 */
export type PaginaSala = {
  versione: string;
  aggiornato: boolean;
  c_e_una_sala: boolean;
  id: number | null;
  tipo: string | null;
  tipo_etichetta: string | null;
  stato: string | null;
  stagione: string | null;
  chiamate_totali: number;
  round_totali: number;
  turno: TurnoLetto | null;
  prossimi: TurnoLetto[];
  chiamate: ChiamataLetta[];
  disponibili: GiocatoreLibero[];
  mia_squadra_id: number | null;
  posso_amministrare: boolean;
  anni_minimo: number;
  anni_massimo: number;
  miei_acquisti: ChiamataLetta[];
  anni_correggibili: boolean;
  anni_chiudono_il: string | null;
  anni_motivo: string;
};

export type EsitoChiamata = {
  fatta: boolean;
  messaggio: string;
  violazioni: ViolazioneDiSala[];
};

export type SquadraEstratta = {
  squadra_id: number;
  squadra: string;
  /** "bassa" sono le peggio classificate: si giocano le pick 1-5. */
  fascia: string;
};

export type Lottery = {
  ordine: SquadraEstratta[];
  pesi: number[];
  spiegazione: string;
  /** Quanto era probabile ogni pick, prima dell'estrazione. */
  probabilita: { squadra: string; per_pick: number[] }[];
};

export type Tabellone = {
  c_e_una_sala: boolean;
  tipo_etichetta: string;
  round: { numero: number; squadre: string[] }[];
};

export type InScadenza = {
  squadra: string;
  giocatore: string;
  club: string;
  ruoli: string;
  ingaggio: number;
};

/* --- assegnazioni --------------------------------------------------------- */

export type LiberoAssegnabile = {
  id: number;
  nome: string;
  club: string;
  ruoli: string[];
  ingaggio: number;
  nazionalita: string;
  u21: boolean;
};

export type SquadraAssegnabile = {
  id: number;
  nome: string;
  giocatori: number;
  anni_impegnati: number;
  monte_ingaggi: number;
  /** Sul Cap pesa anche il Dead Money: questo numero lo tiene già dentro. */
  spazio_salariale: number;
};

export type ViolazioneAssegnazione = {
  codice: string;
  articolo: string;
  messaggio: string;
  bloccante: boolean;
};

export type PaginaAssegnazioni = {
  posso_assegnare: boolean;
  anni_minimo: number;
  anni_massimo: number;
  monte_anni: number;
  limite_cap: number;
  in_listone: number;
  liberi: LiberoAssegnabile[];
  squadre: SquadraAssegnabile[];
};

export type EsitoAssegnazione = {
  fatta: boolean;
  messaggio: string;
  violazioni: ViolazioneAssegnazione[];
};

export type NuovaSala = {
  tipo: "SETTEMBRE" | "RIPARAZIONE";
  round_totali: number;
  secondi_per_chiamata: number | null;
  ordine_lottery: number[];
};

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
  // Le due strade per rientrare, le uniche due rotte oltre ad accesso e
  // registrazione che rispondono a chi non ha una sessione.
  rientraConCodice: (corpo: {
    nome_utente: string;
    codice: string;
    nuova: string;
    conferma: string;
  }) =>
    chiama<void>("/recupero/codice", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  chiediAlPresidente: (nome_utente: string) =>
    chiama<void>("/recupero/richiesta", {
      method: "POST",
      body: JSON.stringify({ nome_utente }),
    }),
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
    prolungamenti?: Record<number, number>;
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
  rivendicaSquadra: (squadra_id: number) =>
    chiama<{ id: number; nome: string }>("/onboarding/squadra/rivendica", {
      method: "POST",
      body: JSON.stringify({ squadra_id }),
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
  regole: () => chiama<PaginaRegole>("/lega/regole"),
  under21: () => chiama<PaginaUnder21>("/lega/under21"),
  ricalcolaUnder21: () =>
    chiama<PaginaUnder21>("/lega/under21", { method: "POST" }),
  anteprimaRegole: (valori: Record<string, ValoreRegola>, stagione: string) =>
    chiama<CambiamentiRegole>("/lega/regole/anteprima", {
      method: "POST",
      body: JSON.stringify({ valori, stagione }),
    }),
  cambiaRegole: (valori: Record<string, ValoreRegola>, stagione: string) =>
    chiama<PaginaRegole>("/lega/regole", {
      method: "PUT",
      body: JSON.stringify({ valori, stagione }),
    }),
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
  svuotaListone: (conferma: string) =>
    chiama<{ messaggio: string; giocatori: number; contratti: number }>(
      "/importazione/listone/svuota",
      { method: "POST", body: JSON.stringify({ conferma }) },
    ),
  importaListone: (
    contenuto_base64: string,
    nome: string,
    sostituisci = false,
  ) =>
    chiama<RiepilogoImport>("/importazione/listone", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome, sostituisci }),
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
  anteprimaTabellino: (contenuto_base64: string, nome: string) =>
    chiama<EsitoTabellinoImport>("/importazione/tabellino/anteprima", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  importaTabellino: (contenuto_base64: string, nome: string) =>
    chiama<RiepilogoImport>("/importazione/tabellino", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  anteprimaCalendario: (contenuto_base64: string, nome: string) =>
    chiama<EsitoCalendarioImport>("/importazione/calendario/anteprima", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  importaCalendario: (contenuto_base64: string, nome: string) =>
    chiama<RiepilogoImport>("/importazione/calendario", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, nome }),
    }),
  formazione: (giornata: number, competizione: string, modulo: string) =>
    chiama<PaginaFormazione>(
      `/formazione?giornata=${giornata}` +
        `&competizione=${encodeURIComponent(competizione)}` +
        `&modulo=${encodeURIComponent(modulo)}`,
    ),
  schiera: (corpo: {
    giornata: number;
    competizione: string;
    modulo: string;
    titolari: number[];
    panchina: number[];
  }) =>
    chiama<{ salvata: boolean; messaggio: string }>("/formazione", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  giornata: (giornata: number, competizione: string) =>
    chiama<PaginaGiornata>(
      `/giornata?giornata=${giornata}&competizione=${encodeURIComponent(competizione)}`,
    ),
  caricaVoti: (corpo: {
    giornata: number;
    testo?: string;
    contenuto_base64?: string;
  }) =>
    chiama<VotiLetti>("/giornata/voti", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  calcolaGiornata: (giornata: number, competizione: string) =>
    chiama<GiornataCalcolata>(
      `/giornata/calcola?giornata=${giornata}` +
        `&competizione=${encodeURIComponent(competizione)}`,
      { method: "POST" },
    ),
  // «Fino a» è solo una vista; da dove parte il campionato lo dice la lega.
  calendario: (fino_a: number | null) =>
    chiama<PaginaCalendario>(
      fino_a === null ? "/calendario" : `/calendario?fino_a=${fino_a}`,
    ),
  coppa: () => chiama<PaginaCoppa>("/coppa"),
  f1Rush: () => chiama<PaginaF1>("/f1-rush"),
  assegnaF1: (squadra: string) =>
    chiama<PaginaF1>("/f1-rush/vincitrice", {
      method: "POST",
      body: JSON.stringify({ squadra }),
    }),
  regolamento: () => chiama<PaginaRegolamento>("/regolamento"),
  statoChat: () => chiama<StatoChat>("/regolamento/chat"),
  svincolabili: (squadra: number) =>
    chiama<Svincoli>(`/squadre/${squadra}/svincoli`),
  svincola: (squadra: number, giocatore_id: number, motivo: MotivoSvincolo) =>
    chiama<{ messaggio: string; anni_liberati: number; dead_money: number }>(
      `/squadre/${squadra}/svincoli`,
      { method: "POST", body: JSON.stringify({ giocatore_id, motivo }) },
    ),
  sala: (versione?: string) =>
    chiama<PaginaSala>(
      versione === undefined
        ? "/sala"
        : `/sala?versione=${encodeURIComponent(versione)}`,
    ),
  assegnazioni: () => chiama<PaginaAssegnazioni>("/assegnazioni"),
  anteprimaAssegnazione: (
    giocatore_id: number,
    squadra_id: number,
    anni: number,
  ) =>
    chiama<EsitoAssegnazione>("/assegnazioni/anteprima", {
      method: "POST",
      body: JSON.stringify({ giocatore_id, squadra_id, anni }),
    }),
  assegna: (giocatore_id: number, squadra_id: number, anni: number) =>
    chiama<EsitoAssegnazione>("/assegnazioni", {
      method: "POST",
      body: JSON.stringify({ giocatore_id, squadra_id, anni }),
    }),
  estraiLottery: () => chiama<Lottery>("/sala/lottery", { method: "POST" }),
  tabellone: () => chiama<Tabellone>("/sala/tabellone"),
  scadenze: () => chiama<InScadenza[]>("/sala/scadenze"),
  apriSala: (corpo: NuovaSala) =>
    chiama<PaginaSala>("/sala", {
      method: "POST",
      body: JSON.stringify(corpo),
    }),
  cominciaSala: () => chiama<PaginaSala>("/sala/comincia", { method: "POST" }),
  chiudiSala: () => chiama<PaginaSala>("/sala/chiudi", { method: "POST" }),
  chiamaGiocatore: (giocatore_id: number, anni: number) =>
    chiama<EsitoChiamata>("/sala/chiamate", {
      method: "POST",
      body: JSON.stringify({ giocatore_id, anni }),
    }),
  correggiAnni: (giocatore_id: number, anni: number) =>
    chiama<EsitoChiamata>("/sala/anni", {
      method: "PUT",
      body: JSON.stringify({ giocatore_id, anni }),
    }),
  caricaImmagine: (contenuto_base64: string, tipo_mime: string) =>
    chiama<{ data_uri: string }>("/immagini", {
      method: "POST",
      body: JSON.stringify({ contenuto_base64, tipo_mime }),
    }),
};

/**
 * Chiede una regola e consegna la risposta **a pezzi**, man mano che arrivano.
 *
 * Non passa da `chiama` perché quella aspetta un JSON intero: qui il corpo è
 * una riga JSON per pezzo (`application/x-ndjson`), e il punto è mostrarli
 * mentre arrivano — una domanda di regolamento ha una risposta breve ma il
 * modello ci mette qualche secondo, e senza streaming la pagina resta muta e
 * sembra rotta.
 *
 * `onErrore` è separato da `onPezzo` di proposito: un guasto a metà risposta
 * arriva quando lo stato HTTP è già stato mandato, e deve restare
 * distinguibile da quello che ha detto il modello.
 */
export async function chiediAlRegolamento(
  testo: string,
  storico: MessaggioChat[],
  onPezzo: (pezzo: string) => void,
  onErrore: (messaggio: string) => void,
): Promise<void> {
  const risposta = await fetch("/api/regolamento/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ testo, storico }),
  });

  if (!risposta.ok) {
    let dettaglio = `Errore ${risposta.status}`;
    try {
      const corpo = await risposta.json();
      if (typeof corpo?.detail === "string") dettaglio = corpo.detail;
    } catch {
      /* risposta senza corpo JSON: tengo il messaggio generico */
    }
    throw new ErroreApi(risposta.status, dettaglio);
  }

  const lettore = risposta.body?.getReader();
  if (!lettore) throw new ErroreApi(500, "Risposta senza corpo.");

  const decodifica = new TextDecoder();
  let avanzo = "";

  function consuma(blocco: string, ultimo: boolean) {
    avanzo += blocco;
    const righe = avanzo.split("\n");
    // L'ultima riga può essere spezzata a metà fra due blocchi: resta
    // nell'avanzo finché non arriva il resto.
    avanzo = ultimo ? "" : (righe.pop() ?? "");
    for (const riga of righe) {
      if (!riga.trim()) continue;
      try {
        const letta = JSON.parse(riga);
        if (typeof letta.testo === "string") onPezzo(letta.testo);
        else if (typeof letta.errore === "string") onErrore(letta.errore);
      } catch {
        /* riga illeggibile: meglio saltarla che rompere la risposta */
      }
    }
  }

  for (;;) {
    const { done, value } = await lettore.read();
    if (done) break;
    consuma(decodifica.decode(value, { stream: true }), false);
  }
  consuma(decodifica.decode(), true);
}
