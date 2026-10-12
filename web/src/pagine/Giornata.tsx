import { useState } from "react";
import {
  ErroreApi,
  api,
  type PartitaLetta,
  type SquadraDellaPartita,
} from "../api";
import { Campo } from "../campo";
import { useCarica } from "../carica";
import { leggiBase64, scarica } from "../file";

/**
 * Giornata: gli scontri diretti, i due campi uno di fronte all'altro, il conto.
 *
 * È la pagina della domenica. Appena i voti sono caricati ogni partita mostra
 * **come finirebbe**, con i punti sulle maglie: è lo stesso calcolo che poi
 * scrive il risultato, non una stima, e vederlo prima di salvarlo è il punto.
 *
 * Il conto lo fa il server. Qui non c'è una regola di punteggio: arrivano i
 * numeri già fatti, e questa pagina li dispone.
 */

function etichettaCompetizione(nome: string): string {
  const parole = nome.replace(/_/g, " ").toLowerCase();
  return parole.charAt(0).toUpperCase() + parole.slice(1);
}

function Meta({ squadra }: { squadra: SquadraDellaPartita }) {
  const t = squadra.tabellino;
  if (!t) {
    return squadra.panchina.length > 0 ? (
      <p className="didascalia">Panchina: {squadra.panchina.join(", ")}</p>
    ) : null;
  }
  return (
    <div className="conto">
      {t.modificatore_difesa !== 0 && (
        <span>Modificatore difesa: {t.modificatore_difesa.toFixed(1)}</span>
      )}
      {t.malus_adattamento !== 0 && (
        <span>
          Fuori posizione: {t.adattati}{" "}
          {t.adattati === 1 ? "giocatore" : "giocatori"} (
          {t.malus_adattamento.toFixed(1)})
        </span>
      )}
      {t.malus_emergenza !== 0 && (
        <span>
          Portiere d'emergenza: {t.malus_emergenza.toFixed(1)} (Lodo Messina)
        </span>
      )}
      {t.sostituzioni.map((s) => (
        <span key={s}>↔ {s}</span>
      ))}
      {t.senza_voto_rimasti.length > 0 && (
        <span>
          Senza voto e senza cambio: {t.senza_voto_rimasti.join(", ")}
        </span>
      )}
    </div>
  );
}

function MetaSquadra({ squadra }: { squadra: SquadraDellaPartita }) {
  return (
    <div className="lato">
      <h4>
        {squadra.squadra}
        {squadra.modulo && <span className="suo-modulo">{squadra.modulo}</span>}
      </h4>
      {squadra.ha_schierato ? (
        <>
          <Campo reparti={squadra.reparti} />
          <Meta squadra={squadra} />
        </>
      ) : (
        <div className="riquadro avviso">Non ha schierato la formazione.</div>
      )}
    </div>
  );
}

function Partita({ partita }: { partita: PartitaLetta }) {
  const giocata = partita.gol_casa !== null;
  return (
    <section className="scontro">
      <header>
        <h3>
          <span>{partita.casa.squadra}</span>
          {giocata ? (
            <strong>
              {partita.gol_casa} - {partita.gol_trasferta}
            </strong>
          ) : (
            <strong className="da-giocare">—</strong>
          )}
          <span>{partita.trasferta.squadra}</span>
        </h3>
        <p className="didascalia">
          {partita.stato === "da giocare"
            ? "Da giocare"
            : `${partita.punti_casa?.toFixed(1)} — ${partita.punti_trasferta?.toFixed(1)} fantapunti · ${
                partita.stato === "salvata"
                  ? "risultato salvato"
                  : "provvisorio, non ancora salvato"
              }`}
        </p>
      </header>
      <div className="lati">
        <MetaSquadra squadra={partita.casa} />
        <MetaSquadra squadra={partita.trasferta} />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Voti e calcolo
// ---------------------------------------------------------------------------

function Voti({
  giornata,
  modello,
  onFatto,
}: {
  giornata: number;
  modello: string;
  // I non abbinati salgono col messaggio: questo modulo viene rimontato
  // appena la giornata si ricarica, e tenendoli qui sparivano prima di
  // essere letti — proprio l'elenco che serve a capire quali voti mancano.
  onFatto: (messaggio: string, nonAbbinati: string[]) => void;
}) {
  const [testo, setTesto] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function invia() {
    setErrore(null);
    setInCorso(true);
    try {
      const corpo = file
        ? { giornata, contenuto_base64: await leggiBase64(file) }
        : { giornata, testo };
      const esito = await api.caricaVoti(corpo);
      setTesto("");
      setFile(null);
      onFatto(esito.messaggio, esito.non_abbinati);
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

  return (
    <>
      <p className="prosa">
        I voti si prendono da Fantacalcio o dall'app della lega e si incollano
        qui: il sito non riesce a scaricarli da solo. Servono almeno{" "}
        <code>giocatore</code> (o l'<code>id</code> del listone) e{" "}
        <code>voto</code>. Le altre colonne — gol, assist, ammonizioni,
        espulsioni, rigori, autogol, gol subiti, imbattuto — si aggiungono se ci
        sono. Un voto lasciato in bianco vuol dire <strong>senza voto</strong>,
        che non è uno zero.
      </p>

      <button
        className="secondario"
        onClick={() => scarica("voti-modello.csv", modello)}
      >
        ⬇️ Scarica il modello dei voti
      </button>

      <label className="scegli-file">
        <input
          type="file"
          accept=".csv,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <span>{file ? `📄 ${file.name}` : "Scegli un file…"}</span>
      </label>

      <div className="campo">
        <label htmlFor="voti-incollati">…oppure incolla qui la tabella</label>
        <textarea
          id="voti-incollati"
          rows={7}
          value={testo}
          onChange={(e) => setTesto(e.target.value)}
          placeholder={"giocatore;voto;gol;assist\nDybala;7;1;1"}
          disabled={file !== null}
        />
      </div>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        onClick={invia}
        disabled={inCorso || (!file && !testo.trim())}
      >
        {inCorso ? "Leggo…" : "📥 Leggi e salva i voti"}
      </button>
    </>
  );
}

function Calcolo({
  giornata,
  competizione,
  voti,
  senzaFormazione,
  onFatto,
}: {
  giornata: number;
  competizione: string;
  voti: number;
  senzaFormazione: string[];
  onFatto: (messaggio: string) => void;
}) {
  const [errore, setErrore] = useState<string | null>(null);
  const [avvisi, setAvvisi] = useState<string[]>([]);
  const [inCorso, setInCorso] = useState(false);

  async function calcola() {
    setErrore(null);
    setAvvisi([]);
    setInCorso(true);
    try {
      const esito = await api.calcolaGiornata(giornata, competizione);
      setAvvisi(esito.avvisi);
      onFatto(esito.messaggio);
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

  return (
    <>
      {voti === 0 && (
        <div className="avviso">
          📭 Per questa giornata non ci sono voti: caricali nella scheda
          accanto, poi torna qui.
        </div>
      )}
      {senzaFormazione.length > 0 && (
        <div className="avviso">
          ⚠️ Queste squadre non hanno schierato: {senzaFormazione.join(", ")}.
          Le loro partite restano da calcolare finché non c'è una formazione.
        </div>
      )}
      <p className="prosa">
        Il calcolo riscrive gol e fantapunti delle partite di questa giornata:
        si può rifare quando arrivano voti corretti.
      </p>
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
      {avvisi.map((a) => (
        <div key={a} className="avviso">
          ⚠️ {a}
        </div>
      ))}
      <button
        className="principale"
        onClick={calcola}
        disabled={inCorso || voti === 0}
      >
        {inCorso ? "Calcolo…" : `⚡ Calcola la giornata ${giornata}`}
      </button>
    </>
  );
}

// ---------------------------------------------------------------------------

export function Giornata() {
  const [giornata, setGiornata] = useState(0);
  const [competizione, setCompetizione] = useState("CAMPIONATO");
  const [giro, setGiro] = useState(0);
  const [conferma, setConferma] = useState<string | null>(null);
  const [nonAbbinati, setNonAbbinati] = useState<string[]>([]);
  const [scheda, setScheda] = useState<"voti" | "calcola">("voti");
  const { dato, errore, inCorso } = useCarica(
    () => api.giornata(giornata, competizione),
    [giornata, competizione, giro],
  );

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const mostrata = dato.giornata;

  function aggiorna(messaggio: string, nonAbbinati: string[] = []) {
    setConferma(messaggio);
    setNonAbbinati(nonAbbinati);
    // La giornata si fissa qui, e non è un dettaglio: finché `giornata` vale
    // zero il server risponde «la prima non ancora disputata», e appena si
    // calcola la 12 quella diventa la 13. Senza questa riga, dopo il calcolo
    // la pagina scivola sulla giornata dopo mentre il messaggio parla di
    // quella appena fatta, e sembra che non sia successo niente.
    setGiornata(mostrata);
    setGiro((g) => g + 1);
  }

  if (dato.calendario_vuoto) {
    return (
      <div className="vuoto">
        <h1>⚔️ Giornata</h1>
        <p>
          Il calendario è vuoto: prima si importano le partite dalla pagina
          «Importa dati», poi qui compaiono gli scontri diretti.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="intestazione-pagina">
        <h1>⚔️ Giornata</h1>
        <p>
          Gli scontri diretti giornata per giornata, con le formazioni in campo.
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      {nonAbbinati.length > 0 && (
        <div className="avviso">
          ⚠️ Voti non abbinati ({nonAbbinati.length}):{" "}
          {nonAbbinati.slice(0, 10).join(", ")}
          {nonAbbinati.length > 10 && "…"}. Controlla i nomi, oppure metti nel
          file la colonna «id» del listone.
        </div>
      )}

      <div className="filtri">
        {dato.competizioni.length > 1 && (
          <div className="campo">
            <label htmlFor="competizione">Competizione</label>
            <select
              id="competizione"
              value={dato.competizione}
              onChange={(e) => setCompetizione(e.target.value)}
            >
              {dato.competizioni.map((c) => (
                <option key={c} value={c}>
                  {etichettaCompetizione(c)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="campo">
          <label htmlFor="giornata">Giornata</label>
          <select
            id="giornata"
            value={dato.giornata}
            onChange={(e) => setGiornata(Number(e.target.value))}
          >
            {dato.giornate.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div className="riquadro stato-blocco aperta">
          <strong>📊 Giornata {dato.giornata}</strong>
          <span>
            {dato.partite.length}{" "}
            {dato.partite.length === 1 ? "partita" : "partite"} ·{" "}
            {dato.formazioni_salvate === 1
              ? "una formazione salvata"
              : `${dato.formazioni_salvate} formazioni salvate`}{" "}
            ·{" "}
            {dato.voti_caricati
              ? `${dato.voti_caricati} voti caricati`
              : "voti non ancora caricati"}
          </span>
        </div>
      </div>

      {dato.partite.map((p) => (
        <Partita key={p.id} partita={p} />
      ))}

      {dato.posso_calcolare ? (
        <div className="riquadro">
          <h2>Voti e calcolo della giornata</h2>
          <p className="didascalia">
            Prima i voti, poi il calcolo: senza voti non si calcola niente.
          </p>
          <div className="schede">
            <button
              className={scheda === "voti" ? "scheda attiva" : "scheda"}
              onClick={() => setScheda("voti")}
            >
              📥 Carica i voti
            </button>
            <button
              className={scheda === "calcola" ? "scheda attiva" : "scheda"}
              onClick={() => setScheda("calcola")}
            >
              ⚡ Calcola
            </button>
          </div>
          {scheda === "voti" ? (
            <Voti
              key={`voti-${dato.giornata}-${giro}`}
              giornata={dato.giornata}
              modello={dato.modello_voti}
              onFatto={aggiorna}
            />
          ) : (
            <Calcolo
              giornata={dato.giornata}
              competizione={dato.competizione}
              voti={dato.voti_caricati}
              senzaFormazione={dato.senza_formazione}
              onFatto={aggiorna}
            />
          )}
        </div>
      ) : (
        <p className="didascalia">
          I voti li carica il presidente di lega, che poi calcola la giornata.
        </p>
      )}
    </>
  );
}
