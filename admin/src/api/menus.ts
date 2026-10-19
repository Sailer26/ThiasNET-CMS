// Menu del sito (D-140, D-141, D-145): l'albero intero si salva con la versione.
import { request } from "./client";

export interface MenuItemData {
  uid: string;
  label?: string;
  page_id?: number;
  url?: string;
  children: MenuItemData[];
}

export interface MenuInfo {
  location: string;
  label: string;
  max_depth: number;
  automatic: boolean;
  manual: boolean;
  version: number;
  items: MenuItemData[];
}

export async function fetchMenus(): Promise<MenuInfo[]> {
  return (await request<MenuInfo[]>("GET", "/menus")).data;
}

export async function storeMenu(location: string, version: number, items: MenuItemData[]): Promise<MenuInfo> {
  return (await request<MenuInfo>("PUT", `/menus/${encodeURIComponent(location)}`, { version, items })).data;
}

export async function resetMenu(location: string, version: number): Promise<MenuInfo> {
  return (await request<MenuInfo>("DELETE", `/menus/${encodeURIComponent(location)}`, { version })).data;
}
