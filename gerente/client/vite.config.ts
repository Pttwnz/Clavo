import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [],
      manifest: {
        name: "Gerente Clavo",
        short_name: "Gerente",
        description: "Pedidos, tareas y avisos para gerencia",
        theme_color: "#1a1a2e",
        background_color: "#1a1a2e",
        display: "standalone",
        start_url: "/",
        icons: [],
      },
    }),
  ],
  server: {
    port: 5178,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:37893",
        changeOrigin: true,
      },
    },
  },
});
