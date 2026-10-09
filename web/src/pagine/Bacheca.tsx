import { useState, type FormEvent } from "react";
import Markdown from "react-markdown";
import {
  api,
  ErroreApi,
  type AnnuncioLetto,
  type Bacheca as DatiBacheca,
  type Scritto,
} from "../api";
import { useCarica } from "../carica";

/**
 * Il testo degli annunci è Markdown scritto da una persona, e si rende con
 * `<Markdown>`: quel componente l'HTML non lo esegue.
 *
 * Non è un dettaglio di stile. Passare lo stesso testo a
 * `dangerouslySetInnerHTML` vorrebbe dire che chi scrive un annuncio può
 * infilare uno `<script>` nella pagina di tutti gli altri — ed è la stessa
 * ragione per cui la versione Streamlit non usa `unsafe_allow_html`.
 */
function Testo({ children }: { children: string }) {
  return (
    <div className="prosa">
      <Markdown>{children}</Markdown>
    </div>
  );
}

function Pastiglie({ annuncio }: { annuncio: AnnuncioLetto }) {
  return (
    <div className="pastiglie">
      <span className="pastiglia">
        {annuncio.tipo_icona} {annuncio.tipo_etichetta}
      </span>
      {annuncio.in_evidenza && (
        <span className="pastiglia ambra">📌 In evidenza</span>
      )}
      {!annuncio.pubblicato && <span className="pastiglia rossa">Bozza</span>}
      {annuncio.giornata !== null && (
        <span className="pastiglia azzurra">Giornata {annuncio.giornata}</span>
      )}
    </div>
  );
}

function Azioni({
  annuncio,
  onFatto,
}: {
  annuncio: AnnuncioLetto;
  onFatto: (messaggio: string) => void;
}) {
  const [chiedo, setChiedo] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  async function prova(azione: () => Promise<unknown>, riuscito: string) {
    setErrore(null);
    setInCorso(true);
    try {
      await azione();
      onFatto(riuscito);
    } catch (guasto) {
      setErrore(guasto instanceof ErroreApi ? guasto.message : "Non riesco.");
    } finally {
      setInCorso(false);
    }
  }

  return (
    <>
      <div className="azioni">
        <button
          className="secondario"
          disabled={inCorso}
          onClick={() =>
            prova(
              () =>
                api.correggiAnnuncio(annuncio.id, {
                  in_evidenza: !annuncio.in_evidenza,
                }),
              annuncio.in_evidenza ? "Evidenza tolta." : "Messo in evidenza.",
            )
          }
        >
          {annuncio.in_evidenza ? "Togli evidenza" : "📌 Metti in evidenza"}
        </button>
        <button
          className="secondario"
          disabled={inCorso}
          onClick={() =>
            prova(
              () =>
                api.correggiAnnuncio(annuncio.id, {
                  pubblicato: !annuncio.pubblicato,
                }),
              annuncio.pubblicato ? "Riportato a bozza." : "Pubblicato.",
            )
          }
        >
          {annuncio.pubblicato ? "Riporta a bozza" : "Pubblica"}
        </button>
        <button
          className="secondario pericolo"
          disabled={inCorso}
          onClick={() => setChiedo(true)}
        >
          Elimina
        </button>
      </div>

      {/* Due passaggi: un annuncio cancellato non si recupera. */}
      {chiedo && (
        <div className="conferma-pericolo">
          <p>
            Eliminare «{annuncio.titolo}»? <strong>Non si torna indietro.</strong>
          </p>
          <div className="azioni">
            <button
              className="pericoloso"
              disabled={inCorso}
              onClick={() =>
                prova(
                  () => api.cancellaAnnuncio(annuncio.id),
                  `«${annuncio.titolo}» eliminato.`,
                )
              }
            >
              Sì, elimina
            </button>
            <button className="secondario" onClick={() => setChiedo(false)}>
              Annulla
            </button>
          </div>
        </div>
      )}

      {errore && <div className="errore">{errore}</div>}
    </>
  );
}

function vuoto(dati: DatiBacheca): Scritto {
  return {
    titolo: "",
    testo: "",
    tipo: dati.tipi[0]?.nome ?? "NOTIZIA",
    giornata: null,
    pubblicato: true,
    in_evidenza: false,
  };
}

function Modulo({
  dati,
  onChiudi,
  onScritto,
}: {
  dati: DatiBacheca;
  onChiudi: () => void;
  onScritto: (messaggio: string) => void;
}) {
  const [campi, setCampi] = useState<Scritto>(vuoto(dati));
  const [errore, setErrore] = useState<string | null>(null);
  const [inCorso, setInCorso] = useState(false);

  function cambia<K extends keyof Scritto>(chiave: K, valore: Scritto[K]) {
    setCampi((precedenti) => ({ ...precedenti, [chiave]: valore }));
  }

  // Le regole stanno accanto al campo: scoprirle solo dall'errore del server
  // fa credere che il sito sia rotto.
  const problemi: string[] = [];
  if (campi.titolo.trim().length < dati.titolo_minimo)
    problemi.push(`Il titolo vuole almeno ${dati.titolo_minimo} caratteri.`);
  if (campi.titolo.length > dati.titolo_massimo)
    problemi.push(`Il titolo non può superare ${dati.titolo_massimo} caratteri.`);
  if (!campi.testo.trim()) problemi.push("Il testo non può essere vuoto.");

  async function invia(evento: FormEvent) {
    evento.preventDefault();
    setErrore(null);
    setInCorso(true);
    try {
      const nuovo = await api.scriviInBacheca(campi);
      onScritto(
        nuovo.pubblicato ? `«${nuovo.titolo}» pubblicato.` : "Bozza salvata.",
      );
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
        <h2>✍️ Scrivi un annuncio</h2>
        <button type="button" className="secondario" onClick={onChiudi}>
          Annulla
        </button>
      </div>

      <div className="coppia">
        <div className="campo">
          <label htmlFor="b-tipo">Tipo</label>
          <select
            id="b-tipo"
            value={campi.tipo}
            onChange={(e) => cambia("tipo", e.target.value)}
          >
            {dati.tipi.map((t) => (
              <option key={t.nome} value={t.nome}>
                {t.icona} {t.etichetta}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="b-giornata">Giornata di riferimento</label>
          <input
            id="b-giornata"
            type="number"
            min={1}
            max={76}
            placeholder="nessuna"
            value={campi.giornata ?? ""}
            onChange={(e) =>
              cambia("giornata", e.target.value ? Number(e.target.value) : null)
            }
          />
        </div>
      </div>

      <div className="campo">
        <label htmlFor="b-titolo">Titolo</label>
        <input
          id="b-titolo"
          value={campi.titolo}
          maxLength={dati.titolo_massimo}
          placeholder="La giornata in tre righe"
          onChange={(e) => cambia("titolo", e.target.value)}
          autoFocus
        />
      </div>

      <div className="campo">
        <label htmlFor="b-testo">
          Testo <span className="tenue">— si scrive in Markdown</span>
        </label>
        <textarea
          id="b-testo"
          rows={10}
          value={campi.testo}
          maxLength={dati.testo_massimo}
          placeholder={"**grassetto**, *corsivo*, - elenchi, [link](https://...)"}
          onChange={(e) => cambia("testo", e.target.value)}
        />
      </div>

      <div className="interruttori">
        <label>
          <input
            type="checkbox"
            checked={campi.in_evidenza}
            onChange={(e) => cambia("in_evidenza", e.target.checked)}
          />
          📌 Metti in evidenza <span className="tenue">(resta in cima)</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={!campi.pubblicato}
            onChange={(e) => cambia("pubblicato", !e.target.checked)}
          />
          Salva come bozza <span className="tenue">(la vedi solo tu)</span>
        </label>
      </div>

      {/* L'anteprima si aggiorna da sola, e usa lo stesso componente della
          bacheca: quello che si vede qui è esattamente quello che leggeranno. */}
      {campi.testo.trim() && (
        <div className="anteprima">
          <h4>Anteprima</h4>
          <h3>{campi.titolo || "(senza titolo)"}</h3>
          <Testo>{campi.testo}</Testo>
        </div>
      )}

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
        {inCorso ? "Salvo…" : campi.pubblicato ? "Pubblica" : "Salva la bozza"}
      </button>
    </form>
  );
}

export function Bacheca() {
  const [giro, setGiro] = useState(0);
  const { dato, errore, inCorso } = useCarica(() => api.bacheca(), [giro]);
  const [scrivo, setScrivo] = useState(false);
  const [filtro, setFiltro] = useState<string | null>(null);
  const [conferma, setConferma] = useState<string | null>(null);

  function aggiorna(messaggio: string) {
    setConferma(messaggio);
    setScrivo(false);
    setGiro((g) => g + 1);
  }

  if (inCorso) return <div className="fantasma alto" />;
  if (errore) return <div className="errore">{errore}</div>;
  if (!dato) return null;

  if (scrivo) {
    return (
      <Modulo
        dati={dato}
        onChiudi={() => setScrivo(false)}
        onScritto={aggiorna}
      />
    );
  }

  // Solo i tipi che compaiono davvero: un filtro che non filtra niente è
  // una voce in più da leggere e nient'altro.
  const presenti = dato.tipi.filter((t) =>
    dato.annunci.some((a) => a.tipo === t.nome),
  );
  const annunci = filtro
    ? dato.annunci.filter((a) => a.tipo === filtro)
    : dato.annunci;

  return (
    <>
      <div className="intestazione-pagina">
        <h1>📣 Bacheca</h1>
        <p>
          Cosa succede in {dato.nome_lega}: notizie, comunicazioni e recap di
          giornata.
        </p>
      </div>

      {conferma && <div className="conferma">{conferma}</div>}

      {dato.posso_scrivere ? (
        <button className="secondario crea" onClick={() => setScrivo(true)}>
          ✍️ Scrivi un annuncio
        </button>
      ) : (
        <p className="tenue">
          Solo chi amministra la lega può scrivere in bacheca.
        </p>
      )}

      {dato.annunci.length === 0 && (
        <div className="vuoto">
          📭 La bacheca è vuota. Il primo annuncio lo scrive chi amministra la
          lega.
        </div>
      )}

      {presenti.length > 1 && (
        <div className="filtri">
          <button
            className={filtro === null ? "filtro attiva" : "filtro"}
            onClick={() => setFiltro(null)}
          >
            Tutto
          </button>
          {presenti.map((t) => (
            <button
              key={t.nome}
              className={filtro === t.nome ? "filtro attiva" : "filtro"}
              onClick={() => setFiltro(t.nome)}
            >
              {t.icona} {t.etichetta}
            </button>
          ))}
        </div>
      )}

      <div className="annunci">
        {annunci.map((a) => (
          <article
            key={a.id}
            className={a.pubblicato ? "annuncio" : "annuncio bozza"}
          >
            <Pastiglie annuncio={a} />
            <h2>{a.titolo}</h2>
            <p className="firma">
              {a.autore_nome || "chi amministra"} · {a.data_leggibile}
            </p>
            <Testo>{a.testo}</Testo>
            {dato.posso_scrivere && <Azioni annuncio={a} onFatto={aggiorna} />}
          </article>
        ))}
      </div>
    </>
  );
}
