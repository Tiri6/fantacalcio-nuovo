import { useState, type FormEvent } from "react";
import { api, ErroreApi, type Albo as DatiAlbo, type TitoloLetto } from "../api";
import { useCarica } from "../carica";

/**
 * La storia della lega. Si registra a competizione finita.
 *
 * Una competizione ha **un** vincitore per stagione: registrare lo stesso
 * titolo due volte non aggiunge una riga, sostituisce quella che c'era. La
 * regola sta nel dominio, e qui si avvisa prima di premere.
 */
function Modulo({
  dati,
  onChiudi,
  onRegistrato,
}: {
  dati: DatiAlbo;
  onChiudi: () => void;
  onRegistrato: (messaggio: string) => void;
}) {
  const [competizione, setCompetizione] = useState(
    dati.competizioni[0]?.nome ?? "CAMPIONATO",
  );
  const [stagione, setStagione] = useState(dati.stagione_corrente);
  const [squadra, setSquadra] = useState(dati.squadre[0] ?? "");
  const [note, setNote] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  // Si avvisa prima, non dopo: scoprire di aver sovrascritto un titolo
  // quando è già successo è il modo peggiore di saperlo.
  const sostituisce = dati.titoli.find(
    (t) => t.competizione === competizione && t.stagione === stagione,
  );

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      const nuovo = await api.registraTitolo({
        competizione,
        stagione,
        squadra_nome: squadra,
        note,
      });
      onRegistrato(
        `${nuovo.competizione_icona} ${nuovo.competizione_etichetta} ${nuovo.stagione} a «${nuovo.squadra_nome}».`,
      );
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a registrare.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form className="modulo" onSubmit={invia}>
      <div className="modulo-testata">
        <h2>➕ Registra un titolo</h2>
        <button type="button" className="secondario" onClick={onChiudi}>
          Annulla
        </button>
      </div>

      <div className="terna">
        <div className="campo">
          <label htmlFor="a-competizione">Competizione</label>
          <select
            id="a-competizione"
            value={competizione}
            onChange={(e) => setCompetizione(e.target.value)}
          >
            {dati.competizioni.map((c) => (
              <option key={c.nome} value={c.nome}>
                {c.icona} {c.etichetta}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="a-stagione">Stagione</label>
          <input
            id="a-stagione"
            value={stagione}
            maxLength={20}
            onChange={(e) => setStagione(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="a-squadra">Vincitrice</label>
          <select
            id="a-squadra"
            value={squadra}
            onChange={(e) => setSquadra(e.target.value)}
          >
            {dati.squadre.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="campo">
        <label htmlFor="a-note">Nota</label>
        <input
          id="a-note"
          value={note}
          maxLength={200}
          placeholder="Vinta all'ultima giornata"
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      {sostituisce && (
        <div className="avviso">
          ⚠️ Quella stagione è già assegnata a «{sostituisce.squadra_nome}».
          Registrando ora, quel titolo viene <strong>sostituito</strong>: il
          vincitore è uno solo.
        </div>
      )}
      {!dati.squadre.length && (
        <div className="errore">Non ci sono squadre da premiare.</div>
      )}
      {errore && <div className="errore">{errore}</div>}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || !squadra || !stagione.trim()}
      >
        {inCorso ? "Registro…" : sostituisce ? "Sostituisci il titolo" : "Registra il titolo"}
      </button>
    </form>
  );
}

function Riga({
  titolo,
  posso,
  onCancellato,
}: {
  titolo: TitoloLetto;
  posso: boolean;
  onCancellato: (messaggio: string) => void;
}) {
  const [chiedo, setChiedo] = useState(false);
  const [inCorso, setInCorso] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);

  async function cancella() {
    setInCorso(true);
    try {
      await api.cancellaTitolo(titolo.id);
      onCancellato(`Titolo ${titolo.stagione} cancellato.`);
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
      setInCorso(false);
    }
  }

  return (
    <article className="titolo">
      <span className="coppa">{titolo.competizione_icona}</span>
      <div className="dettagli">
        <h3>
          {titolo.competizione_etichetta}{" "}
          <span className="tenue">{titolo.stagione}</span>
        </h3>
        <p className="vincitrice">{titolo.squadra_nome}</p>
        {titolo.note && <p className="nota">{titolo.note}</p>}
        {errore && <div className="errore">{errore}</div>}
      </div>
      {posso &&
        (chiedo ? (
          <div className="azioni">
            <button className="pericoloso" disabled={inCorso} onClick={cancella}>
              Sì, cancella
            </button>
            <button className="secondario" onClick={() => setChiedo(false)}>
              Annulla
            </button>
          </div>
        ) : (
          <button className="secondario pericolo" onClick={() => setChiedo(true)}>
            Cancella
          </button>
        ))}
    </article>
  );
}

export function Albo() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.albo(), [giro]);
  const [registro, setRegistro] = useState(false);
  const [conferma, setConferma] = useState<string | null>(null);

  function aggiorna(messaggio: string) {
    setConferma(messaggio);
    setRegistro(false);
    setGiro((g) => g + 1);
  }

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  if (registro) {
    return (
      <Modulo
        dati={dato}
        onChiudi={() => setRegistro(false)}
        onRegistrato={aggiorna}
      />
    );
  }

  const stagioni = [...new Set(dato.titoli.map((t) => t.stagione))];

  return (
    <>
      <div className="intestazione-pagina">
        <h1>🏛️ Albo d'oro</h1>
        <p>
          La storia di {dato.nome_lega}: campionati, coppe e supercoppe.
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      {dato.posso_registrare && (
        <button className="secondario crea" onClick={() => setRegistro(true)}>
          ➕ Registra un titolo
        </button>
      )}

      {dato.titoli.length === 0 ? (
        <div className="vuoto">
          🫥 L'albo è vuoto. Si riempie a fine stagione, quando c'è qualcosa da
          scriverci.
        </div>
      ) : (
        <>
          {dato.bacheche.length > 0 && (
            <>
              <h2 className="sottotitolo">Chi ha vinto di più</h2>
              <div className="bacheche">
                {dato.bacheche.map((b) => (
                  <div key={b.squadra} className="bacheca-squadra">
                    <span className="totale">{b.totale}</span>
                    <span className="nome">{b.squadra}</span>
                    <span className="dettaglio tenue">
                      {dato.competizioni
                        .filter((c) => b.titoli[c.nome])
                        .map((c) => `${c.icona} ${b.titoli[c.nome]}`)
                        .join(" · ")}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {stagioni.map((stagione) => (
            <div key={stagione} className="stagione">
              <h2 className="sottotitolo">{stagione}</h2>
              <div className="titoli">
                {dato.titoli
                  .filter((t) => t.stagione === stagione)
                  .map((t) => (
                    <Riga
                      key={t.id}
                      titolo={t}
                      posso={dato.posso_registrare}
                      onCancellato={aggiorna}
                    />
                  ))}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  );
}
