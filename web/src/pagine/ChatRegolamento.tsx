import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { Link } from "react-router-dom";
import {
  ErroreApi,
  api,
  chiediAlRegolamento,
  type MessaggioChat,
} from "../api";
import { useCarica } from "../carica";

/**
 * Chat sul regolamento: si chiede una norma a parole e si riceve la risposta.
 *
 * La pagina Regolamento mostra le tabelle; questa risponde alle domande che le
 * tabelle non chiudono («posso mettere un difensore al posto di un
 * attaccante?»). La fonte è la stessa: il dossier che il gestionale costruisce
 * dai parametri di *questa* lega, non il ricordo che il modello ha di altri
 * fantacalci.
 *
 * **La conversazione vive nel browser e viaggia a ogni domanda.** Il server non
 * tiene sessioni di chat: niente da far scadere, niente da ripulire, e due
 * schede aperte non si mescolano le risposte.
 */

export function ChatRegolamento() {
  const { dato, errore, inCorso } = useCarica(() => api.statoChat(), []);
  const [storico, setStorico] = useState<MessaggioChat[]>([]);
  const [domanda, setDomanda] = useState("");
  const [inArrivo, setInArrivo] = useState<string | null>(null);
  const [guasto, setGuasto] = useState<string | null>(null);
  const fondo = useRef<HTMLDivElement>(null);

  // La risposta cresce dal basso: senza questo, chi legge deve inseguirla.
  useEffect(() => {
    fondo.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [storico, inArrivo]);

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  async function chiedi(testo: string) {
    const pulita = testo.trim();
    if (!pulita || inArrivo !== null) return;

    const prima = storico;
    setDomanda("");
    setGuasto(null);
    setStorico([...prima, { ruolo: "utente", testo: pulita }]);
    setInArrivo("");

    let risposta = "";
    try {
      await chiediAlRegolamento(
        pulita,
        prima,
        (pezzo) => {
          risposta += pezzo;
          setInArrivo(risposta);
        },
        (messaggio) => setGuasto(messaggio),
      );
    } catch (errore) {
      setGuasto(
        errore instanceof ErroreApi
          ? errore.message
          : "Non riesco a contattare il server.",
      );
    } finally {
      setInArrivo(null);
      if (risposta) {
        setStorico((s) => [...s, { ruolo: "assistente", testo: risposta }]);
      }
    }
  }

  if (!dato.attiva) {
    return (
      <>
        <div className="intestazione-pagina">
          <h1>💬 Chat sul regolamento</h1>
        </div>
        <div className="riquadro avviso">
          🔌 <strong>La chat non è ancora attiva.</strong> Serve una chiave
          dell'API di Anthropic: è l'unico pezzo del sito che non gira da solo.
        </div>
        {dato.posso_configurare ? (
          <div className="prosa">
            <p>
              <strong>Come si attiva</strong> (lo puoi fare tu, sei il
              presidente):
            </p>
            <ol>
              <li>
                prendi una chiave su{" "}
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noreferrer"
                >
                  console.anthropic.com
                </a>
              </li>
              <li>
                aggiungila fra le variabili d'ambiente del servizio, con nome{" "}
                <code>{dato.nome_secret}</code>
              </li>
              <li>salva: il servizio riparte da solo</li>
            </ol>
            <p className="didascalia">
              In locale la stessa riga va in{" "}
              <code>.streamlit/secrets.toml</code>, che non finisce su Git.
            </p>
          </div>
        ) : (
          <p className="didascalia">
            Chiedi al presidente della lega di configurarla: gli basta
            aggiungere una variabile d'ambiente.
          </p>
        )}
        <Link to="/regolamento">📖 Torna al regolamento</Link>
      </>
    );
  }

  return (
    <>
      <div className="intestazione-pagina">
        <h1>💬 Chat sul regolamento</h1>
        <p>Chiedi una norma a parole: rispondo con le regole di questa lega.</p>
      </div>

      <details className="formato">
        <summary>Su cosa rispondo</summary>
        <div className="prosa">
          <p className="didascalia">
            La scheda che leggo è generata dal gestionale: i parametri del
            regolamento, le scelte di questa lega, le tabelle del Mantra e i
            punti che la lega non ha ancora votato. Rose, contratti e utenti non
            ci sono: la chat parla di regole, non di squadre.
          </p>
          <p className="didascalia">
            Le domande vengono inviate ad Anthropic per essere elaborate. Non
            scriverci dentro niente che non scriveresti in bacheca.
          </p>
          <pre className="scheda-chat">{dato.scheda}</pre>
        </div>
      </details>

      {storico.length === 0 && inArrivo === null && (
        <>
          <p className="didascalia">
            Non sai da dove cominciare? Prova una di queste.
          </p>
          <div className="esempi">
            {dato.domande_di_esempio.map((esempio) => (
              <button
                key={esempio}
                className="secondario"
                onClick={() => chiedi(esempio)}
              >
                {esempio}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="conversazione">
        {storico.map((m, indice) => (
          <div
            key={indice}
            className={m.ruolo === "utente" ? "bolla mia" : "bolla"}
          >
            {/* La risposta è Markdown: senza renderlo si leggono gli
                asterischi. Con `<Markdown>` e non con
                `dangerouslySetInnerHTML`, come la bacheca: quel componente
                l'HTML non lo esegue, e qui il testo arriva da un modello. */}
            <Markdown>{m.testo}</Markdown>
          </div>
        ))}
        {inArrivo !== null && (
          <div className="bolla">
            {inArrivo ? (
              <Markdown>{inArrivo}</Markdown>
            ) : (
              <span className="didascalia">Cerco nel regolamento…</span>
            )}
          </div>
        )}
        <div ref={fondo} />
      </div>

      {guasto && (
        <div className="errore" role="alert">
          ⚠️ {guasto}
        </div>
      )}

      <form
        className="in-linea"
        onSubmit={(e) => {
          e.preventDefault();
          chiedi(domanda);
        }}
      >
        <div className="campo">
          <label htmlFor="domanda">Chiedi una regola…</label>
          <input
            id="domanda"
            value={domanda}
            maxLength={dato.limite_domanda}
            onChange={(e) => setDomanda(e.target.value)}
            placeholder="Quanti annuali mi servono con 32 giocatori?"
            autoFocus
          />
        </div>
        <button
          className="principale"
          type="submit"
          disabled={inArrivo !== null || !domanda.trim()}
        >
          {inArrivo !== null ? "…" : "Chiedi"}
        </button>
      </form>

      {storico.length > 0 && (
        <button className="secondario" onClick={() => setStorico([])}>
          🧹 Svuota la conversazione
        </button>
      )}

      <p>
        <Link to="/regolamento">📖 Il regolamento in tabella</Link>
      </p>
    </>
  );
}
