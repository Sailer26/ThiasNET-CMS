import { useEffect, useState } from "react";
import { fetchChecks, fetchDraft, publishPage, type CheckItem } from "../../api/drafts";
import { errorMessage } from "../../api/client";
import type { PageNode } from "../../api/types";
import { ed } from "../../text/editor";
import { it } from "../../text/it";
import { FormDialog } from "../../ui/FormDialog";
import { WarningList, type ListedError } from "../editor/ErrorList";

type State =
  | { kind: "loading" }
  | { kind: "ready"; version: number; blocking: CheckItem[]; warnings: CheckItem[] }
  | { kind: "failed"; message: string };

function where(path: string): string {
  if (path.startsWith("seo")) return ed.page.seo;
  if (path.startsWith("zones")) return ed.publish.wholePage;
  return ed.page.title;
}

/** Sul telefono non si corregge: si legge e basta (D-136). */
function listed(items: CheckItem[]): ListedError[] {
  return items.map((item) => ({ key: `${item.path}:${item.code}`, where: where(item.path), message: item.message }));
}

interface Props {
  node: PageNode;
  onClose: () => void;
  onDone: (text: string) => void;
}

/** "Pubblica le modifiche" dal telefono (D-97, D-136): stessa verifica del computer. */
export function PhonePublish({ node, onClose, onDone }: Props) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    // Se il controllo non risponde si pubblica lo stesso: il server ricontrolla (D-135).
    const checks = fetchChecks(node.id).catch(() => ({ blocking: [], warnings: [] }));
    Promise.all([fetchDraft(node.id), checks]).then(
      ([draft, found]) => {
        if (active) setState({ kind: "ready", version: draft.version, ...found });
      },
      (error: unknown) => {
        if (active) setState({ kind: "failed", message: errorMessage(error) });
      },
    );
    return () => {
      active = false;
    };
  }, [node.id]);

  const ready = state.kind === "ready" ? state : null;
  const blocked = ready !== null && ready.blocking.length > 0;
  return (
    <FormDialog
      title={it.tree.phoneTitle}
      submitLabel={ready && ready.warnings.length > 0 ? ed.publish.anyway : ed.publish.confirm}
      canSubmit={ready !== null && !blocked}
      onClose={onClose}
      onSubmit={async () => {
        if (!ready) return;
        await publishPage(node.id, ready.version);
        onDone(it.tree.phonePublished(node.title));
      }}
    >
      {state.kind === "loading" && <p role="status">{it.tree.phoneChecking}</p>}
      {state.kind === "failed" && <p role="alert">{state.message}</p>}
      {ready && !blocked && <p>{it.tree.phoneQuestion(node.title)}</p>}
      {blocked && (
        <section className="notice notice--error error-list">
          <p>{it.tree.phoneBlocked}</p>
          <ul>
            {listed(ready.blocking).map((item) => (
              <li key={item.key}>
                <strong>{item.where}</strong> · {item.message}
              </li>
            ))}
          </ul>
          <p>{it.tree.phoneFix}</p>
        </section>
      )}
      {ready && !blocked && <WarningList warnings={listed(ready.warnings)} />}
    </FormDialog>
  );
}
