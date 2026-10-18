import { useEffect, useRef, useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import { Link } from "../router/Link";
import { paths, useRoute } from "../router/router";
import { useSession } from "../session/context";
import { it } from "../text/it";
import { FormDialog } from "../ui/FormDialog";
import { NoticeArea } from "../ui/Notice";
import { Logo } from "./Logo";

export function AppShell({ children }: { children: ReactNode }) {
  const { site, user, logout, logoutEverywhere } = useSession();
  const route = useRoute();
  const [confirmAll, setConfirmAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const firstRoute = useRef(true);
  const current = (name: string) => (route.name === name ? "page" : undefined);

  // Cambio di schermata: titolo della scheda e focus sul titolo, così chi usa un lettore
  // di schermo sa dove si trova (non al primo caricamento).
  useEffect(() => {
    const titles: Record<string, string> = {
      pages: it.titles.pages,
      trash: it.titles.trash,
      media: it.titles.media,
      page: it.titles.page,
      "not-found": it.titles.notFound,
    };
    document.title = `${titles[route.name] ?? it.brand} · ${site.name} · ${it.brand}`;
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
          <Link to={paths.pages} aria-current={current("pages")}>
            {it.shell.pages}
          </Link>
          <Link to={paths.media} aria-current={current("media")}>
            {it.shell.media}
          </Link>
          <Link to={paths.trash} aria-current={current("trash")}>
            {it.shell.trash}
          </Link>
        </nav>
        <div className="shell__account">
          <a className="button button--ghost" href={site.url} target="_blank" rel="noopener noreferrer">
            {it.shell.openSite}
          </a>
          <span className="shell__user">{user.email}</span>
          <button type="button" className="button button--ghost" onClick={exit} disabled={leaving}>
            {it.shell.logout}
          </button>
          <button type="button" className="button button--ghost" onClick={() => setConfirmAll(true)}>
            {it.shell.logoutAll}
          </button>
        </div>
      </header>
      <NoticeArea
        notice={error ? { kind: "error", text: error } : null}
        onClose={() => setError(null)}
      />
      <main className="shell__main">{children}</main>
      {confirmAll && (
        <FormDialog
          title={it.shell.logoutAll}
          submitLabel={it.shell.logoutAll}
          danger
          onSubmit={logoutEverywhere}
          onClose={() => setConfirmAll(false)}
        >
          <p>{it.shell.logoutAllConfirm}</p>
        </FormDialog>
      )}
    </div>
  );
}
