import { useEffect, useRef, useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import { refreshUnread, useUnread } from "../features/admin/unread";
import { Link } from "../router/Link";
import { paths, useRoute } from "../router/router";
import { Permission } from "../session/can";
import { useSession } from "../session/context";
import { it } from "../text/it";
import { NoticeArea } from "../ui/Notice";
import { Logo } from "./Logo";

const TITLES: Record<string, string> = {
  pages: it.titles.pages,
  trash: it.titles.trash,
  media: it.titles.media,
  page: it.titles.page,
  messages: it.titles.messages,
  message: it.titles.message,
  users: it.titles.users,
  audit: it.titles.audit,
  profile: it.titles.profile,
  "not-found": it.titles.notFound,
};

/** Numero dei messaggi da leggere: all'avvio e quando la finestra torna visibile (D-126). */
function useUnreadCount(enabled: boolean): number {
  const unread = useUnread();
  useEffect(() => {
    if (!enabled) return;
    void refreshUnread();
    const onVisible = () => {
      if (document.visibilityState === "visible") void refreshUnread();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [enabled]);
  return enabled ? unread : 0;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { site, user, logout, can } = useSession();
  const route = useRoute();
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const firstRoute = useRef(true);
  const showMessages = can(Permission.messagesView);
  const unread = useUnreadCount(showMessages);
  const current = (...names: string[]) => (names.includes(route.name) ? "page" : undefined);

  // Cambio di schermata: titolo della scheda e focus sul titolo, così chi usa un lettore
  // di schermo sa dove si trova (non al primo caricamento).
  useEffect(() => {
    document.title = `${TITLES[route.name] ?? it.brand} · ${site.name} · ${it.brand}`;
    if (firstRoute.current) {
      firstRoute.current = false;
      return;
    }
    document.querySelector<HTMLElement>("main h1")?.focus();
  }, [route, site.name]);

  function exit() {
    if (leaving) return;
    setLeaving(true);
    setError(null);
    logout().catch((failure: unknown) => {
      setError(errorMessage(failure));
      setLeaving(false);
    });
  }

  return (
    <div className="shell">
      <header className="shell__header">
        <div className="shell__brand">
          <Logo />
          <span className="shell__site">{site.name}</span>
        </div>
        <nav className="shell__nav" aria-label={it.shell.nav}>
          <Link to={paths.pages} aria-current={current("pages", "page")}>
            {it.shell.pages}
          </Link>
          <Link to={paths.media} aria-current={current("media")}>
            {it.shell.media}
          </Link>
          <Link to={paths.trash} aria-current={current("trash")}>
            {it.shell.trash}
          </Link>
          {showMessages && (
            <Link to={paths.messages} aria-current={current("messages", "message")}>
              {it.shell.messages}
              {unread > 0 && (
                <span className="shell__count">
                  <span aria-hidden="true">{unread}</span>
                  <span className="visually-hidden">{it.shell.unread(unread)}</span>
                </span>
              )}
            </Link>
          )}
          {can(Permission.usersManage) && (
            <Link to={paths.users} aria-current={current("users")}>
              {it.shell.users}
            </Link>
          )}
          {can(Permission.auditView) && (
            <Link to={paths.audit} aria-current={current("audit")}>
              {it.shell.audit}
            </Link>
          )}
        </nav>
        <div className="shell__account">
          <a className="button button--ghost" href={site.url} target="_blank" rel="noopener noreferrer">
            {it.shell.openSite}
          </a>
          <Link className="shell__user" to={paths.profile} aria-current={current("profile")} title={it.shell.profile}>
            {user.email}
          </Link>
          <button type="button" className="button button--ghost" onClick={exit} disabled={leaving}>
            {it.shell.logout}
          </button>
        </div>
      </header>
      <NoticeArea notice={error ? { kind: "error", text: error } : null} onClose={() => setError(null)} />
      <main className="shell__main">{children}</main>
    </div>
  );
}
