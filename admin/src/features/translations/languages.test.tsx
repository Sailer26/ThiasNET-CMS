import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../../App";
import { localized, setCsrfToken } from "../../api/client";
import { catalog } from "../../test/catalog";
import { fakeApi, node, signedIn, type Call, type FakeApi } from "../../test/fakeApi";
import { LOCALE_STORAGE_KEY } from "../../session/LocaleProvider";
import { transport } from "../editor/preview/transport";

const HOME = node("Home", { id: 1, is_home: true, slug: "", path: "/", status: "published" });
const START = node("Startseite", { id: 2, locale: "de", is_home: true, slug: "", path: "/", status: "draft" });

function start(at: string): FakeApi {
  const api = fakeApi();
  signedIn(api);
  window.history.replaceState(null, "", at);
  return api;
}

const inGerman = (call: Call) => call.path.includes("locale=de");

function tree(api: FakeApi, german: () => ReturnType<typeof node>[]) {
  api.on("GET", "/pages/tree", (call) => ({ data: inGerman(call) ? german() : [HOME], meta: { truncated: false } }));
}

describe("lingue nel pannello (7c, D-159)", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.spyOn(transport, "submit").mockImplementation(() => undefined);
  });

  test("la lingua scelta in alto cambia l'albero ed è ricordata su questo computer", async () => {
    const api = start("/admin/pagine");
    tree(api, () => [START]);
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    expect(await screen.findByRole("link", { name: "Home" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Lingua dei contenuti"), "de");
    expect(await screen.findByRole("link", { name: "Startseite" })).toBeInTheDocument();
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("de");
    unmount();
    render(<App />);
    expect(await screen.findByRole("link", { name: "Startseite" })).toBeInTheDocument();
    expect(screen.getByLabelText("Lingua dei contenuti")).toHaveValue("de");
  });

  test("una lingua ricordata che il tema non ha più si ignora", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "fr");
    const api = start("/admin/pagine");
    tree(api, () => [START]);
    render(<App />);
    expect(await screen.findByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByLabelText("Lingua dei contenuti")).toHaveValue("it");
    expect(api.callsTo("GET", "/pages/tree")[0]?.path).toContain("locale=it");
  });

  test("lingua senza homepage: la si crea come traduzione di quella principale", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "de");
    const api = start("/admin/pagine");
    let created = false;
    tree(api, () => (created ? [START] : []));
    api.on("POST", "/pages/1/translations", () => {
      created = true;
      return { status: 201, data: START };
    });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText(/Deutsch: ancora nessuna homepage/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Crea la homepage in Deutsch" }));
    expect(await screen.findByText(/Homepage in Deutsch creata/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Startseite" })).toBeInTheDocument();
    expect(api.callsTo("POST", "/pages/1/translations")[0]?.body).toEqual({ locale: "de" });
  });

  test("editor: Traduzioni crea la lingua mancante e porta il pannello in quella lingua", async () => {
    const api = start("/admin/pagine/7");
    const draft = { title: "Chi siamo", layout: "page", seo: {}, zones: { main: [], sidebar: [] } };
    api.on("GET", "/pages/7", { data: node("Chi siamo", { id: 7, path: "/chi-siamo" }) });
    api.on("GET", "/pages/7/draft", { data: { version: 1, data: draft, from_published: false, updated_at: null } });
    api.on("GET", "/pages/8", { data: node("Chi siamo", { id: 8, locale: "de", path: "/chi-siamo" }) });
    api.on("GET", "/pages/8/draft", { data: { version: 2, data: draft, from_published: false, updated_at: null } });
    api.on("GET", "/blocks", { data: catalog() });
    tree(api, () => []);
    api.on("GET", "/pages/7/translations", {
      data: [
        { locale: "it", label: "Italiano", id: 7, title: "Chi siamo", status: "draft" },
        { locale: "de", label: "Deutsch", id: null, title: null, status: null },
      ],
    });
    api.on("POST", "/pages/7/translations", { status: 201, data: { id: 8, locale: "de" } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Traduzioni" }));
    await user.click(await screen.findByRole("button", { name: "Traduci in Deutsch" }));
    await waitFor(() => expect(window.location.pathname).toBe("/admin/pagine/8"));
    expect(screen.getByLabelText("Lingua dei contenuti")).toHaveValue("de");
    expect(api.callsTo("POST", "/pages/7/translations")[0]?.body).toEqual({ locale: "de" });
    // l'editor della traduzione propone i link della sua lingua
    await waitFor(() => expect(api.callsTo("GET", "/pages/8/draft")).toHaveLength(1));
    expect(api.callsTo("GET", "/pages/tree").at(-1)?.path).toContain("locale=de");
  });

  test("menu e notizie seguono la lingua del pannello", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "de");
    const api = start("/admin/menu");
    tree(api, () => [START]);
    api.on("GET", "/menus", {
      data: [{ location: "main", locale: "de", label: "Menu principale", max_depth: 2, automatic: true, manual: false, version: 0, items: [] }],
    });
    const { unmount } = render(<App />);
    expect(await screen.findByText("Menu principale")).toBeInTheDocument();
    expect(api.callsTo("GET", "/menus")[0]?.path).toBe("/menus?locale=de");
    unmount();

    window.history.replaceState(null, "", "/admin/raccolte/news");
    api.on("GET", "/collections", { data: [] });
    api.on("GET", "/collections/news/entries", { data: [], meta: { total: 0, pages: 1 } });
    render(<App />);
    expect(await screen.findByText("Ancora nessuna notizia.")).toBeInTheDocument();
    expect(api.callsTo("GET", "/collections/news/entries")[0]?.path).toContain("locale=de");
    expect(api.callsTo("GET", "/collections")[0]?.path).toBe("/collections?locale=de");
  });

  test("l'editor porta il pannello nella lingua della sua pagina", async () => {
    const api = start("/admin/pagine/8");
    const draft = { title: "Über uns", layout: "page", seo: {}, zones: { main: [], sidebar: [] } };
    api.on("GET", "/pages/8", { data: node("Über uns", { id: 8, locale: "de", path: "/ueber-uns" }) });
    api.on("GET", "/pages/8/draft", { data: { version: 1, data: draft, from_published: false, updated_at: null } });
    api.on("GET", "/blocks", { data: catalog() });
    tree(api, () => [START]);
    render(<App />);
    expect(await screen.findByLabelText("Titolo della pagina")).toHaveValue("Über uns");
    await waitFor(() => expect(screen.getByLabelText("Lingua dei contenuti")).toHaveValue("de"));
    expect(api.callsTo("GET", "/pages/tree")[0]?.path).toContain("locale=de");
  });

  test("traduzione già fatta da qualcun altro: messaggio chiaro e riga aggiornata", async () => {
    const api = start("/admin/pagine/7");
    const draft = { title: "Chi siamo", layout: "page", seo: {}, zones: { main: [], sidebar: [] } };
    api.on("GET", "/pages/7", { data: node("Chi siamo", { id: 7, path: "/chi-siamo" }) });
    api.on("GET", "/pages/7/draft", { data: { version: 1, data: draft, from_published: false, updated_at: null } });
    api.on("GET", "/blocks", { data: catalog() });
    tree(api, () => []);
    const it = { locale: "it", label: "Italiano", id: 7, title: "Chi siamo", status: "draft" };
    api.on(
      "GET",
      "/pages/7/translations",
      { data: [it, { locale: "de", label: "Deutsch", id: null, title: null, status: null }] },
      { data: [it, { locale: "de", label: "Deutsch", id: 9, title: "Über uns", status: "published" }] },
    );
    api.on("POST", "/pages/7/translations", {
      status: 409,
      error: { code: "translation_exists", message: "Questa lingua ha già la sua traduzione" },
    });
    const user = userEvent.setup();
    render(<App />);
    const toggle = await screen.findByRole("button", { name: "Traduzioni" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.click(await screen.findByRole("button", { name: "Traduci in Deutsch" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Esiste già una traduzione in Deutsch");
    expect(await screen.findByRole("button", { name: "Apri in Deutsch" })).toBeInTheDocument();
    expect(screen.getByText("online")).toBeInTheDocument();
  });

  test("widget nella lingua del pannello, anche al salvataggio", async () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "de");
    const api = start("/admin/widget");
    tree(api, () => [START]);
    api.on("GET", "/widgets", {
      data: [{ area: "footer", label: "Piè di pagina", locale: "de", types: [], version: 0, items: [] }],
    });
    render(<App />);
    expect(await screen.findByText("Piè di pagina")).toBeInTheDocument();
    expect(api.callsTo("GET", "/widgets")[0]?.path).toBe("/widgets?locale=de");
    expect(api.callsTo("GET", "/pages/tree")[0]?.path).toContain("locale=de");
  });

  test("localized aggiunge la lingua anche a un indirizzo con altri parametri", () => {
    expect(localized("/menus", "de")).toBe("/menus?locale=de");
    expect(localized("/x?page=2", "rm")).toBe("/x?page=2&locale=rm");
  });
});
