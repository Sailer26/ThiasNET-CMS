import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import type { FieldSchema } from "../../api/catalog";
import type { CollectionInfo, Entry } from "../../api/entries";
import { fakeApi, ME, node, signedIn, type FakeApi } from "../../test/fakeApi";
import { transport } from "../editor/preview/transport";

const SCHEMA: FieldSchema = {
  title: "Notizie",
  type: "object",
  additionalProperties: false,
  required: ["date"],
  properties: {
    date: { type: "string", title: "Data", maxLength: 10, "x-date": true },
    cover: { type: "integer", title: "Immagine di copertina", minimum: 1, "x-media": "image" },
    summary: { type: "string", title: "Riassunto", maxLength: 300, "x-multiline": true },
  },
};

function collections(listing = true): CollectionInfo[] {
  return [{ key: "news", label: "Notizie", per_page: 10, schema: SCHEMA, listing: listing ? { page_id: 9, path: "/notizie" } : null }];
}

function entry(extra: Partial<Entry> = {}): Entry {
  return {
    id: 5,
    collection: "news",
    locale: "it",
    slug: "festa",
    title: "Festa",
    status: "draft",
    version: 1,
    publish_at: null,
    published_at: null,
    sort_at: null,
    updated_at: "2026-10-24T08:00:00+00:00",
    has_draft: true,
    url: "/notizie/festa",
    schedule: null,
    ...extra,
  };
}

function start(at: string, me = ME): FakeApi {
  const api = fakeApi();
  signedIn(api, me);
  window.history.replaceState(null, "", at);
  return api;
}

function editorApi(api: FakeApi, doc = { title: "Festa", fields: {}, seo: {} }) {
  api.on("GET", "/collections", { data: collections() });
  api.on("GET", "/entries/5", { data: entry() });
  api.on("GET", "/entries/5/draft", { data: { version: 1, data: doc, from_published: false } });
}

describe("notizie nel pannello (7b)", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.spyOn(transport, "submit").mockImplementation(() => undefined);
  });

  test("elenco con stato e avviso se manca la pagina elenco; nuova notizia apre l'editor", async () => {
    const api = start("/admin/raccolte/news");
    api.on("GET", "/collections/news/entries", {
      data: [entry({ status: "published", has_draft: true, sort_at: "2026-10-24T00:00:00+00:00" })],
      meta: { total: 1, pages: 1 },
    });
    api.on("GET", "/collections", { data: collections(false) });
    api.on("POST", "/collections/news/entries", { data: entry({ id: 6, title: "Mercato" }) });
    api.on("GET", "/entries/6", { data: entry({ id: 6, title: "Mercato" }) });
    api.on("GET", "/entries/6/draft", { data: { version: 1, data: { title: "Mercato", fields: {}, seo: {} }, from_published: false } });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Notizie" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notizie" })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("link", { name: "Festa" })).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("Modifiche non pubblicate")).toBeInTheDocument();
    expect(screen.getByText("24.10.2026")).toBeInTheDocument();
    expect(screen.getByText(/Elenco notizie/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nuova notizia" }));
    const dialog = await screen.findByRole("dialog", { name: "Nuova notizia" });
    await user.type(within(dialog).getByLabelText("Titolo della notizia"), "Mercato");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    expect(await screen.findByLabelText("Titolo")).toHaveValue("Mercato");
    expect(window.location.pathname).toBe("/admin/raccolte/news/6");
    expect(api.callsTo("POST", "/collections/news/entries")[0]?.body).toEqual({ title: "Mercato" });
  });

  test("editor: data e testo, poi pubblica dopo il controllo con gli avvisi", async () => {
    const api = start("/admin/raccolte/news/5");
    editorApi(api);
    api.on("PUT", "/entries/5/draft", { data: { version: 2 } });
    api.on("GET", "/entries/5/checks", {
      data: { blocking: [], warnings: [{ path: "seo/description", code: "seo_empty", message: "Manca la descrizione" }] },
    });
    api.on("POST", "/entries/5/publish", { data: entry({ status: "published", has_draft: false, version: 2 }) });
    const user = userEvent.setup();
    render(<App />);
    const date = await screen.findByLabelText(/^Data/);
    await user.type(date, "2026-10-25");
    await user.type(screen.getByLabelText(/Riassunto/), "Tutti in piazza");
    await user.click(screen.getByRole("button", { name: "Pubblica" }));
    const confirm = await screen.findByRole("dialog", { name: "Pubblicare la notizia?" });
    expect(confirm).toHaveTextContent("https://www.prova.ch/notizie/festa");
    expect(confirm).toHaveTextContent("Manca la descrizione");
    await user.click(within(confirm).getByRole("button", { name: "Pubblica comunque" }));
    expect(await screen.findByText("Notizia pubblicata.")).toBeInTheDocument();
    const saved = api.callsTo("PUT", "/entries/5/draft").at(-1)?.body as { version: number; fields: Record<string, unknown> };
    expect(saved.fields).toEqual({ date: "2026-10-25", summary: "Tutti in piazza" });
    expect(api.callsTo("POST", "/entries/5/publish")[0]?.body).toEqual({ draft_version: 2 });
    expect(transport.submit).toHaveBeenCalledWith(expect.any(String), "/_preview/entries/5", expect.anything());
  });

  test("errori bloccanti del controllo: elencati con il nome del campo", async () => {
    const api = start("/admin/raccolte/news/5");
    editorApi(api, { title: "Festa", fields: {}, seo: {} });
    api.on("GET", "/entries/5/checks", {
      data: { blocking: [{ path: "fields/date", code: "required", message: "Campo obbligatorio" }], warnings: [] },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Pubblica" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Data");
    expect(alert).toHaveTextContent("Campo obbligatorio");
    expect(api.callsTo("POST", "/entries/5/publish")).toHaveLength(0);
  });

  test("cestino: recupera una notizia", async () => {
    const api = start("/admin/raccolte/news");
    api.on("GET", "/collections", { data: collections() });
    api.on(
      "GET",
      "/collections/news/entries",
      { data: [], meta: { total: 0, pages: 1 } },
      { data: [entry({ title: "Vecchia" })], meta: { total: 1, pages: 1 } },
      { data: [], meta: { total: 0, pages: 1 } },
    );
    api.on("POST", "/entries/5/restore", { data: entry({ title: "Vecchia" }) });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Ancora nessuna notizia.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cestino" }));
    await user.click(await screen.findByRole("button", { name: "Recupera" }));
    expect(await screen.findByText(/è tornata tra le notizie/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/entries/5/restore")[0]?.body).toEqual({ version: 1 });
  });
});

describe("notizia dal telefono (D-97, D-154)", () => {
  beforeEach(() => setCsrfToken(null));

  function phoneApi(me = ME) {
    const api = start("/admin/", me);
    api.on("GET", "/pages/tree", { data: [node("Home", { id: 1, is_home: true, slug: "", path: "/" })], meta: { truncated: false } });
    api.on("GET", "/collections", { data: collections() });
    api.on("POST", "/collections/news/entries", { data: entry({ id: 7, title: "Strada chiusa" }) });
    api.on("PUT", "/entries/7/draft", { data: { version: 2 } });
    api.on("GET", "/entries/7/checks", { data: { blocking: [], warnings: [] } });
    api.on("POST", "/entries/7/publish", { data: entry({ id: 7, status: "published" }) });
    return api;
  }

  async function write(user: ReturnType<typeof userEvent.setup>, submit: string) {
    await user.click(await screen.findByRole("button", { name: "Notizia" }));
    const dialog = await screen.findByRole("dialog", { name: "Nuova notizia" });
    await user.type(await within(dialog).findByLabelText("Titolo"), "Strada chiusa");
    await user.type(await within(dialog).findByLabelText("Testo"), "Lavori fino a venerdì");
    await user.click(within(dialog).getByRole("button", { name: submit }));
  }

  test("chi può pubblicare: bozza con la data di oggi e il testo, controllo, online", async () => {
    const api = phoneApi();
    const user = userEvent.setup();
    render(<App />);
    await write(user, "Pubblica");
    expect(await screen.findByText('"Strada chiusa" è online.')).toBeInTheDocument();
    const draft = api.callsTo("PUT", "/entries/7/draft")[0]?.body as { version: number; fields: Record<string, unknown> };
    expect(draft.version).toBe(1);
    expect(draft.fields.summary).toBe("Lavori fino a venerdì");
    expect(draft.fields.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(api.callsTo("POST", "/entries/7/publish")[0]?.body).toEqual({ draft_version: 2 });
  });

  test("chi non può pubblicare: resta in bozza", async () => {
    const editor = { ...ME, role: "editor" as const, can_publish: false, permissions: ["content.edit", "profile"] };
    const api = phoneApi(editor);
    const user = userEvent.setup();
    render(<App />);
    await write(user, "Salva in bozza");
    expect(await screen.findByText(/salvata in bozza: la pubblicherà/)).toBeInTheDocument();
    await waitFor(() => expect(api.callsTo("PUT", "/entries/7/draft")).toHaveLength(1));
    expect(api.callsTo("POST", "/entries/7/publish")).toHaveLength(0);
  });
});
