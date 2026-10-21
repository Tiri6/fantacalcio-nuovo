import { useEffect, useMemo, useRef, useState } from "react";
import {
  ErroreApi,
  api,
  type CasellaFormazione,
  type GiocatoreScelta,
  type PaginaFormazione,
  type SquadraInCampo,
} from "../api";
import { Badge, Campo, CampoComposizione, type PostoInCampo } from "../campo";
import { useCarica } from "../carica";

/**
 * Formazione: chi mandi in campo, e cosa si vede quando la giornata chiude.
 *
 * Due momenti che non si mescolano: finché la giornata è aperta si compone la
 * propria formazione, dal blocco in poi si guardano quelle di tutti.
 *
 * **Qui dentro non c'è una riga di regolamento Mantra.** Quali ruoli stanno in
 * una casella e chi ci si adatta pagando il malus lo decide il server, che
 * manda per ogni casella due elenchi: chi la occupa di diritto e chi la
 * occuperebbe adattandosi. Questa pagina li mostra. Rifare quel conto qui
 * vorrebbe dire tenere la tabella Mantra in due posti, e il secondo
 * invecchierebbe in silenzio.
 */

function etichettaCompetizione(nome: string): string {
  const parole = nome.replace(/_/g, " ").toLowerCase();
  return parole.charAt(0).toUpperCase() + parole.slice(1);
}

/**
 * «Un adattamento: 1 punto in meno», al plurale solo quando serve.
 *
 * La stessa frase che il server rimanda dopo il salvataggio
 * (`formazioni.frase_adattamenti`): qui serve *prima*, mentre si compone, e
 * due lingue non possono condividere una funzione. Se cambia la regola del
 * singolare, cambiano tutte e due.
 */
function fraseAdattamenti(quanti: number, malus: number): string {
  const costo = Math.abs(malus) * quanti;
  const quanto = `${costo} ${costo === 1 ? "punto" : "punti"} in meno`;
  return quanti === 1
    ? `Un adattamento: ${quanto}.`
    : `${quanti} adattamenti: ${quanto}.`;
}

function mancaDetto(secondi: number): string {
  const ore = Math.floor(secondi / 3600);
  const minuti = Math.floor((secondi % 3600) / 60);
  if (ore >= 24) {
    const giorni = Math.floor(ore / 24);
    return `${giorni} ${giorni === 1 ? "giorno" : "giorni"} e ${ore % 24}h`;
  }
  return `${ore}h ${String(minuti).padStart(2, "0")}m`;
}

/** Il conto alla rovescia della barra: ore e minuti, poi solo minuti. */
function mancaBreve(secondi: number): string {
  if (secondi >= 3600) return mancaDetto(secondi);
  const minuti = Math.ceil(secondi / 60);
  return minuti <= 1 ? "meno di un minuto" : `${minuti} minuti`;
}

/** Media e titolarità come le ha calcolate il server; un trattino se mancano. */
function Statistiche({ giocatore }: { giocatore: GiocatoreScelta }) {
  const trattino = <span aria-label="nessun voto">–</span>;
  return (
    <span className="statistiche">
      <span>
        Media{" "}
        <b>
          {giocatore.media_voto === null
            ? trattino
            : giocatore.media_voto.toFixed(2)}
        </b>
      </span>
      <span>
        Titolare{" "}
        <b>
          {giocatore.titolare_pct === null ? (
            trattino
          ) : (
            <>{giocatore.titolare_pct}%</>
          )}
        </b>
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Il campo
// ---------------------------------------------------------------------------

function SchierataDa({ squadra }: { squadra: SquadraInCampo }) {
  return (
    <div className="schierata">
      <h3>
        {squadra.squadra} <span className="suo-modulo">{squadra.modulo}</span>
      </h3>
      <Campo reparti={squadra.reparti} variante="formazione" />
      {squadra.panchina.length > 0 && (
        <p className="didascalia">
          Panchina: {squadra.panchina.map((g) => g.nome).join(", ")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Il modulo, con il suo schema a puntini
// ---------------------------------------------------------------------------

/**
 * I puntini di un modulo, dall'attacco in alto al portiere in basso.
 *
 * Si legge solo la scritta («4-3-1-2»: quattro, tre, uno, due): è disegno, non
 * regola. Se un modulo è valido o no, e che caselle ha, lo decide il server.
 */
function SchemaModulo({ modulo }: { modulo: string }) {
  const file = modulo
    .split("-")
    .map(Number)
    .filter((n) => Number.isFinite(n) && n > 0)
    .reverse();
  return (
    <span className="schema-modulo" aria-hidden="true">
      {[...file, 1].map((quanti, i) => (
        <span key={i} className={i === file.length ? "fila fila-porta" : "fila"}>
          {Array.from({ length: quanti }, (_, j) => (
            <i key={j} />
          ))}
        </span>
      ))}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Comporre
// ---------------------------------------------------------------------------

type Filtro = "T" | "P" | "D" | "C" | "A";
const FILTRI: Filtro[] = ["T", "P", "D", "C", "A"];
const NOME_FILTRO: Record<Filtro, string> = {
  T: "Tutti",
  P: "Portieri",
  D: "Difensori",
  C: "Centrocampisti",
  A: "Attaccanti",
};

function RigaGiocatore({
  giocatore,
  nota,
  attivo,
  disabilitato,
  onClick,
}: {
  giocatore: GiocatoreScelta;
  nota?: string;
  attivo?: boolean;
  disabilitato?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={attivo ? "giocatore-riga attivo" : "giocatore-riga"}
      aria-pressed={attivo}
      disabled={disabilitato}
      onClick={onClick}
    >
      <Badge sigla={giocatore.sigla} />
      <span className="chi">
        <strong>{giocatore.nome}</strong>
        <small>
          {giocatore.ruoli.join("/")}
          {nota ? ` · ${nota}` : ""}
        </small>
        <Statistiche giocatore={giocatore} />
      </span>
    </button>
  );
}

function Componi({
  dato,
  onModulo,
  onSalvata,
}: {
  dato: PaginaFormazione;
  onModulo: (modulo: string) => void;
  onSalvata: (messaggio: string) => void;
}) {
  const [titolari, setTitolari] = useState<number[]>(dato.titolari);
  const [panchina, setPanchina] = useState<number[]>(dato.panchina);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);
  // Quale casella ha la scelta aperta, e il tasto da cui è partita (ci si
  // torna chiudendo, per chi usa la tastiera).
  const [aperta, setAperta] = useState<number | null>(null);
  const partenza = useRef<HTMLButtonElement | null>(null);
  const [filtro, setFiltro] = useState<Filtro>("T");
  const [ricerca, setRicerca] = useState("");
  // Il conto alla rovescia parte dai secondi che il server ha mandato.
  const [avvio] = useState(() => Date.now());
  const [adesso, setAdesso] = useState(avvio);
  useEffect(() => {
    if (dato.blocco.mancano_secondi === null) return;
    const giro = window.setInterval(() => setAdesso(Date.now()), 15000);
    return () => window.clearInterval(giro);
  }, [dato.blocco.mancano_secondi]);

  const perId = useMemo(
    () => new Map(dato.rosa.map((g) => [g.id, g])),
    [dato.rosa],
  );

  /**
   * Chi entra in una casella lascia all'altra il giocatore che usciva.
   *
   * La scelta mostra **tutti** quelli che la casella ammette, anche se sono
   * già schierati altrove: togliere i già scelti sembra più pulito, ma rende
   * impossibile il gesto più comune, cioè spostare un difensore da una casella
   * all'altra — per farlo toccherebbe prima svuotare quella di destinazione.
   *
   * Lo scambio vale solo se l'altra casella accetta chi esce: una punta in
   * difesa sarebbe peggio del doppione. Quando non lo accetta, quella casella
   * si riempie col primo che ci può stare e non gioca già: è lo stesso
   * criterio della proposta iniziale, e lascia chi compone libero di andare
   * avanti invece di consegnargli un doppione da sbrogliare.
   */
  function scegli(posizione: number, giocatore: number) {
    const dopo = [...titolari];
    const usciva = dopo[posizione];
    const altrove = dopo.indexOf(giocatore);
    dopo[posizione] = giocatore;

    if (altrove >= 0 && altrove !== posizione) {
      const casella = dato.caselle[altrove];
      const ammessi = casella ? [...casella.liberi, ...casella.adattati] : [];
      dopo[altrove] = ammessi.includes(usciva)
        ? usciva
        : // Nessuno libero per quella casella: il doppione resta, si vede, e
          // il salvataggio dice quale.
          (ammessi.find((g) => !dopo.includes(g)) ?? dopo[altrove]);
    }

    setTitolari(dopo);
    // Chi entra fra i titolari esce dalla panchina — e non è solo quello che
    // hai appena scelto: il rimpiazzo pescato per la casella svuotata poteva
    // essere seduto lì, e sarebbe rimasto titolare e panchinaro insieme.
    setPanchina((prima) => prima.filter((g) => !dopo.includes(g)));
  }

  function inPanchina(giocatore: number, dentro: boolean) {
    setPanchina((prima) =>
      dentro
        ? [...prima.filter((g) => g !== giocatore), giocatore]
        : prima.filter((g) => g !== giocatore),
    );
  }

  function chiudi() {
    setAperta(null);
    partenza.current?.focus();
  }

  // Quanti stanno fuori ruolo: non è un ricalcolo della regola, è la lettura
  // della risposta del server — il giocatore scelto sta negli «adattati» di
  // quella casella e non nei «liberi».
  const fuoriPosizione = dato.caselle.filter(
    (c) =>
      titolari[c.indice] !== undefined &&
      c.adattati.includes(titolari[c.indice]),
  );

  const scelti = new Set(titolari);
  const disponibili = dato.rosa.filter((g) => !scelti.has(g.id));

  // Chi è finito in due caselle. Capita quando lo scambio non era possibile,
  // e va detto subito: il server lo rifiuterebbe comunque, ma scoprirlo al
  // salvataggio vuol dire cercare da soli quale casella sistemare.
  const doppioni = [...new Set(titolari)].filter(
    (g) => titolari.filter((altro) => altro === g).length > 1,
  );

  async function salva() {
    setErrore(null);
    setInCorso(true);
    try {
      const esito = await api.schiera({
        giornata: dato.giornata,
        competizione: dato.competizione,
        modulo: dato.modulo,
        titolari,
        panchina,
      });
      onSalvata(esito.messaggio);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(false);
    }
  }

  // Le caselle raggruppate per reparto, nell'ordine in cui arrivano (porta per
  // prima); sul campo si disegnano al contrario, l'attacco in alto.
  const perReparto: PostoInCampo[][] = [];
  let ultimoReparto = "";
  for (const casella of dato.caselle) {
    const id = titolari[casella.indice];
    const posto: PostoInCampo = {
      indice: casella.indice,
      sigla: casella.sigla,
      etichetta: casella.etichetta,
      giocatore: perId.get(id) ?? null,
      adattato: casella.adattati.includes(id),
      doppio: titolari.filter((g) => g === id).length > 1,
    };
    if (casella.reparto === ultimoReparto)
      perReparto[perReparto.length - 1].push(posto);
    else perReparto.push([posto]);
    ultimoReparto = casella.reparto;
  }
  const righeCampo = [...perReparto].reverse();

  const casellaAperta = aperta === null ? null : dato.caselle[aperta];

  // La rosa disponibile, filtrata per reparto e per nome.
  const cerca = ricerca.trim().toLowerCase();
  const visibili = disponibili.filter(
    (g) =>
      (filtro === "T" || g.sigla === filtro) &&
      (cerca === "" || g.nome.toLowerCase().includes(cerca)),
  );

  const restano =
    dato.blocco.mancano_secondi === null
      ? null
      : Math.max(
          0,
          dato.blocco.mancano_secondi - Math.floor((adesso - avvio) / 1000),
        );

  return (
    <div className="componi">
      <section aria-labelledby="titolo-modulo" className="riquadro">
        <h2 id="titolo-modulo" className="titolo-sezione">
          Modulo
        </h2>
        <div className="moduli" role="group" aria-label="Scegli il modulo">
          {dato.moduli.map((m) => (
            <button
              key={m}
              type="button"
              className={m === dato.modulo ? "modulo-tasto attivo" : "modulo-tasto"}
              aria-pressed={m === dato.modulo}
              onClick={() => m !== dato.modulo && onModulo(m)}
            >
              <SchemaModulo modulo={m} />
              <span>{m}</span>
            </button>
          ))}
        </div>
        <p className="didascalia">
          {dato.modulo_ufficiale
            ? "Ogni casella dice quali ruoli ci stanno di diritto, come nello schema ufficiale Mantra. "
            : `${dato.difensori} difensori · ${dato.centrocampisti} centrocampisti · ${dato.attaccanti} attaccanti. `}
          {dato.adattamento_ammesso
            ? `Chi non è del ruolo che la casella chiede gioca lo stesso, con ${dato.malus_adattamento} punto in meno (modalità ${dato.modalita_sostituzioni}).`
            : "In modalità Easy nessuno può giocare fuori posizione."}
        </p>
      </section>

      <div className="componi-griglia">
        <section aria-labelledby="titolo-campo">
          <h2 id="titolo-campo" className="titolo-sezione">
            In campo{" "}
            <span className="didascalia">tocca una maglia per cambiare</span>
          </h2>
          <CampoComposizione
            righe={righeCampo}
            malus={dato.malus_adattamento}
            onApri={(indice, tasto) => {
              partenza.current = tasto;
              setAperta(indice);
            }}
          />
        </section>

        <div className="componi-lato">
          <section aria-labelledby="titolo-panchina">
            <h2 id="titolo-panchina" className="titolo-sezione">
              Panchina{" "}
              <span className="didascalia">
                entra il primo che può farlo ({panchina.length}/
                {dato.panchinari})
              </span>
            </h2>
            <ol className="panchina-striscia">
              {panchina.map((id, posto) => {
                const g = perId.get(id);
                if (!g) return null;
                return (
                  <li key={id}>
                    <button
                      type="button"
                      className="panchinaro"
                      aria-label={`${posto + 1}° in panchina: ${g.nome}, ${g.ruoli.join("/")}. Tocca per toglierlo`}
                      onClick={() => inPanchina(id, false)}
                    >
                      <span className="ordine">{posto + 1}</span>
                      <Badge sigla={g.sigla} />
                      <strong>{g.nome}</strong>
                      <small>{g.ruoli.join("/")}</small>
                      <span className="togli" aria-hidden="true">
                        ✕
                      </span>
                    </button>
                  </li>
                );
              })}
              {panchina.length < dato.panchinari && (
                <li className="panchinaro vuoto" aria-hidden="true">
                  <span className="ordine">{panchina.length + 1}</span>
                  <small>libero</small>
                </li>
              )}
            </ol>
          </section>

          <section aria-labelledby="titolo-rosa">
            <h2 id="titolo-rosa" className="titolo-sezione">
              Rosa disponibile{" "}
              <span className="didascalia">
                {disponibili.length - panchina.length} fuori dalla panchina
              </span>
            </h2>
            <div className="filtri-rosa">
              <div className="gruppo-filtri" role="group" aria-label="Reparto">
                {FILTRI.map((f) => (
                  <button
                    key={f}
                    type="button"
                    className={filtro === f ? "filtro attiva" : "filtro"}
                    aria-pressed={filtro === f}
                    aria-label={NOME_FILTRO[f]}
                    onClick={() => setFiltro(f)}
                  >
                    {f === "T" ? "Tutti" : f}
                  </button>
                ))}
              </div>
              <input
                type="search"
                className="cerca"
                placeholder="Cerca per nome"
                aria-label="Cerca un giocatore per nome"
                value={ricerca}
                onChange={(e) => setRicerca(e.target.value)}
              />
            </div>
            <ul className="rosa-elenco">
              {visibili.map((g) => {
                const posto = panchina.indexOf(g.id);
                const dentro = posto >= 0;
                const pieno = panchina.length >= dato.panchinari;
                return (
                  <li key={g.id}>
                    <RigaGiocatore
                      giocatore={g}
                      attivo={dentro}
                      nota={
                        dentro
                          ? `in panchina, ${posto + 1}°`
                          : !pieno
                            ? "tocca per la panchina"
                            : "panchina piena"
                      }
                      disabilitato={!dentro && pieno}
                      onClick={() => inPanchina(g.id, !dentro)}
                    />
                  </li>
                );
              })}
            </ul>
            {visibili.length === 0 && (
              <p className="didascalia">Nessun giocatore corrisponde.</p>
            )}
          </section>
        </div>
      </div>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <div className="barra-salva" role="region" aria-label="Riepilogo">
        <div className="riepilogo">
          <strong>{dato.modulo}</strong>
          <span
            className={
              doppioni.length > 0
                ? "esito rosso"
                : fuoriPosizione.length > 0
                  ? "esito ambra"
                  : "esito"
            }
            title={
              fuoriPosizione.length > 0
                ? fraseAdattamenti(
                    fuoriPosizione.length,
                    dato.malus_adattamento,
                  )
                : undefined
            }
          >
            {doppioni.length > 0
              ? `⛔ ${doppioni.length === 1 ? "1 doppione" : `${doppioni.length} doppioni`}`
              : fuoriPosizione.length > 0
                ? `🔁 ${fuoriPosizione.length} ${fuoriPosizione.length === 1 ? "adattamento" : "adattamenti"} (−${Math.abs(dato.malus_adattamento) * fuoriPosizione.length})`
                : "Nessun adattamento"}
          </span>
          <span className="blocco-stato">
            {restano === null
              ? "🗓️ Aperta"
              : `⏳ Chiude fra ${mancaBreve(restano)}`}
          </span>
        </div>
        <button
          type="button"
          className="principale salva"
          onClick={salva}
          disabled={inCorso || doppioni.length > 0}
        >
          {inCorso ? "Salvo…" : "💾 Salva"}
        </button>
      </div>

      {casellaAperta && (
        <FoglioScelta
          casella={casellaAperta}
          scelto={titolari[casellaAperta.indice]}
          titolari={titolari}
          panchina={panchina}
          dato={dato}
          perId={perId}
          onScegli={(id) => {
            scegli(casellaAperta.indice, id);
            chiudi();
          }}
          onChiudi={chiudi}
        />
      )}
    </div>
  );
}

/**
 * La scelta di chi occupa una casella: un foglio che sale dal basso sul
 * telefono, un pannello sul computer. Elenca prima chi ci sta di diritto,
 * poi chi ci si adatta pagando il malus — l'ordine e le liste sono del server.
 */
function FoglioScelta({
  casella,
  scelto,
  titolari,
  panchina,
  dato,
  perId,
  onScegli,
  onChiudi,
}: {
  casella: CasellaFormazione;
  scelto: number | undefined;
  titolari: number[];
  panchina: number[];
  dato: PaginaFormazione;
  perId: Map<number, GiocatoreScelta>;
  onScegli: (id: number) => void;
  onChiudi: () => void;
}) {
  const radice = useRef<HTMLDivElement>(null);

  // Esc chiude, Tab resta dentro il foglio, la pagina sotto non scorre, e il
  // focus parte da chi è già scelto.
  useEffect(() => {
    const prima = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const iniziale =
      radice.current?.querySelector<HTMLElement>(".giocatore-riga.attivo") ??
      radice.current?.querySelector<HTMLElement>(".giocatore-riga");
    iniziale?.focus();

    function tasto(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onChiudi();
        return;
      }
      if (e.key !== "Tab" || !radice.current) return;
      const dentro = Array.from(
        radice.current.querySelectorAll<HTMLElement>("button:not(:disabled)"),
      );
      if (dentro.length === 0) return;
      const primo = dentro[0];
      const ultimo = dentro[dentro.length - 1];
      if (e.shiftKey && document.activeElement === primo) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primo.focus();
      }
    }
    document.addEventListener("keydown", tasto);
    return () => {
      document.body.style.overflow = prima;
      document.removeEventListener("keydown", tasto);
    };
  }, []);

  function dove(id: number): string | undefined {
    const altrove = titolari.indexOf(id);
    if (id === scelto) return "qui";
    if (altrove >= 0)
      return `in campo come ${dato.caselle[altrove]?.etichetta ?? "titolare"}`;
    const posto = panchina.indexOf(id);
    return posto >= 0 ? `in panchina, ${posto + 1}°` : undefined;
  }

  const liberi = casella.liberi
    .map((id) => perId.get(id))
    .filter((g): g is GiocatoreScelta => g !== undefined);
  const adattati = casella.adattati
    .map((id) => perId.get(id))
    .filter((g): g is GiocatoreScelta => g !== undefined);

  return (
    <div className="foglio-velo" onClick={onChiudi}>
      <div
        ref={radice}
        className="foglio"
        role="dialog"
        aria-modal="true"
        aria-labelledby="foglio-titolo"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h3 id="foglio-titolo">
            Chi gioca come {casella.etichetta}{" "}
            <small>({casella.reparto})</small>
          </h3>
          <button
            type="button"
            className="chiudi"
            aria-label="Chiudi senza cambiare"
            onClick={onChiudi}
          >
            ✕
          </button>
        </header>
        <div className="foglio-corpo">
          <ul className="rosa-elenco">
            {liberi.map((g) => (
              <li key={g.id}>
                <RigaGiocatore
                  giocatore={g}
                  attivo={g.id === scelto}
                  nota={dove(g.id)}
                  onClick={() => onScegli(g.id)}
                />
              </li>
            ))}
          </ul>
          {adattati.length > 0 && (
            <>
              <h4>
                Adattati{" "}
                <span className="distintivo ambra">
                  −{Math.abs(dato.malus_adattamento)}
                </span>{" "}
                <small>giocano fuori ruolo e costano punti</small>
              </h4>
              <ul className="rosa-elenco">
                {adattati.map((g) => (
                  <li key={g.id}>
                    <RigaGiocatore
                      giocatore={g}
                      attivo={g.id === scelto}
                      nota={dove(g.id)}
                      onClick={() => onScegli(g.id)}
                    />
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function Formazione() {
  const [giornata, setGiornata] = useState(0);
  const [competizione, setCompetizione] = useState("CAMPIONATO");
  // Il modulo sta qui e non nel modulo di composizione: cambiarlo cambia le
  // caselle, quindi chi la occupa di diritto e chi ci si adatta — tutta roba
  // che decide il server. Tenendolo di sotto, la pagina restava con le caselle
  // del modulo vecchio e le tendine offrivano i giocatori sbagliati.
  const [modulo, setModulo] = useState("");
  const [giro, setGiro] = useState(0);
  const [conferma, setConferma] = useState<string | null>(null);
  const { dato, errore, inCorso } = useCarica(
    () => api.formazione(giornata, competizione, modulo),
    [giornata, competizione, modulo, giro],
  );

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const giornate = Array.from(
    { length: dato.giornate_totali },
    (_, i) => i + 1,
  );

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📋 Formazione</h1>
        <p>
          Chi mandi in campo. Si chiude un minuto prima del calcio d'inizio.
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      <div className="filtri">
        <div className="campo">
          <label htmlFor="giornata">Giornata</label>
          <select
            id="giornata"
            value={dato.giornata}
            onChange={(e) => {
              setGiornata(Number(e.target.value));
              // Un'altra giornata puo' avere gia' una formazione salvata,
              // col suo modulo: si lascia scegliere al server.
              setModulo("");
            }}
          >
            {giornate.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>

        {dato.competizioni.length > 1 && (
          <div className="campo">
            <label htmlFor="competizione">Competizione</label>
            <select
              id="competizione"
              value={dato.competizione}
              onChange={(e) => {
                setCompetizione(e.target.value);
                setModulo("");
              }}
            >
              {dato.competizioni.map((c) => (
                <option key={c} value={c}>
                  {etichettaCompetizione(c)}
                </option>
              ))}
            </select>
          </div>
        )}

        <div
          className={
            dato.blocco.modificabile
              ? "riquadro stato-blocco aperta"
              : "riquadro stato-blocco chiusa"
          }
        >
          {dato.blocco.modificabile ? (
            dato.blocco.mancano_secondi !== null ? (
              <>
                <strong>⏳ Ancora aperta</strong>
                <span>
                  Mancano {mancaDetto(dato.blocco.mancano_secondi)} alla
                  chiusura.
                </span>
              </>
            ) : (
              <>
                <strong>🗓️ Nessun orario in calendario</strong>
                <span>
                  Finché non c'è un calcio d'inizio, le formazioni restano
                  aperte.
                </span>
              </>
            )
          ) : (
            <>
              <strong>🔒 Formazioni chiuse</strong>
              <span>{dato.blocco.motivo}</span>
            </>
          )}
        </div>
      </div>

      {dato.avviso && <div className="avviso">♻️ {dato.avviso}</div>}

      {dato.posso_schierare ? (
        <Componi
          // Rimontare quando cambia giornata, competizione o modulo: le scelte
          // di prima non valgono per un'altra partita ne' per altre caselle.
          key={`${dato.giornata}-${dato.competizione}-${dato.modulo}-${giro}`}
          dato={dato}
          onModulo={setModulo}
          onSalvata={(messaggio) => {
            setConferma(messaggio);
            setGiro((g) => g + 1);
          }}
        />
      ) : (
        <div className="riquadro avviso">
          {dato.mia_squadra_id === null
            ? "Non hai una squadra in questa lega: qui sotto puoi comunque vedere le formazioni degli altri."
            : dato.blocco.modificabile
              ? "La tua rosa è vuota: prima si fa il draft."
              : "La giornata è chiusa: la tua formazione è quella che vedi qui sotto insieme alle altre."}
        </div>
      )}

      <h2>Le formazioni della giornata</h2>
      {dato.squadre.length === 0 ? (
        <p className="didascalia">
          Nessuno ha ancora salvato la formazione per questa giornata.
        </p>
      ) : (
        <>
          <p className="didascalia">
            {dato.schierate === 1 ? "Una squadra" : `${dato.schierate} squadre`}{" "}
            su {dato.totali} {dato.schierate === 1 ? "ha" : "hanno"} schierato.
            Le formazioni sono visibili a tutti.
          </p>
          <div className="schierate">
            {dato.squadre.map((s) => (
              <SchierataDa key={s.squadra_id} squadra={s} />
            ))}
          </div>
        </>
      )}

      {dato.mancanti.length > 0 && (
        <div className="avviso">
          ⚠️ Senza formazione: {dato.mancanti.join(", ")}. Chi non schiera
          prende {dato.titolari_richiesti} posti vuoti, cioè zero punti.
        </div>
      )}
    </>
  );
}
