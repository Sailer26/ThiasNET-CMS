import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { errorMessage } from "../../api/client";
import { listMedia, PICKER_PAGE_SIZE, uploadMedia, type Media, type MediaKind } from "../../api/media";
import { ed } from "../../text/editor";
import { Dialog } from "../../ui/Dialog";
import { useMedia } from "./MediaContext";

const ACCEPT: Record<MediaKind, string> = {
  image: "image/jpeg,image/png,image/webp,image/gif",
  document: "application/pdf",
};
const SEARCH_PAUSE_MS = 300;

interface Props {
  kind: MediaKind;
  multiple?: boolean;
  onChoose: (media: Media[]) => void;
  onClose: () => void;
}

function Library({ kind, multiple, onChoose }: Omit<Props, "onClose">) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Media[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Media[]>([]);
  const latest = useRef(0);
  const { remember } = useMedia();

  const load = useCallback(
    (q: string, pageNo: number) => {
      const request = ++latest.current;
      listMedia({ kind, q, page: pageNo }).then(
        (result) => {
          if (request !== latest.current) return;
          setItems((current) => (pageNo === 1 ? result.items : [...current, ...result.items]));
          setTotal(result.total);
          setError(null);
        },
        (failure: unknown) => {
          if (request === latest.current) setError(errorMessage(failure));
        },
      );
    },
    [kind],
  );

  useEffect(() => {
    const timer = setTimeout(() => load(query, page), query && page === 1 ? SEARCH_PAUSE_MS : 0);
    return () => clearTimeout(timer);
  }, [load, query, page]);

  function pick(media: Media) {
    remember(media);
    if (!multiple) {
      onChoose([media]);
      return;
    }
    setChosen((current) =>
      current.some((m) => m.id === media.id) ? current.filter((m) => m.id !== media.id) : [...current, media],
    );
  }

  const missingAlt = items.filter((m) => m.kind === "image" && !m.alt.trim()).length;
  return (
    <div className="picker">
      <label className="field">
        <span>{ed.media.search}</span>
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
        />
      </label>
      {missingAlt > 0 && <p className="hint">{ed.media.missingAltCount(missingAlt)}</p>}
      {error && (
        <p className="form__error" role="alert">
          {error}
        </p>
      )}
      {items.length === 0 && !error && <p className="hint">{ed.media.empty}</p>}
      <ul className="picker__grid">
        {items.map((media) => {
          const selected = chosen.some((m) => m.id === media.id);
          return (
            <li key={media.id}>
              <button
                type="button"
                className={`picker__item${selected ? " picker__item--chosen" : ""}`}
                aria-pressed={multiple ? selected : undefined}
                onClick={() => pick(media)}
              >
                {media.thumbnail_url ? (
                  <img src={media.thumbnail_url} alt="" width={120} height={90} loading="lazy" />
                ) : (
                  <span className="picker__file">{media.ext.toUpperCase()}</span>
                )}
                <span className="picker__name">{media.name}</span>
                {media.kind === "image" && !media.alt.trim() && (
                  <span className="badge badge--error">{ed.media.noAlt}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="form__actions">
        {items.length < total && (
          <button type="button" className="button" onClick={() => setPage(page + 1)}>
            {ed.media.more(Math.min(PICKER_PAGE_SIZE, total - items.length))}
          </button>
        )}
        {multiple && (
          <button
            type="button"
            className="button button--primary"
            disabled={chosen.length === 0}
            onClick={() => onChoose(chosen)}
          >
            {ed.media.addChosen(chosen.length)}
          </button>
        )}
      </div>
    </div>
  );
}

function Upload({ kind, onChoose }: Omit<Props, "onClose">) {
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<Media | null>(null);
  const fileId = useId();
  const altId = useId();
  const { remember } = useMedia();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadMedia(file, alt);
      remember(result.media);
      if (result.duplicate) setDuplicate(result.media);
      else onChoose([result.media]);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  if (duplicate) {
    return (
      <div className="form">
        <p role="status">{ed.media.duplicate(duplicate.name)}</p>
        <div className="form__actions">
          <button type="button" className="button button--primary" onClick={() => onChoose([duplicate])}>
            {ed.media.useExisting}
          </button>
        </div>
      </div>
    );
  }
  return (
    <form className="form" onSubmit={(event) => void submit(event)} noValidate>
      <div className="field">
        <label htmlFor={fileId}>{kind === "image" ? ed.media.fileImage : ed.media.fileDocument}</label>
        <input
          id={fileId}
          type="file"
          accept={ACCEPT[kind]}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <p className="hint">{ed.media.limits}</p>
      </div>
      {kind === "image" && (
        <div className="field">
          <label htmlFor={altId}>{ed.media.alt}</label>
          <input
            id={altId}
            value={alt}
            maxLength={250}
            aria-describedby={`${altId}-help`}
            onChange={(event) => setAlt(event.target.value)}
          />
          <span id={`${altId}-help`} className="hint">
            {ed.media.altHelp}
          </span>
        </div>
      )}
      {error && (
        <p className="form__error" role="alert">
          {error}
        </p>
      )}
      <div className="form__actions">
        <button type="submit" className="button button--primary" disabled={!file || busy}>
          {busy ? ed.media.uploading : ed.media.upload}
        </button>
      </div>
    </form>
  );
}

/** Scelta di un media dalla libreria o caricamento di un file nuovo (D-111). */
export function MediaPicker({ kind, multiple = false, onChoose, onClose }: Props) {
  const [tab, setTab] = useState<"library" | "upload">("library");
  return (
    <Dialog title={kind === "image" ? ed.media.titleImage : ed.media.titleDocument} onClose={onClose}>
      <div className="tabs" role="group" aria-label={ed.media.tabs}>
        <button
          type="button"
          className="button button--small"
          aria-pressed={tab === "library"}
          onClick={() => setTab("library")}
        >
          {ed.media.library}
        </button>
        <button
          type="button"
          className="button button--small"
          aria-pressed={tab === "upload"}
          onClick={() => setTab("upload")}
        >
          {ed.media.uploadTab}
        </button>
      </div>
      {tab === "library" ? (
        <Library kind={kind} multiple={multiple} onChoose={onChoose} />
      ) : (
        <Upload kind={kind} onChoose={onChoose} />
      )}
      <div className="form__actions">
        <button type="button" className="button" onClick={onClose}>
          {ed.zones.close}
        </button>
      </div>
    </Dialog>
  );
}
