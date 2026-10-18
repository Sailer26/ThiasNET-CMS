// fetch finto per i test: risposte nella busta del server, registro delle chiamate.
import { vi } from "vitest";
import type { Me, PageNode, Site } from "../api/types";

export interface FakeResponse {
  status?: number;
  data?: unknown;
  error?: { code: string; message: string; details?: unknown };
  meta?: Record<string, unknown>;
  headers?: Record<string, string>;
}

export interface Call {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
}

type Handler = FakeResponse | ((call: Call) => FakeResponse);

export interface FakeApi {
  calls: Call[];
  on: (method: string, path: string, ...responses: Handler[]) => void;
  callsTo: (method: string, path: string) => Call[];
}

export function fakeApi(): FakeApi {
  const routes = new Map<string, Handler[]>();
  const calls: Call[] = [];
  const respond = (response: FakeResponse) => {
    const status = response.status ?? 200;
    const ok = status < 400;
    const body = {
      success: ok,
      data: ok ? (response.data ?? null) : null,
      error: ok ? null : (response.error ?? { code: "error", message: "Errore" }),
      ...(response.meta ? { meta: response.meta } : {}),
    };
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json", ...response.headers },
    });
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const path = String(input).replace("/api/admin", "");
      const call: Call = {
        method,
        path,
        body: init.body ? JSON.parse(String(init.body)) : undefined,
        headers: (init.headers ?? {}) as Record<string, string>,
      };
      calls.push(call);
      const key = `${method} ${path.split("?")[0]}`;
      const queue = routes.get(key);
      if (!queue || queue.length === 0) throw new Error(`fetch non previsto: ${key}`);
      const handler = queue.length > 1 ? queue.shift()! : queue[0]!;
      return respond(typeof handler === "function" ? handler(call) : handler);
    }),
  );
  return {
    calls,
    on: (method, path, ...responses) => routes.set(`${method} ${path}`, responses),
    callsTo: (method, path) => calls.filter((c) => c.method === method && c.path.split("?")[0] === path),
  };
}

export const ME: Me = {
  id: 2,
  email: "anna@example.ch",
  role: "admin",
  active: true,
  can_publish: true,
  totp_enabled: false,
  last_login_at: null,
  tour_completed_at: null,
  created_at: "2026-10-01T08:00:00+00:00",
  permissions: ["content.edit", "content.publish", "profile", "users.view"],
};

export const SITE: Site = {
  name: "Comune di Prova",
  url: "https://www.prova.ch",
  locales: ["it", "de"],
  default_locale: "it",
  default_layout: "page",
  home_layout: "home",
};

let nextId = 100;

export function node(title: string, extra: Partial<PageNode> = {}): PageNode {
  const id = extra.id ?? nextId++;
  const slug = extra.slug ?? title.toLowerCase().replace(/\s+/g, "-");
  return {
    id,
    parent_id: null,
    locale: "it",
    slug,
    path: `/${slug}`,
    is_home: false,
    title,
    layout: "page",
    status: "draft",
    publish_at: null,
    published_at: null,
    sort: 0,
    version: 1,
    has_draft: false,
    updated_at: null,
    updated_by: null,
    deleted_at: null,
    children: [],
    ...extra,
  };
}

/** Sessione pronta: csrf, me e site rispondono. */
export function signedIn(api: FakeApi, me: Me = ME): void {
  api.on("GET", "/auth/csrf", { data: { csrf_token: "tok-1" } });
  api.on("GET", "/auth/me", { data: me });
  api.on("GET", "/site", { data: SITE });
}
