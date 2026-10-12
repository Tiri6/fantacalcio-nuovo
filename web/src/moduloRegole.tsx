import { useEffect, useMemo, useState } from "react";
import {
  ErroreApi,
  api,
  type CampoRegola,
  type PaginaRegole,
  type ValoreRegola,
} from "./api";

/**
 * Il modulo con cui si cambiano le regole di lega.
 *
 * **Nessuna casella è scritta qui dentro.** L'elenco delle opzioni arriva dal
 * server già diviso in gruppi, con per ogni campo il tipo, il valore di
 * adesso e — per quelli a scelta — le voci ammesse. Scrivere il modulo a mano
 * vorrebbe dire una terza copia dell'elenco delle opzioni, dopo la dataclass
 * e le etichette: la terza copia è quella che si dimentica, e un'opzione
 * aggiunta domani resterebbe invisibile senza che nessuno se ne accorga.
 *
 * Prima di salvare si legge **cosa cambia**, e lo dice il server: una regola
 * toccata per sbaglio la scoprirebbero dieci persone a giornata in corso, e
 * rileggere tre righe costa meno di rimediare.
 */

/** Quanto si aspetta prima di chiedere l'anteprima, mentre si digita. */
const PAUSA_ANTEPRIMA = 500;

function Casella({
  campo,
  valore,
  onCambia,
}: {
  campo: CampoRegola;
  valore: ValoreRegola;
  onCambia: (valore: ValoreRegola) => void;
}) {
  const id = `regola-${campo.nome.replace(".", "-")}`;

  if (campo.tipo === "booleano") {
    return (
      <label className="interruttore">
        <input
          type="checkbox"
          checked={Boolean(valore)}
          onChange={(e) => onCambia(e.target.checked)}
        />
        <span>{campo.etichetta}</span>
      </label>
    );
  }

  if (campo.tipo === "scelta") {
    return (
      <div className="campo">
        <label htmlFor={id}>{campo.etichetta}</label>
        <select
          id={id}
          value={String(valore ?? "")}
          onChange={(e) => onCambia(e.target.value)}
        >
          {campo.scelte.map((s) => (
            <option key={s.valore} value={s.valore}>
              {s.etichetta}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (campo.tipo === "multi") {
    const scelti = Array.isArray(valore) ? valore.map(String) : [];
    return (
      <div className="campo campo-largo">
        <label>{campo.etichetta}</label>
        <div className="scelte-multiple">
          {campo.scelte.map((s) => {
            const dentro = scelti.includes(s.valore);
            return (
              <button
                key={s.valore}
                type="button"
                className={dentro ? "pastiglia verde" : "pastiglia"}
                aria-pressed={dentro}
                onClick={() =>
                  onCambia(
                    dentro
                      ? scelti.filter((v) => v !== s.valore)
                      : [...scelti, s.valore],
                  )
                }
              >
                {s.etichetta}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  const numerico = campo.tipo === "intero" || campo.tipo === "decimale";
  return (
    <div className="campo">
      <label htmlFor={id}>
        {campo.etichetta}
        {campo.unita === "milioni" && (
          <span className="tenue"> (in milioni)</span>
        )}
      </label>
      <input
        id={id}
        type={numerico ? "number" : "text"}
        step={campo.tipo === "decimale" ? "any" : 1}
        value={valore === null || valore === undefined ? "" : String(valore)}
        placeholder={campo.opzionale ? "nessun limite" : undefined}
        onChange={(e) =>
          onCambia(
            numerico && e.target.value !== ""
              ? Number(e.target.value)
              : e.target.value,
          )
        }
      />
    </div>
  );
}

export function ModuloRegole({
  regole,
  onSalvato,
}: {
  regole: PaginaRegole;
  onSalvato: (regole: PaginaRegole, messaggio: string) => void;
}) {
  // Solo quel che si è toccato: mandare l'intero modulo vorrebbe dire
  // riscrivere anche le regole che non si volevano cambiare, e basterebbe
  // una casella letta male per cambiarne una di nascosto.
  const [tocchi, setTocchi] = useState<Record<string, ValoreRegola>>({});
  const [stagione, setStagione] = useState(regole.stagione);
  const [cambia, setCambia] = useState<string[]>([]);
  const [avvisi, setAvvisi] = useState<string[]>([]);
  const [errore, setErrore] = useState("");
  const [guasto, setGuasto] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  const cambiaStagione = stagione.trim() && stagione.trim() !== regole.stagione;
  const qualcosa = Object.keys(tocchi).length > 0 || Boolean(cambiaStagione);

  const valori = useMemo(() => {
    const tutti: Record<string, ValoreRegola> = {};
    for (const gruppo of regole.gruppi) {
      for (const campo of gruppo.campi) tutti[campo.nome] = campo.valore;
    }
    return { ...tutti, ...tocchi };
  }, [regole, tocchi]);

  // L'anteprima la calcola il server: `differenze` sta nel dominio, e una
  // seconda copia qui direbbe prima o poi una cosa diversa da quella che il
  // server poi salva.
  useEffect(() => {
    if (!qualcosa) {
      setCambia([]);
      setAvvisi([]);
      setErrore("");
      return;
    }
    let vivo = true;
    const attesa = window.setTimeout(async () => {
      try {
        const esito = await api.anteprimaRegole(tocchi, stagione);
        if (!vivo) return;
        setCambia(esito.cambia);
        setAvvisi(esito.avvisi);
        setErrore(esito.errore);
      } catch (e) {
        if (vivo)
          setGuasto(
            e instanceof ErroreApi
              ? e.message
              : "Non riesco a contattare il server.",
          );
      }
    }, PAUSA_ANTEPRIMA);
    return () => {
      vivo = false;
      window.clearTimeout(attesa);
    };
  }, [tocchi, stagione, qualcosa]);

  async function salva() {
    setGuasto(null);
    setInCorso(true);
    try {
      const nuove = await api.cambiaRegole(tocchi, stagione);
      setTocchi({});
      onSalvato(
        nuove,
        cambia.length === 1
          ? "Regole aggiornate: 1 modifica salvata."
          : `Regole aggiornate: ${cambia.length} modifiche salvate.`,
      );
    } catch (e) {
      setGuasto(
        e instanceof ErroreApi
          ? e.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <>
      <p className="didascalia">
        Le caselle partono da come sta la lega adesso: cambia quel che serve e
        salva. Rose, calendario e albo restano dove sono — è il motivo per cui
        questa pagina esiste invece di dover rifare la lega.
      </p>

      <div className="campo">
        <label htmlFor="regola-stagione">Stagione</label>
        <input
          id="regola-stagione"
          value={stagione}
          onChange={(e) => setStagione(e.target.value)}
        />
      </div>

      {regole.gruppi.map((gruppo) => (
        <details key={gruppo.titolo} className="formato" open>
          <summary>{gruppo.titolo}</summary>
          <div className="caselle-regole">
            {gruppo.campi.map((campo) => (
              <Casella
                key={campo.nome}
                campo={campo}
                valore={valori[campo.nome]}
                onCambia={(v) =>
                  setTocchi((precedenti) => ({
                    ...precedenti,
                    [campo.nome]: v,
                  }))
                }
              />
            ))}
          </div>
        </details>
      ))}

      {regole.escluse.length > 0 && (
        <details className="formato">
          <summary>Cosa da qui non si cambia</summary>
          <ul className="elenco-teste">
            {regole.escluse.map((e) => (
              <li key={e.nome}>
                <code>{e.nome}</code> — {e.motivo}
              </li>
            ))}
          </ul>
        </details>
      )}

      {qualcosa && (
        <div className="riquadro">
          <h3>Cosa cambia</h3>
          {errore ? (
            <div className="errore" role="alert">
              {errore}
            </div>
          ) : cambia.length === 0 ? (
            <p className="didascalia">Per ora non hai cambiato niente.</p>
          ) : (
            <ul className="elenco-teste">
              {cambia.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          {avvisi.map((a) => (
            <div key={a} className="riquadro avviso">
              ⚠️ {a}
            </div>
          ))}
        </div>
      )}

      {guasto && (
        <div className="errore" role="alert">
          {guasto}
        </div>
      )}

      <button
        className="principale"
        onClick={salva}
        disabled={inCorso || !qualcosa || Boolean(errore)}
      >
        {inCorso ? "Salvo…" : "💾 Salva le regole nuove"}
      </button>
    </>
  );
}
