import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  ErroreApi,
  type Emergenza as DatiEmergenza,
  type GiocatoreInRosa,
  type Violazione,
} from "../api";
import { milioni, useCarica } from "../carica";

function Numero({
  etichetta,
  valore,
  nota,
  sfora,
  quota,
}: {
  etichetta: string;
  valore: string;
  nota?: string;
  sfora?: boolean;
  quota?: number;
}) {
  return (
    <div className="riquadro">
      <span className="etichetta">{etichetta}</span>
      <span className={`valore${sfora ? " sfora" : ""}`}>{valore}</span>
      {nota && <span className="nota">{nota}</span>}
      {quota !== undefined && (
        <div className="barra">
          <div
            className={sfora ? "piena sfora" : "piena"}
            style={{ width: `${Math.min(100, Math.max(0, quota * 100))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function RigaViolazione({ v }: { v: Violazione }) {
  return (
    <li className={v.bloccante ? "blocco" : "avviso"}>
      <strong>{v.articolo}</strong> {v.messaggio}
      {/* Di quanto sfora, non solo che sfora: e' la regola del progetto. */}
      {v.valore !== null && v.limite !== null && (
        <span className="scarto">
          {v.valore} su {v.limite}
        </span>
      )}
    </li>
  );
}

function Rosa({
  rosa,
  riferimento,
}: {
  rosa: GiocatoreInRosa[];
  riferimento: string;
}) {
  if (rosa.length === 0) {
    return (
      <p className="vuoto">
        Rosa vuota. I giocatori si assegnano dalla pagina «Draft».
      </p>
    );
  }
  const giorno = new Date(riferimento).toLocaleDateString("it-IT");
  return (
    <>
      <div className="tabella-contenitore">
        <table className="tabella">
          <thead>
            <tr>
              <th>Giocatore</th>
              <th>Club</th>
              <th>Ruoli</th>
              <th>Nazionalità</th>
              <th className="numerica">Età</th>
              <th className="centrata">U21</th>
              <th className="numerica">Anni</th>
              <th className="numerica">Ingaggio</th>
            </tr>
          </thead>
          <tbody>
            {rosa.map((g) => (
              <tr key={g.id}>
                <td className="forte">
                  {g.nome}
                  {g.prolungato && (
                    <span className="segno" title="Lodo Corti: già prolungato">
                      ↗
                    </span>
                  )}
                </td>
                <td className="tenue">{g.club}</td>
                <td>
                  <span className="ruoli">{g.ruoli.join("/")}</span>
                </td>
                <td className="tenue">
                  {g.italiano && <span title="Italiano">🇮🇹 </span>}
                  {g.nazionalita}
                </td>
                <td className="numerica">{g.eta ?? "—"}</td>
                <td className="centrata">{g.u21 ? "●" : ""}</td>
                <td className={`numerica${g.in_scadenza ? " scadenza" : ""}`}>
                  {g.anni_residui}
                </td>
                <td className="numerica">{milioni(g.ingaggio, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="didascalia">
        Under 21 valutati al {giorno} · ingaggi dalla fonte Capology · ↗ già
        prolungato (Lodo Corti)
      </p>
    </>
  );
}

/**
 * Portiere d'emergenza: il Lodo Messina dell'articolo 8.
 *
 * Il sito non sa da solo chi è indisponibile — le indisponibilità stanno su
 * Leghe Fantacalcio, e da un server quel sito non si legge (vedi
 * PUNTI_APERTI.md). Quindi li dichiara chi attiva, spuntando i suoi portieri:
 * è una dichiarazione, e resta scritta col nome di chi l'ha fatta.
 *
 * Non si tiene nessuna regola qui: `ammessa`, `va_revocata` e `motivo`
 * arrivano dal dominio. Il server ricontrolla tutto comunque — un bottone
 * nascosto non è un controllo.
 */
function Emergenza({
  squadra,
  dati,
  posso,
  onCambiata,
}: {
  squadra: number;
  dati: DatiEmergenza;
  posso: boolean;
  onCambiata: (messaggio: string) => void;
}) {
  const [fuori, setFuori] = useState<number[]>(
    dati.portieri.filter((p) => !p.disponibile).map((p) => p.id),
  );
  const [scelto, setScelto] = useState<number | null>(
    dati.candidati[0]?.id ?? null,
  );
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  // Niente portieri in rosa: non è un'emergenza, è una rosa da completare.
  // Mostrare qui un pannello sull'emergenza porterebbe fuori strada.
  if (dati.portieri.length === 0) return null;

  // A chi guarda la squadra di un altro si dice soltanto com'è la porta: il
  // pannello con le spunte e i candidati non gli serve a niente.
  if (!posso) {
    if (!dati.attiva) return null;
    return (
      <section>
        <h2 className="sezione">🧤 Portiere d'emergenza</h2>
        <p className="avviso">
          {dati.in_carica_nome} copre la porta come portiere d'emergenza (art.
          8, Lodo Messina): vota con {dati.malus} punto di malus.
        </p>
      </section>
    );
  }

  const tuttiFuori = fuori.length === dati.portieri.length;

  function spunta(id: number) {
    setFuori((precedenti) =>
      precedenti.includes(id)
        ? precedenti.filter((p) => p !== id)
        : [...precedenti, id],
    );
  }

  async function prova(azione: () => Promise<unknown>, riuscito: string) {
    setErrore(null);
    setInCorso(true);
    try {
      await azione();
      onCambiata(riuscito);
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
    } finally {
      setInCorso(false);
    }
  }

  return (
    <section>
      <h2 className="sezione">🧤 Portiere d'emergenza</h2>

      <p className={dati.va_revocata ? "avviso" : "tenue"}>{dati.motivo}</p>

      {dati.attiva ? (
        <div className="riquadro-modulo">
          <h3>{dati.in_carica_nome}</h3>
          <p className="tenue">
            Non ha contratto: non pesa su monte anni né su Salary Cap, e vota
            con {dati.malus} punto di malus (Lodo Messina bis). Si tiene finché
            uno dei portieri di ruolo non torna disponibile, anche solo in
            panchina.
          </p>
          {errore && <div className="errore">{errore}</div>}
          <button
            className={dati.va_revocata ? "principale" : "secondario"}
            disabled={inCorso}
            onClick={() =>
              prova(
                () => api.revocaPortiereEmergenza(squadra),
                "Portiere d'emergenza revocato.",
              )
            }
          >
            {inCorso ? "Revoco…" : "Revoca il portiere d'emergenza"}
          </button>
        </div>
      ) : (
        <div className="riquadro-modulo">
          <h3>I tuoi portieri</h3>
          <p className="tenue">
            Spunta quelli indisponibili — infortunati e nemmeno in panchina.
            L'emergenza spetta solo se lo sono <strong>tutti</strong>.
          </p>
          <div className="interruttori">
            {dati.portieri.map((p) => (
              <label key={p.id}>
                <input
                  type="checkbox"
                  checked={fuori.includes(p.id)}
                  onChange={() => spunta(p.id)}
                />
                {p.nome} <span className="tenue">indisponibile</span>
              </label>
            ))}
          </div>

          {tuttiFuori && (
            <div className="campo">
              <label htmlFor="e-portiere">
                Portiere da pescare fra gli svincolati
              </label>
              <select
                id="e-portiere"
                value={scelto ?? ""}
                onChange={(e) => setScelto(Number(e.target.value))}
              >
                {dati.candidati.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome} — {c.club} ({milioni(c.ingaggio, 2)})
                  </option>
                ))}
              </select>
            </div>
          )}

          {tuttiFuori && dati.candidati.length === 0 && (
            <div className="errore">
              Non c'è nessun portiere svincolato nel listone: senza candidati
              l'emergenza non si può aprire.
            </div>
          )}
          {errore && <div className="errore">{errore}</div>}

          <button
            className="principale"
            disabled={inCorso || !tuttiFuori || scelto === null}
            onClick={() =>
              prova(
                () => api.attivaPortiereEmergenza(squadra, scelto!, fuori),
                "Portiere d'emergenza attivato.",
              )
            }
          >
            {inCorso ? "Attivo…" : "Attiva il portiere d'emergenza"}
          </button>
        </div>
      )}
    </section>
  );
}

export function Squadra() {
  const { id } = useParams();
  const numero = Number(id);
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(
    () => api.squadra(numero),
    [numero, giro],
  );
  const [conferma, setConferma] = useState<string | null>(null);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const c = dato.conti;
  const capResiduo = c.limite_cap - c.monte_ingaggi;

  return (
    <>
      <Link to="/squadre" className="indietro">
        ← Tutte le squadre
      </Link>

      {conferma && <div className="conferma">{conferma}</div>}

      <header className="testata-squadra">
        <div
          className="striscia"
          style={{
            background: `linear-gradient(90deg, ${dato.colori.primario}, ${dato.colori.secondario})`,
          }}
        />
        <div>
          <h1>
            {dato.nome}
            {dato.e_mia && <span className="pastiglia-mia">LA TUA</span>}
          </h1>
          {dato.motto && <p className="motto">{dato.motto}</p>}
        </div>
        <dl className="anagrafica">
          <div>
            <dt>Presidente</dt>
            <dd>{dato.presidente || "—"}</dd>
          </div>
          <div>
            <dt>Stadio</dt>
            <dd>{dato.stadio || "—"}</dd>
          </div>
          <div>
            <dt>Città</dt>
            <dd>{dato.citta || "—"}</dd>
          </div>
          <div>
            <dt>Curva</dt>
            <dd>{dato.curva || "—"}</dd>
          </div>
          {dato.anno_fondazione && (
            <div>
              <dt>Fondata nel</dt>
              <dd>{dato.anno_fondazione}</dd>
            </div>
          )}
        </dl>
      </header>

      <section>
        <h2 className="sezione">🏆 Bacheca</h2>
        {dato.titoli.length === 0 ? (
          <p className="vuoto">
            Ancora nessun titolo. La bacheca si riempie da sola quando chi
            amministra registra un vincitore nell'albo d'oro.
          </p>
        ) : (
          <div className="pastiglie">
            {dato.titoli.map((t, i) => (
              <span key={i} className="pastiglia">
                {t.icona} {t.etichetta} {t.stagione}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="sezione">Conti</h2>
        <div className="riquadri">
          <Numero
            etichetta="Rosa"
            valore={String(c.giocatori)}
            nota={`su ${c.limite_dimensione}${c.slot_u21 ? ` (+${c.slot_u21} U21)` : ""}`}
            sfora={c.giocatori > c.limite_dimensione}
            quota={c.giocatori / Math.max(c.limite_dimensione, 1)}
          />
          <Numero
            etichetta="Anni di contratto"
            valore={`${c.anni_impegnati}/${c.monte_anni}`}
            nota={`${c.monte_anni - c.anni_impegnati} liberi`}
            sfora={c.anni_impegnati > c.monte_anni}
            quota={c.anni_impegnati / Math.max(c.monte_anni, 1)}
          />
          <Numero
            etichetta="Cap residuo"
            valore={milioni(capResiduo)}
            nota={`su ${milioni(c.limite_cap, 0)}`}
            sfora={capResiduo < 0}
            quota={c.monte_ingaggi / Math.max(c.limite_cap, 1)}
          />
          <Numero
            etichetta="Italiani"
            valore={String(c.italiani)}
            nota={`di cui ${c.u21} Under 21`}
          />
        </div>
      </section>

      <section>
        <h2 className="sezione">Rosa</h2>
        <Rosa rosa={dato.rosa} riferimento={dato.riferimento_u21} />
      </section>

      <Emergenza
        squadra={numero}
        dati={dato.emergenza}
        posso={dato.posso_gestirla}
        onCambiata={(messaggio) => {
          setConferma(messaggio);
          setGiro((g) => g + 1);
        }}
      />

      <section>
        <h2 className="sezione">Conformità al regolamento</h2>
        {dato.violazioni.length === 0 ? (
          <p className="conforme">✅ Nessuna violazione: rosa conforme.</p>
        ) : (
          <ul className="violazioni">
            {dato.violazioni.map((v) => (
              <RigaViolazione key={v.codice} v={v} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
