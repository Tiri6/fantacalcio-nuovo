import { useEffect, useState, type FormEvent } from "react";
import { ErroreApi, api, type ModuloRegistrazione } from "../api";
import { useSessione } from "../sessione";

/**
 * La porta d'ingresso del sito: si entra o ci si iscrive.
 *
 * Due moduli e non due pagine. Chi arriva non sa ancora se ha un account —
 * spesso lo scopre provando — e mandarlo avanti e indietro fra due indirizzi
 * gli fa perdere quello che aveva gia' scritto. Qui la scheda cambia e il
 * resto della pagina resta dov'e'.
 *
 * Le regole (password minima, eta' minima, squadre del cuore) **arrivano dal
 * server**: sono le stesse che il dominio poi applica. Scriverle qui vorrebbe
 * dire che la pagina promette una cosa e il server ne pretende un'altra.
 */

type Scheda = "entra" | "iscriviti";

function Entra() {
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
      // in App.tsx mostra il sito.
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
    <form onSubmit={invia} noValidate>
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
    </form>
  );
}

const VUOTA = {
  nome: "",
  cognome: "",
  data_nascita: "",
  sesso: "NON_DICHIARATO",
  citta: "",
  squadra_preferita: "",
  nome_utente: "",
  email: "",
  password: "",
  conferma: "",
};

function Iscriviti({ onEntrato }: { onEntrato: () => void }) {
  const { iscriviti } = useSessione();
  const [modulo, setModulo] = useState<ModuloRegistrazione | null>(null);
  const [campi, setCampi] = useState({ ...VUOTA });
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .moduloRegistrazione()
      .then((m) => {
        if (!vivo) return;
        setModulo(m);
        // La tendina parte dall'ultima voce, «nessuna»: chi non tifa non
        // deve scegliere una squadra a caso per andare avanti.
        setCampi((c) => ({
          ...c,
          squadra_preferita:
            m.squadre_preferite[m.squadre_preferite.length - 1] ?? "",
        }));
      })
      .catch(() => vivo && setErrore("Non riesco a contattare il server."));
    return () => {
      vivo = false;
    };
  }, []);

  function cambia(chiave: keyof typeof VUOTA, valore: string) {
    setCampi((precedenti) => ({ ...precedenti, [chiave]: valore }));
  }

  // Le regole stanno accanto al campo, non nell'errore che arriva dopo: una
  // registrazione che fallisce senza lasciare traccia fa credere che il sito
  // sia rotto. Il server le ricontrolla comunque — e' lui ad avere l'ultima
  // parola — ma chi compila deve saperle prima di premere.
  const minimo = modulo?.password_minima ?? 8;
  const problemi: string[] = [];
  if (campi.nome_utente && campi.nome_utente.trim().length < 3)
    problemi.push("Il nome utente vuole almeno 3 caratteri.");
  if (campi.password && campi.password.length < minimo)
    problemi.push(`La password vuole almeno ${minimo} caratteri.`);
  if (campi.password && campi.conferma && campi.password !== campi.conferma)
    problemi.push("Le due password non coincidono.");

  const obbligatori = [
    campi.nome,
    campi.cognome,
    campi.data_nascita,
    campi.citta,
    campi.nome_utente,
    campi.email,
    campi.password,
    campi.conferma,
  ];
  const pronto =
    obbligatori.every((v) => v.trim()) && problemi.length === 0 && !!modulo;

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      await iscriviti(campi);
      onEntrato();
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

  if (!modulo) {
    return errore ? (
      <div className="errore" role="alert">
        {errore}
      </div>
    ) : (
      <div className="fantasma alto" />
    );
  }

  return (
    <form onSubmit={invia} noValidate>
      {modulo.primo_utente && (
        <div className="avviso corona">
          👑 Sei il primo ad arrivare: il tuo account sarà quello del{" "}
          <strong>presidente di lega</strong>, l'unico che può creare la lega,
          invitare gli altri e ratificare gli scambi.
        </div>
      )}

      <h3 className="porta-gruppo">Chi sei</h3>
      <div className="coppia">
        <div className="campo">
          <label htmlFor="r-nome">Nome</label>
          <input
            id="r-nome"
            value={campi.nome}
            onChange={(e) => cambia("nome", e.target.value)}
            autoComplete="given-name"
            autoFocus
            required
          />
        </div>
        <div className="campo">
          <label htmlFor="r-cognome">Cognome</label>
          <input
            id="r-cognome"
            value={campi.cognome}
            onChange={(e) => cambia("cognome", e.target.value)}
            autoComplete="family-name"
            required
          />
        </div>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="r-nascita">Data di nascita</label>
          <input
            id="r-nascita"
            value={campi.data_nascita}
            onChange={(e) => cambia("data_nascita", e.target.value)}
            placeholder="gg/mm/aaaa"
            inputMode="numeric"
            autoComplete="bday"
            required
          />
        </div>
        <div className="campo">
          <label htmlFor="r-sesso">Sesso</label>
          <select
            id="r-sesso"
            value={campi.sesso}
            onChange={(e) => cambia("sesso", e.target.value)}
          >
            {modulo.sessi.map((s) => (
              <option key={s.nome} value={s.nome}>
                {s.etichetta}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="r-citta">Città</label>
          <input
            id="r-citta"
            value={campi.citta}
            onChange={(e) => cambia("citta", e.target.value)}
            autoComplete="address-level2"
            required
          />
        </div>
        <div className="campo">
          <label htmlFor="r-squadra">Squadra del cuore</label>
          <select
            id="r-squadra"
            value={campi.squadra_preferita}
            onChange={(e) => cambia("squadra_preferita", e.target.value)}
          >
            {modulo.squadre_preferite.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <h3 className="porta-gruppo">Come entri</h3>
      <div className="coppia">
        <div className="campo">
          <label htmlFor="r-utente">Nome utente</label>
          <input
            id="r-utente"
            value={campi.nome_utente}
            onChange={(e) => cambia("nome_utente", e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="campo">
          <label htmlFor="r-email">Email</label>
          <input
            id="r-email"
            type="email"
            value={campi.email}
            onChange={(e) => cambia("email", e.target.value)}
            autoComplete="email"
            required
          />
        </div>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="r-password">Password</label>
          <input
            id="r-password"
            type="password"
            value={campi.password}
            onChange={(e) => cambia("password", e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="campo">
          <label htmlFor="r-conferma">Ripetila</label>
          <input
            id="r-conferma"
            type="password"
            value={campi.conferma}
            onChange={(e) => cambia("conferma", e.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
      </div>

      <p className="porta-aiuto">
        Password di almeno {minimo} caratteri. L'email non riceverà posta: serve
        a farti trovare se qualcuno ti ha già invitato a una lega.
      </p>

      {problemi.map((p) => (
        <div key={p} className="errore">
          {p}
        </div>
      ))}
      {errore && (
        <div className="errore" role="alert">
          {errore}
        </div>
      )}

      <button
        className="principale"
        type="submit"
        disabled={!pronto || inCorso}
      >
        {inCorso ? "Creo l'account…" : "Crea l'account"}
      </button>
    </form>
  );
}

const PUNTI = [
  {
    icona: "📋",
    titolo: "Contratti e monte anni",
    testo: "Durate, scadenze e monte anni: i conti sempre quadrati.",
  },
  {
    icona: "💰",
    titolo: "Salary Cap",
    testo: "Ingaggi reali da Capology, Dead Money e spazio residuo.",
  },
  {
    icona: "🎱",
    titolo: "Draft e scambi",
    testo: "Lottery, ordine dei giri e scambi validati sul regolamento.",
  },
];

export function Accesso() {
  const [scheda, setScheda] = useState<Scheda>("entra");

  return (
    <div className="porta">
      <section className="porta-vetrina">
        <div className="porta-marchio">
          <span className="porta-stemma" aria-hidden="true">
            ⚽
          </span>
          <span>FantaCalcio NuoVo</span>
        </div>

        <h1>
          La rivoluzione
          <br />
          del fantacalcio
        </h1>
        <p className="porta-richiamo">La gestione a 360 gradi del tuo team.</p>

        <ul className="porta-punti">
          {PUNTI.map((p) => (
            <li key={p.titolo}>
              <span className="icona" aria-hidden="true">
                {p.icona}
              </span>
              <div>
                <strong>{p.titolo}</strong>
                <span>{p.testo}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="accesso">
        <div className="accesso-riquadro">
          <div className="porta-schede" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={scheda === "entra"}
              className={scheda === "entra" ? "scheda attiva" : "scheda"}
              onClick={() => setScheda("entra")}
            >
              Entra
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={scheda === "iscriviti"}
              className={scheda === "iscriviti" ? "scheda attiva" : "scheda"}
              onClick={() => setScheda("iscriviti")}
            >
              Registrati
            </button>
          </div>

          {scheda === "entra" ? (
            <>
              <h2>Bentornato</h2>
              <p className="porta-spiega">Entra con le tue credenziali.</p>
              <Entra />
              <p className="porta-passaggio">
                Non hai ancora un account?{" "}
                <button type="button" onClick={() => setScheda("iscriviti")}>
                  Registrati
                </button>
              </p>
            </>
          ) : (
            <>
              <h2>Crea il tuo account</h2>
              <p className="porta-spiega">
                Bastano un minuto e i dati qui sotto.
              </p>
              <Iscriviti onEntrato={() => setScheda("entra")} />
              <p className="porta-passaggio">
                Hai già un account?{" "}
                <button type="button" onClick={() => setScheda("entra")}>
                  Entra
                </button>
              </p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
