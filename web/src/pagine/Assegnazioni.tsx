import { useEffect, useMemo, useState } from "react";
import {
  ErroreApi,
  api,
  type LiberoAssegnabile,
  type PaginaAssegnazioni,
  type SquadraAssegnabile,
  type ViolazioneAssegnazione,
} from "../api";
import { milioni, useCarica } from "../carica";

/**
 * Registrare chi si è preso chi, un giocatore alla volta.
 *
 * Non è la Draft Room: lì il draft si **conduce**, a turni, con nove persone
 * che aspettano. Qui si prende nota di quel che è successo altrove — una
 * chiamata concordata al telefono, uno scambio fatto a voce, un errore da
 * correggere — e per questo una rosa che sfora avvisa invece di fermare. Un
 * sito che si rifiuta di registrare la realtà costringe a tenerne una copia
 * da un'altra parte, ed è lì che i conti cominciano a divergere.
 */

/** Quanto si aspetta prima di chiedere al server come resterebbe la rosa. */
const PAUSA = 400;

function Violazioni({ voci }: { voci: ViolazioneAssegnazione[] }) {
  if (voci.length === 0) return null;
  return (
    <div className="sala-violazioni" role="status">
      {voci.map((v) => (
        <p key={v.codice + v.messaggio}>
          <span className={v.bloccante ? "pastiglia rossa" : "pastiglia ambra"}>
            {v.articolo}
          </span>{" "}
          {v.messaggio}
        </p>
      ))}
    </div>
  );
}

function Modulo({
  dato,
  onFatta,
}: {
  dato: PaginaAssegnazioni;
  onFatta: (messaggio: string) => void;
}) {
  const [cerca, setCerca] = useState("");
  const [scelto, setScelto] = useState<LiberoAssegnabile | null>(null);
  const [squadra, setSquadra] = useState<SquadraAssegnabile | null>(
    dato.squadre[0] ?? null,
  );
  const [anni, setAnni] = useState(dato.anni_minimo);
  const [violazioni, setViolazioni] = useState<ViolazioneAssegnazione[]>([]);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  const trovati = useMemo(() => {
    const parola = cerca.trim().toLowerCase();
    const filtrati = parola
      ? dato.liberi.filter(
          (g) =>
            g.nome.toLowerCase().includes(parola) ||
            g.club.toLowerCase().includes(parola) ||
            g.ruoli.some((r) => r.toLowerCase() === parola),
        )
      : dato.liberi;
    return filtrati.slice(0, 20);
  }, [cerca, dato.liberi]);

  // Come resterebbe la rosa lo dice il server: la regola sta nel dominio, e
  // una seconda copia qui direbbe prima o poi una cosa diversa.
  useEffect(() => {
    if (!scelto || !squadra) {
      setViolazioni([]);
      return;
    }
    let vivo = true;
    const attesa = window.setTimeout(async () => {
      try {
        const esito = await api.anteprimaAssegnazione(
          scelto.id,
          squadra.id,
          anni,
        );
        if (vivo) setViolazioni(esito.violazioni);
      } catch {
        /* l'anteprima è un di più: se non arriva, resta il bottone */
      }
    }, PAUSA);
    return () => {
      vivo = false;
      window.clearTimeout(attesa);
    };
  }, [scelto, squadra, anni]);

  async function assegna() {
    if (!scelto || !squadra) return;
    setErrore(null);
    setInCorso(true);
    try {
      const esito = await api.assegna(scelto.id, squadra.id, anni);
      setScelto(null);
      setCerca("");
      setViolazioni([]);
      onFatta(esito.messaggio);
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
  for (let n = dato.anni_minimo; n <= dato.anni_massimo; n += 1) {
    anniPossibili.push(n);
  }

  return (
    <div className="riquadro">
      <h2>Un giocatore alla volta</h2>

      <div className="campo">
        <label htmlFor="as-cerca">Cerca fra gli svincolati</label>
        <input
          id="as-cerca"
          type="search"
          value={cerca}
          placeholder="Nome, club o ruolo"
          onChange={(e) => setCerca(e.target.value)}
        />
      </div>

      <div className="sala-liberi">
        {trovati.length === 0 ? (
          <p className="didascalia">Nessuno svincolato con questo nome.</p>
        ) : (
          trovati.map((g) => (
            <button
              key={g.id}
              className={
                scelto?.id === g.id ? "sala-libero scelto" : "sala-libero"
              }
              onClick={() => setScelto(g)}
            >
              <span className="forte">
                {g.nome}
                {g.u21 && <span className="pastiglia verde">U21</span>}
              </span>
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
          <div className="caselle-regole">
            <div className="campo">
              <label htmlFor="as-squadra">Alla squadra</label>
              <select
                id="as-squadra"
                value={squadra?.id ?? ""}
                onChange={(e) =>
                  setSquadra(
                    dato.squadre.find((s) => s.id === Number(e.target.value)) ??
                      null,
                  )
                }
              >
                {dato.squadre.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nome}
                  </option>
                ))}
              </select>
            </div>

            <div className="campo">
              <label htmlFor="as-anni">Anni di contratto</label>
              <select
                id="as-anni"
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
          </div>

          {squadra && (
            <p className="didascalia">
              {squadra.nome}: {squadra.giocatori} giocatori ·{" "}
              {squadra.anni_impegnati} anni su {dato.monte_anni} · spazio
              salariale {milioni(squadra.spazio_salariale)} · in arrivo{" "}
              {milioni(scelto.ingaggio)}
              {scelto.nazionalita && ` · ${scelto.nazionalita}`}
            </p>
          )}

          <Violazioni voci={violazioni} />
          {errore && (
            <div className="errore" role="alert">
              {errore}
            </div>
          )}

          <button className="principale" onClick={assegna} disabled={inCorso}>
            {inCorso
              ? "Registro…"
              : `Assegna ${scelto.nome} a ${squadra?.nome ?? ""}`}
          </button>
        </>
      )}
    </div>
  );
}

export function Assegnazioni() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.assegnazioni(), [giro]);
  const [appena, setAppena] = useState<string | null>(null);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore)
    return (
      <div className="vuoto">
        <h1>📝 Assegnazioni</h1>
        <p>{errore}</p>
      </div>
    );
  if (!dato) return null;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📝 Assegnazioni</h1>
        <p>
          Registra chi si è preso chi: {dato.liberi.length} da assegnare su{" "}
          {dato.in_listone} in listone.
        </p>
      </div>

      {appena && <div className="conferma">{appena}</div>}

      {!dato.posso_assegnare ? (
        <div className="riquadro avviso">
          🔒 Le assegnazioni le registra il presidente di lega (art. 1).
        </div>
      ) : dato.in_listone === 0 ? (
        <div className="riquadro avviso">
          📋 Il listone non è ancora caricato: senza, non c'è niente da
          assegnare. Si importa dalla pagina «Importa dati».
        </div>
      ) : dato.liberi.length === 0 ? (
        <div className="conferma">
          ✅ Tutti i giocatori del listone sono assegnati.
        </div>
      ) : (
        <Modulo
          dato={dato}
          onFatta={(messaggio) => {
            setAppena(messaggio);
            setGiro((g) => g + 1);
          }}
        />
      )}

      <p className="didascalia">
        Per registrare un draft intero c'è l'import delle rose, con l'anteprima
        riga per riga: sta in «Importa dati». Qui si fa il caso singolo — una
        chiamata concordata, una correzione — e una rosa che sfora avvisa senza
        fermare, perché quel che è successo va scritto comunque.
      </p>
    </>
  );
}
