import { useCallback, useEffect, useId, useState } from "react";
import { ApiError, errorMessage } from "../../api/client";
import { deleteMedia, getMedia, replaceFile, updateMedia, type Folder, type MediaDetail } from "../../api/media";
import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { mt } from "../../text/media";
import { FormDialog } from "../../ui/FormDialog";
import { FocalPointPicker } from "./FocalPointPicker";
import { flattenFolders } from "./FolderTree";
import { formatBytes } from "./format";

interface Props {
  id: number;
  folders: Folder[];
  onChanged: () => void;
  onDeleted: (name: string) => void;
  onClose: () => void;
}

/** Dettaglio di un file (D-117): nome, testo alternativo, cartella, punto focale, Sostituisci,
 * Usato in, Elimina. */
export function MediaDetailPanel({ id, folders, onChanged, onDeleted, onClose }: Props) {
  const [media, setMedia] = useState<MediaDetail | null>(null);
  const [name, setName] = useState("");
  const [alt, setAlt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const altId = useId();
  const nameId = useId();
  const replaceId = useId();

  const load = useCallback(
    () =>
      getMedia(id).then(
        (found) => {
          setMedia(found);
          setName(found.name);
          setAlt(found.alt); // gli errori restano: li toglie solo l'azione successiva
        },
        (failure: unknown) => setError(errorMessage(failure)),
      ),
    [id],
  );

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<void>, done: string) {
    if (!media) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(done);
      await load();
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
      if (failure instanceof ApiError && failure.code === "version_conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  if (!media) {
    return (
      <aside className="media-detail" aria-label={mt.detail}>
        {error ? <p role="alert">{error}</p> : <p role="status">{mt.loading}</p>}
      </aside>
    );
  }

  const image = media.kind === "image";
  const changedText = name.trim() !== media.name || alt.trim() !== media.alt;
  return (
    <aside className="media-detail" aria-labelledby={`${nameId}-title`}>
      <div className="media-detail__head">
        <h2 id={`${nameId}-title`}>{media.name}</h2>
        <button type="button" className="button button--small" onClick={onClose}>
          {mt.close}
        </button>
      </div>
      {media.thumbnail_url && <img className="media-detail__preview" src={media.thumbnail_url} alt="" />}
      <p className="hint">
        {media.ext.toUpperCase()} · {formatBytes(media.size_bytes ?? 0)}
        {media.width && media.height ? ` · ${media.width}×${media.height}` : ""} ·{" "}
        <a href={media.url} target="_blank" rel="noopener noreferrer">
          {mt.open}
        </a>
      </p>
      <div className="notice-area" aria-live="polite">
        {notice && <p className="notice notice--success">{notice}</p>}
      </div>
      {error && (
        <p className="form__error" role="alert">
          {error}
        </p>
      )}
      <div className="field">
        <label htmlFor={nameId}>{mt.name}</label>
        <input id={nameId} value={name} maxLength={200} onChange={(event) => setName(event.target.value)} />
      </div>
      {image && (
        <div className="field">
          <label htmlFor={altId}>{mt.alt}</label>
          <input id={altId} value={alt} maxLength={250} aria-describedby={`${altId}-help`} onChange={(event) => setAlt(event.target.value)} />
          <span id={`${altId}-help`} className="hint">
            {mt.altHelp}
          </span>
        </div>
      )}
      <div className="form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={!changedText || busy}
          onClick={() => void run(async () => void (await updateMedia(media.id, media.version, { name: name.trim(), alt: alt.trim() })), mt.saved)}
        >
          {mt.save}
        </button>
      </div>
      <label className="field">
        <span>{mt.folder}</span>
        <select
          value={media.folder_id ?? ""}
          disabled={busy}
          onChange={(event) => {
            const folderId = event.target.value ? Number(event.target.value) : null;
            void run(async () => void (await updateMedia(media.id, media.version, { folder_id: folderId })), mt.saved);
          }}
        >
          <option value="">{mt.noFolder}</option>
          {flattenFolders(folders).map((row) => (
            <option key={row.folder.id} value={row.folder.id}>
              {"— ".repeat(row.depth - 1)}
              {row.folder.name}
            </option>
          ))}
        </select>
      </label>
      {image && media.thumbnail_url && (
        <section aria-label={mt.focal}>
          <h3>{mt.focal}</h3>
          <FocalPointPicker
            key={`${media.id}-${media.version}`}
            src={media.url}
            initial={{ x: media.focal_x ?? 50, y: media.focal_y ?? 50 }}
            busy={busy}
            onSave={(focal) =>
              void run(async () => void (await updateMedia(media.id, media.version, { focal_x: focal.x, focal_y: focal.y })), mt.saved)
            }
          />
        </section>
      )}
      <div className="field">
        <label htmlFor={replaceId}>{mt.replace}</label>
        <input
          id={replaceId}
          type="file"
          accept={image ? "image/jpeg,image/png,image/webp,image/gif" : "application/pdf"}
          disabled={busy}
          aria-describedby={`${replaceId}-help`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void run(async () => void (await replaceFile(media.id, media.version, file)), mt.replaced);
          }}
        />
        <span id={`${replaceId}-help`} className="hint">
          {mt.replaceHelp} {image ? "" : mt.replacePdf}
        </span>
      </div>
      <section aria-label={mt.usedBy}>
        <h3>{mt.usedBy}</h3>
        {media.used_by.length === 0 ? (
          <p className="hint">{mt.notUsed}</p>
        ) : (
          <ul className="media-detail__uses">
            {media.used_by.map((use) => (
              <li key={`${use.page_id}-${use.where}`}>
                <Link to={paths.page(use.page_id)}>{use.title}</Link> <span className="hint">({mt.where_[use.where] ?? use.where})</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <button type="button" className="button button--danger" disabled={busy} onClick={() => setConfirming(true)}>
        {mt.remove}
      </button>
      {confirming && (
        <FormDialog
          title={mt.remove}
          submitLabel={mt.remove}
          danger
          onClose={() => setConfirming(false)}
          onSubmit={async () => {
            try {
              await deleteMedia(media.id, media.version);
            } catch (failure) {
              if (failure instanceof ApiError && failure.code === "media_in_use") {
                setConfirming(false);
                setError(mt.inUse);
                await load();
                return;
              }
              throw failure;
            }
            setConfirming(false);
            onDeleted(media.name);
          }}
        >
          <p>{mt.removeConfirm(media.name)}</p>
        </FormDialog>
      )}
    </aside>
  );
}
