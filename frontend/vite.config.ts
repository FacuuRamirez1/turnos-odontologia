import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // En Docker `localhost` es el propio contenedor web: el proxy debe apuntar
        // al servicio `api`. Fuera de Docker: VITE_PROXY_TARGET=http://localhost:8000.
        target: process.env.VITE_PROXY_TARGET ?? "http://api:8000",
        changeOrigin: true,
      },
    },
  },
});
