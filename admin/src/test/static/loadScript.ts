// Carica uno script statico del CMS (app/static/cms) in una pagina jsdom tutta sua:
// gli ascoltatori globali non passano da un test all'altro.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { JSDOM, type DOMWindow } from "jsdom";

// I test girano dalla cartella admin/ (npm run test).
const STATIC = resolve(process.cwd(), "..", "app", "static", "cms");
export const ORIGIN = "https://sito.test";

export function source(name: string): string {
  return readFileSync(resolve(STATIC, name), "utf8");
}

export interface Page {
  window: DOMWindow;
  document: Document;
}

interface Options {
  body: string;
  script: string;
  attributes?: Record<string, string>;
  path?: string;
  parent?: DOMWindow;
  cookie?: string;
}

/** Pagina con lo script in fondo al body, eseguito come un vero <script> (currentScript). */
export function pageWith({ body, script, attributes = {}, path = "/", parent, cookie }: Options): Page {
  const attrs = Object.entries(attributes)
    .map(([key, value]) => ` ${key}="${value}"`)
    .join("");
  const html = `<!doctype html><html><head></head><body>${body}<script${attrs}>${source(script)}</script></body></html>`;
  const dom = new JSDOM(html, {
    url: ORIGIN + path,
    runScripts: "dangerously",
    pretendToBeVisual: true,
    beforeParse(window) {
      if (parent) Object.defineProperty(window, "parent", { value: parent });
      if (cookie) window.document.cookie = cookie;
      window.HTMLElement.prototype.scrollIntoView = function scrollIntoView() {};
    },
  });
  return { window: dom.window, document: dom.window.document };
}

/** Una finestra "pannello" della stessa origine, che registra i messaggi ricevuti. */
export function panelWindow(): { window: DOMWindow; messages: unknown[] } {
  const dom = new JSDOM("<!doctype html><title>Pannello</title>", { url: ORIGIN + "/admin/" });
  const messages: unknown[] = [];
  dom.window.addEventListener("message", (event) => messages.push(event.data));
  return { window: dom.window, messages };
}

export const tick = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 10));
