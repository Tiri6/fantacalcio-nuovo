import { useMemo, useState } from "react";
import {
  ErroreApi,
  api,
  type CasellaFormazione,
  type PaginaFormazione,
  type SquadraInCampo,
} from "../api";
import { Campo } from "../campo";
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

// ---------------------------------------------------------------------------
// Il campo
// ---------------------------------------------------------------------------

function SchierataDa({ squadra }: { squadra: SquadraInCampo }) {
  return (
    <div className="schierata">
      <h3>
        {squadra.squadra} <span className="suo-modulo">{squadra.modulo}</span>
      </h3>
      <Campo reparti={squadra.reparti} />
      {squadra.panchina.length > 0 && (
        <p className="didascalia">
          Panchina: {squadra.panchina.map((g) => g.nome).join(", ")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Comporre
// ---------------------------------------------------------------------------

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

  const perId = useMemo(
    () => new Map(dato.rosa.map((g) => [g.id, g])),
    [dato.rosa],
  );

  /**
   * Chi entra in una casella lascia all'altra il giocatore che usciva.
   *
   * Le tendine mostrano **tutti** quelli che la casella ammette, anche se sono
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

  // Le caselle raggruppate per reparto, nell'ordine in cui arrivano.
  const perReparto: { reparto: string; caselle: CasellaFormazione[] }[] = [];
  for (const casella of dato.caselle) {
    const ultimo = perReparto[perReparto.length - 1];
    if (ultimo && ultimo.reparto === casella.reparto)
      ultimo.caselle.push(casella);
    else perReparto.push({ reparto: casella.reparto, caselle: [casella] });
  }

  return (
    <div className="riquadro">
      <div className="riga-modulo">
        <div className="campo">
          <label htmlFor="modulo">Modulo</label>
          <select
            id="modulo"
            value={dato.modulo}
            onChange={(e) => onModulo(e.target.value)}
          >
            {dato.moduli.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <p className="didascalia">
          {dato.modulo_ufficiale
            ? "Ogni casella dice quali ruoli ci stanno di diritto, come nello schema ufficiale Mantra. "
            : `${dato.difensori} difensori · ${dato.centrocampisti} centrocampisti · ${dato.attaccanti} attaccanti. `}
          {dato.adattamento_ammesso
            ? `Chi non è del ruolo che la casella chiede gioca lo stesso, con ${dato.malus_adattamento} punto in meno (modalità ${dato.modalita_sostituzioni}).`
            : "In modalità Easy nessuno può giocare fuori posizione."}
        </p>
      </div>

      {perReparto.map((gruppo) => (
        <div key={gruppo.reparto} className="reparto-scelta">
          <h3>{gruppo.reparto}</h3>
          <div className="caselle">
            {gruppo.caselle.map((casella) => {
              const scelto = titolari[casella.indice];
              const { liberi, adattati } = casella;
              const doppio = titolari.filter((g) => g === scelto).length > 1;
              return (
                <div key={casella.indice} className="campo">
                  <label htmlFor={`casella-${casella.indice}`}>
                    {casella.etichetta}
                  </label>
                  <select
                    id={`casella-${casella.indice}`}
                    value={scelto ?? ""}
                    className={
                      doppio
                        ? "doppio"
                        : casella.adattati.includes(scelto)
                          ? "adattato"
                          : undefined
                    }
                    onChange={(e) =>
                      scegli(casella.indice, Number(e.target.value))
                    }
                  >
                    {liberi.map((g) => (
                      <option key={g} value={g}>
                        {perId.get(g)?.nome} ({perId.get(g)?.ruoli.join("/")})
                      </option>
                    ))}
                    {adattati.length > 0 && (
                      <optgroup label={`Adattati (−${dato.malus_adattamento})`}>
                        {adattati.map((g) => (
                          <option key={g} value={g}>
                            {perId.get(g)?.nome} (
                            {perId.get(g)?.ruoli.join("/")})
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {doppioni.length > 0 && (
        <div className="errore" role="alert">
          ⛔ {doppioni.map((g) => perId.get(g)?.nome).join(", ")}{" "}
          {doppioni.length === 1 ? "è schierato" : "sono schierati"} in due
          caselle: ognuno può stare in un posto solo.
        </div>
      )}

      {fuoriPosizione.length > 0 && (
        <div className="avviso">
          🔁 Fuori posizione:{" "}
          {fuoriPosizione
            .map(
              (c) =>
                `${perId.get(titolari[c.indice])?.nome} nella casella «${c.etichetta}»`,
            )
            .join(", ")}
          . {fraseAdattamenti(fuoriPosizione.length, dato.malus_adattamento)}
        </div>
      )}

      <h3>
        Panchina{" "}
        <span className="didascalia">
          l'ordine conta: entra il primo che può farlo ({panchina.length}/
          {dato.panchinari})
        </span>
      </h3>
      <div className="panchina-scelta">
        {disponibili.map((g) => {
          const dentro = panchina.includes(g.id);
          const pieno = panchina.length >= dato.panchinari;
          return (
            <label
              key={g.id}
              className={dentro ? "interruttore preso" : "interruttore"}
            >
              <input
                type="checkbox"
                checked={dentro}
                disabled={!dentro && pieno}
                onChange={(e) => inPanchina(g.id, e.target.checked)}
              />
              <span>
                {dentro && (
                  <strong className="ordine">
                    {panchina.indexOf(g.id) + 1}
                  </strong>
                )}
                {g.nome} <small>{g.ruoli.join("/")}</small>
              </span>
            </label>
          );
        })}
      </div>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        onClick={salva}
        disabled={inCorso || doppioni.length > 0}
      >
        {inCorso ? "Salvo…" : "💾 Salva la formazione"}
      </button>
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
