import { PagePlaceholder } from "./features/page-tree/PagePlaceholder";
import { PageTreeScreen } from "./features/page-tree/PageTreeScreen";
import { TrashScreen } from "./features/page-tree/TrashScreen";
import { Link } from "./router/Link";
import { paths, useRoute, type Route } from "./router/router";
import { SessionProvider } from "./session/SessionProvider";
import { AppShell } from "./shell/AppShell";
import { it } from "./text/it";

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case "pages":
      return <PageTreeScreen />;
    case "trash":
      return <TrashScreen />;
    case "page":
      return <PagePlaceholder />;
    case "not-found":
      return (
        <section className="screen">
          <p>{it.shell.notFound}</p>
          <Link className="button" to={paths.pages}>
            {it.shell.backToPages}
          </Link>
        </section>
      );
  }
}

function Panel() {
  const route = useRoute();
  return (
    <AppShell>
      <Screen route={route} />
    </AppShell>
  );
}

export function App() {
  return (
    <SessionProvider>
      <Panel />
    </SessionProvider>
  );
}
