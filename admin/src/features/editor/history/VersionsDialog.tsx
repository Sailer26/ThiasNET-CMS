import { useEffect, useState } from "react";
import { errorMessage } from "../../../api/client";
import type { Revision } from "../../../api/revisions";
import { ed } from "../../../text/editor";
import { Dialog } from "../../../ui/Dialog";
import { formatZurich } from "../schedule/siteTime";

interface Props {
  /** Le versioni da mostrare (di una pagina o di una notizia). */
  load: () => Promise<Revision[]>;
  onLook: (revision: Revision) => void;
  onRestore: (revision: Revision) => void;
  onClose: () => void;
}

/** Versioni della pagina (D-121): chi e quando, Guarda, Ripristina nella bozza. */
export function VersionsDialog({ load, onLook, onRestore, onClose }: Props) {
  const [items, setItems] = useState<Revision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    load().then(
      (found) => {
        if (active) setItems(found);
      },
      (failure: unknown) => {
        if (active) setError(errorMessage(failure));
      },
    );
    return () => {
      active = false;
    };
  }, [load]);

  return (
    <Dialog title={ed.versions.title} onClose={onClose}>
      {error && <p role="alert">{error}</p>}
      {!items && !error && <p role="status">{ed.loading}</p>}
      {items?.length === 0 && <p className="hint">{ed.versions.empty}</p>}
      {items && items.length > 0 && (
        <ul className="versions">
          {items.map((revision) => (
            <li key={revision.id} className="versions__item">
              <div>
                <strong>{ed.versions.kinds[revision.kind] ?? revision.kind}</strong> · {formatZurich(revision.created_at)}
                <p className="hint">
                  {revision.author_name} · {revision.title}
                </p>
              </div>
              <div className="form__actions">
                <button type="button" className="button button--small" onClick={() => onLook(revision)}>
                  {ed.versions.look}
                </button>
                <button type="button" className="button button--small" onClick={() => onRestore(revision)}>
                  {ed.versions.restore}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="form__actions">
        <button type="button" className="button" onClick={onClose}>
          {ed.zones.close}
        </button>
      </div>
    </Dialog>
  );
}
