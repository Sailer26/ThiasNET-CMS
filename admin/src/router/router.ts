// Router minimo sulla History API (D-89: meno di 10 schermate, niente libreria).
import { useMemo, useSyncExternalStore } from "react";

export type Route =
  | { name: "pages" }
  | { name: "page"; id: number }
  | { name: "trash" }
  | { name: "media" }
  | { name: "not-found" };

export const paths = {
  pages: "/admin/pagine",
  trash: "/admin/cestino",
  media: "/admin/media",
  page: (id: number) => `/admin/pagine/${id}`,
} as const;

const PAGE_RE = /^\/admin\/pagine\/(\d+)$/;

export function parseRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "");
  if (path === "/admin" || path === paths.pages) return { name: "pages" };
  if (path === paths.trash) return { name: "trash" };
  if (path === paths.media) return { name: "media" };
  const page = PAGE_RE.exec(path);
  if (page) return { name: "page", id: Number(page[1]) };
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
