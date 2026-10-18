import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fetchMe, fetchSite, logout, logoutEverywhere } from "../api/auth";
import { ApiError, errorMessage, onSessionExpired, refreshCsrf } from "../api/client";
import type { Me, Site } from "../api/types";
import { browser } from "../router/router";
import { it } from "../text/it";
import { Dialog } from "../ui/Dialog";
import { Logo } from "../shell/Logo";
import type { PermissionName } from "./can";
import { SessionContext, type Session } from "./context";
import { LoginForm } from "./LoginForm";

/** Dopo tanto tempo con la finestra nascosta si controlla la sessione al ritorno (D-90). */
export const STALE_AFTER_MS = 15 * 60 * 1000;

type State =
  | { status: "loading" }
  | { status: "failed"; message: string }
  | { status: "anonymous" }
  | { status: "ready"; user: Me; site: Site };

async function loadSession(): Promise<{ user: Me; site: Site }> {
  const user = await fetchMe({ session: false });
  const site = await fetchSite();
  return { user, site };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [expired, setExpired] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const userEmail = state.status === "ready" ? state.user.email : null;
  const emailRef = useRef(userEmail);
  useEffect(() => {
    emailRef.current = userEmail;
  }, [userEmail]);

  const enter = useCallback(async () => {
    setState({ status: "ready", ...(await loadSession()) });
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await refreshCsrf();
        const loaded = await loadSession();
        if (active) setState({ status: "ready", ...loaded });
      } catch (error) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setState({ status: "anonymous" });
        else setState({ status: "failed", message: errorMessage(error) });
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => onSessionExpired(() => setExpired(emailRef.current !== null)), []);

  useEffect(() => {
    if (userEmail === null) return;
    let hiddenAt: number | null = null;
    function check() {
      if (document.visibilityState === "hidden") {
        hiddenAt = Date.now();
        return;
      }
      if (hiddenAt !== null && Date.now() - hiddenAt > STALE_AFTER_MS) {
        // Un 401 apre la finestra di nuovo accesso; gli altri errori si vedranno alla prossima azione.
        fetchMe().catch(() => undefined);
      }
      hiddenAt = null;
    }
    document.addEventListener("visibilitychange", check);
    return () => document.removeEventListener("visibilitychange", check);
  }, [userEmail]);

  const reenter = useCallback(async () => {
    const loaded = await loadSession();
    if (loaded.user.email !== emailRef.current) {
      browser.reload(); // è entrato un altro utente: niente dati del precedente sullo schermo
      return;
    }
    setState({ status: "ready", ...loaded });
    setExpired(false);
    setReloadKey((key) => key + 1);
  }, []);

  const leave = useCallback(async (end: () => Promise<void>) => {
    try {
      await end();
    } catch (error) {
      // Sessione già scaduta: si è comunque fuori, si va all'accesso.
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    setExpired(false);
    setState({ status: "anonymous" });
  }, []);

  const session = useMemo<Session | null>(() => {
    if (state.status !== "ready") return null;
    const permissions = new Set(state.user.permissions);
    return {
      user: state.user,
      site: state.site,
      reloadKey,
      can: (permission: PermissionName) => permissions.has(permission),
      logout: () => leave(logout),
      logoutEverywhere: () => leave(logoutEverywhere),
    };
  }, [state, reloadKey, leave]);

  if (state.status === "loading") {
    return (
      <main className="boot">
        <p role="status">{it.loading}</p>
      </main>
    );
  }
  if (state.status === "failed") {
    return (
      <main className="boot">
        <h1>{it.brand}</h1>
        <p role="alert">{state.message}</p>
        <button type="button" className="button" onClick={browser.reload}>
          {it.retry}
        </button>
      </main>
    );
  }
  if (state.status === "anonymous" || session === null) {
    return (
      <main className="login">
        <div className="login__card">
          <Logo />
          <h1>{it.login.title}</h1>
          <LoginForm onLoggedIn={enter} />
        </div>
      </main>
    );
  }
  return (
    <SessionContext.Provider value={session}>
      {children}
      {expired && (
        <Dialog title={it.login.expiredTitle} onClose={() => undefined} opaque>
          <p className="hint">{it.login.expiredHelp}</p>
          <LoginForm initialEmail={session.user.email} lockEmail onLoggedIn={reenter} />
        </Dialog>
      )}
    </SessionContext.Provider>
  );
}
