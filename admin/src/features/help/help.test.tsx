import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import { fakeApi, ME, signedIn } from "../../test/fakeApi";

function start(path: string) {
  const api = fakeApi();
  signedIn(api, ME);
  api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
  window.history.replaceState(null, "", path);
  render(<App />);
  return { api, user: userEvent.setup() };
}

describe("Chiedi a Thias", () => {
  beforeEach(() => setCsrfToken(null));

  test("dalla testata: scrivi, invia, conferma; il messaggio non parte vuoto", async () => {
    const { api, user } = start("/admin/pagine");
    api.on("POST", "/support-requests", { status: 201, data: { id: 1, sent: true } });
    await user.click(await screen.findByRole("button", { name: "Chiedi a Thias" }));
    const dialog = await screen.findByRole("dialog", { name: "Chiedi a Thias" });
    expect(within(dialog).getByRole("button", { name: "Invia" })).toBeDisabled();
    await user.type(within(dialog).getByLabelText("Che cosa ti serve?"), "Come cambio la foto?");
    await user.click(within(dialog).getByRole("button", { name: "Invia" }));
    expect(await screen.findByText(/Thias ti risponde per email appena/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/support-requests")[0]?.body).toEqual({
      message: "Come cambio la foto?",
      page_id: null,
      screen: "/admin/pagine",
    });
  });

  test("dall'editor manda anche la pagina aperta", async () => {
    const { api, user } = start("/admin/pagine/7");
    api.on("GET", "/pages/7", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    api.on("GET", "/pages/7/draft", { status: 404, error: { code: "not_found", message: "Pagina non trovata" } });
    api.on("GET", "/blocks", { data: { types: {}, layouts: {}, variants: {}, locales: ["it"] } });
    api.on("POST", "/support-requests", { status: 201, data: { id: 2, sent: true } });
    await user.click(await screen.findByRole("button", { name: "Chiedi a Thias" }));
    const dialog = await screen.findByRole("dialog", { name: "Chiedi a Thias" });
    expect(dialog).toHaveTextContent("Thias vedrà anche la pagina che hai aperto.");
    await user.type(within(dialog).getByLabelText("Che cosa ti serve?"), "Aiuto");
    await user.click(within(dialog).getByRole("button", { name: "Invia" }));
    await waitFor(() => expect(api.callsTo("POST", "/support-requests")[0]?.body).toMatchObject({ page_id: 7 }));
  });

  test("troppe richieste: il messaggio del server resta nella finestra", async () => {
    const { api, user } = start("/admin/pagine");
    api.on("POST", "/support-requests", {
      status: 429,
      error: { code: "rate_limited", message: "Hai già scritto diverse volte" },
      headers: { "Retry-After": "600" },
    });
    await user.click(await screen.findByRole("button", { name: "Chiedi a Thias" }));
    const dialog = await screen.findByRole("dialog", { name: "Chiedi a Thias" });
    await user.type(within(dialog).getByLabelText("Che cosa ti serve?"), "Ancora");
    await user.click(within(dialog).getByRole("button", { name: "Invia" }));
    expect(await within(dialog).findByRole("alert")).toBeInTheDocument();
  });
});
