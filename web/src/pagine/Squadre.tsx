import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { milioni, useCarica } from "../carica";
import { IntestazioneOrdinabile } from "../intestazioneOrdinabile";
import { ModuloIdentita } from "../moduloIdentita";
import { useOrdinamento } from "../ordinamento";

/**
 * La lista delle squadre è la pagina principale: da qui si apre la scheda di
 * ognuna, con l'identità in alto. Si ordina cliccando l'intestazione.
 *
 * **Chi può creare una squadra non si decide qui.** Il pulsante è visibile a
 * tutti; `posso_crearne` e il motivo (`perche_non_crearne`) arrivano dal
 * server, che applica la stessa regola alla rotta di creazione: spegnere un
 * pulsante non è un controllo.
 */
export function Squadre() {
  const [giro, setGiro] = useState(0);
  const { dato: squadre, errore } = useCarica(() => api.squadre(), [giro]);
  const { dato: galleria } = useCarica(() => api.identita(), [giro]);
  const [creando, setCreando] = useState(false);
  const [conferma, setConferma] = useState<string | null>(null);

  const { ordinate, colonna, direzione, imposta } = useOrdinamento(
    squadre ?? [],
    {
      nome: (s) => s.nome,
      presidente: (s) => s.presidente || null,
      giocatori: (s) => s.giocatori,
      anni: (s) => s.anni_impegnati,
      ingaggi: (s) => s.monte_ingaggi,
      dead: (s) => s.dead_money,
    },
  );

  if (creando && galleria) {
    return (
      <ModuloIdentita
        galleria={galleria}
        squadra={null}
        onChiudi={() => setCreando(false)}
        onSalvata={(messaggio) => {
          setCreando(false);
          setConferma(messaggio);
          setGiro((g) => g + 1);
        }}
      />
    );
  }

  const intestazioni = [
    ["nome", "Squadra", undefined],
    ["presidente", "Presidente", undefined],
    ["giocatori", "Rosa", "numerica"],
    ["anni", "Anni", "numerica"],
    ["ingaggi", "Ingaggi", "numerica"],
    ["dead", "Dead money", "numerica"],
  ] as const;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>Squadre</h1>
        <p>
          {squadre
            ? galleria
              ? `${squadre.length} squadre su ${galleria.squadre_previste} previste dalla lega.`
              : `${squadre.length} squadre iscritte alla lega.`
            : "Carico le squadre…"}
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}
      {errore && <div className="errore">{errore}</div>}

      <div className="crea-squadra">
        <button
          type="button"
          className="secondario crea"
          disabled={!galleria || !galleria.posso_crearne}
          aria-describedby="perche-non-crearne"
          onClick={() => setCreando(true)}
        >
          ➕ Crea una squadra
        </button>
        {galleria && !galleria.posso_crearne && (
          <p id="perche-non-crearne" className="didascalia">
            {galleria.perche_non_crearne}
          </p>
        )}
      </div>

      {/* Scheletri invece di uno spinner: la pagina non salta quando i dati
          arrivano, perche' lo spazio era gia' quello giusto. */}
      {!squadre && !errore && (
        <div className="caricamento">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="fantasma" />
          ))}
        </div>
      )}

      {squadre && (
        <div className="tabella-contenitore">
          <table className="tabella lista-squadre">
            <thead>
              <tr>
                {intestazioni.map(([nome, etichetta, classe]) => (
                  <IntestazioneOrdinabile
                    key={nome}
                    nome={nome}
                    attiva={colonna}
                    direzione={direzione}
                    onOrdina={imposta}
                    className={classe}
                  >
                    {etichetta}
                  </IntestazioneOrdinabile>
                ))}
              </tr>
            </thead>
            <tbody>
              {ordinate.map((s) => (
                <tr key={s.id} className={s.e_mia ? "mia" : undefined}>
                  <td className="forte">
                    <Link to={`/squadre/${s.id}`} className="squadra-link">
                      <span
                        className="pallino-squadra"
                        aria-hidden="true"
                        style={{
                          background: `linear-gradient(90deg, ${s.colori.primario} 50%, ${s.colori.secondario} 50%)`,
                        }}
                      />
                      {s.nome}
                      {s.e_mia && <span className="pastiglia-mia">LA TUA</span>}
                    </Link>
                  </td>
                  <td className="tenue">{s.presidente || "—"}</td>
                  <td className="numerica">{s.giocatori}</td>
                  <td className="numerica">{s.anni_impegnati}</td>
                  <td className="numerica">{milioni(s.monte_ingaggi)}</td>
                  <td className="numerica">
                    {s.dead_money ? milioni(s.dead_money) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
