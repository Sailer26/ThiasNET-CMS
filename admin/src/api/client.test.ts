import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { fakeApi } from "../test/fakeApi";
import {
  ApiError,
  errorMessage,
  getCsrfToken,
  isConflict,
  onSessionExpired,
  refreshCsrf,
  request,
  setCsrfToken,
} from "./client";

describe("client delle API", () => {
  beforeEach(() => setCsrfToken(null));

  test("restituisce data e meta della busta", async () => {
    const api = fakeApi();
    api.on("GET", "/pages/tree", { data: [1], meta: { truncated: false } });
    await expect(request("GET", "/pages/tree")).resolves.toEqual({ data: [1], meta: { truncated: false } });
  });

  test("manda il token CSRF solo sulle scritture", async () => {
    const api = fakeApi();
    api.on("GET", "/auth/csrf", { data: { csrf_token: "abc" } });
    api.on("POST", "/pages", { status: 201, data: {} });
    api.on("GET", "/pages", { data: [] });
    await refreshCsrf();
    expect(getCsrfToken()).toBe("abc");
    await request("POST", "/pages", { title: "x" });
    await request("GET", "/pages");
    expect(api.callsTo("POST", "/pages")[0]?.headers["X-CSRFToken"]).toBe("abc");
    expect(api.callsTo("POST", "/pages")[0]?.body).toEqual({ title: "x" });
    expect(api.callsTo("GET", "/pages")[0]?.headers["X-CSRFToken"]).toBeUndefined();
  });

  test("dopo un errore CSRF prende un token nuovo e riprova una sola volta", async () => {
    const api = fakeApi();
    const csrf = { status: 403, error: { code: "csrf", message: "Sessione scaduta" } };
    api.on("POST", "/pages", csrf, { status: 201, data: { id: 1 } });
    api.on("GET", "/auth/csrf", { data: { csrf_token: "nuovo" } });
    setCsrfToken("vecchio");
    await expect(request("POST", "/pages", {})).resolves.toEqual({ data: { id: 1 }, meta: {} });
    expect(api.callsTo("POST", "/pages").map((c) => c.headers["X-CSRFToken"])).toEqual(["vecchio", "nuovo"]);
  });

  test("non riprova all'infinito se il CSRF fallisce ancora", async () => {
    const api = fakeApi();
    api.on("PATCH", "/pages/1", { status: 403, error: { code: "csrf", message: "Sessione scaduta" } });
    api.on("GET", "/auth/csrf", { data: { csrf_token: "t" } });
    await expect(request("PATCH", "/pages/1", {})).rejects.toMatchObject({ code: "csrf" });
    expect(api.callsTo("PATCH", "/pages/1")).toHaveLength(2);
  });

  test("un 401 avvisa che la sessione è scaduta, tranne quando si accede", async () => {
    const api = fakeApi();
    api.on("GET", "/pages", { status: 401, error: { code: "unauthorized", message: "Accesso richiesto" } });
    const listener = vi.fn();
    const stop = onSessionExpired(listener);
    await expect(request("GET", "/pages")).rejects.toBeInstanceOf(ApiError);
    await expect(request("GET", "/pages", undefined, { session: false })).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledTimes(1);
    stop();
    await expect(request("GET", "/pages")).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  test("errori leggibili: rete, troppi tentativi, conflitto, risposta non JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const offline = await request("GET", "/x").catch((e: unknown) => e);
    expect(errorMessage(offline)).toMatch(/Connessione non disponibile/);

    const api = fakeApi();
    api.on("POST", "/auth/login", {
      status: 429,
      error: { code: "rate_limited", message: "Troppe richieste" },
      headers: { "Retry-After": "120" },
    });
    const limited = await request("POST", "/auth/login", {}, { session: false }).catch((e: unknown) => e);
    expect(errorMessage(limited)).toBe("Troppi tentativi: riprova tra 2 minuti");

    api.on("PATCH", "/pages/3", {
      status: 409,
      error: {
        code: "version_conflict",
        message: "Qualcun altro…",
        details: { updated_by_name: "luca@example.ch", updated_at: "2026-10-18T09:05:00+00:00" },
      },
    });
    const conflict = await request("PATCH", "/pages/3", {}).catch((e: unknown) => e);
    expect(isConflict(conflict)).toBe(true);
    expect(errorMessage(conflict)).toMatch(/^Nel frattempo luca@example\.ch ha modificato questa pagina \(alle /);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>", { status: 502 })));
    const broken = await request("GET", "/x").catch((e: unknown) => e);
    expect(broken).toMatchObject({ status: 502, code: "server_error" });
    expect(errorMessage(new Error("boom"))).toMatch(/Si è verificato un errore/);
  });
});
