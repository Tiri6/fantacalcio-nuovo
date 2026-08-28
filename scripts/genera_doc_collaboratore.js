// Genera il documento Word da girare a chi entra nel progetto.
//
//     npm install docx && node scripts/genera_doc_collaboratore.js
//
// Il contenuto e' lo stesso di COLLABORARE.md: se cambia uno, cambia l'altro.
// Esiste in due formati perche' un .md si legge su GitHub e un .docx si
// gira a chi su GitHub non e' ancora entrato.

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LevelFormat, ExternalHyperlink,
} = require("docx");
const fs = require("fs");

const VERDE = "1D6B36";
const VERDE_CHIARO = "E8F2EA";
const GRIGIO = "5A6B60";
const LARGHEZZA = 9360; // 6.5" in DXA

const p = (testo, opz = {}) =>
  new Paragraph({ spacing: { after: 140 }, ...opz,
    children: Array.isArray(testo) ? testo : [new TextRun(testo)] });

const h1 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 160 } });
const h2 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_2,
  spacing: { before: 260, after: 120 } });

const punto = (testo) =>
  new Paragraph({ numbering: { reference: "punti", level: 0 }, spacing: { after: 100 },
    children: Array.isArray(testo) ? testo : [new TextRun(testo)] });

const g = (t) => new TextRun({ text: t, bold: true });
const mono = (t) => new TextRun({ text: t, font: "Consolas", size: 19 });

const link = (testo, url) =>
  new ExternalHyperlink({ link: url,
    children: [new TextRun({ text: testo, style: "Hyperlink" })] });

// --- tabelle ---------------------------------------------------------------

function cella(contenuto, { intestazione = false, larghezza } = {}) {
  // Le intestazioni arrivano sempre come stringa: costruire il TextRun qui e'
  // l'unico modo di darle grassetto e colore. Rileggere `.text` da un TextRun
  // gia' fatto non funziona — non lo espone, e le celle escono vuote.
  const figli = intestazione
    ? [new TextRun({ text: String(contenuto), bold: true, color: VERDE })]
    : Array.isArray(contenuto)
      ? contenuto
      : [new TextRun(String(contenuto))];
  return new TableCell({
    width: { size: larghezza, type: WidthType.DXA },
    shading: intestazione
      ? { type: ShadingType.CLEAR, fill: VERDE_CHIARO }
      : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [new Paragraph({ spacing: { after: 0 }, children: figli })],
  });
}

function tabella(intestazioni, righe) {
  const n = intestazioni.length;
  const colonne = Array(n).fill(Math.floor(LARGHEZZA / n));
  colonne[n - 1] = LARGHEZZA - colonne[0] * (n - 1);
  return new Table({
    columnWidths: colonne,
    width: { size: LARGHEZZA, type: WidthType.DXA },
    borders: {
      top:    { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
      left:   { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
      right:  { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
      insideVertical:   { style: BorderStyle.SINGLE, size: 4, color: "CFD8D2" },
    },
    rows: [
      new TableRow({ tableHeader: true,
        children: intestazioni.map((t, i) => cella(t, { intestazione: true, larghezza: colonne[i] })) }),
      ...righe.map((r) => new TableRow({
        children: r.map((c, i) => cella(c, { larghezza: colonne[i] })) })),
    ],
  });
}

function codice(righe) {
  return righe.map((riga, i) => new Paragraph({
    spacing: { before: i === 0 ? 60 : 0, after: i === righe.length - 1 ? 160 : 0 },
    shading: { type: ShadingType.CLEAR, fill: "F2F5F3" },
    indent: { left: 220 },
    children: [new TextRun({ text: riga || " ", font: "Consolas", size: 18 })],
  }));
}

function nota(titolo, testo) {
  return new Paragraph({
    spacing: { before: 120, after: 200 },
    indent: { left: 220 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: VERDE, space: 12 } },
    children: [
      new TextRun({ text: titolo + " ", bold: true, color: VERDE }),
      new TextRun({ text: testo, color: "333333" }),
    ],
  });
}

// --- documento -------------------------------------------------------------

const doc = new Document({
  creator: "FantaCalcio NuoVo",
  title: "Istruzioni per collaborare",
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 22, color: "1F2A24" },
                  paragraph: { spacing: { line: 300 } } },
      heading1: { run: { font: "Calibri", size: 34, bold: true, color: VERDE } },
      heading2: { run: { font: "Calibri", size: 26, bold: true, color: "1F2A24" } },
    },
  },
  numbering: {
    config: [{
      reference: "punti",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 400, hanging: 220 } } } }],
    }, {
      reference: "regole",
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 420, hanging: 300 } } } }],
    }],
  },
  sections: [{
    properties: { page: { margin: { top: 1100, bottom: 1100, left: 1100, right: 1100 } } },
    children: [
      new Paragraph({ spacing: { after: 60 },
        children: [new TextRun({ text: "FANTACALCIO NUOVO", bold: true, size: 18,
          color: VERDE, characterSpacing: 60 })] }),
      new Paragraph({ spacing: { after: 120 },
        children: [new TextRun({ text: "Istruzioni per collaborare", bold: true,
          size: 44, color: "1F2A24" })] }),
      new Paragraph({ spacing: { after: 320 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: VERDE, space: 8 } },
        children: [new TextRun({ text: "Si legge una volta sola: cosa accettare, come si modifica il progetto, cosa non fare mai.",
          color: GRIGIO, size: 21 })] }),

      p([g("Cos'e'. "), new TextRun("Il gestionale della nostra lega di fantacalcio manageriale. Contratti, monte anni, Salary Cap, budget, draft, scambi e competizioni stanno qui. Il gioco vero e proprio — voti, formazioni, risultati — resta su Leghe Fantacalcio: questo sito non lo sostituisce, gestisce tutto il resto.")]),
      p([g("Com'e' fatto. "), new TextRun("Python + Streamlit per l'interfaccia, Supabase (PostgreSQL) per i dati. Il codice sta su GitHub e il sito si aggiorna a ogni modifica accettata.")]),

      h1("I tre livelli di accesso"),
      p("Non ti serve tutto subito."),
      tabella(["Vuoi…", "Ti serve", "Come"], [
        ["Usare il sito da partecipante", "Solo l'indirizzo", "Apri il link e registrati"],
        ["Modificare il codice", "Account GitHub + invito", "Passi 1 e 2"],
        ["Gestire il deploy", "Lo stesso invito", "Passi 1 e 2"],
      ]),
      new Paragraph({ spacing: { before: 180, after: 140 },
        children: [new TextRun("Il secondo e il terzo arrivano "), g("insieme"),
          new TextRun(": su Streamlit Community Cloud i permessi dell'app non si impostano su Streamlit, li decide l'accesso in scrittura alla repository. Un invito solo copre entrambi.")] }),

      h1("1. Accetta l'invito su GitHub"),
      p([new TextRun("Marco ti aggiunge come collaboratore con permesso "), g("Write"),
         new TextRun(". Ti arriva una mail da GitHub, oppure trovi l'invito su "),
         link("github.com/notifications", "https://github.com/notifications"), new TextRun(".")]),
      p([new TextRun("Accettalo. Da quel momento vedi "), mono("Tiri6/fantacalcio-nuovo"),
         new TextRun(": e' privata, quindi prima dell'invito ti risponde 404 come se non esistesse.")]),
      nota("Perche' Write e non Admin.", "Write copre tutto il lavoro quotidiano: creare branch, pushare, aprire pull request, amministrare l'app su Streamlit. Admin servirebbe solo per cancellare la repository o renderla pubblica — e nella cronologia c'e' ancora una vecchia chiave Supabase, quindi pubblica non deve diventarlo."),

      h1("2. Collega Streamlit"),
      p([new TextRun("Vai su "), link("share.streamlit.io", "https://share.streamlit.io"),
         new TextRun(" e fai "), g("Sign in with GitHub"), new TextRun(".")]),
      p([new TextRun("Quando GitHub ti chiede l'autorizzazione, "),
         g("concedi anche l'accesso alle repository private"),
         new TextRun(". Se salti quel permesso Streamlit non vede il progetto e risponde «This repository does not exist»: un messaggio bugiardo, la repository esiste ed e' lui a non vederla.")]),
      p("Fatto questo, nella dashboard compare l'app. Non devi ripubblicarla: e' gia' online, tu ne diventi amministratore."),

      h1("3. Il ciclo di lavoro"),
      h2("Con Claude — il modo in cui lavoriamo"),
      p([new TextRun("Apri Claude Code sulla repository e di' direttamente cosa vuoi fare. Nessun preambolo: "),
         mono("CLAUDE.md"), new TextRun(" si carica da solo e rimanda a "), mono("MEMORIA.md"),
         new TextRun(", che dice a che punto siamo e quali trappole sono gia' costate tempo a qualcun altro.")]),
      p([new TextRun("Per capire il progetto per intero c'e' "), mono("PROGETTO.md"),
         new TextRun(": decisioni prese, regole applicate, com'e' fatto dentro e cosa manca.")]),
      p([new TextRun("A fine sessione, prima di pubblicare, lancia "), mono("/memoria"),
         new TextRun(": aggiorna la memoria per chi viene dopo. E' l'unica cosa che tiene allineate due persone che non lavorano nello stesso momento.")]),

      h2("A mano"),
      ...codice([
        "git clone https://github.com/Tiri6/fantacalcio-nuovo.git",
        "cd fantacalcio-nuovo",
        "",
        "python3 -m venv .venv",
        ".venv/bin/pip install -r requirements.txt -r requirements-dev.txt",
        "",
        ".venv/bin/pytest              # devono passare tutti",
        ".venv/bin/streamlit run app.py",
      ]),
      p([new TextRun("Senza credenziali parte in "), g("modalita' demo"),
         new TextRun(": dati inventati, database locale, nessun rischio di toccare quelli veri. E' il modo giusto per provare.")]),

      h2("In ogni caso: un branch a testa"),
      ...codice([
        "git pull                         # sempre, prima di iniziare",
        "git checkout -b luca/svincoli    # un branch per ogni cosa che fai",
        "# ... lavori ...",
        ".venv/bin/pytest && .venv/bin/ruff check .",
        "git push -u origin luca/svincoli",
      ]),
      p([new TextRun("Poi su GitHub apri una "), g("pull request"), new TextRun(" verso "),
         mono("main"), new TextRun(". Marco la guarda e la unisce; un paio di minuti dopo il sito e' aggiornato. Se lavorate entrambi direttamente su "),
         mono("main"), new TextRun(" vi pestate i piedi.")]),

      h1("Le sei regole"),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 120 },
        children: [g("Mai una chiave dentro un file pubblicato. "),
          new TextRun("Le credenziali di Supabase vanno solo nei secret di Streamlit, o nel file locale "),
          mono(".streamlit/secrets.toml"),
          new TextRun(" che git ignora. Un test fallisce apposta se ci finisce una chiave vera: se si accende, non aggirarlo.")] }),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 120 },
        children: [g("Nessun numero del regolamento sparso nel codice. "),
          new TextRun("Monte anni 66, Salary Cap 100M, rosa 30–33: stanno tutti in "),
          mono("ParametriLega"),
          new TextRun(" e solo li'. La lega cambia le regole per votazione, e devono restare modificabili in un punto solo.")] }),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 120 },
        children: [g("La logica non importa Streamlit. "),
          new TextRun("Solo "), mono("ui.py"), new TextRun(", "), mono("schermate.py"),
          new TextRun(" e i file in "), mono("viste/"),
          new TextRun(". E' quello che tiene i test veloci e la logica riutilizzabile.")] }),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 120 },
        children: [g("Prima di pubblicare, i test devono passare. "),
          mono("pytest"), new TextRun(" e "), mono("ruff check ."),
          new TextRun(": sono la rete che permette a due persone di toccare lo stesso codice senza rompersi a vicenda.")] }),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 120 },
        children: [g("Mai due sessioni Claude sullo stesso branch nello stesso momento.")] }),
      new Paragraph({ numbering: { reference: "regole", level: 0 }, spacing: { after: 200 },
        children: [g("Fuori dalla repository restano "),
          new TextRun("il PDF del regolamento, il database con i dati veri e ogni credenziale. Anche se la repository e' privata.")] }),

      h1("Tre cose che ti risparmiano un pomeriggio"),
      punto([g("Provare in locale non basta. "),
        new TextRun("SQLite (la demo) e PostgREST (Supabase) rispondono diversamente quando una tabella e' vuota: il primo da' le colonne, il secondo no. Del codice che funziona in locale puo' rompersi in produzione. C'e' un finto backend apposta in "),
        mono("tests/test_backend_vuoto.py"), new TextRun(".")]),
      punto([g("Nelle cache di Streamlit vanno solo DataFrame, "),
        new TextRun("mai oggetti di dominio: un oggetto in cache conserva la forma che aveva quando ci e' entrato, e dopo un aggiornamento rompe l'app. C'e' un test che lo verifica.")]),
      punto([g("Se il sito da' un errore strano dopo un aggiornamento, "),
        new TextRun("prima di cercare il bug riavvialo: menu ⋮ → Reboot app. Streamlit ricarica app.py e le viste, ma non i moduli gia' importati, e per un po' gira codice misto.")]),

      h1("Se qualcosa va storto"),
      tabella(["Sintomo", "Cos'e' successo"], [
        ["GitHub risponde 404 sulla repository", "Invito non ancora accettato"],
        ["«This repository does not exist» su Streamlit", "Manca il permesso sulle repository private (passo 2)"],
        ["«Il database non ha le tabelle»", "Su Supabase non e' stato eseguito db/schema.sql"],
        ["L'app non scrive, o il login non va", "Nei secret c'e' la chiave anon invece della service_role"],
        ["«Il sito sta ancora usando il codice precedente»", "Riavvia l'app: menu ⋮ → Reboot app"],
        ["git push rifiutato", "Qualcuno ha pubblicato prima di te: git pull --rebase"],
        ["La sidebar dice «Modalita' demo»", "Nessuna credenziale. In locale e' normale"],
      ]),

      h1("Dove trovare il resto"),
      p("Nella repository, e si legge quando serve."),
      tabella(["File", "A cosa serve"], [
        ["PROGETTO.md", "Tutto il progetto: decisioni, regole, architettura, cosa manca"],
        ["CLAUDE.md", "Le regole per chi scrive codice, e dove mettere le mani"],
        ["MEMORIA.md", "A che punto siamo e le trappole gia' pagate"],
        ["README.md", "Come si usa il sito, schermata per schermata"],
        ["PUNTI_APERTI.md", "Le ambiguita' del regolamento ancora da sciogliere"],
      ]),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("FantaCalcio-NuoVo-istruzioni-collaboratore.docx", buf);
  console.log("scritto");
});
