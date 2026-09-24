import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    setupFiles: ["./src/testing/setup.js"],
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
