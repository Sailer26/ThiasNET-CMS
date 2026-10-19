// Impostazioni del sito e dell'aspetto (D-143): schema, valori e versione dal server.
import type { FieldSchema } from "./catalog";
import { request } from "./client";

export type SettingsScope = "site" | "appearance";
export type SettingsValues = Record<string, unknown>;

export interface SettingsSection {
  schema: FieldSchema;
  values: SettingsValues;
  version: number;
}

export async function fetchSettings(): Promise<Record<SettingsScope, SettingsSection>> {
  return (await request<Record<SettingsScope, SettingsSection>>("GET", "/settings")).data;
}

export async function storeSettings(scope: SettingsScope, version: number, values: SettingsValues): Promise<SettingsSection> {
  return (await request<SettingsSection>("PUT", `/settings/${scope}`, { version, values })).data;
}
