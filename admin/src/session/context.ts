import { createContext, useContext } from "react";
import type { Me, Site } from "../api/types";
import type { PermissionName } from "./can";

export interface Session {
  user: Me;
  site: Site;
  /** Cresce dopo un nuovo accesso: le schermate ricaricano i loro dati. */
  reloadKey: number;
  can: (permission: PermissionName) => boolean;
  logout: () => Promise<void>;
  logoutEverywhere: () => Promise<void>;
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession fuori da SessionProvider");
  return session;
}
