import { useState, type FormEvent } from "react";
import {
  api,
  ErroreApi,
  type Galleria,
  type ModificaIdentita,
  type SquadraInGalleria,
} from "./api";

/**
 * Il modulo per creare una squadra o cambiarne l'identità.
 *
 * La maglia la disegna il server, non questo modulo: due squadre con gli
 * stessi colori devono venire identiche a chiunque le guardi, e la funzione
 * che le disegna è già provata in Python. Niente anteprima dal vivo: la maglia
 * nuova compare appena il salvataggio è andato a buon fine.
 *
 * Chi può usarlo non si decide qui: lo dicono `modificabile` e `posso_crearne`
 * del server, e le rotte rifiutano comunque chi non può.
 */

function vuota(stili: Galleria["stili"]): ModificaIdentita {
  return {
    nome: "",
    presidente: "",
    motto: "",
    stadio: "",
    citta: "",
    curva: "",
    colore_primario: "#2e7d32",
    colore_secondario: "#ffffff",
    stile_maglia: stili[0]?.nome ?? "TINTA_UNITA",
    anno_fondazione: new Date().getFullYear(),
  };
}

function daSquadra(s: SquadraInGalleria): ModificaIdentita {
  return {
    nome: s.nome,
    presidente: s.presidente,
    motto: s.motto,
    stadio: s.stadio,
    citta: s.citta,
    curva: s.curva,
    colore_primario: s.colore_primario,
    colore_secondario: s.colore_secondario,
    stile_maglia: s.stile_maglia,
    anno_fondazione: s.anno_fondazione,
  };
}

export function ModuloIdentita({
  galleria,
  squadra,
  onChiudi,
  onSalvata,
}: {
  galleria: Galleria;
  squadra: SquadraInGalleria | null;
  onChiudi: () => void;
  onSalvata: (messaggio: string) => void;
}) {
  const nuova = squadra === null;
  const [campi, setCampi] = useState<ModificaIdentita>(
    nuova ? vuota(galleria.stili) : daSquadra(squadra),
  );
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  function cambia<K extends keyof ModificaIdentita>(
    chiave: K,
    valore: ModificaIdentita[K],
  ) {
    setCampi((precedenti) => ({ ...precedenti, [chiave]: valore }));
  }

  // Le regole stanno accanto al campo, non solo nell'errore del server: una
  // regola che si scopre solo fallendo fa credere che il sito sia rotto.
  const occupati = galleria.nomi_occupati.filter(
    (n) => nuova || n.toLowerCase() !== squadra.nome.toLowerCase(),
  );
  const problemi: string[] = [];
  if (!campi.nome.trim()) problemi.push("Il nome della squadra è obbligatorio.");
  if (!campi.presidente.trim()) problemi.push("Il nome del presidente è obbligatorio.");
  if (occupati.some((n) => n.toLowerCase() === campi.nome.trim().toLowerCase()))
    problemi.push(`Esiste già una squadra chiamata «${campi.nome.trim()}».`);

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      const salvata = nuova
        ? await api.creaSquadra(campi)
        : await api.salvaIdentita(squadra.id, campi);
      onSalvata(`«${salvata.nome}» ${nuova ? "creata" : "aggiornata"}.`);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi ? guasto.message : "Non riesco a salvare.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form className="modulo" onSubmit={invia}>
      <div className="modulo-testata">
        <h2>{nuova ? "Crea una squadra" : `Modifica «${squadra.nome}»`}</h2>
        <button type="button" className="secondario" onClick={onChiudi}>
          Annulla
        </button>
      </div>

      <div className="campo">
        <label htmlFor="i-nome">Nome della squadra</label>
        <input
          id="i-nome"
          value={campi.nome}
          maxLength={60}
          onChange={(e) => cambia("nome", e.target.value)}
          autoFocus
        />
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="i-presidente">Presidente</label>
          <input
            id="i-presidente"
            value={campi.presidente}
            maxLength={60}
            onChange={(e) => cambia("presidente", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="i-anno">Anno di fondazione</label>
          <input
            id="i-anno"
            type="number"
            min={1900}
            max={2100}
            value={campi.anno_fondazione ?? ""}
            onChange={(e) =>
              cambia("anno_fondazione", e.target.value ? Number(e.target.value) : null)
            }
          />
        </div>
      </div>

      <div className="campo">
        <label htmlFor="i-motto">Motto</label>
        <input
          id="i-motto"
          value={campi.motto}
          maxLength={120}
          placeholder="Chi non risica non rosica"
          onChange={(e) => cambia("motto", e.target.value)}
        />
      </div>

      <div className="terna">
        <div className="campo">
          <label htmlFor="i-stadio">Stadio</label>
          <input
            id="i-stadio"
            value={campi.stadio}
            maxLength={80}
            placeholder="Arena del Padel"
            onChange={(e) => cambia("stadio", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="i-citta">Città</label>
          <input
            id="i-citta"
            value={campi.citta}
            maxLength={60}
            onChange={(e) => cambia("citta", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="i-curva">Curva</label>
          <input
            id="i-curva"
            value={campi.curva}
            maxLength={60}
            placeholder="Curva Nord"
            onChange={(e) => cambia("curva", e.target.value)}
          />
        </div>
      </div>

      <div className="terna">
        <div className="campo">
          <label htmlFor="i-primario">Colore primario</label>
          <input
            id="i-primario"
            type="color"
            value={campi.colore_primario}
            onChange={(e) => cambia("colore_primario", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="i-secondario">Colore secondario</label>
          <input
            id="i-secondario"
            type="color"
            value={campi.colore_secondario}
            onChange={(e) => cambia("colore_secondario", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="i-stile">Disegno della maglia</label>
          <select
            id="i-stile"
            value={campi.stile_maglia}
            onChange={(e) => cambia("stile_maglia", e.target.value)}
          >
            {galleria.stili.map((s) => (
              <option key={s.nome} value={s.nome}>
                {s.etichetta}
              </option>
            ))}
          </select>
        </div>
      </div>

      {problemi.map((p) => (
        <div key={p} className="errore">
          {p}
        </div>
      ))}
      {errore && <div className="errore">{errore}</div>}

      <button
        className="principale"
        type="submit"
        disabled={inCorso || problemi.length > 0}
      >
        {inCorso ? "Salvo…" : nuova ? "Crea la squadra" : "💾 Salva"}
      </button>
    </form>
  );
}
