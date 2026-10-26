// Unico punto per le chiamate a /api/admin: busta {success, data, error, meta}, token CSRF
// solo in memoria, un nuovo tentativo dopo un errore CSRF, evento di sessione scaduta (D-90).
import { it } from "../text/it";
import type { ConflictDetails } from "./types";

export const API_BASE = "/api/admin";
const WRITES = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const SECONDS_PER_MINUTE = 60;

export type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface Envelope<T> {
  success: boolean;
  data: T;
  error: { code: string; message: string; details?: unknown } | null;
  meta?: Record<string, unknown>;
}

export interface ApiResult<T> {
  data: T;
  meta: Record<string, unknown>;
}

export interface RequestOptions {
  /** false per accesso e controllo iniziale: un 401 lì non è una sessione scaduta. */
  session?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly retryAfter: number | undefined;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

let csrfToken: string | null = null;
const expiredListeners = new Set<() => void>();

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export function onSessionExpired(listener: () => void): () => void {
  expiredListeners.add(listener);
  return () => {
    expiredListeners.delete(listener);
  };
}

async function send(method: Method, path: string, body: unknown): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const form = body instanceof FormData; // file da caricare: il browser mette da sé il tipo multipart
  if (body !== undefined && !form) headers["Content-Type"] = "application/json";
  if (WRITES.has(method) && csrfToken) headers["X-CSRFToken"] = csrfToken;
  try {
    return await fetch(API_BASE + path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network", it.errors.network);
  }
}

async function envelope<T>(response: Response): Promise<Envelope<T> | null> {
  try {
    return (await response.json()) as Envelope<T>;
  } catch {
    return null;
  }
}

function retryAfter(response: Response): number | undefined {
  const seconds = Number(response.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined;
}

export async function refreshCsrf(): Promise<void> {
  const { data } = await request<{ csrf_token: string }>("GET", "/auth/csrf", undefined, {
    session: false,
  });
  csrfToken = data.csrf_token;
}

export async function request<T>(
  method: Method,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<ApiResult<T>> {
  let response = await send(method, path, body);
  let payload = await envelope<T>(response);
  if (response.status === 403 && payload?.error?.code === "csrf" && WRITES.has(method)) {
    await refreshCsrf(); // token scaduto con la sessione: uno nuovo e un solo nuovo tentativo
    response = await send(method, path, body);
    payload = await envelope<T>(response);
  }
  if (response.ok && payload?.success) {
    return { data: payload.data, meta: payload.meta ?? {} };
  }
  // D-127: solo "unauthorized" è una sessione scaduta; password o codice sbagliati no.
  if (response.status === 401 && options.session !== false && payload?.error?.code === "unauthorized") {
    expiredListeners.forEach((listener) => listener());
  }
  const error = payload?.error;
  throw new ApiError(
    response.status,
    error?.code ?? "server_error",
    error?.message ?? it.errors.generic,
    error?.details,
    retryAfter(response),
  );
}

function clock(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("it-CH", { hour: "2-digit", minute: "2-digit" });
}

export function isConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "version_conflict";
}

/** Aggiunge la lingua del pannello (D-159) a un indirizzo dell'API. */
export function localized(path: string, locale: string): string {
  return `${path}${path.includes("?") ? "&" : "?"}locale=${encodeURIComponent(locale)}`;
}

/** Il messaggio da mostrare all'utente: quello del server, già in italiano. */
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return it.errors.generic;
  if (error.status === 429 && error.retryAfter) {
    return it.errors.rateLimited(Math.max(1, Math.ceil(error.retryAfter / SECONDS_PER_MINUTE)));
  }
  if (error.code === "version_conflict") {
    const details = (error.details ?? {}) as Partial<ConflictDetails>;
    return it.errors.conflict(details.updated_by_name ?? "un altro utente", clock(details.updated_at ?? null));
  }
  return error.message;
}
