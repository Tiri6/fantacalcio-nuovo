import { useState, type FormEvent } from "react";
import { api, ErroreApi, type DatiLega, type Partecipante } from "../api";
import { useCarica } from "../carica";

/**
 * «Come si entra qui dentro?» e «con che regole giochiamo?».
 *
 * Le regole si leggono e basta: cambiarle è un modulo da quaranta caselle e
 * sta in una pagina sua. Qui ci sono i comandi corti di chi amministra —
 * delegare la bacheca, riservare un posto, rimettere in piedi chi è rimasto
 * fuori — che sono quelli che si usano davvero fra una giornata e l'altra.
 */
function Invita({ onFatto }: { onFatto: (dati: DatiLega, m: string) => void }) {
  const [email, setEmail] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      const dati = await api.invita(email);
      onFatto(dati, `Posto riservato per ${email.trim()}.`);
      setEmail("");
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a invitare.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    // `noValidate`: la regola su cosa sia un indirizzo valido ce l'ha il
    // dominio (`EmailNonValida`), ed e' l'unica copia. Lasciando fare al
    // browser, il suo fumetto bloccherebbe l'invio prima che il server possa
    // dire la sua, e l'errore comparirebbe in un posto e in una forma diversi
    // da tutti gli altri errori del sito.
    <form className="in-linea" onSubmit={invia} noValidate>
      <div className="campo">
        <label htmlFor="l-email">Email di chi vuoi invitare</label>
        <input
          id="l-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="nome@esempio.it"
        />
      </div>
      <button className="secondario" type="submit" disabled={!email.trim() || inCorso}>
        {inCorso ? "Riservo…" : "Riserva il posto"}
      </button>
      {errore && <div className="errore">{errore}</div>}
    </form>
  );
}

function Ruoli({
  dati,
  onFatto,
}: {
  dati: DatiLega;
  onFatto: (dati: DatiLega, m: string) => void;
}) {
  // Il presidente non è nell'elenco: non si cede la lega con una tendina, e
  // nemmeno si cambia il ruolo a se stessi.
  const altri = dati.partecipanti.filter(
    (p) => !p.sono_io && p.ruolo !== "PRESIDENTE",
  );
  const [chi, setChi] = useState(altri[0]?.nome_utente ?? "");
  const [ruolo, setRuolo] = useState(dati.ruoli_assegnabili[0]?.nome ?? "");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  if (altri.length === 0) {
    return <p className="tenue">Non c'è nessun altro partecipante in questa lega.</p>;
  }

  const scelto = altri.find((p) => p.nome_utente === chi);
  const gia = scelto?.ruolo === ruolo;

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      const nuovi = await api.assegnaRuolo(chi, ruolo);
      const etichetta = dati.ruoli_assegnabili.find((r) => r.nome === ruolo)?.etichetta;
      onFatto(nuovi, `${scelto?.nome_completo} ora è ${etichetta}.`);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a salvare il ruolo.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form className="in-linea" onSubmit={invia}>
      <div className="campo">
        <label htmlFor="l-chi">Partecipante</label>
        <select id="l-chi" value={chi} onChange={(e) => setChi(e.target.value)}>
          {altri.map((p) => (
            <option key={p.nome_utente} value={p.nome_utente}>
              {p.nome_completo} ({p.ruolo_etichetta})
            </option>
          ))}
        </select>
      </div>
      <div className="campo">
        <label htmlFor="l-ruolo">Ruolo</label>
        <select id="l-ruolo" value={ruolo} onChange={(e) => setRuolo(e.target.value)}>
          {dati.ruoli_assegnabili.map((r) => (
            <option key={r.nome} value={r.nome}>
              {r.etichetta}
            </option>
          ))}
        </select>
      </div>
      <button className="secondario" type="submit" disabled={gia || inCorso}>
        {gia ? "Ha già questo ruolo" : inCorso ? "Assegno…" : "Assegna"}
      </button>
      {errore && <div className="errore">{errore}</div>}
    </form>
  );
}

function Password({
  dati,
  onFatto,
}: {
  dati: DatiLega;
  onFatto: (dati: DatiLega, m: string) => void;
}) {
  const [chi, setChi] = useState(
    dati.partecipanti.find((p) => !p.sono_io)?.nome_utente ?? "",
  );
  const [generata, setGenerata] = useState<{ chi: string; password: string } | null>(
    null,
  );
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function reimposta(nome: string) {
    setErrore(null);
    setInCorso(true);
    try {
      const esito = await api.reimpostaPassword(nome);
      setGenerata({ chi: esito.nome_utente, password: esito.password });
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a reimpostarla.",
      );
    } finally {
      setInCorso(false);
    }
  }

  async function archivia(id: number) {
    try {
      const nuovi = await api.archiviaRichiesta(id);
      onFatto(nuovi, "Richiesta archiviata.");
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
    }
  }

  return (
    <>
      {/* Le richieste stanno in cima e sempre aperte: chi ha chiesto aiuto è
          rimasto fuori dal sito, e un pannello richiudibile che nessuno apre
          lo lascia fuori per sempre. */}
      {dati.richieste_password.length > 0 && (
        <div className="richieste">
          <h4>🙋 Qualcuno non riesce a entrare</h4>
          {dati.richieste_password.map((r) => (
            <div key={r.id} className="richiesta">
              <span className="forte">{r.nome_utente}</span>
              <span className="tenue">{r.chiesta_il.slice(0, 10)}</span>
              <div className="azioni">
                <button
                  className="secondario"
                  disabled={inCorso}
                  onClick={() => reimposta(r.nome_utente)}
                >
                  Reimposta la sua password
                </button>
                <button className="secondario" onClick={() => archivia(r.id)}>
                  Archivia
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {generata ? (
        <>
          <p className="tenue">
            Password temporanea di <strong>{generata.chi}</strong>:
          </p>
          <div className="codice-grande">{generata.password}</div>
          <div className="avviso">
            ⚠️ <strong>Consegnagliela adesso</strong>, a voce o in privato: non
            parte nessuna mail e ricaricando la pagina non ricompare. Al primo
            accesso sarà obbligato a sostituirla, quindi vive pochi minuti.
          </div>
          <button className="secondario" onClick={() => setGenerata(null)}>
            Ho finito
          </button>
        </>
      ) : (
        <div className="in-linea">
          <div className="campo">
            <label htmlFor="l-reset">Partecipante</label>
            <select id="l-reset" value={chi} onChange={(e) => setChi(e.target.value)}>
              {dati.partecipanti
                .filter((p) => !p.sono_io)
                .map((p) => (
                  <option key={p.nome_utente} value={p.nome_utente}>
                    {p.nome_completo} ({p.nome_utente})
                  </option>
                ))}
            </select>
          </div>
          <button
            className="secondario"
            disabled={!chi || inCorso}
            onClick={() => reimposta(chi)}
          >
            {inCorso ? "Genero…" : "Genera una password temporanea"}
          </button>
        </div>
      )}
      {errore && <div className="errore">{errore}</div>}
    </>
  );
}

function Pannello({
  titolo,
  spiegazione,
  children,
}: {
  titolo: string;
  spiegazione?: string;
  children: React.ReactNode;
}) {
  const [aperto, setAperto] = useState(false);
  return (
    <div className={aperto ? "pannello aperto" : "pannello"}>
      <button className="testa-pannello" onClick={() => setAperto((v) => !v)}>
        <span>{titolo}</span>
        <span className="freccia">{aperto ? "▾" : "▸"}</span>
      </button>
      {aperto && (
        <div className="corpo-pannello">
          {spiegazione && <p className="tenue">{spiegazione}</p>}
          {children}
        </div>
      )}
    </div>
  );
}

function Partecipanti({ righe }: { righe: Partecipante[] }) {
  return (
    <div className="tabella-contenitore">
      <table className="tabella">
        <thead>
          <tr>
            <th>Partecipante</th>
            <th>Utente</th>
            <th>Ruolo</th>
            <th>Squadra</th>
          </tr>
        </thead>
        <tbody>
          {righe.map((p) => (
            <tr key={p.nome_utente}>
              <td className="forte">
                {p.nome_completo}
                {p.sono_io && <span className="pastiglia verde">tu</span>}
              </td>
              <td className="tenue">{p.nome_utente}</td>
              <td>{p.ruolo_etichetta}</td>
              <td>{p.squadra}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SCHEDE = ["Chi c'è", "Regole", "Punteggio"] as const;

export function Lega() {
  const { dato, errore, inCorso } = useCarica(() => api.lega(), []);
  const [scheda, setScheda] = useState<(typeof SCHEDE)[number]>("Chi c'è");
  const [conferma, setConferma] = useState<string | null>(null);
  const [copiato, setCopiato] = useState(false);
  const [sostituito, setSostituito] = useState<DatiLega | null>(null);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  // Le risposte di scrittura riportano già la lega aggiornata: usarla evita
  // un secondo giro di rete e il lampo della pagina che si ricarica.
  const d = sostituito ?? dato;

  function aggiorna(nuovi: DatiLega, messaggio: string) {
    setSostituito(nuovi);
    setConferma(messaggio);
  }

  return (
    <>
      <div className="intestazione-pagina">
        <h1>⚙️ Impostazioni della lega</h1>
        <p>
          {d.nome} · stagione {d.stagione} · {d.modalita}
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      {d.problemi_schema.length > 0 && (
        <div className="avviso grande">
          <h3>⚠️ Il database non è aggiornato</h3>
          <p>
            Il sito si aspetta tabelle o colonne che nel database non ci sono.
            Finché restano assenti, alcune pagine mostrano errori.
          </p>
          <ul>
            {d.problemi_schema.map((p) => (
              <li key={p.messaggio}>{p.messaggio}</li>
            ))}
          </ul>
          {d.sql_di_riparazione ? (
            <>
              <p>
                Incolla questa query nel <strong>SQL Editor</strong> di Supabase.
                È rieseguibile e non cancella niente.
              </p>
              <pre className="sql">{d.sql_di_riparazione}</pre>
            </>
          ) : (
            <p className="tenue">Segnalalo a chi amministra la lega.</p>
          )}
        </div>
      )}

      <h2 className="sottotitolo">Come si entra</h2>
      <div className="ingresso">
        <div className="codice-invito">
          <span className="etichetta">Codice d'invito</span>
          <span className="codice">{d.codice_invito}</span>
          <button
            className="secondario"
            onClick={() => {
              navigator.clipboard?.writeText(d.codice_invito);
              setCopiato(true);
            }}
          >
            {copiato ? "Copiato" : "Copia"}
          </button>
          <p className="tenue">
            Chi ha questo codice può unirsi alla lega dalla schermata iniziale,
            scheda «Unisciti a una lega».
          </p>
        </div>

        <div className="riquadri">
          <div className="riquadro">
            <span className="etichetta">Partecipanti</span>
            <span className="valore">
              {d.partecipanti.length}
              <span className="tenue">/{d.posti}</span>
            </span>
            <span className="nota">iscritti sui posti previsti</span>
            <div className="barra">
              <div
                className="piena"
                style={{
                  width: `${Math.min(d.partecipanti.length / Math.max(d.posti, 1), 1) * 100}%`,
                }}
              />
            </div>
          </div>
          <div className="riquadro">
            <span className="etichetta">Squadre fondate</span>
            <span className="valore">{d.squadre_fondate}</span>
            <span className="nota">
              {d.partecipanti.length - d.squadre_fondate} ancora senza squadra
            </span>
          </div>
        </div>
      </div>

      {d.posso_amministrare && (
        <div className="pannelli">
          <Pannello
            titolo="✍️ Chi può scrivere in bacheca"
            spiegazione="L'editor pubblica in bacheca e basta: non ratifica scambi e non importa dati. È una delega stretta, non una seconda presidenza."
          >
            <Ruoli dati={d} onFatto={aggiorna} />
          </Pannello>

          <Pannello
            titolo="✉️ Invita qualcuno per email"
            spiegazione="Riservare un posto non manda nessuna mail: l'app non ha un server di posta. Registra chi è atteso, così quando quella persona si iscrive con quell'indirizzo trova la lega già pronta. Il codice va comunque girato a mano."
          >
            <Invita onFatto={aggiorna} />
            {d.inviti.length > 0 && (
              <div className="tabella-contenitore">
                <table className="tabella">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Stato</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.inviti.map((i) => (
                      <tr key={i.email}>
                        <td>{i.email}</td>
                        <td className="tenue">{i.stato}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Pannello>

          {d.posso_reimpostare_password && (
            <Pannello titolo="🔐 Reimposta la password di un partecipante">
              <Password dati={d} onFatto={aggiorna} />
            </Pannello>
          )}
        </div>
      )}

      <div className="schede">
        {SCHEDE.map((s) => (
          <button
            key={s}
            className={scheda === s ? "scheda attiva" : "scheda"}
            onClick={() => setScheda(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {scheda === "Chi c'è" && <Partecipanti righe={d.partecipanti} />}

      {scheda === "Regole" && (
        <>
          {d.regole.map((gruppo) => (
            <div key={gruppo.titolo}>
              <h2 className="sottotitolo">{gruppo.titolo}</h2>
              <div className="riquadri">
                {gruppo.voci.map((v) => (
                  <div key={v.etichetta} className="riquadro">
                    <span className="etichetta">{v.etichetta}</span>
                    <span className="valore piccolo">{v.valore}</span>
                    {v.nota && <span className="nota">{v.nota}</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}

          <h2 className="sottotitolo">
            Moduli ammessi ({d.moduli_ammessi.length} su {d.moduli_possibili})
          </h2>
          <div className="pastiglie">
            {d.moduli_ammessi.map((m) => (
              <span key={m} className="pastiglia">
                {m}
              </span>
            ))}
          </div>

          <div className="scheda-nota">
            <h3>🔁 Sostituzioni</h3>
            <p>{d.spiegazione_sostituzioni}</p>
          </div>
        </>
      )}

      {scheda === "Punteggio" && (
        <>
          <h2 className="sottotitolo">Fasce di gol</h2>
          <div className="tabella-contenitore stretta">
            <table className="tabella">
              <thead>
                <tr>
                  <th>Fantapunti</th>
                  <th className="numerica">Gol</th>
                </tr>
              </thead>
              <tbody>
                {d.fasce_gol.map((f) => (
                  <tr key={f.da}>
                    <td>{f.da}</td>
                    <td className="numerica forte">{f.gol}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="sottotitolo">Modificatori attivi</h2>
          <div className="pastiglie">
            {d.modificatori.length ? (
              d.modificatori.map((m) => (
                <span key={m} className="pastiglia verde">
                  {m}
                </span>
              ))
            ) : (
              <span className="tenue">Nessuno</span>
            )}
          </div>

          <h2 className="sottotitolo">Bonus e malus</h2>
          <div className="tabella-contenitore stretta">
            <table className="tabella">
              <tbody>
                {d.bonus.map((b) => (
                  <tr key={b.etichetta}>
                    <td>{b.etichetta}</td>
                    <td className="numerica forte">{b.valore}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!d.posso_cambiare_regole && (
        <p className="didascalia">
          Le regole le cambia chi ha creato la lega.
        </p>
      )}
    </>
  );
}
