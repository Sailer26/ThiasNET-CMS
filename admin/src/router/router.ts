// Router minimo sulla History API (D-89: meno di 10 schermate, niente libreria).
import { useMemo, useSyncExternalStore } from "react";

export type Route =
  | { name: "pages" }
  | { name: "page"; id: number }
  | { name: "trash" }
  | { name: "media" }
  | { name: "messages" }
  | { name: "message"; id: number }
  | { name: "users" }
  | { name: "audit" }
  | { name: "profile" }
  | { name: "settings" }
  | { name: "menus" }
  | { name: "widgets" }
  | { name: "entries"; collection: string }
  | { name: "entry"; collection: string; id: number }
  | { name: "not-found" };

export const paths = {
  pages: "/admin/pagine",
  trash: "/admin/cestino",
  media: "/admin/media",
  page: (id: number) => `/admin/pagine/${id}`,
  messages: "/admin/messaggi",
  message: (id: number) => `/admin/messaggi/${id}`,
  users: "/admin/utenti",
  audit: "/admin/registro",
  profile: "/admin/profilo",
  settings: "/admin/impostazioni",
  menus: "/admin/menu",
  widgets: "/admin/widget",
  entries: (collection: string) => `/admin/raccolte/${collection}`,
  entry: (collection: string, id: number) => `/admin/raccolte/${collection}/${id}`,
} as const;

const PAGE_RE = /^\/admin\/pagine\/(\d{1,9})$/;
const MESSAGE_RE = /^\/admin\/messaggi\/(\d{1,9})$/;
const ENTRIES_RE = /^\/admin\/raccolte\/([a-z][a-z0-9_]{0,63})(?:\/(\d{1,9}))?$/;
const SIMPLE: Record<string, Route> = {
  [paths.trash]: { name: "trash" },
  [paths.media]: { name: "media" },
  [paths.messages]: { name: "messages" },
  [paths.users]: { name: "users" },
  [paths.audit]: { name: "audit" },
  [paths.profile]: { name: "profile" },
  [paths.settings]: { name: "settings" },
  [paths.menus]: { name: "menus" },
  [paths.widgets]: { name: "widgets" },
};

export function parseRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "");
  if (path === "/admin" || path === paths.pages) return { name: "pages" };
  const simple = SIMPLE[path];
  if (simple) return simple;
  const page = PAGE_RE.exec(path);
  if (page) return { name: "page", id: Number(page[1]) };
  const message = MESSAGE_RE.exec(path);
  if (message) return { name: "message", id: Number(message[1]) };
  const entries = ENTRIES_RE.exec(path);
  if (entries) {
    const collection = entries[1]!;
    return entries[2] ? { name: "entry", collection, id: Number(entries[2]) } : { name: "entries", collection };
  }
  return { name: "not-found" };
}

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

type Guard = () => Promise<boolean>;
let guard: Guard | null = null;

/** Una schermata (l'editor) può chiedere di finire qualcosa prima di uscire (D-104). */
export function setNavigationGuard(next: Guard | null): void {
  guard = next;
}

export async function navigate(to: string): Promise<void> {
  if (to === window.location.pathname) return;
  if (guard && !(await guard())) return;
  window.history.pushState(null, "", to);
  listeners.forEach((listener) => listener());
}

export function useRoute(): Route {
  const pathname = useSyncExternalStore(subscribe, () => window.location.pathname);
  return useMemo(() => parseRoute(pathname), [pathname]);
}

/** Ricarica completa (cambio di utente): in una funzione sola per poterla sostituire nei test. */
export const browser = {
  reload: (): void => window.location.reload(),
};
