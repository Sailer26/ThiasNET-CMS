import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import type { PageNode } from "../../api/types";
import { fakeApi, ME, node, signedIn, type FakeApi } from "../../test/fakeApi";

function site(): PageNode[] {
  const home = node("Home", { id: 1, is_home: true, slug: "", path: "/", status: "published" });
  const child = node("Orari", { id: 4, parent_id: 2, path: "/servizi/orari", status: "published", has_draft: true });
  const servizi = node("Servizi", { id: 2, path: "/servizi", status: "published", children: [child] });
  const contatti = node("Contatti", { id: 3, path: "/contatti", publish_at: "2026-11-01T08:00:00+00:00", status: "scheduled" });
  return [home, servizi, contatti];
}

function setup(nodes: PageNode[] = site(), me = ME): { api: FakeApi; user: ReturnType<typeof userEvent.setup> } {
  const api = fakeApi();
  signedIn(api, me);
  api.on("GET", "/pages/tree", { data: nodes, meta: { truncated: false } });
  render(<App />);
  return { api, user: userEvent.setup() };
}

const row = (title: string) => screen.getByRole("group", { name: `Azioni per "${title}"` });

describe("albero delle pagine", () => {
  beforeEach(() => {
    setCsrfToken("tok");
    window.history.replaceState(null, "", "/admin/pagine");
  });

  test("mostra pagine, sottopagine e stati", async () => {
    setup();
    expect(await screen.findByRole("link", { name: "Servizi" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Orari" })).toHaveAttribute("href", "/admin/pagine/4");
    expect(screen.getByText("/servizi/orari")).toBeInTheDocument();
    expect(screen.getByText("Modifiche non pubblicate")).toBeInTheDocument();
    expect(screen.getByText("Programmata")).toBeInTheDocument();
    expect(within(row("Home")).queryByRole("button", { name: "Cestina" })).not.toBeInTheDocument();
    expect(within(row("Servizi")).getByRole("link", { name: "Vedi online" })).toHaveAttribute(
      "href",
      "https://www.prova.ch/servizi",
    );
    expect(within(row("Servizi")).getByRole("link", { name: "Anteprima" })).toHaveAttribute("href", "/_preview/2");
    // sopra c'è la homepage; aria-disabled: il pulsante resta raggiungibile da tastiera
    expect(within(row("Servizi")).getByRole("button", { name: "Su" })).toHaveAttribute("aria-disabled", "true");
    expect(within(row("Contatti")).getByRole("button", { name: "Giù" })).toHaveAttribute("aria-disabled", "true");
  });

  test("su e giù mandano tutte le sorelle nel nuovo ordine", async () => {
    const { api, user } = setup();
    api.on("POST", "/pages/reorder", { data: { ids: [] } });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Contatti"' })).getByRole("button", { name: "Su" }));
    await waitFor(() =>
      expect(api.callsTo("POST", "/pages/reorder")[0]?.body).toEqual({ parent_id: null, locale: "it", ids: [1, 3, 2] }),
    );
    expect(await screen.findByText('"Contatti" è stata spostata.')).toBeInTheDocument();
  });

  test("elenco cambiato nel frattempo: avviso e ricarica", async () => {
    const { api, user } = setup();
    api.on("POST", "/pages/reorder", {
      status: 422,
      error: { code: "reorder_mismatch", message: "L'elenco non corrisponde alle pagine: ricarica e riprova" },
    });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Servizi"' })).getByRole("button", { name: "Giù" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("L'elenco non corrisponde");
    await waitFor(() => expect(api.callsTo("GET", "/pages/tree")).toHaveLength(2));
  });

  test("errore qualsiasi nel riordino: solo l'avviso", async () => {
    const { api, user } = setup();
    api.on("POST", "/pages/reorder", { status: 403, error: { code: "forbidden", message: "Non hai i permessi" } });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Servizi"' })).getByRole("button", { name: "Giù" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Non hai i permessi");
  });

  test("nuova pagina: solo titolo e posizione, col layout standard", async () => {
    const { api, user } = setup();
    api.on("POST", "/pages", { status: 201, data: node("Eventi") });
    await user.click(await screen.findByRole("button", { name: "Nuova pagina" }));
    const dialog = screen.getByRole("dialog", { name: "Nuova pagina" });
    expect(within(dialog).getByRole("button", { name: "Crea" })).toBeDisabled();
    await user.type(within(dialog).getByLabelText("Titolo della pagina"), "Eventi");
    await user.selectOptions(within(dialog).getByLabelText("Dove la metto?"), "2");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.callsTo("POST", "/pages")[0]?.body).toEqual({ title: "Eventi", locale: "it", parent_id: 2, layout: "page" });
    expect(screen.getByText('"Eventi" è stata creata.')).toBeInTheDocument();
  });

  test("sito vuoto: crea la homepage", async () => {
    const { api, user } = setup([]);
    api.on("POST", "/pages", { status: 201, data: node("Home", { is_home: true }) });
    expect(screen.queryByRole("button", { name: "Nuova pagina" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Crea la homepage" }));
    const dialog = screen.getByRole("dialog", { name: "Crea la homepage" });
    expect(within(dialog).getByLabelText("Titolo della pagina")).toHaveValue("Home");
    expect(within(dialog).queryByLabelText("Dove la metto?")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    await waitFor(() =>
      expect(api.callsTo("POST", "/pages")[0]?.body).toEqual({ title: "Home", locale: "it", parent_id: null, layout: "home", slug: "" }),
    );
  });

  test("errore del server resta nella finestra; Annulla la chiude", async () => {
    const { api, user } = setup();
    api.on("POST", "/pages", { status: 409, error: { code: "slug_taken", message: "Esiste già una pagina con questo indirizzo" } });
    await user.click(await screen.findByRole("button", { name: "Nuova pagina" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Titolo della pagina"), "Servizi");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Esiste già una pagina");
    await user.click(within(dialog).getByRole("button", { name: "Annulla" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("sposta in: solo destinazioni valide, con la versione", async () => {
    const { api, user } = setup();
    api.on("PATCH", "/pages/3", { data: node("Contatti") });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Contatti"' })).getByRole("button", { name: "Sposta in…" }));
    const dialog = screen.getByRole("dialog", { name: 'Sposta "Contatti"' });
    const options = within(dialog).getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(['Sotto "Servizi"', '— Sotto "Orari"']);
    await user.selectOptions(within(dialog).getByLabelText("Nuova posizione"), "4");
    await user.click(within(dialog).getByRole("button", { name: "Sposta" }));
    await waitFor(() => expect(api.callsTo("PATCH", "/pages/3")[0]?.body).toEqual({ version: 1, parent_id: 4 }));
  });

  test("conflitto: chi ha salvato, finestra chiusa, elenco ricaricato", async () => {
    const { api, user } = setup();
    api.on("PATCH", "/pages/4", {
      status: 409,
      error: {
        code: "version_conflict",
        message: "Qualcun altro ha modificato questa pagina",
        details: { current_version: 2, updated_by: 9, updated_by_name: "luca@example.ch", updated_at: null },
      },
    });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Orari"' })).getByRole("button", { name: "Indirizzo…" }));
    const dialog = screen.getByRole("dialog", { name: 'Indirizzo di "Orari"' });
    const input = within(dialog).getByLabelText("Ultima parte dell'indirizzo");
    expect(within(dialog).getByRole("button", { name: "Salva indirizzo" })).toBeDisabled();
    await user.clear(input);
    await user.type(input, "Orari-Estate");
    expect(within(dialog).getByText("/servizi/orari-estate")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Salva indirizzo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Nel frattempo luca@example.ch ha modificato questa pagina. Ho ricaricato l'elenco",
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.callsTo("PATCH", "/pages/4")[0]?.body).toEqual({ version: 1, slug: "orari-estate" });
    await waitFor(() => expect(api.callsTo("GET", "/pages/tree")).toHaveLength(2));
  });

  test("cestina con conferma; senza permesso di pubblicare le pagine online restano", async () => {
    const { api, user } = setup();
    api.on("DELETE", "/pages/4", { data: node("Orari") });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Orari"' })).getByRole("button", { name: "Cestina" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Potrai recuperarla dal Cestino");
    await user.click(within(dialog).getByRole("button", { name: "Cestina" }));
    await waitFor(() => expect(api.callsTo("DELETE", "/pages/4")[0]?.body).toEqual({ version: 1 }));
    expect(await screen.findByText('"Orari" è nel cestino.')).toBeInTheDocument();
  });

  test("editor senza permesso di pubblicare: Cestina spiega perché non si può", async () => {
    const { api, user } = setup(site(), { ...ME, role: "editor", can_publish: false, permissions: ["content.edit", "profile"] });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Servizi"' })).getByRole("button", { name: "Cestina" }));
    expect(await screen.findByText(/serve il permesso di pubblicare/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.callsTo("DELETE", "/pages/2")).toHaveLength(0);
  });

  test("un secondo clic mentre il primo spostamento è in corso non parte", async () => {
    const { api, user } = setup();
    let finish: () => void = () => undefined;
    api.on("POST", "/pages/reorder", { data: { ids: [] } });
    const original = globalThis.fetch;
    vi.stubGlobal("fetch", (input: string, init?: RequestInit) =>
      String(input).includes("/pages/reorder")
        ? new Promise<Response>((resolve) => {
            finish = () => void original(input, init).then(resolve);
          })
        : original(input, init),
    );
    const contatti = within(await screen.findByRole("group", { name: 'Azioni per "Contatti"' }));
    await user.click(contatti.getByRole("button", { name: "Su" }));
    await user.click(within(row("Servizi")).getByRole("button", { name: "Giù" }));
    expect(within(row("Servizi")).getByRole("button", { name: "Giù" })).toHaveAttribute("aria-disabled", "true");
    finish();
    await screen.findByText('"Contatti" è stata spostata.');
    expect(api.callsTo("POST", "/pages/reorder")).toHaveLength(1);
  });

  test("pagina sparita nel frattempo: finestra chiusa, avviso, elenco ricaricato", async () => {
    const { api, user } = setup();
    api.on("PATCH", "/pages/3", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Contatti"' })).getByRole("button", { name: "Sposta in…" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Sposta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Pagina non trovata");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(api.callsTo("GET", "/pages/tree")).toHaveLength(2));
  });

  test("nelle conferme il focus parte da Annulla", async () => {
    const { user } = setup();
    await user.click(within(await screen.findByRole("group", { name: 'Azioni per "Contatti"' })).getByRole("button", { name: "Cestina" }));
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Annulla" })).toHaveFocus();
  });

  test("albero incompleto: niente modifiche, solo consultazione", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: site().slice(1), meta: { truncated: true } });
    render(<App />);
    expect(await screen.findByText("Ci sono molte pagine: ne mostro solo una parte.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Crea la homepage" })).not.toBeInTheDocument();
    expect(within(row("Servizi")).getByRole("button", { name: "Sposta in…" })).toHaveAttribute("aria-disabled", "true");
  });

  test("elenco troncato ed errore di caricamento", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { status: 500, error: { code: "server_error", message: "Errore del server" } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Errore del server");
  });

  test("avviso quando l'albero è troncato; il titolo apre la schermata dell'editor", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: site(), meta: { truncated: true } });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Ci sono molte pagine: ne mostro solo una parte.")).toBeInTheDocument();
    api.on("GET", "/pages/2", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    api.on("GET", "/pages/2/draft", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    api.on("GET", "/blocks", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    await user.click(screen.getByRole("link", { name: "Servizi" }));
    expect(window.location.pathname).toBe("/admin/pagine/2");
    expect(await screen.findByRole("alert")).toHaveTextContent("Pagina non trovata");
  });

  test("dal telefono: Pubblica le modifiche con il controllo e Pubblica comunque (D-136)", async () => {
    const { api, user } = setup();
    api.on("GET", "/pages/4/draft", { data: { version: 3, data: {}, from_published: false, updated_at: null } });
    api.on("GET", "/pages/4/checks", {
      data: { blocking: [], warnings: [{ path: "seo/description", code: "seo_empty", message: "Manca la descrizione." }] },
    });
    api.on("POST", "/pages/4/publish", { data: node("Orari", { id: 4, status: "published" }) });
    await user.click(await screen.findByRole("button", { name: 'Pubblica le modifiche di "Orari"' }));
    expect(screen.queryByRole("button", { name: 'Pubblica le modifiche di "Servizi"' })).not.toBeInTheDocument();
    const dialog = await screen.findByRole("dialog", { name: "Pubblicare le modifiche?" });
    expect(await within(dialog).findByText(/Manca la descrizione/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Pubblica comunque" }));
    expect(await screen.findByText('"Orari" è online con le modifiche.')).toBeInTheDocument();
    expect(api.callsTo("POST", "/pages/4/publish")[0]?.body).toEqual({ draft_version: 3 });
  });

  test("dal telefono: con un errore da correggere non si pubblica", async () => {
    const { api, user } = setup();
    api.on("GET", "/pages/4/draft", { data: { version: 3, data: {}, from_published: false, updated_at: null } });
    api.on("GET", "/pages/4/checks", {
      data: { blocking: [{ path: "zones/main/0/data/media_id", code: "alt_missing", message: "Aggiungi il testo alternativo all'immagine" }], warnings: [] },
    });
    await user.click(await screen.findByRole("button", { name: 'Pubblica le modifiche di "Orari"' }));
    const dialog = await screen.findByRole("dialog", { name: "Pubblicare le modifiche?" });
    expect(await within(dialog).findByText(/Aggiungi il testo alternativo/)).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Correggi dal computer");
    expect(within(dialog).getByRole("button", { name: "Pubblica" })).toBeDisabled();
    expect(api.callsTo("POST", "/pages/4/publish")).toHaveLength(0);
  });

  test("dal telefono: senza il permesso di pubblicare niente pulsante", async () => {
    setup(site(), { ...ME, role: "editor", can_publish: false, permissions: ["content.edit", "profile"] });
    expect(await screen.findByRole("link", { name: "Orari" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pubblica le modifiche/ })).not.toBeInTheDocument();
  });
});
