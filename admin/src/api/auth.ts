import { request, setCsrfToken } from "./client";
import type { Me, Site, User } from "./types";

interface TokenOnly {
  csrf_token: string;
}

export type LoginResult = { totpRequired: true } | { totpRequired: false; user: User };

export async function login(email: string, password: string): Promise<LoginResult> {
  const { data } = await request<TokenOnly & { totp_required: boolean; user?: User }>(
    "POST",
    "/auth/login",
    { email, password },
    { session: false },
  );
  setCsrfToken(data.csrf_token);
  return data.totp_required || !data.user
    ? { totpRequired: true }
    : { totpRequired: false, user: data.user };
}

export async function loginTotp(code: string): Promise<User> {
  const { data } = await request<TokenOnly & { user: User }>(
    "POST",
    "/auth/login/totp",
    { code },
    { session: false },
  );
  setCsrfToken(data.csrf_token);
  return data.user;
}

async function endSession(path: string): Promise<void> {
  const { data } = await request<TokenOnly>("POST", path, undefined, { session: false });
  setCsrfToken(data.csrf_token);
}

export const logout = (): Promise<void> => endSession("/auth/logout");
export const logoutEverywhere = (): Promise<void> => endSession("/auth/logout-all");

export async function fetchMe(options: { session?: boolean } = {}): Promise<Me> {
  return (await request<Me>("GET", "/auth/me", undefined, options)).data;
}

export async function fetchSite(): Promise<Site> {
  return (await request<Site>("GET", "/site")).data;
}
