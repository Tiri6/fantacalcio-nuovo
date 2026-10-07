import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // In sviluppo React sta su 5173 e l'API su 8000. Il proxy fa sembrare
    // che siano lo stesso dominio, come saranno in produzione: cosi' il
    // cookie di sessione funziona qui esattamente come funzionera' li'.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
