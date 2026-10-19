import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import type { Me } from "../../api/types";
import { fakeApi, ME, signedIn, type FakeApi } from "../../test/fakeApi";

const ADMIN: Me = { ...ME, permissions: [...ME.permissions, "settings.edit"] };

function sections(siteVersion = 0, name = "Comune di Prova") {
  return {
    site: {
      version: siteVersion,
      values: { name, email: "info@prova.ch" },
      schema: {
        type: "object",
        required: ["name"],
        properties: {
          name: { type: "string", title: "Nome del sito", maxLength: 120 },
          email: { type: "string", title: "Email di contatto", maxLength: 254 },
        },
      },
    },
    appearance: {
      version: 0,
      values: { accent_color: "#0B5FFF", header_style: "light" },
      schema: {
        type: "object",
        required: [],
        properties: {
          accent_color: { type: "string", title: "Colore principale", enum: ["#0B5FFF", "#1F7A4D"], "x-color": true },
          header_style: { type: "string", title: "Stile header", enum: ["light", "dark"] },
        },
      },
    },
  };
}

function start(me: Me = ADMIN): FakeApi {
  const api = fakeApi();
  signedIn(api, me);
  api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
  window.history.replaceState(null, "", "/admin/impostazioni");
  return api;
}

describe("impostazioni (6a, D-143)", () => {
  beforeEach(() => setCsrfToken(null));

  test("dati del sito: modifica e salva con la versione", async () => {
    const api = start();
    api.on("GET", "/settings", { data: sections() });
    api.on("PUT", "/settings/site", { data: { ...sections(1, "Comune di Locarno").site } });
    const user = userEvent.setup();
    render(<App />);
    const site = await screen.findByRole("region", { name: "Dati del sito" });
    const name = within(site).getByLabelText(/Nome del sito/);
    await user.clear(name);
    await user.type(name, "Comune di Locarno");
    await user.click(within(site).getByRole("button", { name: "Salva" }));
    expect(await screen.findByText(/Impostazioni salvate/)).toBeInTheDocument();
    expect(api.callsTo("PUT", "/settings/site")[0]?.body).toEqual({
      version: 0,
      values: { name: "Comune di Locarno", email: "info@prova.ch" },
    });
    expect(screen.getByRole("link", { name: "Impostazioni" })).toHaveAttribute("aria-current", "page");
  });

  test("errori del server sotto i campi", async () => {
    const api = start();
    api.on("GET", "/settings", { data: sections() });
    api.on("PUT", "/settings/site", {
      status: 422,
      error: { code: "invalid_content", message: "Campi non validi", details: [{ path: "email", code: "invalid_email", message: "Indirizzo email non valido" }] },
    });
    const user = userEvent.setup();
    render(<App />);
    const site = await screen.findByRole("region", { name: "Dati del sito" });
    await user.click(within(site).getByRole("button", { name: "Salva" }));
    expect(await within(site).findByText("Indirizzo email non valido")).toBeInTheDocument();
  });

  test("salvate da un altro: avviso e Ricarica", async () => {
    const api = start();
    api.on("GET", "/settings", { data: sections() }, { data: sections(3, "Nome nuovo") });
    api.on("PUT", "/settings/site", {
      status: 409,
      error: { code: "version_conflict", message: "Qualcun altro ha modificato", details: { current_version: 3, updated_by_name: "Luca" } },
    });
    const user = userEvent.setup();
    render(<App />);
    const site = await screen.findByRole("region", { name: "Dati del sito" });
    await user.click(within(site).getByRole("button", { name: "Salva" }));
    await user.click(await screen.findByRole("button", { name: "Ricarica" }));
    await waitFor(() => expect(within(screen.getByRole("region", { name: "Dati del sito" })).getByLabelText(/Nome del sito/)).toHaveValue("Nome nuovo"));
  });

  test("aspetto: i colori del tema come campioni", async () => {
    const api = start();
    api.on("GET", "/settings", { data: sections() });
    api.on("PUT", "/settings/appearance", { data: { ...sections().appearance, version: 1 } });
    const user = userEvent.setup();
    render(<App />);
    const look = await screen.findByRole("region", { name: "Aspetto" });
    const green = within(look).getByRole("radio", { name: "#1F7A4D" });
    expect(green.parentElement?.querySelector(".swatch")).not.toBeNull();
    await user.click(green);
    await user.click(within(look).getByRole("button", { name: "Salva" }));
    await waitFor(() =>
      expect(api.callsTo("PUT", "/settings/appearance")[0]?.body).toEqual({
        version: 0,
        values: { accent_color: "#1F7A4D", header_style: "light" },
      }),
    );
  });

  test("un editor non vede Impostazioni e l'indirizzo diretto dice Non hai accesso", async () => {
    const api = start(ME);
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Non hai accesso a questa sezione." })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Impostazioni" })).not.toBeInTheDocument();
    expect(api.callsTo("GET", "/settings")).toHaveLength(0);
  });

  test("dopo il salvataggio il nome nuovo compare in alto; l'errore sparisce correggendo", async () => {
    const api = start();
    api.on("GET", "/settings", { data: sections() });
    api.on(
      "PUT",
      "/settings/site",
      { status: 422, error: { code: "invalid_content", message: "Campi non validi", details: [{ path: "name", code: "required", message: "Campo obbligatorio" }] } },
      { data: { ...sections(1, "Comune di Locarno").site } },
    );
    const user = userEvent.setup();
    render(<App />);
    const site = await screen.findByRole("region", { name: "Dati del sito" });
    await user.click(within(site).getByRole("button", { name: "Salva" }));
    expect(await within(site).findByText("Campo obbligatorio")).toBeInTheDocument();
    const name = within(site).getByLabelText(/Nome del sito/);
    await user.clear(name);
    await user.type(name, "Comune di Locarno");
    expect(within(site).queryByText("Campo obbligatorio")).not.toBeInTheDocument();
    await user.click(within(site).getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(document.querySelector(".shell__site")).toHaveTextContent("Comune di Locarno"));
  });
});
