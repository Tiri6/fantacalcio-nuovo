import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./stile.css";
import { avviaTema } from "./tema";

// Prima del primo disegno: altrimenti la pagina comparirebbe scura e
// diventerebbe chiara un istante dopo, che e' il difetto piu' visibile di
// un tema fatto male.
avviaTema();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
