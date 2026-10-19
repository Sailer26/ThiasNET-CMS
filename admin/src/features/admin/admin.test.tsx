import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test } from "vitest";
import { App } from "../../App";
import { zurichMidnight } from "../../api/admin";
import { setCsrfToken } from "../../api/client";
import type { Me, User } from "../../api/types";
import { fakeApi, ME, signedIn, type FakeApi } from "../../test/fakeApi";
import { actionLabel, diffLines } from "./actions";
import { generatePassword, GENERATED_LENGTH } from "./password";
import { setUnread } from "./unread";

const ADMIN: Me = {
  ...ME,
  permissions: [...ME.permissions, "users.manage", "messages.view"],
};
const OWNER: Me = {
  ...ME,
  id: 1,
  email: "thias@example.ch",
  role: "owner",
  permissions: [...ADMIN.permissions, "audit.view"],
};

const USERS: User[] = [
  { ...OWNER, id: 1 },
  { ...ME, id: 2 },
  {
    ...ME,
    id: 3,
    email: "luca@example.ch",
    role: "editor",
    can_publish: false,
    totp_enabled: true,
    last_login_at: "2026-10-18T08:00:00+00:00",
  },
];

const MESSAGE = {
  id: 7,
  name: "Mario Rossi",
  email: "mario@example.ch",
  phone: "+41 91 123 45 67",
  page: { id: 3, title: "Contatti", path: "/contatti", trashed: false },
  created_at: "2026-10-18T08:00:00+00:00",
  read_at: null,
  delivery: "failed",
  failure: "smtp",
  expires_at: "2027-10-18T08:00:00+00:00",
  excerpt: "Vorrei sapere gli orari",
  message: "Vorrei sapere gli orari dello sportello.\nGrazie",
};

function go(path: string) {
  act(() => {
    window.history.pushState(null, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

function start(me: Me, path: string): FakeApi {
  const api = fakeApi();
  signedIn(api, me);
  api.on("GET", "/pages/tree", { data: [], meta: { truncated: false } });
  api.on("GET", "/messages/summary", { data: { unread: 2, total: 5 } });
  window.history.replaceState(null, "", path);
  return api;
}

describe("amministrazione: menu e permessi", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("l'amministratore vede Messaggi (con il numero da leggere) e Utenti, non il Registro", async () => {
    start(ADMIN, "/admin/");
    render(<App />);
    const nav = await screen.findByRole("navigation", { name: "Menu del pannello" });
    expect(await within(nav).findByRole("link", { name: /Messaggi.*2 da leggere/ })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Utenti" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Registro" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: ME.email })).toHaveAttribute("href", "/admin/profilo");
  });

  test("l'editor non vede le sezioni e un indirizzo diretto dice Non hai accesso", async () => {
    const api = start(ME, "/admin/registro");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Non hai accesso a questa sezione." })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Messaggi/ })).not.toBeInTheDocument();
    expect(api.callsTo("GET", "/messages/summary")).toHaveLength(0);
    expect(api.callsTo("GET", "/audit")).toHaveLength(0);
  });
});

describe("messaggi", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("elenco, apertura (segnato come letto), rispondi, telefono, elimina con conferma", async () => {
    const api = start(ADMIN, "/admin/messaggi");
    api.on("GET", "/messages", { data: [MESSAGE], meta: { total: 1 } });
    api.on("GET", "/messages/7", { data: MESSAGE });
    api.on("PATCH", "/messages/7", { data: { ...MESSAGE, read_at: "2026-10-19T08:00:00+00:00" } });
    api.on("DELETE", "/messages/7", { data: null });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Email non partita")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Mario Rossi/ }));

    expect(await screen.findByRole("heading", { name: "Mario Rossi" })).toBeInTheDocument();
    expect(api.callsTo("PATCH", "/messages/7")[0]?.body).toEqual({ read: true });
    expect(screen.getByText(/leggilo qui/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Rispondi" }).getAttribute("href")).toMatch(/^mailto:mario%40example\.ch\?subject=/);
    expect(screen.getByRole("link", { name: "+41 91 123 45 67" })).toHaveAttribute("href", "tel:+41911234567");

    await user.click(screen.getByRole("button", { name: "Elimina" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("sparisce per sempre");
    await user.click(within(dialog).getByRole("button", { name: "Elimina" }));
    await waitFor(() => expect(api.callsTo("DELETE", "/messages/7")).toHaveLength(1));
    expect(await screen.findByRole("heading", { name: "Messaggi" })).toBeInTheDocument();
  });

  test("filtro Da leggere e ricerca vanno al server", async () => {
    const api = start(ADMIN, "/admin/messaggi");
    api.on("GET", "/messages", { data: [], meta: { total: 0 } });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Nessun messaggio.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Da leggere" }));
    await waitFor(() => expect(api.callsTo("GET", "/messages").at(-1)?.path).toContain("unread=1"));
    await user.type(screen.getByLabelText("Cerca per nome o email"), "mario");
    await waitFor(() => expect(api.callsTo("GET", "/messages").at(-1)?.path).toContain("q=mario"));
  });

  test("segna come da leggere torna all'elenco", async () => {
    const api = start(ADMIN, "/admin/messaggi/7");
    api.on("GET", "/messages/7", { data: { ...MESSAGE, read_at: "2026-10-19T08:00:00+00:00", delivery: "sent" } });
    api.on("PATCH", "/messages/7", { data: MESSAGE });
    api.on("GET", "/messages", { data: [MESSAGE], meta: { total: 1 } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Segna come da leggere" }));
    expect(api.callsTo("PATCH", "/messages/7")[0]?.body).toEqual({ read: false });
    expect(await screen.findByRole("heading", { name: "Messaggi" })).toBeInTheDocument();
  });
});

describe("utenti", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("l'amministratore crea un editor con la password generata", async () => {
    const api = start(ADMIN, "/admin/utenti");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("POST", "/users", { status: 201, data: { ...USERS[2], id: 9, email: "nuovo@example.ch" } });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("luca@example.ch")).toBeInTheDocument();
    // la propria riga rimanda al profilo, quella di ThiasNET non ha azioni
    expect(screen.getByRole("link", { name: "Modifica dal tuo profilo" })).toHaveAttribute("href", "/admin/profilo");
    expect(screen.queryByRole("group", { name: "Azioni per thias@example.ch" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Nuovo utente" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByLabelText("Ruolo")).not.toBeInTheDocument();
    const password = within(dialog).getByLabelText("Password iniziale");
    expect((password as HTMLInputElement).value).toHaveLength(GENERATED_LENGTH);
    await user.type(within(dialog).getByLabelText("Email"), "nuovo@example.ch");
    await user.click(within(dialog).getByLabelText("Può pubblicare"));
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    expect(await screen.findByText("Utente nuovo@example.ch creato.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/users")[0]?.body).toEqual({
      email: "nuovo@example.ch",
      password: (password as HTMLInputElement).value,
      role: "editor",
      can_publish: true,
    });
  });

  test("disattiva, nuova password e azzera il codice a 6 cifre", async () => {
    const api = start(ADMIN, "/admin/utenti");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("PATCH", "/users/3", { data: USERS[2] });
    api.on("POST", "/users/3/totp/reset", { data: null });
    const user = userEvent.setup();
    render(<App />);
    const row = await screen.findByRole("group", { name: "Azioni per luca@example.ch" });

    await user.click(within(row).getByRole("button", { name: "Disattiva" }));
    let dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("non potrà più entrare");
    await user.click(within(dialog).getByRole("button", { name: "Disattiva" }));
    await waitFor(() => expect(api.callsTo("PATCH", "/users/3")[0]?.body).toEqual({ active: false }));

    await user.click(within(row).getByRole("button", { name: "Nuova password" }));
    dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(api.callsTo("PATCH", "/users/3")).toHaveLength(2));
    expect((api.callsTo("PATCH", "/users/3")[1]?.body as { password: string }).password).toHaveLength(GENERATED_LENGTH);

    await user.click(within(row).getByRole("button", { name: "Azzera codice a 6 cifre" }));
    dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Conferma" }));
    await waitFor(() => expect(api.callsTo("POST", "/users/3/totp/reset")).toHaveLength(1));
  });

  test("email già usata: il messaggio spiega come riattivare", async () => {
    const api = start(ADMIN, "/admin/utenti");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("POST", "/users", { status: 409, error: { code: "email_taken", message: "Email già in uso." } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Nuovo utente" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Email"), "luca@example.ch");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Email già in uso. Se era disattivato, riattivalo");
  });

  test("ThiasNET sceglie il ruolo; un amministratore non ha la casella Può pubblicare", async () => {
    const api = start(OWNER, "/admin/utenti");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("POST", "/users", { status: 201, data: USERS[1] });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Nuovo utente" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Ruolo"), "admin");
    expect(within(dialog).queryByLabelText("Può pubblicare")).not.toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Email"), "capo@example.ch");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    await waitFor(() => expect(api.callsTo("POST", "/users")[0]?.body).toMatchObject({ role: "admin", can_publish: false }));
  });
});

describe("registro attività", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("righe con etichette, dettagli come testo, filtri al server", async () => {
    const api = start(OWNER, "/admin/registro");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("GET", "/audit", {
      data: [
        {
          id: 1,
          user_id: 2,
          actor_email: "anna@example.ch",
          action: "page.published",
          entity: "page",
          entity_id: "3",
          entity_label: "Contatti",
          diff: { title: ["Vecchio", "<b>Nuovo</b>"] },
          created_at: "2026-10-18T08:00:00+00:00",
        },
      ],
      meta: { total: 1 },
    });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText(/Pagina pubblicata/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contatti" })).toHaveAttribute("href", "/admin/pagine/3");
    expect(screen.getByText("title: Vecchio → <b>Nuovo</b>")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Tipo"), "pages");
    await waitFor(() => expect(api.callsTo("GET", "/audit").at(-1)?.path).toContain("category=pages"));
    await user.selectOptions(screen.getByLabelText("Chi"), "2");
    await waitFor(() => expect(api.callsTo("GET", "/audit").at(-1)?.path).toContain("user_id=2"));
    await user.click(screen.getByRole("button", { name: "Solo questo oggetto" }));
    await waitFor(() => expect(api.callsTo("GET", "/audit").at(-1)?.path).toContain("entity=page&entity_id=3"));
  });

  test("etichette: un'azione sconosciuta resta com'è; i dettagli non sono HTML", () => {
    expect(actionLabel("page.published")).toBe("Pagina pubblicata");
    expect(actionLabel("qualcosa.nuovo")).toBe("qualcosa.nuovo");
    expect(diffLines(null)).toEqual([]);
    expect(diffLines({ role: ["editor", "admin"], extra: { a: 1 } })).toEqual(["role: editor → admin", 'extra: {"a":1}']);
  });
});

describe("profilo", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("password attuale sbagliata: errore sotto i campi, nessun nuovo accesso (D-127)", async () => {
    const api = start(ME, "/admin/profilo");
    api.on("POST", "/auth/password", {
      status: 401,
      error: { code: "invalid_password", message: "La password attuale non è corretta" },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByLabelText("Password attuale"), "sbagliata");
    await user.type(screen.getByLabelText(/^Nuova password/), "una-nuova-password");
    await user.type(screen.getByLabelText("Ripeti la nuova password"), "una-nuova-password");
    await user.click(screen.getByRole("button", { name: "Cambia password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La password attuale non è corretta");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.callsTo("POST", "/auth/password")[0]?.body).toEqual({
      current_password: "sbagliata",
      new_password: "una-nuova-password",
    });
  });

  test("le due password nuove devono essere uguali", async () => {
    const api = start(ME, "/admin/profilo");
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByLabelText("Password attuale"), "attuale");
    await user.type(screen.getByLabelText(/^Nuova password/), "una-nuova-password");
    await user.type(screen.getByLabelText("Ripeti la nuova password"), "un-altra-password");
    await user.click(screen.getByRole("button", { name: "Cambia password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("non sono uguali");
    expect(api.callsTo("POST", "/auth/password")).toHaveLength(0);
  });

  test("attiva il codice a 6 cifre: chiave, link per l'app, codice e password", async () => {
    const api = start(ME, "/admin/profilo");
    api.on("POST", "/auth/totp/setup", {
      data: { secret: "JBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/ThiasNET:anna?secret=JBSWY3DPEHPK3PXP" },
    });
    api.on("POST", "/auth/totp/enable", { data: null });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Non attivo.");
    api.on("GET", "/auth/me", { data: { ...ME, totp_enabled: true } });
    await user.click(screen.getByRole("button", { name: "Attiva" }));
    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Apri nell'app di autenticazione" }).getAttribute("href")).toMatch(/^otpauth:\/\//);
    await user.type(screen.getByLabelText("Codice di 6 cifre"), "123456");
    await user.type(screen.getByLabelText("La tua password"), "segreta-lunga");
    await user.click(screen.getByRole("button", { name: "Attiva" }));
    expect(await screen.findByText("Codice a 6 cifre attivato.")).toBeInTheDocument();
    expect(api.callsTo("POST", "/auth/totp/enable")[0]?.body).toEqual({ code: "123456", password: "segreta-lunga" });
    expect(screen.getByText(/Attivo: ad ogni accesso/)).toBeInTheDocument();
  });

  test("esci da tutti i dispositivi chiede conferma", async () => {
    const api = start(ME, "/admin/profilo");
    api.on("POST", "/auth/logout-all", { data: { csrf_token: "t2" } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Esci da tutti i dispositivi" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Verrai disconnesso da tutti");
    await user.click(within(dialog).getByRole("button", { name: "Esci da tutti i dispositivi" }));
    expect(await screen.findByRole("heading", { name: "Accedi al pannello" })).toBeInTheDocument();
    expect(api.callsTo("POST", "/auth/logout-all")).toHaveLength(1);
  });
});

describe("password generata", () => {
  test("16 caratteri, senza lettere ambigue, ogni volta diversa", () => {
    const first = generatePassword();
    expect(first).toHaveLength(GENERATED_LENGTH);
    expect(first).toMatch(/^[A-HJ-NP-Za-km-z2-9_-]+$/);
    expect(generatePassword()).not.toBe(first);
  });
});

test("navigazione: dal menu ai messaggi", async () => {
  setCsrfToken(null);
  const api = start(ADMIN, "/admin/");
  api.on("GET", "/messages", { data: [], meta: { total: 0 } });
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("link", { name: /Messaggi/ }));
  expect(await screen.findByRole("heading", { name: "Messaggi" })).toHaveFocus();
  expect(document.title).toBe("Messaggi · Comune di Prova · ThiasNET CMS");
  go("/admin/");
});

describe("correzioni dalla review", () => {
  beforeEach(() => {
    setCsrfToken(null);
    setUnread(0);
  });

  test("se segnarlo come letto non riesce, il messaggio si legge lo stesso", async () => {
    const api = start(ADMIN, "/admin/messaggi/7");
    api.on("GET", "/messages/7", { data: MESSAGE });
    api.on("PATCH", "/messages/7", { status: 500, error: { code: "server_error", message: "Errore del server" } });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Mario Rossi" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Errore del server");
    expect(screen.getByText(/Vorrei sapere gli orari dello sportello/)).toBeInTheDocument();
  });

  test("Mostra altri non ripete un messaggio già in elenco", async () => {
    const api = start(ADMIN, "/admin/messaggi");
    const second = { ...MESSAGE, id: 8, name: "Lia Bassi" };
    api.on(
      "GET",
      "/messages",
      { data: [MESSAGE], meta: { total: 3 } },
      { data: [MESSAGE, second], meta: { total: 3 } },
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Mostra altri" }));
    expect(await screen.findByText(/Lia Bassi/)).toBeInTheDocument();
    expect(screen.getAllByText(/Mario Rossi/)).toHaveLength(1);
  });

  test("elenco non caricato: Riprova al posto del caricamento infinito", async () => {
    const api = start(OWNER, "/admin/registro");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on(
      "GET",
      "/audit",
      { status: 500, error: { code: "server_error", message: "Errore del server" } },
      { data: [], meta: { total: 0 } },
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Nessuna attività con questi filtri.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("i giorni del registro sono svizzeri: mezzanotte di Zurigo, 'al' comprende il giorno", async () => {
    expect(zurichMidnight("2026-10-19")).toBe("2026-10-19T00:00:00+02:00");
    expect(zurichMidnight("2026-10-24", true)).toBe("2026-10-25T00:00:00+02:00");
    expect(zurichMidnight("2026-12-31", true)).toBe("2027-01-01T00:00:00+01:00");
    expect(zurichMidnight("ieri")).toBeUndefined();

    const api = start(OWNER, "/admin/registro");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("GET", "/audit", { data: [], meta: { total: 0 } });
    render(<App />);
    await screen.findByText("Nessuna attività con questi filtri.");
    fireEvent.change(screen.getByLabelText("Dal"), { target: { value: "2026-10-19" } });
    fireEvent.change(screen.getByLabelText("Al"), { target: { value: "2026-10-19" } });
    await waitFor(() => {
      const query = new URLSearchParams(api.callsTo("GET", "/audit").at(-1)?.path.split("?")[1]);
      expect(query.get("since")).toBe("2026-10-19T00:00:00+02:00");
      expect(query.get("until")).toBe("2026-10-20T00:00:00+02:00");
    });
  });

  test("un elenco con una forma sbagliata è un errore, non un elenco vuoto", async () => {
    const api = start(ADMIN, "/admin/utenti");
    api.on("GET", "/users", { data: { non: "un elenco" } });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Si è verificato un errore");
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });

  test("registro: 'Dal' dopo 'Al' si segnala senza chiedere al server", async () => {
    const api = start(OWNER, "/admin/registro");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    api.on("GET", "/audit", { data: [], meta: { total: 0 } });
    render(<App />);
    await screen.findByText("Nessuna attività con questi filtri.");
    fireEvent.change(screen.getByLabelText("Dal"), { target: { value: "2026-10-20" } });
    await waitFor(() => expect(api.callsTo("GET", "/audit").at(-1)?.path).toContain("since="));
    const before = api.callsTo("GET", "/audit").length;
    fireEvent.change(screen.getByLabelText("Al"), { target: { value: "2026-10-19" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("viene dopo");
    expect(api.callsTo("GET", "/audit")).toHaveLength(before);
  });

  test("utenti: ruolo e permesso di pubblicare spiegati accanto ai campi", async () => {
    const api = start(OWNER, "/admin/utenti");
    api.on("GET", "/users", { data: USERS, meta: { total: 3 } });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Nuovo utente" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Ruolo")).toHaveAccessibleDescription(/gestisce anche utenti e messaggi/);
    expect(within(dialog).getByLabelText("Può pubblicare")).toHaveAccessibleDescription(/qualcun altro le pubblica/);
  });
});
