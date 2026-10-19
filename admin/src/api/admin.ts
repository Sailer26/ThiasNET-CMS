// Amministrazione (5c-2): messaggi, utenti, registro, profilo.
import { request, setCsrfToken } from "./client";
import type { Role, User } from "./types";

export const ADMIN_PAGE_SIZE = 25;
export const AUDIT_PAGE_SIZE = 50;

// --- Messaggi del modulo contatti (D-126) -------------------------------------------------
export interface MessagePage {
  id: number;
  title: string;
  path: string;
  trashed: boolean;
}

export interface MessageSummary {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  page: MessagePage | null;
  created_at: string;
  read_at: string | null;
  delivery: "sent" | "pending" | "failed";
  failure: string | null;
  expires_at: string;
  excerpt?: string;
  message?: string;
}

export interface Listing<T> {
  items: T[];
  total: number;
}

export async function listMessages(options: { q?: string; unread?: boolean; page?: number }): Promise<Listing<MessageSummary>> {
  const params = new URLSearchParams({ page: String(options.page ?? 1), limit: String(ADMIN_PAGE_SIZE) });
  if (options.q) params.set("q", options.q);
  if (options.unread) params.set("unread", "1");
  const { data, meta } = await request<MessageSummary[]>("GET", `/messages?${params.toString()}`);
  return { items: data, total: typeof meta.total === "number" ? meta.total : data.length };
}

export async function messagesSummary(): Promise<{ unread: number; total: number }> {
  return (await request<{ unread: number; total: number }>("GET", "/messages/summary")).data;
}

export async function getMessage(id: number): Promise<MessageSummary> {
  return (await request<MessageSummary>("GET", `/messages/${id}`)).data;
}

export async function markMessage(id: number, read: boolean): Promise<MessageSummary> {
  return (await request<MessageSummary>("PATCH", `/messages/${id}`, { read })).data;
}

export async function deleteMessage(id: number): Promise<void> {
  await request("DELETE", `/messages/${id}`);
}

// --- Utenti (D-123) -------------------------------------------------------------------------
export async function listUsers(page = 1): Promise<Listing<User>> {
  const { data, meta } = await request<User[]>("GET", `/users?page=${page}&limit=100`);
  return { items: data, total: typeof meta.total === "number" ? meta.total : data.length };
}

export async function createUser(body: { email: string; password: string; role: Exclude<Role, "owner">; can_publish: boolean }): Promise<User> {
  return (await request<User>("POST", "/users", body)).data;
}

export async function updateUser(
  id: number,
  changes: { email?: string; password?: string; role?: Exclude<Role, "owner">; active?: boolean; can_publish?: boolean },
): Promise<User> {
  return (await request<User>("PATCH", `/users/${id}`, changes)).data;
}

export async function resetTotp(id: number): Promise<void> {
  await request("POST", `/users/${id}/totp/reset`);
}

// --- Registro (D-124) -----------------------------------------------------------------------
export interface AuditEntry {
  id: number;
  user_id: number | null;
  actor_email: string | null;
  action: string;
  entity: string | null;
  entity_id: string | null;
  entity_label: string | null;
  diff: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditQuery {
  user_id?: number | undefined;
  category?: string | undefined;
  entity?: string | undefined;
  entity_id?: string | undefined;
  since?: string | undefined;
  until?: string | undefined;
  page?: number | undefined;
}

export async function listAudit(query: AuditQuery): Promise<Listing<AuditEntry>> {
  const params = new URLSearchParams({ page: String(query.page ?? 1), limit: String(AUDIT_PAGE_SIZE) });
  for (const key of ["user_id", "category", "entity", "entity_id", "since", "until"] as const) {
    const value = query[key];
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const { data, meta } = await request<AuditEntry[]>("GET", `/audit?${params.toString()}`);
  return { items: data, total: typeof meta.total === "number" ? meta.total : data.length };
}

// --- Profilo (D-125) ------------------------------------------------------------------------
export async function changePassword(current: string, next: string): Promise<void> {
  const { data } = await request<{ csrf_token: string }>("POST", "/auth/password", {
    current_password: current,
    new_password: next,
  });
  setCsrfToken(data.csrf_token);
}

export async function totpSetup(): Promise<{ secret: string; otpauth_uri: string }> {
  return (await request<{ secret: string; otpauth_uri: string }>("POST", "/auth/totp/setup")).data;
}

export async function totpEnable(code: string, password: string): Promise<void> {
  await request("POST", "/auth/totp/enable", { code, password });
}

export async function totpDisable(code: string, password: string): Promise<void> {
  await request("POST", "/auth/totp/disable", { code, password });
}
