import {
  useLayoutEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
} from "react";
import {
  LUNGHEZZA_DATA,
  applicaModifica,
  daIncolla,
  esaminaData,
} from "./data";

/**
 * Il campo per una data scritta `gg/mm/aaaa`, pensato per il telefono.
 *
 * Il tastierino numerico di iOS e di Android non ha lo slash: chi doveva
 * scrivere `15/03/1990` non poteva. Qui si digitano solo cifre e le barre le
 * mette il campo (`15` → `15/`, `1503` → `15/03/`), si può cancellare senza
 * bloccarsi sulla barra e si può incollare la data in qualunque formato.
 *
 * La logica sta in `data.ts`, che si prova senza browser. Questo file la
 * collega a un input vero: cursore, incolla, messaggi.
 *
 * **Il valore è sempre la stringa `gg/mm/aaaa`**, la stessa che il server già
 * legge: chi usa il campo la manda com'è, non deve convertire niente.
 *
 * La validazione sta qui, accanto al campo, e non solo nell'errore del server:
 * una regola che si scopre soltanto dal rifiuto del modulo fa credere che il
 * sito sia rotto. Le età minima e massima restano al server, che le conosce.
 */
export function CampoData({
  id,
  valore,
  onCambia,
  etichetta = "Data di nascita",
  obbligatorio = true,
}: {
  id: string;
  valore: string;
  onCambia: (valore: string) => void;
  etichetta?: string;
  obbligatorio?: boolean;
}) {
  const campo = useRef<HTMLInputElement>(null);
  // Dove rimettere il cursore dopo il rendering. React riscrive il testo del
  // campo e il browser porta il cursore in fondo: correggendo una cifra in
  // mezzo, il secondo backspace cancellerebbe l'ultima cifra invece di quella
  // accanto.
  const cursore = useRef<number | null>(null);
  const [toccato, setToccato] = useState(false);

  const esame = esaminaData(valore);
  const incompleta = toccato && valore !== "" && !esame.completa;
  const messaggio = esame.errore
    ? esame.errore
    : incompleta
      ? "Scrivila per intero: gg/mm/aaaa, per esempio 24/03/1991."
      : null;
  const idMessaggio = `${id}-messaggio`;

  function rimettiIlCursore() {
    const el = campo.current;
    const dove = cursore.current;
    cursore.current = null;
    if (el && dove !== null && document.activeElement === el) {
      el.setSelectionRange(dove, dove);
    }
  }

  // Dopo ogni cambio di testo. Se il testo non cambia (una lettera rifiutata)
  // il rendering non parte, e lo si rimette a mano più sotto.
  useLayoutEffect(rimettiIlCursore, [valore]);

  function applica(
    precedente: string,
    nuovo: string,
    dove: number,
    tipo: "digitazione" | "incolla",
  ) {
    const modifica = applicaModifica(precedente, nuovo, dove, tipo);
    cursore.current = modifica.cursore;
    onCambia(modifica.valore);
    if (modifica.valore === precedente)
      window.requestAnimationFrame(rimettiIlCursore);
  }

  function cambia(evento: ChangeEvent<HTMLInputElement>) {
    const el = evento.target;
    applica(
      valore,
      el.value,
      el.selectionStart ?? el.value.length,
      "digitazione",
    );
  }

  /**
   * Incollare passa da qui e non dal normale `onChange` per due ragioni: il
   * `maxLength` taglierebbe `  15/03/1990` (con gli spazi) prima che il campo
   * la veda, e una data intera in un altro formato (`5-3-1990`, `1990-03-15`)
   * va riconosciuta come data, non trattata come cifre da accodare.
   */
  function incolla(evento: ClipboardEvent<HTMLInputElement>) {
    evento.preventDefault();
    const testo = evento.clipboardData.getData("text");
    const intera = daIncolla(testo);
    if (intera) {
      cursore.current = null;
      onCambia(intera);
      return;
    }
    const el = evento.currentTarget;
    const da = el.selectionStart ?? valore.length;
    const a = el.selectionEnd ?? da;
    const grezzo = valore.slice(0, da) + testo + valore.slice(a);
    applica(valore, grezzo, da + testo.length, "incolla");
  }

  return (
    <div className="campo">
      <label htmlFor={id}>{etichetta}</label>
      <input
        id={id}
        ref={campo}
        value={valore}
        onChange={cambia}
        onPaste={incolla}
        onBlur={() => setToccato(true)}
        placeholder="gg/mm/aaaa"
        inputMode="numeric"
        autoComplete="bday"
        maxLength={LUNGHEZZA_DATA}
        required={obbligatorio}
        aria-invalid={esame.errore || incompleta ? true : undefined}
        aria-describedby={messaggio ? idMessaggio : undefined}
      />
      {messaggio && (
        <p id={idMessaggio} className="campo-messaggio" role="status">
          {messaggio}
        </p>
      )}
    </div>
  );
}
