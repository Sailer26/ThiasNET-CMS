import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../App";
import { request, setCsrfToken } from "../api/client";
import { browser } from "../router/router";
import { fakeApi, ME, signedIn, SITE } from "../test/fakeApi";
import { STALE_AFTER_MS } from "./SessionProvider";

const UNAUTHORIZED = { status: 401, error: { code: "unauthorized", message: "Accesso richiesto" } };

function anonymous() {
  const api = fakeApi();
  api.on("GET", "/auth/csrf", { data: { csrf_token: "tok-0" } });
  api.on("GET", "/auth/me", UNAUTHORIZED, { data: ME });
  api.on("GET", "/site", { data: SITE });
  api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
  return api;
}

describe("accesso e sessione", () => {
  beforeEach(() => {
    setCsrfToken(null);
    window.history.replaceState(null, "", "/admin/");
  });

  test("senza sessione mostra l'accesso; con email e password entra", async () => {
    const api = anonymous();
    api.on("POST", "/auth/login", { data: { totp_required: false, user: ME, csrf_token: "tok-2" } });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Accedi al pannello" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email"), "anna@example.ch");
    await user.type(screen.getByLabelText("Password"), "segreta-lunga");
    await user.click(screen.getByRole("button", { name: "Accedi" }));
    expect(await screen.findByText("Comune di Prova")).toBeInTheDocument();
    expect(api.callsTo("POST", "/auth/login")[0]?.body).toEqual({
      email: "anna@example.ch",
      password: "segreta-lunga",
    });
    expect(screen.getByRole("link", { name: "Apri il sito" })).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("credenziali sbagliate: il messaggio del server", async () => {
    const api = anonymous();
    api.on("POST", "/auth/login", {
      status: 401,
      error: { code: "invalid_credentials", message: "Email o password non corretti" },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByLabelText("Email"), "x@example.ch");
    await user.type(screen.getByLabelText("Password"), "sbagliata");
    await user.click(screen.getByRole("button", { name: "Accedi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o password non corretti");
  });

  test("con il secondo fattore chiede il codice; se scade torna all'email", async () => {
    const api = anonymous();
    api.on("POST", "/auth/login", { data: { totp_required: true, csrf_token: "tok-t" } });
    api.on(
      "POST",
      "/auth/login/totp",
      { status: 410, error: { code: "totp_expired", message: "Tempo scaduto: accedi di nuovo" } },
      { data: { user: ME, csrf_token: "tok-3" } },
    );
    const user = userEvent.setup();
    render(<App />);
    const login = async () => {
      await user.type(screen.getByLabelText("Email"), "anna@example.ch");
      await user.type(screen.getByLabelText("Password"), "segreta-lunga");
      await user.click(screen.getByRole("button", { name: "Accedi" }));
    };
    await screen.findByLabelText("Email");
    await login();
    const code = await screen.findByLabelText("Codice");
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    expect(screen.getByRole("button", { name: "Conferma" })).toBeDisabled();
    await user.type(code, "123456");
    await user.click(screen.getByRole("button", { name: "Conferma" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tempo scaduto");
    await user.clear(screen.getByLabelText("Email"));
    await login();
    await user.type(await screen.findByLabelText("Codice"), "654321");
    await user.click(screen.getByRole("button", { name: "Conferma" }));
    expect(await screen.findByText("Comune di Prova")).toBeInTheDocument();
  });

  test("errore all'avvio diverso da 401: messaggio e niente accesso", async () => {
    const api = fakeApi();
    api.on("GET", "/auth/csrf", { status: 500, error: { code: "server_error", message: "Server fermo" } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server fermo");
  });

  test("sessione scaduta: finestra sopra lo schermo, dopo l'accesso i dati si ricaricano", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    api.on("POST", "/auth/login", { data: { totp_required: false, user: ME, csrf_token: "tok-9" } });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Il sito non ha ancora una homepage.");
    api.on("GET", "/x", UNAUTHORIZED);
    await act(async () => {
      await request("GET", "/x").catch(() => undefined);
    });
    const dialog = await screen.findByRole("dialog", { name: "Per sicurezza devi accedere di nuovo" });
    expect(screen.getByText("Il sito non ha ancora una homepage.")).toBeInTheDocument(); // lo schermo resta
    const email = screen.getAllByLabelText("Email").find((el) => dialog.contains(el))!;
    expect(email).toHaveValue("anna@example.ch");
    expect(email).toHaveAttribute("readonly");
    const trees = api.callsTo("GET", "/pages/tree").length;
    await user.type(screen.getAllByLabelText("Password").find((el) => dialog.contains(el))!, "segreta-lunga");
    await user.click(screen.getByRole("button", { name: "Accedi" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(api.callsTo("GET", "/pages/tree").length).toBe(trees + 1));
  });

  test("se rientra un altro utente il pannello si ricarica da capo", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    const reload = vi.spyOn(browser, "reload").mockImplementation(() => undefined);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Il sito non ha ancora una homepage.");
    api.on("GET", "/x", UNAUTHORIZED);
    await act(async () => {
      await request("GET", "/x").catch(() => undefined);
    });
    const dialog = await screen.findByRole("dialog");
    api.on("POST", "/auth/login", { data: { totp_required: false, user: ME, csrf_token: "t" } });
    api.on("GET", "/auth/me", { data: { ...ME, email: "altro@example.ch" } });
    await user.type(screen.getAllByLabelText("Password").find((el) => dialog.contains(el))!, "segreta-lunga");
    await user.click(screen.getByRole("button", { name: "Accedi" }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  test("dopo molto tempo con la finestra nascosta ricontrolla la sessione, una volta", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    render(<App />);
    await screen.findByText("Il sito non ha ancora una homepage.");
    const before = api.callsTo("GET", "/auth/me").length;
    const visibility = vi.spyOn(document, "visibilityState", "get");
    const now = vi.spyOn(Date, "now");
    now.mockReturnValue(1_000);
    visibility.mockReturnValue("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    now.mockReturnValue(1_000 + STALE_AFTER_MS - 1);
    visibility.mockReturnValue("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(api.callsTo("GET", "/auth/me")).toHaveLength(before); // poco tempo: niente chiamata
    visibility.mockReturnValue("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    now.mockReturnValue(1_000 + STALE_AFTER_MS * 3);
    visibility.mockReturnValue("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    await waitFor(() => expect(api.callsTo("GET", "/auth/me")).toHaveLength(before + 1));
  });

  test("esci e esci da tutti i dispositivi", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    api.on("POST", "/auth/logout-all", { data: { csrf_token: "t2" } });
    api.on("POST", "/auth/logout", { data: { csrf_token: "t3" } });
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await user.click(await screen.findByRole("button", { name: "Esci da tutti i dispositivi" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Verrai disconnesso da tutti");
    await user.click(screen.getAllByRole("button", { name: "Esci da tutti i dispositivi" }).find((b) => dialog.contains(b))!);
    expect(await screen.findByRole("heading", { name: "Accedi al pannello" })).toBeInTheDocument();
    expect(api.callsTo("POST", "/auth/logout-all")).toHaveLength(1);
    unmount();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Esci" }));
    expect(await screen.findByRole("heading", { name: "Accedi al pannello" })).toBeInTheDocument();
  });

  test("esci con la sessione già scaduta porta comunque all'accesso", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    api.on("POST", "/auth/logout", UNAUTHORIZED);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Esci" }));
    expect(await screen.findByRole("heading", { name: "Accedi al pannello" })).toBeInTheDocument();
  });

  test("menu: Pagine e Cestino, schermata sconosciuta", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
    api.on("GET", "/pages/trash", { data: [] });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("link", { name: "Cestino" }));
    expect(await screen.findByText("Il cestino è vuoto.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cestino" })).toHaveAttribute("aria-current", "page");
    act(() => {
      window.history.pushState(null, "", "/admin/nulla");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(await screen.findByText("Questa schermata non esiste.")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Torna alle pagine" }));
    expect(await screen.findByRole("heading", { name: "Pagine" })).toHaveFocus();
    expect(document.title).toBe("Pagine · Comune di Prova · ThiasNET CMS");
  });
});
