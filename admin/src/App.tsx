import { lazy, Suspense } from "react";
import { PageTreeScreen } from "./features/page-tree/PageTreeScreen";
import { TrashScreen } from "./features/page-tree/TrashScreen";
import { MediaScreen } from "./features/media-library/MediaScreen";
import { AuditScreen } from "./features/admin/AuditScreen";
import { MessageScreen, MessagesScreen } from "./features/admin/MessagesScreen";
import { NoAccess } from "./features/admin/NoAccess";
import { ProfileScreen } from "./features/admin/ProfileScreen";
import { UsersScreen } from "./features/admin/UsersScreen";
import { SettingsScreen } from "./features/settings/SettingsScreen";
import { MenusScreen } from "./features/menus/MenusScreen";
import { WidgetsScreen } from "./features/widgets/WidgetsScreen";
import { Link } from "./router/Link";
import { paths, useRoute, type Route } from "./router/router";
import { Permission } from "./session/can";
import { useSession } from "./session/context";
import { SessionProvider } from "./session/SessionProvider";
import { AppShell } from "./shell/AppShell";
import { it } from "./text/it";

// L'editor (con TipTap) si scarica solo quando si apre una pagina.
const EditorScreen = lazy(() =>
  import("./features/editor/EditorScreen").then((module) => ({ default: module.EditorScreen })),
);

function Screen({ route }: { route: Route }) {
  const { can } = useSession();
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
    case "messages":
      return can(Permission.messagesView) ? <MessagesScreen /> : <NoAccess />;
    case "message":
      return can(Permission.messagesView) ? <MessageScreen key={route.id} id={route.id} /> : <NoAccess />;
    case "users":
      return can(Permission.usersManage) ? <UsersScreen /> : <NoAccess />;
    case "audit":
      return can(Permission.auditView) ? <AuditScreen /> : <NoAccess />;
    case "profile":
      return <ProfileScreen />;
    case "menus":
      return can(Permission.publish) ? <MenusScreen /> : <NoAccess />;
    case "widgets":
      return can(Permission.publish) ? <WidgetsScreen /> : <NoAccess />;
    case "settings":
      return can(Permission.settingsEdit) ? <SettingsScreen /> : <NoAccess />;
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
