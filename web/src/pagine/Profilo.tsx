import { useState, type FormEvent } from "react";
import { api, ErroreApi } from "../api";
import { useCarica } from "../carica";
import { TEMI, salvaTema, temaScelto, type Tema } from "../tema";

/**
 * Password nuova e codice di recupero hanno la stessa forma: esistono in
 * chiaro **una volta sola**, nell'istante in cui nascono. Da lì in poi nel
 * database resta solo il loro hash.
 *
 * È il motivo per cui il codice si mostra in grande e si avvisa di copiarlo:
 * ricaricare la pagina non lo fa ricomparire.
 */
function CambioPassword({ onFatto }: { onFatto: (messaggio: string) => void }) {
  const [attuale, setAttuale] = useState("");
  const [nuova, setNuova] = useState("");
  const [conferma, setConferma] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  // Le regole stanno accanto al campo. Il server le ricontrolla comunque —
  // è lui ad avere l'ultima parola — ma scoprirle solo fallendo fa credere
  // che il sito sia rotto.
  const problemi: string[] = [];
  if (nuova && nuova.length < 8)
    problemi.push("La password nuova vuole almeno 8 caratteri.");
  if (nuova && conferma && nuova !== conferma)
    problemi.push("Le due password non coincidono.");
  if (nuova && attuale && nuova === attuale)
    problemi.push("La password nuova è uguale a quella attuale.");

  const pronto = attuale && nuova && conferma && problemi.length === 0;

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      await api.cambiaPassword(attuale, nuova, conferma);
      setAttuale("");
      setNuova("");
      setConferma("");
      onFatto("Password cambiata.");
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a cambiarla.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <form className="riquadro-modulo" onSubmit={invia}>
      <h3>Cambia la password</h3>
      <p className="tenue">
        Serve conoscere quella attuale: senza, chiunque trovasse una sessione
        aperta potrebbe prendersi l'account per sempre.
      </p>

      <div className="campo">
        <label htmlFor="p-attuale">Password attuale</label>
        <input
          id="p-attuale"
          type="password"
          autoComplete="current-password"
          value={attuale}
          onChange={(e) => setAttuale(e.target.value)}
        />
      </div>
      <div className="coppia">
        <div className="campo">
          <label htmlFor="p-nuova">Password nuova</label>
          <input
            id="p-nuova"
            type="password"
            autoComplete="new-password"
            value={nuova}
            onChange={(e) => setNuova(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="p-conferma">Ripetila</label>
          <input
            id="p-conferma"
            type="password"
            autoComplete="new-password"
            value={conferma}
            onChange={(e) => setConferma(e.target.value)}
          />
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
        disabled={!pronto || inCorso}
      >
        {inCorso ? "Cambio…" : "Cambia la password"}
      </button>
    </form>
  );
}

function CodiceRecupero({ gia }: { gia: boolean }) {
  const [codice, setCodice] = useState<string | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function genera() {
    setErrore(null);
    setInCorso(true);
    try {
      const esito = await api.generaCodiceRecupero();
      setCodice(esito.codice);
    } catch (guasto) {
      setErrore(
        guasto instanceof ErroreApi
          ? guasto.message
          : "Non riesco a generarlo.",
      );
    } finally {
      setInCorso(false);
    }
  }

  return (
    <div className="riquadro-modulo">
      <h3>Codice di recupero</h3>
      <p className="tenue">
        È la chiave di scorta: se un giorno non ricordi la password, con questo
        codice rientri da solo e ne scegli una nuova, senza chiedere niente a
        nessuno. Generalo adesso, mentre non serve.
      </p>

      {codice ? (
        <>
          <div className="codice-grande">{codice}</div>
          <div className="avviso">
            ⚠️ <strong>Copialo adesso.</strong> Esiste in chiaro solo in questo
            momento: ricaricando la pagina non ricompare, e nel database ne
            resta solo l'impronta.
          </div>
        </>
      ) : (
        <>
          {gia && (
            <div className="avviso">
              Ne hai già uno. Generandone un altro, il precedente smette di
              valere.
            </div>
          )}
          {errore && <div className="errore">{errore}</div>}
          <button className="secondario" disabled={inCorso} onClick={genera}>
            {inCorso
              ? "Genero…"
              : gia
                ? "Generane uno nuovo"
                : "Genera il codice"}
          </button>
        </>
      )}
    </div>
  );
}

/**
 * Chiaro o scuro.
 *
 * Sta nel profilo e non nelle impostazioni della lega perche' e' una
 * preferenza di chi guarda, non una regola: due persone della stessa lega
 * possono volerlo diverso, e lo stesso utente puo' volerlo diverso fra
 * telefono e portatile.
 */
function Aspetto() {
  const [scelto, setScelto] = useState<Tema>(temaScelto);

  function cambia(tema: Tema) {
    setScelto(tema);
    salvaTema(tema);
  }

  return (
    <div className="riquadro-modulo">
      <h3>Aspetto</h3>
      <p className="tenue">
        «Come il sistema» segue l'impostazione del telefono o del computer e
        cambia da sola al tramonto, se li hai impostati cosi'. La scelta resta
        su questo dispositivo.
      </p>
      <div className="filtri">
        {TEMI.map((t) => (
          <button
            key={t.nome}
            className={scelto === t.nome ? "filtro attiva" : "filtro"}
            aria-pressed={scelto === t.nome}
            onClick={() => cambia(t.nome)}
          >
            {t.icona} {t.etichetta}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Profilo() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.profilo(), [giro]);
  const [conferma, setConferma] = useState<string | null>(null);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  const righe: [string, string][] = [
    ["Email", dato.email || "— non registrata —"],
    ["Data di nascita", dato.data_nascita || "—"],
    ...(dato.eta !== null
      ? ([["Età", `${dato.eta} anni`]] as [string, string][])
      : []),
    ["Sesso", dato.sesso],
    ["Città", dato.citta || "—"],
    ["Squadra del cuore", dato.squadra_preferita || "—"],
  ];

  return (
    <>
      <div className="intestazione-pagina">
        <h1>👤 Il mio profilo</h1>
        {/* Il trattino solo se c'e' qualcosa dopo: chi si e' appena
            registrato non sta ancora in nessuna lega, e un «Marco Rossi —»
            monco sembra un dato che non ha caricato. */}
        <p>
          {dato.nome_completo}
          {dato.nome_lega ? ` — ${dato.nome_lega}` : ""}
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      <div className="riquadri">
        <div className="riquadro">
          <span className="etichetta">Nome utente</span>
          <span className="valore piccolo">{dato.nome_utente}</span>
        </div>
        <div className="riquadro">
          <span className="etichetta">Ruolo</span>
          <span className="valore piccolo">{dato.ruolo_etichetta}</span>
        </div>
        <div className="riquadro">
          <span className="etichetta">Squadra</span>
          <span className="valore piccolo">{dato.squadra}</span>
        </div>
      </div>

      <h2 className="sottotitolo">I tuoi dati</h2>
      <div className="tabella-contenitore">
        <table className="tabella">
          <tbody>
            {righe.map(([campo, valore]) => (
              <tr key={campo}>
                <td className="tenue">{campo}</td>
                <td className="forte">{valore}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="didascalia">
        Questi dati li hai scritti iscrivendoti. Per ora si cambiano solo dal
        database: se ne hai sbagliato uno, scrivilo al presidente di lega.
      </p>

      <h2 className="sottotitolo">Preferenze</h2>
      <Aspetto />

      <div className="moduli-affiancati">
        <CambioPassword
          onFatto={(messaggio) => {
            setConferma(messaggio);
            setGiro((g) => g + 1);
          }}
        />
        <CodiceRecupero gia={dato.ha_codice_recupero} />
      </div>

      <div className="scheda-nota">
        <h3>✉️ Perché non c'è il recupero via email</h3>
        <p>
          Il sito non ha un server di posta, e montarne uno per una lega di
          amici non si giustifica. Al suo posto ci sono due strade: il codice di
          recupero qui sopra, che usi da solo, e la richiesta al presidente
          dalla schermata di accesso, che gli arriva dentro il sito.
        </p>
      </div>
    </>
  );
}
