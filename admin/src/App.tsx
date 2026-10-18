import { lazy, Suspense } from "react";
import { PageTreeScreen } from "./features/page-tree/PageTreeScreen";
import { TrashScreen } from "./features/page-tree/TrashScreen";
import { MediaScreen } from "./features/media-library/MediaScreen";
import { Link } from "./router/Link";
import { paths, useRoute, type Route } from "./router/router";
import { SessionProvider } from "./session/SessionProvider";
import { AppShell } from "./shell/AppShell";
import { it } from "./text/it";

// L'editor (con TipTap) si scarica solo quando si apre una pagina.
const EditorScreen = lazy(() =>
  import("./features/editor/EditorScreen").then((module) => ({ default: module.EditorScreen })),
);

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case "pages":
      return <PageTreeScreen />;
    case "trash":
      return <TrashScreen />;
    case "media":
      return <MediaScreen />;
    case "page":
      return (
        <Suspense fallback={<p role="status">{it.loading}</p>}>
          <EditorScreen key={route.id} pageId={route.id} />
        </Suspense>
      );
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
