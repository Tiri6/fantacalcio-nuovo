import { useState, type FormEvent } from "react";
import { ErroreApi } from "../api";
import { useSessione } from "../sessione";

export function Accesso() {
  const { entra } = useSessione();
  const [nomeUtente, setNomeUtente] = useState("");
  const [password, setPassword] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      await entra(nomeUtente, password);
      // Nessuna navigazione a mano: appena la sessione c'e', l'instradamento
      // in App.tsx mostra il sito. Un redirect esplicito qui si
      // disallineerebbe il giorno che cambia la pagina d'ingresso.
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
    <div className="accesso">
      <form className="accesso-riquadro" onSubmit={invia}>
        <div className="occhiello">Fantacalcio manageriale</div>
        <h1>FantaCalcio NuoVo</h1>
        <p className="sottotitolo">
          Contratti, monte anni, Salary Cap, draft e scambi.
        </p>

        <div className="campo">
          <label htmlFor="nome-utente">Nome utente</label>
          <input
            id="nome-utente"
            value={nomeUtente}
            onChange={(e) => setNomeUtente(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </div>

        <div className="campo">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        <button className="principale" type="submit" disabled={inCorso}>
          {inCorso ? "Un attimo…" : "Entra"}
        </button>

        {errore && (
          <div className="errore" role="alert">
            {errore}
          </div>
        )}

        <p className="nota-demo">
          Modalita' demo: <code>marco</code> (presidente), <code>luca</code>,{" "}
          <code>giulia</code> — password <code>fantanuovo26</code> per tutti.
        </p>
      </form>
    </div>
  );
}
