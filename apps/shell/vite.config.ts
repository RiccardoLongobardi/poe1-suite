import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward all API calls to the FastAPI backend
      "/fob": "http://127.0.0.1:8765",
      "/pricing": "http://127.0.0.1:8765",
      "/builds": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
    },
  },
});
