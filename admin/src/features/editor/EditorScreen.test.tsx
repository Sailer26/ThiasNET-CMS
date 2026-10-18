import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import { catalog } from "../../test/catalog";
import { fakeApi, ME, node, signedIn, type FakeApi } from "../../test/fakeApi";
import { SAVE_DELAY_MS } from "./model/autosave";
import type { PageDocument } from "./model/document";
import { transport } from "./preview/transport";

const UID = "b".repeat(32);

function draftDoc(): PageDocument {
  return {
    title: "Chi siamo",
    layout: "page",
    seo: {},
    zones: {
      main: [
        { uid: UID, type: "heading", variant: null, data: { text: "Benvenuti", level: 2 } },
        { uid: "c".repeat(32), type: "cta", variant: null, data: { title: "Scrivici" } },
      ],
      sidebar: [],
    },
  };
}

function open(options: { status?: "draft" | "published"; me?: typeof ME; version?: number } = {}): {
  api: FakeApi;
  user: ReturnType<typeof userEvent.setup>;
} {
  const api = fakeApi();
  signedIn(api, options.me ?? ME);
  api.on("GET", "/pages/7", { data: node("Chi siamo", { id: 7, path: "/chi-siamo", status: options.status ?? "published", version: 4 }) });
  api.on("GET", "/pages/7/draft", { data: { version: options.version ?? 2, data: draftDoc(), from_published: false, updated_at: null } });
  api.on("GET", "/blocks", { data: catalog() });
  api.on("GET", "/pages/tree", { data: [node("Contatti", { path: "/contatti" })], meta: { truncated: false } });
  api.on("PUT", "/pages/7/draft", (call) => ({ data: { version: ((call.body as { version: number }).version ?? 0) + 1 } }));
  render(<App />);
  return { api, user: userEvent.setup({ advanceTimers: vi.advanceTimersByTime }) };
}

async function ready() {
  return screen.findByLabelText("Titolo della pagina");
}

async function wait(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

describe("editor della pagina", () => {
  let submits: { target: string; action: string; fields: Record<string, string> }[];

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    setCsrfToken("tok");
    window.history.replaceState(null, "", "/admin/pagine/7");
    submits = [];
    vi.spyOn(transport, "submit").mockImplementation((target, action, fields) => {
      submits.push({ target, action, fields });
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("carica la pagina, le zone con le etichette e i blocchi", async () => {
    open();
    expect(await ready()).toHaveValue("Chi siamo");
    expect(screen.getByRole("heading", { name: "Contenuto principale" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Barra laterale" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Titolo.*Benvenuti/ })).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("Tutto salvato")).toBeInTheDocument();
  });

  test("scrivere salva dopo la pausa, con la versione; poi Salvato alle", async () => {
    const { api, user } = open();
    const title = await ready();
    await user.clear(title);
    await user.type(title, "Chi siamo noi");
    expect(api.callsTo("PUT", "/pages/7/draft")).toHaveLength(0);
    expect(screen.getByText("Sto salvando…")).toBeInTheDocument();
    await wait(SAVE_DELAY_MS + 10);
    await waitFor(() => expect(api.callsTo("PUT", "/pages/7/draft")).toHaveLength(1));
    const body = api.callsTo("PUT", "/pages/7/draft")[0]!.body as PageDocument & { version: number };
    expect(body.version).toBe(2);
    expect(body.title).toBe("Chi siamo noi");
    expect(await screen.findByText(/^Salvato alle \d\d:\d\d$/)).toBeInTheDocument();
  });

  test("annulla e ripristina, con i pulsanti e con Ctrl+Z", async () => {
    const { user } = open();
    const title = await ready();
    await user.type(title, "!");
    await user.click(screen.getByRole("button", { name: "Annulla" }));
    expect(title).toHaveValue("Chi siamo");
    await user.click(screen.getByRole("button", { name: "Ripristina" }));
    expect(title).toHaveValue("Chi siamo!");
    title.focus();
    await user.keyboard("{Control>}z{/Control}");
    expect(title).toHaveValue("Chi siamo");
  });

  test("aggiungere un blocco dai riquadri con disegno e frase; eliminarlo con Annulla", async () => {
    const { user } = open();
    await ready();
    const main = screen.getByRole("region", { name: "Contenuto principale" });
    await user.click(within(main).getByRole("button", { name: "Aggiungi blocco" }));
    const dialog = screen.getByRole("dialog", { name: 'Aggiungi un blocco in "Contenuto principale"' });
    expect(within(dialog).queryByRole("button", { name: /Apertura/ })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: /Citazione.*frase in evidenza/ }));
    expect(screen.getByLabelText(/^Citazione/)).toBeInTheDocument(); // il nuovo blocco è aperto
    const row = screen.getByRole("group", { name: 'Azioni per il blocco "Citazione"' });
    await user.click(within(row).getByRole("button", { name: "Elimina" }));
    expect(screen.queryByRole("group", { name: 'Azioni per il blocco "Citazione"' })).not.toBeInTheDocument();
    const notice = screen.getByText('Blocco "Citazione" eliminato.').closest(".notice") as HTMLElement;
    await user.click(within(notice).getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("group", { name: 'Azioni per il blocco "Citazione"' })).toBeInTheDocument();
  });

  test("su, giù, duplica, sposta in un'altra zona", async () => {
    const { user } = open();
    await ready();
    const cta = () => screen.getAllByRole("group", { name: 'Azioni per il blocco "Invito all\'azione"' });
    await user.click(within(cta()[0]!).getByRole("button", { name: "Su" }));
    const rows = within(screen.getByRole("region", { name: "Contenuto principale" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Invito all'azione");
    await user.click(within(cta()[0]!).getByRole("button", { name: "Duplica" }));
    expect(cta()).toHaveLength(2);
    await user.click(within(cta()[0]!).getByRole("button", { name: "Sposta in…" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("combobox")).toHaveDisplayValue("Barra laterale");
    await user.click(within(dialog).getByRole("button", { name: "Sposta" }));
    const sidebar = screen.getByRole("region", { name: "Barra laterale" });
    expect(within(sidebar).getByRole("group", { name: 'Azioni per il blocco "Invito all\'azione"' })).toBeInTheDocument();
  });

  test("modulo dal suo schema: etichette, scelte, link con le pagine del sito", async () => {
    const { user } = open();
    await ready();
    await user.click(screen.getByRole("button", { name: /^Invito all'azione/ }));
    expect(screen.getByLabelText(/Testo del pulsante/)).toBeInTheDocument();
    const link = screen.getByLabelText(/Link del pulsante/);
    await user.type(link, "www.comune.ch");
    await user.tab();
    expect(link).toHaveValue("https://www.comune.ch");
    await user.click(screen.getByRole("button", { name: /^Titolo.*Benvenuti/ }));
    await user.click(screen.getByRole("radio", { name: "Piccolo" }));
    expect(screen.getByRole("radio", { name: "Piccolo" })).toBeChecked();
  });

  test("campo scritto a metà: avviso accanto e al server l'ultimo valore valido", async () => {
    const { api, user } = open();
    await ready();
    await user.click(screen.getByRole("button", { name: /^Invito all'azione/ }));
    await user.type(screen.getByLabelText(/Link del pulsante/), "htt");
    expect(screen.getByText(/Non ancora salvato: controlla il formato/)).toBeInTheDocument();
    await wait(SAVE_DELAY_MS + 10);
    await waitFor(() => expect(api.callsTo("PUT", "/pages/7/draft")).toHaveLength(1));
    const sent = api.callsTo("PUT", "/pages/7/draft")[0]!.body as PageDocument;
    expect(sent.zones.main![1]!.data).toEqual({ title: "Scrivici" });
  });

  test("cambio del tipo di pagina: elenca i blocchi che non hanno posto", async () => {
    const { user } = open();
    await ready();
    const main = screen.getByRole("region", { name: "Contenuto principale" });
    await user.click(within(main).getByRole("button", { name: "Aggiungi blocco" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: /Contatti/ }));
    await user.selectOptions(screen.getByLabelText("Tipo di pagina"), "full");
    const dialog = screen.getByRole("dialog", { name: "Cambiare il tipo di pagina?" });
    expect(dialog).toHaveTextContent("Contatti");
    await user.click(within(dialog).getByRole("button", { name: "Cambia comunque" }));
    expect(screen.queryByRole("heading", { name: "Barra laterale" })).not.toBeInTheDocument();
  });

  test("SEO: titolo e descrizione con anteprima di Google", async () => {
    const { user } = open();
    await ready();
    await user.click(screen.getByText("Motori di ricerca"));
    await user.type(screen.getByLabelText("Descrizione per Google"), "Chi siamo e cosa facciamo");
    expect(screen.getByText("https://www.prova.ch/chi-siamo")).toBeInTheDocument();
    expect(screen.getByText("Chi siamo e cosa facciamo", { selector: ".google__text" })).toBeInTheDocument();
  });

  test("pubblica: salva, chiede conferma con l'indirizzo, pubblica la bozza", async () => {
    const { api, user } = open();
    api.on("POST", "/pages/7/publish", { data: node("Chi siamo", { id: 7, status: "published", path: "/chi-siamo" }) });
    const title = await ready();
    await user.type(title, "!");
    await user.click(screen.getByRole("button", { name: "Pubblica" }));
    const dialog = await screen.findByRole("dialog", { name: "Pubblicare la pagina?" });
    expect(dialog).toHaveTextContent("La pagina andrà online su https://www.prova.ch/chi-siamo. Pubblico?");
    expect(api.callsTo("PUT", "/pages/7/draft")).toHaveLength(1); // salvata prima di chiedere
    await user.click(within(dialog).getByRole("button", { name: "Pubblica" }));
    expect(await screen.findByText("Pagina pubblicata.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/pages/7/publish")[0]!.body).toEqual({ draft_version: 3 });
  });

  test("errori di pubblicazione elencati con Vai al campo", async () => {
    const { api, user } = open({ version: 5 });
    api.on("POST", "/pages/7/publish", {
      status: 422,
      error: {
        code: "invalid_content",
        message: "Contenuto non valido",
        details: [
          { path: "zones/main/1/data/url", code: "required", message: "Campo obbligatorio" },
          { path: "title", code: "invalid_title", message: "Il titolo è obbligatorio" },
        ],
      },
    });
    await ready();
    await user.click(screen.getByRole("button", { name: "Pubblica" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Pubblica" }));
    const list = await screen.findByRole("alert");
    expect(list).toHaveTextContent("Invito all'azione n. 2 · Campo obbligatorio");
    await user.click(within(list).getAllByRole("button", { name: "Vai al campo" })[0]!);
    await wait(20);
    expect(screen.getByLabelText(/Link del pulsante/)).toHaveFocus();
  });

  test("senza permesso di pubblicare: niente Pubblica, una spiegazione", async () => {
    open({ me: { ...ME, role: "editor", can_publish: false, permissions: ["content.edit", "profile"] } });
    await ready();
    expect(screen.queryByRole("button", { name: "Pubblica" })).not.toBeInTheDocument();
    expect(screen.getByText("Per pubblicare chiedi a chi può farlo.")).toBeInTheDocument();
  });

  test("409 al salvataggio: scelta tra la sua versione e la mia", async () => {
    const { api, user } = open();
    api.on(
      "PUT",
      "/pages/7/draft",
      { status: 409, error: { code: "version_conflict", message: "Conflitto", details: { updated_by_name: "luca@example.ch", updated_at: null } } },
      { data: { version: 10 } },
    );
    const title = await ready();
    await user.type(title, " mio");
    await wait(SAVE_DELAY_MS + 10);
    const dialog = await screen.findByRole("dialog", { name: "Qualcun altro ha modificato questa pagina" });
    expect(dialog).toHaveTextContent("Nel frattempo luca@example.ch ha salvato questa pagina");
    api.on("GET", "/pages/7/draft", { data: { version: 9, data: draftDoc(), from_published: false, updated_at: null } });
    await user.click(within(dialog).getByRole("button", { name: "Tieni la mia" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const last = api.callsTo("PUT", "/pages/7/draft").at(-1)!.body as PageDocument & { version: number };
    expect([last.version, last.title]).toEqual([9, "Chi siamo mio"]);
  });

  test("Duplica non supera il massimo della zona (homepage: una sola apertura)", async () => {
    const api = fakeApi();
    signedIn(api);
    const home: PageDocument = {
      title: "Home",
      layout: "home",
      seo: {},
      zones: { hero: [{ uid: UID, type: "hero", variant: null, data: { title: "Ciao" } }], main: [] },
    };
    api.on("GET", "/pages/7", { data: node("Home", { id: 7, path: "/", is_home: true }) });
    api.on("GET", "/pages/7/draft", { data: { version: 1, data: home, from_published: false, updated_at: null } });
    api.on("GET", "/blocks", { data: catalog() });
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    render(<App />);
    const row = await screen.findByRole("group", { name: 'Azioni per il blocco "Apertura"' });
    expect(within(row).getByRole("button", { name: "Duplica" })).toBeDisabled();
  });

  test("Ctrl+Z dentro una finestra non annulla il documento dietro", async () => {
    const { user } = open();
    const title = await ready();
    await user.type(title, "!");
    await user.click(screen.getByRole("button", { name: /^Invito all'azione/ }));
    await user.click(within(screen.getByRole("group", { name: "Azioni per il blocco \"Invito all'azione\"" })).getByRole("button", { name: "Sposta in…" }));
    const dialog = screen.getByRole("dialog");
    within(dialog).getByRole("combobox").focus();
    await user.keyboard("{Control>}z{/Control}");
    expect(title).toHaveValue("Chi siamo!");
  });

  test("ritira dal sito con conferma e la versione della pagina", async () => {
    const { api, user } = open();
    api.on("POST", "/pages/7/unpublish", { data: node("Chi siamo", { id: 7, status: "draft", path: "/chi-siamo", version: 5 }) });
    await ready();
    await user.click(screen.getByRole("button", { name: "Ritira dal sito" }));
    const dialog = screen.getByRole("dialog", { name: "Ritirare la pagina dal sito?" });
    expect(within(dialog).getByRole("button", { name: "Annulla" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Ritira" }));
    expect(await screen.findByText("Pagina ritirata dal sito.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/pages/7/unpublish")[0]!.body).toEqual({ version: 4 });
    expect(screen.getByText("Bozza")).toBeInTheDocument();
  });

  test("scarta le modifiche: torna alla versione online", async () => {
    const { api, user } = open();
    api.on("DELETE", "/pages/7/draft", { data: { version: 0 } });
    const title = await ready();
    await user.type(title, " cambiato");
    await user.click(screen.getByRole("button", { name: "Scarta le modifiche" }));
    api.on("GET", "/pages/7/draft", { data: { version: 0, data: draftDoc(), from_published: true, updated_at: null } });
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Scarta" }));
    expect(await screen.findByText("Modifiche scartate.")).toBeInTheDocument();
    expect(title).toHaveValue("Chi siamo");
    expect(api.callsTo("DELETE", "/pages/7/draft")[0]!.body).toEqual({ version: 3 });
  });

  test("sul tablet si passa da Modifica ad Anteprima", async () => {
    const { user } = open();
    await ready();
    const editor = document.querySelector(".editor")!;
    expect(editor).toHaveClass("editor--edit");
    await user.click(screen.getByRole("button", { name: "Anteprima" }));
    expect(editor).toHaveClass("editor--preview");
    expect(screen.getByRole("button", { name: "Anteprima" })).toHaveAttribute("aria-pressed", "true");
  });

  test("anteprima: form con il documento verso un iframe nuovo; clic nell'anteprima seleziona", async () => {
    open();
    await ready();
    await waitFor(() => expect(submits).toHaveLength(1));
    const [first] = submits;
    expect(first!.action).toBe("/_preview/7");
    expect(first!.fields.csrf_token).toBe("tok-1"); // il token preso all'avvio
    expect(JSON.parse(first!.fields.document!).title).toBe("Chi siamo");
    const frame = document.querySelector<HTMLIFrameElement>(`iframe[name="${first!.target}"]`)!;
    expect(frame).toHaveAttribute("title", "Anteprima della pagina");
    const ready_ = new MessageEvent("message", { data: { type: "cms:ready", uid: null }, origin: window.location.origin, source: frame.contentWindow });
    await act(async () => {
      window.dispatchEvent(ready_);
    });
    await act(async () => {
      window.dispatchEvent(new MessageEvent("message", { data: { type: "cms:block-click", uid: UID }, origin: "https://altro.test", source: frame.contentWindow }));
    });
    expect(screen.queryByLabelText(/Testo del titolo/)).not.toBeInTheDocument();
    await act(async () => {
      window.dispatchEvent(new MessageEvent("message", { data: { type: "cms:block-click", uid: UID }, origin: window.location.origin, source: frame.contentWindow }));
    });
    expect(await screen.findByLabelText(/Testo del titolo/)).toBeInTheDocument();
  });
});
