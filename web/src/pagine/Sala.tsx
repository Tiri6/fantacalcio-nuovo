import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ErroreApi,
  api,
  type ChiamataLetta,
  type GiocatoreLibero,
  type PaginaSala,
  type TurnoLetto,
  type ViolazioneDiSala,
} from "../api";
import { useCarica, milioni } from "../carica";

/**
 * La Draft Room: dieci persone che guardano la stessa pagina e chiamano a
 * turno.
 *
 * **Si aggiorna interrogando, non con un canale aperto.** Ogni due secondi e
 * mezzo si chiede «e' cambiato qualcosa?» mandando l'impronta che si ha: se
 * non e' cambiata, il server risponde due campi e basta. Per dieci persone
 * costa un ordine di grandezza meno in codice da mantenere di dieci
 * connessioni vive, e funziona anche dietro un proxy che le chiude quando gli
 * pare.
 *
 * Due dettagli che sembrano cautele e non lo sono. Il polling si **ferma a
 * scheda nascosta**: una sala aperta in un'altra finestra per tre ore sono
 * quattromila richieste che nessuno guarda. E ogni tanto si chiede la pagina
 * **intera** anche se l'impronta non cambia, perche' una cosa cambia da sola
 * senza che nessuno agisca: la finestra per correggere gli anni, che si
 * chiude col calcio d'inizio.
 */

const PAUSA = 2500;
/** Ogni quanti giri si rilegge tutto comunque. 12 × 2,5 s = mezzo minuto. */
const GIRI_PRIMA_DEL_GIRO_COMPLETO = 12;

function quantoManca(scade_il: string, adesso: number): string {
  const secondi = Math.round((new Date(scade_il).getTime() - adesso) / 1000);
  if (secondi <= 0) return "scaduto";
  const minuti = Math.floor(secondi / 60);
  return `${minuti}:${String(secondi % 60).padStart(2, "0")}`;
}

/** Il tempo che resta al turno, aggiornato al secondo. */
function Cronometro({ scade_il }: { scade_il: string }) {
  const [adesso, setAdesso] = useState(() => Date.now());

  useEffect(() => {
    const battito = window.setInterval(() => setAdesso(Date.now()), 1000);
    return () => window.clearInterval(battito);
  }, []);

  const resta = quantoManca(scade_il, adesso);
  return (
    <span className={resta === "scaduto" ? "sala-tempo scaduto" : "sala-tempo"}>
      ⏱ {resta}
    </span>
  );
}

function Violazioni({ voci }: { voci: ViolazioneDiSala[] }) {
  if (voci.length === 0) return null;
  return (
    <div className="sala-violazioni" role="alert">
      {voci.map((v) => (
        <p key={v.codice + v.messaggio}>
          <span className="pastiglia rossa">{v.articolo}</span> {v.messaggio}
        </p>
      ))}
    </div>
  );
}

/* --- chi amministra ------------------------------------------------------- */

function Apertura({ onAperta }: { onAperta: (p: PaginaSala) => void }) {
  const [tipo, setTipo] = useState<"SETTEMBRE" | "RIPARAZIONE">("SETTEMBRE");
  const [round, setRound] = useState(3);
  const [conTimer, setConTimer] = useState(false);
  const [secondi, setSecondi] = useState(90);
  const [ordine, setOrdine] = useState<number[]>([]);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);
  const squadre = useCarica(() => api.squadre(), []);

  const elenco = squadre.dato ?? [];
  const nome = (id: number) =>
    elenco.find((s) => s.id === id)?.nome ?? String(id);

  /** L'estrazione della Lottery, quando si fa qui e non su un foglio. */
  function sorteggia() {
    const mescolate = elenco.map((s) => s.id);
    for (let i = mescolate.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [mescolate[i], mescolate[j]] = [mescolate[j], mescolate[i]];
    }
    setOrdine(mescolate);
  }

  async function apri() {
    setErrore(null);
    setInCorso(true);
    try {
      onAperta(
        await api.apriSala({
          tipo,
          round_totali: round,
          secondi_per_chiamata: conTimer ? secondi : null,
          ordine_lottery: tipo === "SETTEMBRE" ? ordine : [],
        }),
      );
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
    <div className="riquadro">
      <h2>Apri una sala</h2>
      <div className="campo">
        <label htmlFor="sala-tipo">Che sala</label>
        <select
          id="sala-tipo"
          value={tipo}
          onChange={(e) =>
            setTipo(e.target.value as "SETTEMBRE" | "RIPARAZIONE")
          }
        >
          <option value="SETTEMBRE">Draft di Settembre</option>
          <option value="RIPARAZIONE">Mercato di riparazione</option>
        </select>
      </div>
      <p className="didascalia">
        Cambia una cosa sola, l'ordine di chiamata: Settembre segue la Lottery
        (e la classifica nei round multipli di 3), la riparazione va al
        contrario della classifica in tutti i round.
      </p>

      <div className="campo">
        <label htmlFor="sala-round">Quanti round</label>
        <input
          id="sala-round"
          type="number"
          min={1}
          max={50}
          value={round}
          onChange={(e) => setRound(Number(e.target.value))}
        />
      </div>

      {tipo === "SETTEMBRE" && (
        <div className="sala-lottery">
          <h3>L'ordine della Lottery</h3>
          <p className="didascalia">
            A Settembre l'ordine di chiamata è quello della Lottery (art. 3),
            non la classifica. Clicca le squadre nell'ordine estratto, o fai
            estrarre qui. Lasciandolo vuoto si segue la classifica, che è
            l'ipotesi di comodo: se la Lottery l'avete già fatta, trascrivila.
          </p>
          <div className="sala-comandi">
            <button onClick={sorteggia} disabled={elenco.length === 0}>
              Estrai a sorte
            </button>
            {ordine.length > 0 && (
              <button onClick={() => setOrdine([])}>Azzera</button>
            )}
          </div>
          <div className="sala-liberi">
            {elenco
              .filter((s) => !ordine.includes(s.id))
              .map((s) => (
                <button
                  key={s.id}
                  className="sala-libero"
                  onClick={() => setOrdine((o) => [...o, s.id])}
                >
                  <span className="forte">{s.nome}</span>
                  <span className="tenue">{s.presidente}</span>
                  <span className="tenue">aggiungi</span>
                </button>
              ))}
          </div>
          {ordine.length > 0 && (
            <ol className="sala-coda">
              {ordine.map((id) => (
                <li key={id}>{nome(id)}</li>
              ))}
            </ol>
          )}
          {ordine.length > 0 && ordine.length < elenco.length && (
            <p className="didascalia">
              Mancano {elenco.length - ordine.length} squadre: quelle che
              restano si accodano nell'ordine di classifica.
            </p>
          )}
        </div>
      )}

      <label className="interruttore">
        <input
          type="checkbox"
          checked={conTimer}
          onChange={(e) => setConTimer(e.target.checked)}
        />
        Dai un tempo a ogni chiamata
      </label>
      {conTimer && (
        <div className="campo">
          <label htmlFor="sala-secondi">Secondi per chiamata</label>
          <input
            id="sala-secondi"
            type="number"
            min={10}
            max={900}
            value={secondi}
            onChange={(e) => setSecondi(Number(e.target.value))}
          />
        </div>
      )}
      <p className="didascalia">
        Senza tempo il turno non scade mai: il cronometro si vede, ma non passa
        la mano da solo — il draft si fa insieme, e un turno che salta mentre
        uno sta ancora decidendo è peggio di un draft lento.
      </p>

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
      <button className="principale" onClick={apri} disabled={inCorso}>
        {inCorso ? "Apro…" : "Apri la sala"}
      </button>
    </div>
  );
}

function Comandi({
  pagina,
  onFatto,
}: {
  pagina: PaginaSala;
  onFatto: (p: PaginaSala) => void;
}) {
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function esegui(azione: () => Promise<PaginaSala>) {
    setErrore(null);
    setInCorso(true);
    try {
      onFatto(await azione());
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
    <div className="sala-comandi">
      {pagina.stato === "aperta" && (
        <button
          className="principale"
          disabled={inCorso}
          onClick={() => esegui(api.cominciaSala)}
        >
          Comincia il draft
        </button>
      )}
      {pagina.stato !== "chiusa" && (
        <button disabled={inCorso} onClick={() => esegui(api.chiudiSala)}>
          Chiudi la sala
        </button>
      )}
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}
    </div>
  );
}

/* --- chiamare ------------------------------------------------------------- */

function Chiamata({
  pagina,
  onFatta,
}: {
  pagina: PaginaSala;
  onFatta: (messaggio: string) => void;
}) {
  const [cerca, setCerca] = useState("");
  const [scelto, setScelto] = useState<GiocatoreLibero | null>(null);
  const [anni, setAnni] = useState(1);
  const [violazioni, setViolazioni] = useState<ViolazioneDiSala[]>([]);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  const trovati = useMemo(() => {
    const parola = cerca.trim().toLowerCase();
    const filtrati = parola
      ? pagina.disponibili.filter(
          (g) =>
            g.nome.toLowerCase().includes(parola) ||
            g.club.toLowerCase().includes(parola) ||
            g.ruoli.some((r) => r.toLowerCase() === parola),
        )
      : pagina.disponibili;
    // Venti alla volta: in sala si cerca un nome, non si sfoglia il listone.
    return filtrati.slice(0, 20);
  }, [cerca, pagina.disponibili]);

  async function chiama() {
    if (!scelto) return;
    setErrore(null);
    setViolazioni([]);
    setInCorso(true);
    try {
      const esito = await api.chiamaGiocatore(scelto.id, anni);
      if (esito.fatta) {
        setScelto(null);
        setCerca("");
        onFatta(esito.messaggio);
      } else {
        setViolazioni(esito.violazioni);
      }
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

  const anniPossibili: number[] = [];
  for (let n = pagina.anni_minimo; n <= pagina.anni_massimo; n += 1) {
    anniPossibili.push(n);
  }

  return (
    <div className="riquadro sala-chiamata">
      <h2>La tua chiamata</h2>
      <div className="campo">
        <label htmlFor="sala-cerca">Cerca un giocatore libero</label>
        <input
          id="sala-cerca"
          type="search"
          value={cerca}
          placeholder="Nome, club o ruolo"
          onChange={(e) => setCerca(e.target.value)}
        />
      </div>

      <div className="sala-liberi">
        {trovati.length === 0 ? (
          <p className="didascalia">Nessun giocatore libero con questo nome.</p>
        ) : (
          trovati.map((g) => (
            <button
              key={g.id}
              className={
                scelto?.id === g.id ? "sala-libero scelto" : "sala-libero"
              }
              onClick={() => setScelto(g)}
            >
              <span className="forte">{g.nome}</span>
              <span className="tenue">
                {g.club} · {g.ruoli.join("/")}
              </span>
              <span className="numerica">{milioni(g.ingaggio)}</span>
            </button>
          ))
        )}
      </div>

      {scelto && (
        <>
          <div className="campo">
            <label htmlFor="sala-anni">Anni di contratto</label>
            <select
              id="sala-anni"
              value={anni}
              onChange={(e) => setAnni(Number(e.target.value))}
            >
              {anniPossibili.map((n) => (
                <option key={n} value={n}>
                  {n === 1 ? "1 anno" : `${n} anni`}
                </option>
              ))}
            </select>
          </div>
          <Violazioni voci={violazioni} />
          {errore && (
            <div className="errore" role="alert">
              {errore}
            </div>
          )}
          <button className="principale" onClick={chiama} disabled={inCorso}>
            {inCorso ? "Chiamo…" : `Chiama ${scelto.nome}`}
          </button>
        </>
      )}
    </div>
  );
}

/* --- correggere gli anni -------------------------------------------------- */

function Correzione({
  pagina,
  onFatta,
}: {
  pagina: PaginaSala;
  onFatta: (messaggio: string) => void;
}) {
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState<number | null>(null);

  async function correggi(acquisto: ChiamataLetta, anni: number) {
    setErrore(null);
    setInCorso(acquisto.giocatore_id);
    try {
      const esito = await api.correggiAnni(acquisto.giocatore_id, anni);
      onFatta(`${acquisto.giocatore}: ${esito.messaggio.toLowerCase()}`);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(null);
    }
  }

  const anniPossibili: number[] = [];
  for (let n = pagina.anni_minimo; n <= pagina.anni_massimo; n += 1) {
    anniPossibili.push(n);
  }

  return (
    <div className="riquadro">
      <h2>I tuoi acquisti</h2>
      {pagina.anni_correggibili ? (
        <p className="didascalia">
          Gli anni si correggono solo su chi hai preso in questa sala, e solo
          fino al calcio d'inizio della giornata successiva
          {pagina.anni_chiudono_il && (
            <>
              {" "}
              —{" "}
              <strong>{pagina.anni_chiudono_il.replace("T", " alle ")}</strong>
            </>
          )}
          . Dopo, il contratto è quello (art. 8).
        </p>
      ) : (
        <p className="didascalia">
          {pagina.anni_motivo ||
            "Gli anni si correggono dalla chiusura della sala fino alla giornata successiva."}
        </p>
      )}

      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Giocatore</th>
              <th>Ruoli</th>
              <th className="numerica">Anni</th>
            </tr>
          </thead>
          <tbody>
            {pagina.miei_acquisti.map((a) => (
              <tr key={a.giocatore_id}>
                <td className="forte">{a.giocatore}</td>
                <td className="tenue">{a.ruoli.join("/")}</td>
                <td className="numerica">
                  {pagina.anni_correggibili ? (
                    <select
                      aria-label={`Anni di ${a.giocatore}`}
                      value={a.anni}
                      disabled={inCorso === a.giocatore_id}
                      onChange={(e) => correggi(a, Number(e.target.value))}
                    >
                      {anniPossibili.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  ) : (
                    a.anni
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* --- la pagina ------------------------------------------------------------ */

function Turno({ turno }: { turno: TurnoLetto }) {
  return (
    <div className={turno.e_mio ? "sala-turno mio" : "sala-turno"}>
      <div>
        <span className="pastiglia">{turno.etichetta}</span>
        <h2>{turno.e_mio ? `Tocca a te, ${turno.squadra}` : turno.squadra}</h2>
      </div>
      {turno.scade_il && <Cronometro scade_il={turno.scade_il} />}
    </div>
  );
}

export function Sala() {
  const [pagina, setPagina] = useState<PaginaSala | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [appena, setAppena] = useState<string | null>(null);
  // L'impronta che abbiamo: si manda al server per farsi dire se è cambiato
  // qualcosa. In un ref e non in uno stato perché la deve leggere il giro di
  // polling, che non si ridisegna quando cambia.
  const impronta = useRef<string | null>(null);
  const giri = useRef(0);

  const aggiorna = useCallback(async (daCapo = false) => {
    try {
      const letta = await api.sala(
        daCapo || impronta.current === null ? undefined : impronta.current,
      );
      setErrore(null);
      // `aggiornato: false` vuol dire «la tua è ancora buona»: la risposta è
      // volutamente vuota, e sovrascriverci la pagina la cancellerebbe.
      if (!letta.aggiornato) return;
      impronta.current = letta.versione;
      setPagina(letta);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a contattare il server.",
      );
    }
  }, []);

  useEffect(() => {
    aggiorna(true);
    const battito = window.setInterval(() => {
      // A scheda nascosta non si interroga: una sala dimenticata aperta in
      // un'altra finestra sono migliaia di richieste che nessuno guarda.
      if (document.hidden) return;
      giri.current += 1;
      aggiorna(giri.current % GIRI_PRIMA_DEL_GIRO_COMPLETO === 0);
    }, PAUSA);
    // Tornando sulla scheda si rilegge subito: due secondi e mezzo di pagina
    // vecchia, in sala, sono il turno di qualcun altro.
    function alRitorno() {
      if (!document.hidden) aggiorna(true);
    }
    document.addEventListener("visibilitychange", alRitorno);
    return () => {
      window.clearInterval(battito);
      document.removeEventListener("visibilitychange", alRitorno);
    };
  }, [aggiorna]);

  if (!pagina) {
    if (errore)
      return (
        <div className="vuoto">
          <h1>🎙️ Draft Room</h1>
          <p>{errore}</p>
        </div>
      );
    return <div className="fantasma alto" />;
  }

  const restano = pagina.chiamate_totali - pagina.chiamate.length;
  const liberiInsufficienti =
    pagina.stato !== "chiusa" && pagina.disponibili.length < restano;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🎙️ Draft Room</h1>
        <p>
          {pagina.c_e_una_sala ? (
            <>
              {pagina.tipo_etichetta} {pagina.stagione} · sala {pagina.stato} ·{" "}
              {pagina.chiamate.length} di {pagina.chiamate_totali} chiamate (
              {pagina.round_totali} round)
            </>
          ) : (
            "Nessuna sala aperta."
          )}
        </p>
      </div>

      {appena && <div className="conferma">{appena}</div>}
      {errore && (
        <div className="riquadro avviso">
          ⚠️ {errore} La pagina mostra l'ultimo stato che ha ricevuto.
        </div>
      )}

      {!pagina.c_e_una_sala ? (
        pagina.posso_amministrare ? (
          <Apertura
            onAperta={(p) => {
              impronta.current = p.versione;
              setPagina(p);
            }}
          />
        ) : (
          <div className="riquadro avviso">
            🎙️ La sala la apre chi amministra la lega. Questa pagina si aggiorna
            da sola: quando il draft comincia, lo vedi qui.
          </div>
        )
      ) : (
        <>
          {pagina.turno ? (
            <Turno turno={pagina.turno} />
          ) : (
            <div className="riquadro">
              {pagina.stato === "aperta"
                ? "🎙️ Sala aperta: si chiama appena chi amministra fa cominciare."
                : pagina.stato === "chiusa"
                  ? "🎙️ Sala chiusa: non si chiama più."
                  : "🎙️ Chiamate finite."}
            </div>
          )}

          {pagina.posso_amministrare && (
            <Comandi
              pagina={pagina}
              onFatto={(p) => {
                impronta.current = p.versione;
                setPagina(p);
              }}
            />
          )}

          {liberiInsufficienti && (
            <div className="riquadro avviso">
              ⚠️ Restano {restano} chiamate e {pagina.disponibili.length}{" "}
              giocatori liberi: così la sala non arriva in fondo. Importa il
              listone o svincola prima di continuare.
            </div>
          )}

          {pagina.turno?.e_mio && (
            <Chiamata
              pagina={pagina}
              onFatta={(messaggio) => {
                setAppena(messaggio);
                aggiorna(true);
              }}
            />
          )}

          {pagina.prossimi.length > 0 && (
            <div className="riquadro">
              <h2>Poi tocca a</h2>
              {/* Niente `ol`: i numeri che contano sono quelli delle chiamate
                  (la 7ª, non la 2ª di questo elenco), e un contatore suo
                  accanto al mio li farebbe leggere come «1. 7.» */}
              <ul className="sala-coda senza-numeri">
                {pagina.prossimi.map((t) => (
                  <li key={t.numero} className={t.e_mio ? "mio" : undefined}>
                    <span className="tenue">chiamata {t.numero}</span> ·{" "}
                    {t.squadra}
                    {t.e_mio && <span className="pastiglia verde">tu</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {pagina.miei_acquisti.length > 0 && (
            <Correzione
              pagina={pagina}
              onFatta={(messaggio) => {
                setAppena(messaggio);
                aggiorna(true);
              }}
            />
          )}

          <h2>Chiamate</h2>
          {pagina.chiamate.length === 0 ? (
            <div className="riquadro">Nessuna chiamata, per ora.</div>
          ) : (
            <div className="tabella-contenitore">
              <table className="tabella">
                <thead>
                  <tr>
                    <th className="numerica">#</th>
                    <th>Squadra</th>
                    <th>Giocatore</th>
                    <th>Ruoli</th>
                    <th className="numerica">Anni</th>
                  </tr>
                </thead>
                <tbody>
                  {pagina.chiamate.map((c) => (
                    <tr
                      key={c.numero}
                      className={
                        c.squadra_id === pagina.mia_squadra_id
                          ? "mia"
                          : undefined
                      }
                    >
                      <td className="numerica tenue">{c.numero}</td>
                      <td>{c.squadra}</td>
                      <td className="forte">{c.giocatore}</td>
                      <td className="tenue">{c.ruoli.join("/")}</td>
                      <td className="numerica">{c.anni}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="didascalia">
            La pagina si aggiorna da sola ogni due secondi e mezzo: le chiamate
            degli altri compaiono qui senza ricaricare.
          </p>
        </>
      )}
    </>
  );
}
