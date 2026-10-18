import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { errorMessage } from "../../api/client";
import {
  createFolder,
  deleteFolder,
  fetchFolders,
  fetchUsage,
  listMedia,
  updateFolder,
  uploadMedia,
  type Folder,
  type Media,
  type MediaKind,
  type Usage,
} from "../../api/media";
import { setNavigationGuard } from "../../router/router";
import { mt } from "../../text/media";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { FolderTree, type FolderChoice } from "./FolderTree";
import { formatBytes, usedPercent } from "./format";
import { MediaDetailPanel } from "./MediaDetailPanel";
import { enqueue, runQueue, type QueueItem } from "./queue";

const SEARCH_PAUSE_MS = 300;
const HIGH_USAGE = 90;

interface Listing {
  items: Media[];
  total: number;
  page: number;
}

function QuotaBar({ usage }: { usage: Usage }) {
  const percent = usedPercent(usage.used_bytes, usage.quota_bytes);
  return (
    <div className="quota">
      <meter min={0} max={100} value={percent} aria-label={mt.usage(formatBytes(usage.used_bytes), formatBytes(usage.quota_bytes))} />
      <span>{mt.usage(formatBytes(usage.used_bytes), formatBytes(usage.quota_bytes))}</span>
      {percent >= HIGH_USAGE && <p className="notice notice--info">{mt.usageHigh}</p>}
    </div>
  );
}

function QueueList({ items, running, onStop }: { items: QueueItem[]; running: boolean; onStop: () => void }) {
  if (items.length === 0) return null;
  return (
    <section className="queue" aria-labelledby="queue-title" aria-live="polite">
      <h2 id="queue-title">{mt.queueTitle}</h2>
      <ul>
        {items.map((item) => (
          <li key={item.key} className={`queue__item queue__item--${item.state}`}>
            <span className="queue__name">{item.file.name}</span>
            <span>{mt.states[item.state]}</span>
            {item.message && <span className="hint">{item.message}</span>}
          </li>
        ))}
      </ul>
      {running && (
        <button type="button" className="button button--small" onClick={onStop}>
          {mt.stop}
        </button>
      )}
    </section>
  );
}

/** Pagina Media (D-117 … D-120). */
export function MediaScreen() {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folder, setFolder] = useState<FolderChoice>("all");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<MediaKind | "all">("all");
  const [missingAlt, setMissingAlt] = useState(false);
  const [listing, setListing] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [detail, setDetail] = useState<number | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const latest = useRef(0);
  const stopRef = useRef(false);

  const refreshSide = useCallback(() => {
    fetchFolders().then(setFolders, (e: unknown) => setNotice({ kind: "error", text: errorMessage(e) }));
    fetchUsage().then(setUsage, () => undefined); // la barra è un aiuto: senza, la pagina funziona
  }, []);

  const load = useCallback(
    (page: number) => {
      const request = ++latest.current;
      setLoading(true);
      listMedia({
        q: query || undefined,
        kind: kind === "all" ? undefined : kind,
        folder: query ? undefined : folder === "all" ? undefined : folder,
        missingAlt,
        page,
      }).then(
        (result) => {
          if (request !== latest.current) return;
          setListing((current) => ({
            items: page === 1 || !current ? result.items : [...current.items, ...result.items],
            total: result.total,
            page,
          }));
          setLoading(false);
        },
        (error: unknown) => {
          if (request !== latest.current) return;
          setNotice({ kind: "error", text: errorMessage(error) });
          setLoading(false);
        },
      );
    },
    [query, kind, folder, missingAlt],
  );

  useEffect(() => {
    const timer = setTimeout(() => load(1), query ? SEARCH_PAUSE_MS : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  useEffect(() => {
    refreshSide();
  }, [refreshSide]);

  // Uscire con la coda attiva lo chiede (D-118).
  useEffect(() => {
    if (!running) return;
    setNavigationGuard(async () => window.confirm(mt.leaveQueue));
    return () => setNavigationGuard(null);
  }, [running]);

  async function startUpload(files: File[]) {
    if (files.length === 0) return;
    const items = enqueue(files, usage?.max_upload_bytes ?? 0);
    setQueue(items);
    setRunning(true);
    stopRef.current = false;
    const target = typeof folder === "number" ? folder : null;
    const done = await runQueue(items, (file) => uploadMedia(file, "", target), setQueue, () => stopRef.current);
    setRunning(false);
    const withoutAlt = done.filter((item) => item.state === "done" && item.media?.kind === "image" && !item.media.alt.trim()).length;
    if (withoutAlt > 0) {
      setNotice({
        kind: "info",
        text: mt.altReminder(withoutAlt),
        action: {
          label: mt.addAltNow,
          run: () => {
            setQuery("");
            setMissingAlt(true);
          },
        },
      });
    }
    load(1);
    refreshSide();
  }

  function drop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    void startUpload(Array.from(event.dataTransfer.files));
  }

  const items = listing?.items ?? [];
  return (
    <section className="screen media-screen" aria-labelledby="media-title" onDragOver={(event) => event.preventDefault()} onDrop={drop}>
      <div className="screen__head">
        <h1 id="media-title" tabIndex={-1}>
          {mt.title}
        </h1>
        <label className="button button--primary upload-button">
          {mt.upload}
          <input
            type="file"
            multiple
            className="visually-hidden"
            accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
            disabled={running}
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              event.target.value = "";
              void startUpload(files);
            }}
          />
        </label>
      </div>
      <p className="hint">{mt.dropHere}</p>
      {usage && <QuotaBar usage={usage} />}
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <QueueList items={queue} running={running} onStop={() => (stopRef.current = true)} />
      <div className="media-screen__body">
        <FolderTree
          folders={folders}
          selected={folder}
          onSelect={(choice) => {
            setFolder(choice);
            setQuery("");
          }}
          onCreate={async (name, parentId) => {
            await createFolder(name, parentId);
            refreshSide();
          }}
          onRename={async (target, name) => {
            await updateFolder(target.id, { name });
            refreshSide();
          }}
          onMove={async (target, parentId) => {
            await updateFolder(target.id, { parent_id: parentId });
            refreshSide();
          }}
          onDelete={async (target) => {
            await deleteFolder(target.id);
            setFolder("all");
            refreshSide();
          }}
        />
        <div className="media-screen__main">
          <div className="filters">
            <label className="field">
              <span>{mt.search}</span>
              <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
            <label className="field">
              <span>{mt.kind}</span>
              <select value={kind} onChange={(event) => setKind(event.target.value as MediaKind | "all")}>
                {Object.entries(mt.kinds).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field field--check">
              <span>
                <input type="checkbox" checked={missingAlt} onChange={(event) => setMissingAlt(event.target.checked)} /> {mt.missingAlt}
              </span>
            </label>
          </div>
          <div aria-live="polite">
            {query && <p className="hint">{mt.searchAll}</p>}
            {loading && <p className="hint">{mt.loading}</p>}
            {!loading && listing && items.length === 0 && <p className="hint">{mt.empty}</p>}
          </div>
          <ul className="picker__grid media-grid">
            {items.map((media) => (
              <li key={media.id}>
                <button
                  type="button"
                  className={`picker__item${detail === media.id ? " picker__item--chosen" : ""}`}
                  aria-pressed={detail === media.id}
                  onClick={() => setDetail(media.id)}
                >
                  {media.thumbnail_url ? (
                    <img src={media.thumbnail_url} alt="" width={120} height={90} loading="lazy" />
                  ) : (
                    <span className="picker__file">{media.ext.toUpperCase()}</span>
                  )}
                  <span className="picker__name">{media.name}</span>
                  {media.kind === "image" && !media.alt.trim() && <span className="badge badge--error">{mt.missingAlt}</span>}
                </button>
              </li>
            ))}
          </ul>
          {!loading && listing && items.length < listing.total && (
            <button type="button" className="button" onClick={() => load(listing.page + 1)}>
              {mt.more(Math.min(24, listing.total - items.length))}
            </button>
          )}
        </div>
        {detail !== null && (
          <MediaDetailPanel
            key={detail}
            id={detail}
            folders={folders}
            onClose={() => setDetail(null)}
            onChanged={() => {
              load(1);
              refreshSide();
            }}
            onDeleted={(name) => {
              setDetail(null);
              setNotice({ kind: "success", text: mt.removed(name) });
              load(1);
              refreshSide();
            }}
          />
        )}
      </div>
    </section>
  );
}
