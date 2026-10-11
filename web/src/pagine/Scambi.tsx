import { useState, type FormEvent } from "react";
import {
  ErroreApi,
  api,
  type GiocatoreInRosa,
  type PaginaScambi,
  type ScambioLetto,
  type ViolazioneScambio,
} from "../api";
import { milioni, useCarica } from "../carica";

/**
 * Scambi fra fantallenatori: comporre, proporre, decidere.
 *
 * Nessuna regola vive qui. Quel che si può fare arriva già deciso dal server
 * (`posso_accettare`, `posso_ratificare`…) e le violazioni le calcola
 * `mercato.valida_scambio`: il browser disegna, non giudica. Se giudicasse,
 * fra due mesi direbbe una cosa e il server ne applicherebbe un'altra.
 *
 * Le violazioni si rileggono **a ogni apertura della pagina**, non si
 * conservano con la proposta: fra la proposta e oggi le rose possono essere
 * cambiate, e uno scambio valido ieri può non esserlo più.
 */

function Violazioni({ elenco }: { elenco: ViolazioneScambio[] }) {
  if (elenco.length === 0) return null;
  const bloccanti = elenco.filter((v) => v.bloccante);
  const avvisi = elenco.filter((v) => !v.bloccante);
  return (
    <ul className="violazioni">
      {[...bloccanti, ...avvisi].map((v) => (
        <li key={v.codice} className={v.bloccante ? "blocco" : "avviso"}>
          <strong>{v.articolo}</strong> {v.messaggio}
        </li>
      ))}
    </ul>
  );
}

function Scheda({
  scambio,
  onFatto,
}: {
  scambio: ScambioLetto;
  onFatto: (messaggio: string) => void;
}) {
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);
  const [giornata, setGiornata] = useState<string>("");

  async function decidi(
    azione: "accetta" | "rifiuta" | "annulla" | "ratifica",
    riuscito: string,
  ) {
    setErrore(null);
    setInCorso(true);
    try {
      await api.decidiScambio(
        scambio.id,
        azione,
        giornata ? Number(giornata) : null,
      );
      onFatto(riuscito);
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
    } finally {
      setInCorso(false);
    }
  }

  const stati: Record<string, string> = {
    PROPOSTO: "ambra",
    ACCETTATO: "azzurra",
    RATIFICATO: "verde",
    RIFIUTATO: "rossa",
    ANNULLATO: "",
  };

  return (
    <article className={scambio.aperto ? "scambio" : "scambio chiuso"}>
      <div className="pastiglie">
        <span className={`pastiglia ${stati[scambio.stato] ?? ""}`}>
          {scambio.stato_etichetta}
        </span>
        <span className="tenue">{scambio.creato_il}</span>
        {scambio.giornata_efficacia !== null && (
          <span className="pastiglia">
            Dalla {scambio.giornata_efficacia}ª giornata
          </span>
        )}
      </div>

      <h3>
        {scambio.squadra_a} ⇄ {scambio.squadra_b}
      </h3>

      <div className="movimenti">
        {scambio.movimenti.map((m) => (
          <div key={m.giocatore_id} className="movimento">
            <span className="forte">{m.nome_giocatore}</span>
            <span className="tenue">
              {m.da_squadra} → {m.a_squadra}
            </span>
            <span className="pastiglia">
              {m.anni} {m.anni === 1 ? "anno" : "anni"}
            </span>
          </div>
        ))}
      </div>

      {scambio.note && <p className="prosa">«{scambio.note}»</p>}

      {scambio.aperto && <Violazioni elenco={scambio.violazioni} />}

      {errore && <div className="errore">{errore}</div>}

      {(scambio.posso_accettare ||
        scambio.posso_rifiutare ||
        scambio.posso_annullare ||
        scambio.posso_ratificare) && (
        <div className="azioni">
          {scambio.posso_accettare && (
            <button
              className="principale compatto"
              disabled={inCorso}
              onClick={() => decidi("accetta", "Scambio accettato.")}
            >
              Accetta
            </button>
          )}
          {scambio.posso_rifiutare && (
            <button
              className="secondario"
              disabled={inCorso}
              onClick={() => decidi("rifiuta", "Scambio rifiutato.")}
            >
              Rifiuta
            </button>
          )}
          {scambio.posso_annullare && (
            <button
              className="secondario"
              disabled={inCorso}
              onClick={() => decidi("annulla", "Proposta ritirata.")}
            >
              Ritira
            </button>
          )}
          {scambio.posso_ratificare && (
            <>
              <input
                className="giornata"
                type="number"
                min={1}
                max={76}
                placeholder="giornata"
                value={giornata}
                onChange={(e) => setGiornata(e.target.value)}
                aria-label="Giornata di efficacia"
              />
              <button
                className="principale compatto"
                disabled={inCorso}
                onClick={() => decidi("ratifica", "Scambio ratificato.")}
              >
                Ratifica
              </button>
            </>
          )}
        </div>
      )}

      {scambio.stato === "ACCETTATO" && !scambio.posso_ratificare && (
        <p className="tenue">
          {scambio.violazioni.some((v) => v.bloccante)
            ? "Non è più valido: va ricomposto."
            : "In attesa che il presidente lo ratifichi."}
        </p>
      )}
    </article>
  );
}

function Componi({
  dati,
  onFatto,
}: {
  dati: PaginaScambi;
  onFatto: (messaggio: string) => void;
}) {
  const altre = dati.squadre.filter((s) => s.id !== dati.mia_squadra_id);
  const [controparte, setControparte] = useState(altre[0]?.id ?? 0);
  const [daMe, setDaMe] = useState<number[]>([]);
  const [daLoro, setDaLoro] = useState<number[]>([]);
  const [note, setNote] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [violazioni, setViolazioni] = useState<ViolazioneScambio[]>([]);
  const [inCorso, setInCorso] = useState(false);

  const mia = useCarica(
    () =>
      dati.mia_squadra_id
        ? api.squadra(dati.mia_squadra_id)
        : Promise.resolve(null),
    [dati.mia_squadra_id],
  );
  const loro = useCarica(
    () => (controparte ? api.squadra(controparte) : Promise.resolve(null)),
    [controparte],
  );

  function spunta(
    id: number,
    scelti: number[],
    imposta: (v: number[]) => void,
  ) {
    imposta(
      scelti.includes(id) ? scelti.filter((g) => g !== id) : [...scelti, id],
    );
  }

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setViolazioni([]);
    setInCorso(true);
    try {
      const esito = await api.proponiScambio({
        squadra_b_id: controparte,
        da_me: daMe,
        da_loro: daLoro,
        note,
      });
      if (esito.inviata) {
        setDaMe([]);
        setDaLoro([]);
        setNote("");
        onFatto("Proposta inviata.");
      } else {
        // Non si perde quello che si era composto: si mostra cosa non va.
        setViolazioni(esito.violazioni);
      }
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
    } finally {
      setInCorso(false);
    }
  }

  function Elenco({
    titolo,
    rosa,
    scelti,
    imposta,
  }: {
    titolo: string;
    rosa: GiocatoreInRosa[];
    scelti: number[];
    imposta: (v: number[]) => void;
  }) {
    return (
      <div>
        <h3 className="porta-gruppo">{titolo}</h3>
        <div className="scelta-giocatori">
          {rosa.map((g) => (
            <label
              key={g.id}
              className={
                scelti.includes(g.id) ? "riga-scelta presa" : "riga-scelta"
              }
            >
              <input
                type="checkbox"
                checked={scelti.includes(g.id)}
                onChange={() => spunta(g.id, scelti, imposta)}
              />
              <span className="forte">{g.nome}</span>
              <span className="ruoli">{g.ruoli.join("/")}</span>
              <span className="tenue">
                {g.anni_residui} {g.anni_residui === 1 ? "anno" : "anni"}
              </span>
              <span className="numerica">{milioni(g.ingaggio, 2)}</span>
            </label>
          ))}
        </div>
      </div>
    );
  }

  return (
    <form className="modulo" onSubmit={invia}>
      <div className="campo">
        <label htmlFor="sc-controparte">Con quale squadra</label>
        <select
          id="sc-controparte"
          value={controparte}
          onChange={(e) => {
            setControparte(Number(e.target.value));
            setDaLoro([]);
          }}
        >
          {altre.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome}
            </option>
          ))}
        </select>
      </div>

      <div className="coppia">
        {mia.dato && (
          <Elenco
            titolo={`Dai tu — ${mia.dato.nome}`}
            rosa={mia.dato.rosa}
            scelti={daMe}
            imposta={setDaMe}
          />
        )}
        {loro.dato && (
          <Elenco
            titolo={`Ricevi da ${loro.dato.nome}`}
            rosa={loro.dato.rosa}
            scelti={daLoro}
            imposta={setDaLoro}
          />
        )}
      </div>

      <div className="campo">
        <label htmlFor="sc-note">Due righe per spiegare (facoltative)</label>
        <input
          id="sc-note"
          value={note}
          maxLength={500}
          placeholder="Mi serve un difensore, a te un attaccante"
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      <p className="porta-aiuto">
        Il contratto passa com'è, con ingaggio e anni residui invariati:
        prolungamenti e riduzioni di durata non sono ammessi (art. 8).
      </p>

      <Violazioni elenco={violazioni} />
      {errore && <div className="errore">{errore}</div>}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || (daMe.length === 0 && daLoro.length === 0)}
      >
        {inCorso ? "Invio…" : "Proponi lo scambio"}
      </button>
    </form>
  );
}

export function Scambi() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.scambi(), [giro]);
  const [compongo, setCompongo] = useState(false);
  const [conferma, setConferma] = useState<string | null>(null);

  function aggiorna(messaggio: string) {
    setConferma(messaggio);
    setCompongo(false);
    setGiro((g) => g + 1);
  }

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const aperti = dato.scambi.filter((s) => s.aperto);
  const chiusi = dato.scambi.filter((s) => !s.aperto);

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🤝 Scambi</h1>
        <p>
          Si scambia il giocatore insieme alla durata residua del suo contratto
          (art. 8). Il presidente ratifica.
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      <div className="riquadri">
        <div className="riquadro">
          <span className="etichetta">Scambi conclusi</span>
          <span className="valore">{dato.conclusi}</span>
          <span className="nota">
            {dato.residui === null
              ? "senza limite"
              : `${dato.residui} ancora disponibili`}
          </span>
        </div>
        <div className="riquadro">
          <span className="etichetta">Mercato</span>
          <span className="valore piccolo">
            {dato.mercato_aperto ? "Aperto" : "Chiuso"}
          </span>
          <span className="nota">{dato.finestra}</span>
        </div>
      </div>

      {!dato.mercato_aperto && (
        <div className="avviso">
          🔒 Trade deadline superata: il mercato è bloccato fino a fine stagione
          (art. 5). Le proposte in corso restano valide.
        </div>
      )}

      {dato.mia_squadra_id === null ? (
        <p className="tenue">
          Senza una squadra non si propongono scambi. Fondane una dalla pagina
          «Identità».
        </p>
      ) : compongo ? (
        <Componi dati={dato} onFatto={aggiorna} />
      ) : (
        <button className="secondario crea" onClick={() => setCompongo(true)}>
          🔁 Componi uno scambio
        </button>
      )}

      <h2 className="sottotitolo">In corso</h2>
      {aperti.length === 0 ? (
        <div className="vuoto">Nessuno scambio aperto.</div>
      ) : (
        <div className="scambi">
          {aperti.map((s) => (
            <Scheda key={s.id} scambio={s} onFatto={aggiorna} />
          ))}
        </div>
      )}

      {chiusi.length > 0 && (
        <>
          <h2 className="sottotitolo">Conclusi</h2>
          <div className="scambi">
            {chiusi.map((s) => (
              <Scheda key={s.id} scambio={s} onFatto={aggiorna} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
