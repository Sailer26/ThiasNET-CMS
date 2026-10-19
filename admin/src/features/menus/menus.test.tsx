import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import { fakeApi, ME, node, signedIn, type FakeApi } from "../../test/fakeApi";

const HOME = node("Home", { id: 1, is_home: true, slug: "", path: "/", status: "published" });
const ABOUT = node("Chi siamo", { id: 2, path: "/chi-siamo", status: "published" });

function menus(mainManual = false, version = 0) {
  return [
    {
      location: "main",
      label: "Menu principale",
      max_depth: 2,
      automatic: true,
      manual: mainManual,
      version,
      items: [
        { uid: "1".repeat(32), page_id: 1, children: [] },
        { uid: "2".repeat(32), page_id: 2, children: [] },
      ],
    },
    { location: "footer", label: "Menu footer", max_depth: 1, automatic: false, manual: false, version: 0, items: [] },
  ];
}

function start(me = ME): FakeApi {
  const api = fakeApi();
  signedIn(api, me);
  api.on("GET", "/pages/tree", { data: [HOME, ABOUT], meta: { truncated: false } });
  window.history.replaceState(null, "", "/admin/menu");
  return api;
}

describe("menu del sito (6b, D-140, D-141)", () => {
  beforeEach(() => setCsrfToken(null));

  test("menu principale automatico: le pagine con i loro titoli e la spiegazione", async () => {
    const api = start();
    api.on("GET", "/menus", { data: menus() });
    render(<App />);
    const main = await screen.findByRole("region", { name: "Menu principale" });
    expect(within(main).getByText(/si fa da solo/)).toBeInTheDocument();
    expect(within(main).getByText("Home")).toBeInTheDocument();
    expect(within(main).getByText("Chi siamo")).toBeInTheDocument();
    expect(within(main).queryByRole("button", { name: "Torna automatico" })).not.toBeInTheDocument();
  });

  test("aggiunge un link, lo rientra sotto una pagina e salva con conferma", async () => {
    const api = start();
    api.on("GET", "/menus", { data: menus() });
    api.on("PUT", "/menus/main", (call) => ({ data: { ...menus(true, 1)[0], items: (call.body as { items: unknown }).items } }));
    const user = userEvent.setup();
    render(<App />);
    const main = await screen.findByRole("region", { name: "Menu principale" });
    await user.click(within(main).getByRole("button", { name: "Aggiungi link" }));
    const dialog = await screen.findByRole("dialog", { name: "Aggiungi link" });
    await user.type(within(dialog).getByLabelText(/Testo/), "Orari");
    await user.type(within(dialog).getByLabelText(/Indirizzo/), "https://www.esterno.ch/orari");
    await user.click(within(dialog).getByRole("button", { name: "Aggiungi" }));
    await user.click(within(main).getByRole("button", { name: 'Rientra "Orari"' }));
    await user.click(within(main).getByRole("button", { name: "Salva" }));
    const confirm = await screen.findByRole("dialog", { name: "Salvare il menu?" });
    expect(confirm).toHaveTextContent("subito");
    await user.click(within(confirm).getByRole("button", { name: "Salva" }));
    expect(await screen.findByText(/Menu salvato/)).toBeInTheDocument();
    const sent = api.callsTo("PUT", "/menus/main")[0]?.body as { version: number; items: { page_id?: number; children: { url?: string; label?: string }[] }[] };
    expect(sent.version).toBe(0);
    expect(sent.items[1]?.page_id).toBe(2);
    expect(sent.items[1]?.children[0]).toMatchObject({ url: "https://www.esterno.ch/orari", label: "Orari" });
  });

  test("errori del server elencati; torna automatico con conferma", async () => {
    const api = start();
    api.on("GET", "/menus", { data: menus(true, 3) });
    api.on("PUT", "/menus/main", {
      status: 422,
      error: { code: "invalid_content", message: "Campi non validi", details: [{ path: "items/1/page_id", code: "page_missing", message: "La pagina non c'è più (o è nel cestino)" }] },
    });
    api.on("DELETE", "/menus/main", { data: menus(false, 0)[0] });
    const user = userEvent.setup();
    render(<App />);
    const main = await screen.findByRole("region", { name: "Menu principale" });
    await user.click(within(main).getByRole("button", { name: "Salva" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Salva" }));
    expect(await within(main).findByText(/La pagina non c'è più/)).toBeInTheDocument();
    await user.click(within(main).getByRole("button", { name: "Torna automatico" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Tornare al menu automatico?" })).getByRole("button", { name: "Torna automatico" }));
    await waitFor(() => expect(api.callsTo("DELETE", "/menus/main")[0]?.body).toEqual({ version: 3 }));
  });

  test("chi non può pubblicare non vede Menu", async () => {
    const api = start({ ...ME, role: "editor", can_publish: false, permissions: ["content.edit", "profile"] });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Non hai accesso a questa sezione." })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Menu" })).not.toBeInTheDocument();
    expect(api.callsTo("GET", "/menus")).toHaveLength(0);
  });
});
