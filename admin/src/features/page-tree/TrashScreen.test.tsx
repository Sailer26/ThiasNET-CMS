import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import { fakeApi, node, signedIn } from "../../test/fakeApi";

describe("cestino", () => {
  beforeEach(() => {
    setCsrfToken("tok");
    window.history.replaceState(null, "", "/admin/cestino");
  });

  test("recupera una pagina; errore del server come avviso", async () => {
    const api = fakeApi();
    signedIn(api);
    const old = node("Vecchia", { id: 9, version: 3, deleted_at: "2026-10-10T10:00:00+00:00" });
    const child = node("Figlia", { id: 10, deleted_at: "2026-10-10T10:00:00+00:00" });
    api.on("GET", "/pages/trash", { data: [old, child] }, { data: [child] });
    api.on("POST", "/pages/9/restore", { data: old });
    api.on("POST", "/pages/10/restore", {
      status: 409,
      error: { code: "parent_trashed", message: "Ripristina prima la pagina superiore" },
    });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Vecchia")).toBeInTheDocument();
    expect(screen.getAllByText(/Cestinata il/)[0]).toHaveTextContent("10.10.2026");
    await user.click(screen.getAllByRole("button", { name: "Recupera" })[0]!);
    expect(await screen.findByText('"Vecchia" è tornata tra le pagine (come bozza).')).toBeInTheDocument();
    expect(api.callsTo("POST", "/pages/9/restore")[0]?.body).toEqual({ version: 3 });
    await waitFor(() => expect(screen.queryByText("Vecchia")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Recupera" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ripristina prima la pagina superiore");
  });

  test("errore nel caricamento", async () => {
    const api = fakeApi();
    signedIn(api);
    api.on("GET", "/pages/trash", { status: 500, error: { code: "server_error", message: "Errore del server" } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Errore del server");
  });
});
