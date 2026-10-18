import { useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import { Link } from "../router/Link";
import { paths, useRoute } from "../router/router";
import { useSession } from "../session/context";
import { it } from "../text/it";
import { FormDialog } from "../ui/FormDialog";
import { Notice } from "../ui/Notice";
import { Logo } from "./Logo";

export function AppShell({ children }: { children: ReactNode }) {
  const { site, user, logout, logoutEverywhere } = useSession();
  const route = useRoute();
  const [confirmAll, setConfirmAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = (name: string) => (route.name === name ? "page" : undefined);

  function exit() {
    setError(null);
    logout().catch((failure: unknown) => setError(errorMessage(failure)));
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
          <Link to={paths.trash} aria-current={current("trash")}>
            {it.shell.trash}
          </Link>
        </nav>
        <div className="shell__account" aria-label={it.shell.account}>
          <a className="button button--ghost" href={site.url} target="_blank" rel="noopener noreferrer">
            {it.shell.openSite}
          </a>
          <span className="shell__user">{user.email}</span>
          <button type="button" className="button button--ghost" onClick={exit}>
            {it.shell.logout}
          </button>
          <button type="button" className="button button--ghost" onClick={() => setConfirmAll(true)}>
            {it.shell.logoutAll}
          </button>
        </div>
      </header>
      {error && <Notice kind="error" text={error} onClose={() => setError(null)} />}
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
