import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import type { WidgetAreaInfo, WidgetItem } from "../../api/widgets";
import { fakeApi, node, signedIn, type FakeApi } from "../../test/fakeApi";

const HOME = node("Home", { id: 1, is_home: true, slug: "", path: "/", status: "published" });
const ABOUT = node("Chi siamo", { id: 2, path: "/chi-siamo", status: "published" });
const TITLE = { type: "string", title: "Titolo", maxLength: 80 };
const NOTICE_SCHEMA = {
  title: "Banner avviso",
  type: "object",
  required: ["text"],
  properties: {
    text: { type: "string", title: "Testo dell'avviso", maxLength: 300 },
    level: { type: "string", title: "Tipo", enum: ["info", "warning", "urgent"], "x-enum-titles": ["Informazione", "Attenzione", "Urgente"] },
  },
};
const CTA_SCHEMA = {
  title: "Invito all'azione",
  type: "object",
  required: ["title", "button_label", "url"],
  properties: {
    title: TITLE,
    button_label: { type: "string", title: "Testo del pulsante", maxLength: 40 },
    url: { type: "string", title: "Link del pulsante", maxLength: 2048, format: "safe-url" },
  },
};
const HOURS = { uid: "1".repeat(32), type: "hours", data: { title: "Orari" }, visibility: { mode: "all" as const, pages: [] }, until: null };

function areas(sidebar: WidgetItem[] = [], top: WidgetItem[] = []): WidgetAreaInfo[] {
  return [
    { area: "header_top", label: "Fascia in cima", locale: "it", version: 0, items: top, types: [{ type: "notice", label: "Banner avviso", schema: NOTICE_SCHEMA }] },
    {
      area: "sidebar",
      label: "Colonna laterale",
      locale: "it",
      version: 2,
      items: sidebar,
      types: [
        { type: "hours", label: "Orari", schema: { title: "Orari", type: "object", properties: { title: TITLE } } },
        { type: "cta", label: "Invito all'azione", schema: CTA_SCHEMA },
      ],
    },
  ];
}

function start(found: WidgetAreaInfo[], at = "/admin/widget"): FakeApi {
  const api = fakeApi();
  signedIn(api);
  api.on("GET", "/pages/tree", { data: [HOME, ABOUT], meta: { truncated: false } });
  api.on("GET", "/widgets", { data: found });
  window.history.replaceState(null, "", at);
  return api;
}

function sentItems(api: FakeApi, area: string): WidgetItem[] {
  return (api.callsTo("PUT", `/widgets/${area}`)[0]?.body as { items: WidgetItem[] }).items;
}

describe("widget (6c, D-140, D-142)", () => {
  beforeEach(() => setCsrfToken(null));

  test("aggiunge un invito all'azione solo su una pagina e salva con conferma", async () => {
    const api = start(areas([HOURS]));
    api.on("PUT", "/widgets/sidebar", (call) => ({ data: { ...areas()[1], version: 3, items: (call.body as { items: unknown }).items } }));
    const user = userEvent.setup();
    render(<App />);
    const side = await screen.findByRole("region", { name: "Colonna laterale" });
    expect(within(side).getByText("Orari", { selector: "strong" })).toBeInTheDocument();
    await user.selectOptions(within(side).getByLabelText("Quale widget?"), "cta");
    await user.click(within(side).getByRole("button", { name: "Aggiungi widget" }));
    const dialog = await screen.findByRole("dialog", { name: "Aggiungi: Invito all'azione" });
    const done = within(dialog).getByRole("button", { name: "Fatto" });
    expect(done).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/^Titolo/), "Scrivici");
    await user.type(within(dialog).getByLabelText(/Testo del pulsante/), "Contatti");
    await user.type(within(dialog).getByLabelText(/Link del pulsante/), "/contatti");
    await user.click(within(dialog).getByLabelText("Solo in alcune pagine"));
    expect(done).toBeDisabled(); // nessuna pagina scelta
    await user.click(within(dialog).getByLabelText("Chi siamo"));
    await user.click(done);
    expect(within(side).getByText(/Solo in una pagina/)).toBeInTheDocument();
    await user.click(within(side).getByRole("button", { name: "Salva" }));
    const confirm = await screen.findByRole("dialog", { name: "Salvare questa parte del sito?" });
    await user.click(within(confirm).getByRole("button", { name: "Salva" }));
    expect(await within(side).findByText(/il sito è già aggiornato/)).toBeInTheDocument();
    const call = api.callsTo("PUT", "/widgets/sidebar")[0]?.body as { version: number };
    expect(call.version).toBe(2);
    const items = sentItems(api, "sidebar");
    expect(items[0]).toEqual(HOURS);
    expect(items[1]).toMatchObject({ type: "cta", data: { title: "Scrivici", button_label: "Contatti", url: "/contatti" }, visibility: { mode: "only", pages: [2] }, until: null });
  });

  test("sposta e toglie con il focus sul widget e un annuncio", async () => {
    const other = { ...HOURS, uid: "2".repeat(32), data: { title: "Estate" } };
    start(areas([HOURS, other]));
    const user = userEvent.setup();
    render(<App />);
    const side = await screen.findByRole("region", { name: "Colonna laterale" });
    await user.click(within(side).getByRole("button", { name: 'Giù "Orari" (widget 1)' }));
    expect(within(side).getByRole("status")).toHaveTextContent('"Orari" ora è in posizione 2 di 2.');
    // "Giù" ora è spento (ultimo posto): il focus va su "Modifica" dello stesso widget
    expect(within(side).getByRole("button", { name: 'Modifica "Orari" (widget 2)' })).toHaveFocus();
    await user.click(within(side).getByRole("button", { name: 'Togli "Orari" (widget 2)' }));
    expect(within(side).getByRole("button", { name: 'Modifica "Estate" (widget 1)' })).toHaveFocus();
  });

  test("errori del server con il nome del widget", async () => {
    const api = start(areas([HOURS]));
    api.on("PUT", "/widgets/sidebar", {
      status: 422,
      error: { code: "invalid_content", message: "Campi non validi", details: [{ path: "items/0/visibility/pages", code: "page_missing", message: "Una delle pagine scelte non c'è più (o è nel cestino)" }] },
    });
    const user = userEvent.setup();
    render(<App />);
    const side = await screen.findByRole("region", { name: "Colonna laterale" });
    await user.click(within(side).getByRole("button", { name: "Salva" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Salvare questa parte del sito?" })).getByRole("button", { name: "Salva" }));
    expect(await within(side).findByRole("alert")).toHaveTextContent("Orari: Una delle pagine scelte non c'è più");
  });

  test("banner con fino al: l'ora svizzera arriva con il fuso", async () => {
    const api = start(areas());
    api.on("PUT", "/widgets/header_top", (call) => ({ data: { ...areas()[0], version: 1, items: (call.body as { items: unknown }).items } }));
    const user = userEvent.setup();
    render(<App />);
    const top = await screen.findByRole("region", { name: "Fascia in cima" });
    await user.click(within(top).getByRole("button", { name: "Aggiungi widget" }));
    const dialog = await screen.findByRole("dialog", { name: "Aggiungi: Banner avviso" });
    await user.type(within(dialog).getByLabelText(/Testo dell'avviso/), "Uffici chiusi");
    await user.type(within(dialog).getByLabelText("Giorno"), "2099-01-10");
    await user.type(within(dialog).getByLabelText("Ora"), "08:00");
    await user.click(within(dialog).getByRole("button", { name: "Fatto" }));
    expect(within(top).getByText(/Fino a .*10 gennaio 2099 alle 08:00/)).toBeInTheDocument();
    await user.click(within(top).getByRole("button", { name: "Salva" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Salvare questa parte del sito?" })).getByRole("button", { name: "Salva" }));
    expect(await within(top).findByText(/il sito è già aggiornato/)).toBeInTheDocument();
    expect(sentItems(api, "header_top")[0]).toMatchObject({ type: "notice", data: { text: "Uffici chiusi" }, until: "2099-01-10T08:00:00+01:00" });
  });
});

describe("banner dal telefono (D-97)", () => {
  beforeEach(() => setCsrfToken(null));

  test("dalle pagine: scrive il banner e lo mette in cima senza toccare gli altri widget", async () => {
    const inline = { uid: "3".repeat(32), type: "contacts_inline", data: {}, visibility: { mode: "all" as const, pages: [] }, until: null };
    const top = { ...areas()[0]!, version: 4, items: [inline] };
    const api = start(areas(), "/admin/");
    api.on("GET", "/widgets/header_top", { data: top });
    api.on("PUT", "/widgets/header_top", (call) => ({ data: { ...top, version: 5, items: (call.body as { items: unknown }).items } }));
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Banner avviso" }));
    const dialog = await screen.findByRole("dialog", { name: "Banner avviso sul sito" });
    await user.type(await within(dialog).findByLabelText(/Testo dell'avviso/), "Strada chiusa");
    await user.selectOptions(within(dialog).getByLabelText("Tipo"), "urgent");
    await user.click(within(dialog).getByRole("button", { name: "Mostra sul sito" }));
    expect(await screen.findByText("Il banner è sul sito.")).toBeInTheDocument();
    const call = api.callsTo("PUT", "/widgets/header_top")[0]?.body as { version: number; items: WidgetItem[] };
    expect(call.version).toBe(4);
    expect(call.items[0]).toMatchObject({ type: "notice", data: { text: "Strada chiusa", level: "urgent" }, until: null });
    expect(call.items[1]).toEqual(inline);
  });

  test("toglie il banner con conferma", async () => {
    const notice = { uid: "4".repeat(32), type: "notice", data: { text: "Vecchio", level: "info" }, visibility: { mode: "all" as const, pages: [] }, until: null };
    const top = { ...areas()[0]!, version: 1, items: [notice] };
    const api = start(areas(), "/admin/");
    api.on("GET", "/widgets/header_top", { data: top });
    api.on("PUT", "/widgets/header_top", { data: { ...top, version: 2, items: [] } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Banner avviso" }));
    const dialog = await screen.findByRole("dialog", { name: "Banner avviso sul sito" });
    expect(await within(dialog).findByDisplayValue("Vecchio")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Togli il banner" }));
    const confirm = await screen.findByRole("dialog", { name: "Togliere il banner dal sito?" });
    await user.click(within(confirm).getByRole("button", { name: "Togli il banner" }));
    expect(await screen.findByText("Banner tolto dal sito.")).toBeInTheDocument();
    expect(sentItems(api, "header_top")).toEqual([]);
  });
});

describe("banner dal telefono: conflitto (D-44)", () => {
  beforeEach(() => setCsrfToken(null));

  test("dopo un 409 l'area si rilegge e il secondo tentativo usa la versione nuova", async () => {
    const top = { ...areas()[0]!, version: 1, items: [] };
    const api = start(areas(), "/admin/");
    api.on("GET", "/widgets/header_top", { data: top });
    api.on("PUT", "/widgets/header_top", { status: 409, error: { code: "version_conflict", message: "Qualcun altro ha modificato questa parte del sito" } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Banner avviso" }));
    const dialog = await screen.findByRole("dialog", { name: "Banner avviso sul sito" });
    await user.type(await within(dialog).findByLabelText(/Testo dell'avviso/), "Chiuso");
    await user.click(within(dialog).getByRole("button", { name: "Mostra sul sito" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/un altro utente/);
    await within(dialog).findByLabelText(/Testo dell'avviso/);
    expect(api.callsTo("GET", "/widgets/header_top")).toHaveLength(2);
  });
});
