/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In sviluppo Vite serve il pannello su 127.0.0.1:5173/admin/ e passa a Flask (porta 5000)
// tutto ciò che non è del pannello: API, anteprima, file del tema e media (D-87).
const FLASK = "http://127.0.0.1:5000";
const PROXIED = ["/api", "/_preview", "/static", "/assets", "/_vars.css", "/media"];

export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(PROXIED.map((path) => [path, { target: FLASK, changeOrigin: false }])),
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    assetsInlineLimit: 0, // niente data: (CSP del pannello, D-88)
    modulePreload: { polyfill: false }, // il polyfill è uno script inline
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/test/**", "src/**/*.test.{ts,tsx}"],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
