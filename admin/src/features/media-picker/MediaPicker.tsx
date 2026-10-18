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
  /** Quanti se ne possono ancora aggiungere (es. galleria quasi piena). */
  limit?: number;
  onChoose: (media: Media[]) => void;
  onClose: () => void;
}

interface Listing {
  items: Media[];
  total: number;
  /** Ultima pagina caricata davvero: "Mostra altri" chiede la successiva. */
  page: number;
}

function Library({ kind, multiple, limit = Infinity, onChoose }: Omit<Props, "onClose">) {
  const [query, setQuery] = useState("");
  const [listing, setListing] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Media[]>([]);
  const latest = useRef(0);
  const { remember } = useMedia();

  const load = useCallback(
    (q: string, page: number) => {
      const request = ++latest.current;
      setLoading(true);
      listMedia({ kind, q, page }).then(
        (result) => {
          if (request !== latest.current) return;
          setListing((current) => ({
            items: page === 1 || !current ? result.items : [...current.items, ...result.items],
            total: result.total,
            page,
          }));
          setError(null);
          setLoading(false);
        },
        (failure: unknown) => {
          if (request !== latest.current) return;
          setError(errorMessage(failure));
          setLoading(false);
        },
      );
    },
    [kind],
  );

  // Ricerca: si riparte dalla prima pagina dopo una pausa (mentre si scrive "Mostra altri" sparisce).
  useEffect(() => {
    const timer = setTimeout(() => load(query, 1), query ? SEARCH_PAUSE_MS : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  function pick(media: Media) {
    remember(media);
    if (!multiple) {
      onChoose([media]);
      return;
    }
    setChosen((current) => {
      if (current.some((m) => m.id === media.id)) return current.filter((m) => m.id !== media.id);
      return current.length >= limit ? current : [...current, media];
    });
  }

  const items = listing?.items ?? [];
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
            setLoading(true);
          }}
        />
      </label>
      <div aria-live="polite" className="picker__status">
        {loading && <p className="hint">{ed.media.loading}</p>}
        {!loading && listing && items.length === 0 && <p className="hint">{ed.media.empty}</p>}
        {!loading && missingAlt > 0 && <p className="hint">{ed.media.missingAltCount(missingAlt)}</p>}
        {multiple && limit !== Infinity && <p className="hint">{ed.media.limit(limit)}</p>}
      </div>
      {error && (
        <div className="form__error" role="alert">
          <p>{error}</p>
          <button type="button" className="button button--small" onClick={() => load(query, (listing?.page ?? 0) + 1)}>
            {ed.save.retry}
          </button>
        </div>
      )}
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
        {!loading && listing && items.length < listing.total && (
          <button type="button" className="button" onClick={() => load(query, listing.page + 1)}>
            {ed.media.more(Math.min(PICKER_PAGE_SIZE, listing.total - items.length))}
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
  const open = useRef(true);

  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false; // finestra chiusa durante il caricamento: il campo non cambia più
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadMedia(file, alt);
      remember(result.media);
      if (!open.current) return;
      if (result.duplicate) setDuplicate(result.media);
      else onChoose([result.media]);
    } catch (failure) {
      if (open.current) setError(errorMessage(failure));
    } finally {
      if (open.current) setBusy(false);
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
export function MediaPicker({ kind, multiple = false, limit, onChoose, onClose }: Props) {
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
      {/* La libreria resta montata: ricerca, pagine e scelte non si perdono cambiando scheda. */}
      <div hidden={tab !== "library"}>
        <Library kind={kind} multiple={multiple} {...(limit !== undefined ? { limit } : {})} onChoose={onChoose} />
      </div>
      {tab === "upload" && <Upload kind={kind} onChoose={onChoose} />}
      <div className="form__actions">
        <button type="button" className="button" onClick={onClose}>
          {ed.zones.close}
        </button>
      </div>
    </Dialog>
  );
}
