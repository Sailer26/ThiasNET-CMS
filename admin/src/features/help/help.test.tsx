import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import { fakeApi, ME, signedIn } from "../../test/fakeApi";

function start(path: string, me = ME) {
  const api = fakeApi();
  signedIn(api, me);
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
    await user.click(await screen.findByRole("button", { name: "Aiuto" }));
    await user.click(screen.getByRole("button", { name: "Chiedi a Thias" }));
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
    await user.click(await screen.findByRole("button", { name: "Aiuto" }));
    await user.click(screen.getByRole("button", { name: "Chiedi a Thias" }));
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
    await user.click(await screen.findByRole("button", { name: "Aiuto" }));
    await user.click(screen.getByRole("button", { name: "Chiedi a Thias" }));
    const dialog = await screen.findByRole("dialog", { name: "Chiedi a Thias" });
    await user.type(within(dialog).getByLabelText("Che cosa ti serve?"), "Ancora");
    await user.click(within(dialog).getByRole("button", { name: "Invia" }));
    expect(await within(dialog).findByRole("alert")).toBeInTheDocument();
  });
});

describe("tour al primo accesso (D-133)", () => {
  beforeEach(() => setCsrfToken(null));

  test("parte da solo la prima volta, 5 passi, alla fine lo segna sul server", async () => {
    const { api, user } = start("/admin/pagine", { ...ME, tour_completed_at: null });
    api.on("POST", "/auth/me/tour", { data: { ...ME } });
    const dialog = await screen.findByRole("dialog", { name: "Le pagine del sito" });
    expect(within(dialog).getByText("Passo 1 di 5")).toBeInTheDocument();
    expect(document.querySelector('[data-tour="pages"]')).toHaveClass("tour-target");
    for (const title of ["Apri una pagina", "Modifica un blocco", "Anteprima e Pubblica", "Serve aiuto?"]) {
      await user.click(screen.getByRole("button", { name: "Avanti" }));
      expect(await screen.findByRole("dialog", { name: title })).toBeInTheDocument();
    }
    expect(document.querySelector('[data-tour="help"]')).toHaveClass("tour-target");
    await user.click(screen.getByRole("button", { name: "Indietro" }));
    expect(await screen.findByRole("dialog", { name: "Anteprima e Pubblica" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Avanti" }));
    await user.click(screen.getByRole("button", { name: "Fine" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.callsTo("POST", "/auth/me/tour")).toHaveLength(1);
    expect(document.querySelector(".tour-target")).toBeNull();
  });

  test("Salta il tour lo chiude e non ripartirà", async () => {
    const { api, user } = start("/admin/pagine", { ...ME, tour_completed_at: null });
    api.on("POST", "/auth/me/tour", { data: { ...ME } });
    const dialog = await screen.findByRole("dialog", { name: "Le pagine del sito" });
    await user.click(within(dialog).getByRole("button", { name: "Salta il tour" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.callsTo("POST", "/auth/me/tour")).toHaveLength(1);
  });

  test("chi l'ha già visto non lo rivede, ma può rifarlo dal menu Aiuto", async () => {
    const { user } = start("/admin/pagine");
    expect(await screen.findByRole("heading", { name: "Pagine" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aiuto" }));
    await user.click(screen.getByRole("button", { name: "Rifai il tour" }));
    expect(await screen.findByRole("dialog", { name: "Le pagine del sito" })).toBeInTheDocument();
  });

  test("il menu Aiuto si chiude con Esc", async () => {
    const { user } = start("/admin/pagine");
    const toggle = await screen.findByRole("button", { name: "Aiuto" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Rifai il tour" })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });
});
