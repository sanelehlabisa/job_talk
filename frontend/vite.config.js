import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [process.env.APP_DOMAIN || "localhost"],
    proxy: {
      "/api": { target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000" },
    },
    watch: {
      usePolling: process.env.VITE_USE_POLLING === "true",
      interval: 300,
    },
  },
});
