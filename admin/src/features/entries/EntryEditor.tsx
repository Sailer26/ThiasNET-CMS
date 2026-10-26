import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { ApiError, errorMessage } from "../../api/client";
import {
  changeSlug,
  discardEntryDraft,
  fetchCollections,
  fetchEntry,
  fetchEntryChecks,
  fetchEntryDraft,
  getEntryRevision,
  listEntryRevisions,
  publishEntry,
  restoreEntryRevision,
  saveEntryDraft,
  scheduleEntry,
  trashEntry,
  unpublishEntry,
  unscheduleEntry,
  type CollectionInfo,
  type Entry,
  type EntryDocument,
  type EntryDraft,
} from "../../api/entries";
import type { Revision } from "../../api/revisions";
import { Link } from "../../router/Link";
import { navigate, paths } from "../../router/router";
import { Permission } from "../../session/can";
import { useSession } from "../../session/context";
import { useFollowLocale } from "../../session/localeContext";
import { en } from "../../text/entries";
import { ed } from "../../text/editor";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { ConflictDialog } from "../editor/ConflictDialog";
import { ErrorList, WarningList, type ListedError } from "../editor/ErrorList";
import { VersionsDialog } from "../editor/history/VersionsDialog";
import { Autosave, type SaveState } from "../editor/model/autosave";
import { setPath, type Path } from "../editor/model/document";
import { isFieldErrors } from "../editor/model/errorPaths";
import { startHistory } from "../editor/model/history";
import { SeoFields } from "../editor/page/SeoFields";
import { PreviewPane } from "../editor/preview/PreviewPane";
import { TranslationsBox } from "../translations/TranslationsBox";
import { SaveIndicator } from "../editor/SaveIndicator";
import { ScheduleDialog } from "../editor/schedule/ScheduleDialog";
import { formatZurich } from "../editor/schedule/siteTime";
import { fieldId, SchemaForm } from "../editor/schema/SchemaForm";
import { undoKeys } from "../editor/undoKeys";
import { useAutosaveLifecycle } from "../editor/useAutosaveLifecycle";
import { MediaProvider } from "../media-picker/MediaContext";
import { entrySafe, historyReducer, mediaIdsOf, setSeo, setTitle } from "./entryDocument";

type Confirm = "publish" | "unpublish" | "discard" | "unschedule" | "trash" | null;
type Loaded = { info: CollectionInfo; entry: Entry; draft: EntryDraft };
type LoadState = { kind: "loading" } | { kind: "failed"; message: string } | { kind: "ready"; data: Loaded };

/** Errori del server per percorso ("title", "fields/date", "seo/description"). */
function byPath(details: unknown): Map<string, string> {
  if (!isFieldErrors(details)) return new Map();
  return new Map(details.map((detail) => [detail.path || "general", detail.message]));
}

function only(errors: ReadonlyMap<string, string>, prefix: string): Map<string, string> {
  return new Map([...errors].filter(([key]) => key.startsWith(prefix)).map(([key, value]) => [key.slice(prefix.length), value]));
}

function focusField(id: string) {
  requestAnimationFrame(() => document.getElementById(id)?.focus());
}

function useEntryData(collection: string, id: number): LoadState {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  useEffect(() => {
    let active = true;
    // La pagina elenco è quella della lingua della notizia (D-159), non quella del pannello.
    Promise.all([fetchEntry(id), fetchEntryDraft(id)])
      .then(async ([entry, draft]) => [await fetchCollections(entry.locale), entry, draft] as const)
      .then(
      ([collections, entry, draft]) => {
        const info = collections.find((c) => c.key === collection);
        if (!active) return;
        if (!info || entry.collection !== collection) setState({ kind: "failed", message: en.empty });
        else setState({ kind: "ready", data: { info, entry, draft } });
      },
      (failure: unknown) => {
        if (active) setState({ kind: "failed", message: errorMessage(failure) });
      },
    );
    return () => {
      active = false;
    };
  }, [collection, id]);
  return state;
}

/** L'editor di una notizia (7b): campi dallo schema del tema, anteprima affiancata (D-156),
 * salvataggio automatico e le stesse azioni delle pagine. */
function Workspace({ data }: { data: Loaded }) {
  const { site, can } = useSession();
  const { schema } = data.info;
  const collection = data.info.key;
  useFollowLocale(data.entry.locale);
  const [entry, setEntry] = useState<Entry>(data.entry);
  const [history, dispatch] = useReducer(historyReducer, data.draft.data, startHistory);
  const doc = history.present;
  const edit = useCallback(
    (fn: (d: EntryDocument) => EntryDocument, key: string | null = null) => dispatch({ type: "edit", fn, key, at: Date.now() }),
    [],
  );
  const [save, setSave] = useState<SaveState>({ kind: "saved", at: null });
  const [saved, setSaved] = useState<EntryDocument>(data.draft.data);
  const [autosave] = useState(
    () =>
      new Autosave<EntryDocument>(
        async (current, version, base) => {
          const safe = entrySafe(current, schema, base).doc;
          return { version: await saveEntryDraft(data.entry.id, version, safe), saved: safe };
        },
        data.draft.version,
        data.draft.data,
      ),
  );
  const [editedAfterSchedule, setEditedAfterSchedule] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [serverErrors, setServerErrors] = useState<Map<string, string>>(new Map());
  const [warnings, setWarnings] = useState<Map<string, string>>(new Map());
  const [checking, setChecking] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [view, setView] = useState<"edit" | "preview">("edit");
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [viewing, setViewing] = useState<{ revision: Revision; doc: EntryDocument } | null>(null);
  const [restoring, setRestoring] = useState<Revision | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [slug, setSlug] = useState(data.entry.slug);
  const [renaming, setRenaming] = useState(false);

  useEffect(
    () =>
      autosave.subscribe((state) => {
        setSave(state);
        setSaved(autosave.base);
        if (state.kind === "saved" && state.at) setEditedAfterSchedule(true);
      }),
    [autosave],
  );
  useAutosaveLifecycle(autosave, doc);

  const safe = useMemo(() => entrySafe(doc, schema, saved), [doc, schema, saved]);
  const loadRevisions = useCallback(() => listEntryRevisions(data.entry.id), [data.entry.id]);
  const drop = (key: string) =>
    setServerErrors((current) => (current.has(key) ? new Map([...current].filter(([k]) => k !== key)) : current));

  const keys = undoKeys(
    () => dispatch({ type: "undo" }),
    () => dispatch({ type: "redo" }),
  );

  async function loadTheirs() {
    const draft = await fetchEntryDraft(entry.id);
    autosave.reset(draft.version, draft.data);
    dispatch({ type: "replace", doc: draft.data });
  }

  async function flushed() {
    if (!(await autosave.flush())) throw new ApiError(0, "not_saved", ed.publish.notSaved);
  }

  async function askPublish() {
    if (checking) return; // un doppio clic farebbe due controlli
    setChecking(true);
    try {
      if (!(await autosave.flush())) {
        setNotice({ kind: "error", text: ed.publish.notSaved });
        return;
      }
      // Controllo prima di pubblicare (D-135); se non risponde si conferma lo stesso: ricontrolla publish.
      const checks = await fetchEntryChecks(entry.id).catch(() => null);
      if (checks && checks.blocking.length > 0) {
        setServerErrors(byPath(checks.blocking));
        return;
      }
      setWarnings(checks ? byPath(checks.warnings) : new Map());
      setConfirm("publish");
    } finally {
      setChecking(false);
    }
  }

  async function publish() {
    try {
      setEntry(await publishEntry(entry.id, autosave.draftVersion));
      autosave.reset(0, safe.doc); // la bozza è diventata la notizia online
      setServerErrors(new Map());
      setConfirm(null);
      setNotice({ kind: "success", text: en.published });
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_content") {
        setServerErrors(byPath(error.details));
        setConfirm(null);
        return;
      }
      throw error;
    }
  }

  async function act(run: () => Promise<Entry>, text: string) {
    setEntry(await run());
    setConfirm(null);
    setNotice({ kind: "success", text });
  }

  async function schedule(iso: string) {
    await flushed();
    await scheduleEntry(entry.id, autosave.draftVersion, iso);
    const fresh = await fetchEntry(entry.id);
    setEntry(fresh);
    setEditedAfterSchedule(false);
    setScheduling(false);
    setNotice({ kind: "success", text: ed.schedule.done(formatZurich(fresh.schedule?.publish_at ?? iso)) });
  }

  async function discard() {
    await flushed();
    await discardEntryDraft(entry.id, autosave.draftVersion);
    await loadTheirs();
    setEntry(await fetchEntry(entry.id));
    setConfirm(null);
    setServerErrors(new Map());
    setNotice({ kind: "success", text: ed.discard.done });
  }

  async function trash() {
    await flushed(); // con un salvataggio bloccato si resta qui: niente bozza persa
    await trashEntry(entry.id, entry.version);
    setConfirm(null);
    await navigate(paths.entries(collection));
  }

  async function look(revision: Revision) {
    setVersionsOpen(false);
    try {
      setViewing({ revision, doc: await getEntryRevision(entry.id, revision.id) });
      setView("preview");
    } catch (error) {
      setNotice({ kind: "error", text: errorMessage(error) });
    }
  }

  async function restore(revision: Revision) {
    await flushed();
    await restoreEntryRevision(entry.id, revision.id, autosave.draftVersion);
    await loadTheirs();
    setEntry(await fetchEntry(entry.id)); // versione e "modifiche non pubblicate" aggiornate
    setRestoring(null);
    setViewing(null);
    setNotice({ kind: "success", text: ed.versions.done });
  }

  async function keepMine() {
    const draft = await fetchEntryDraft(entry.id);
    await autosave.keepMine(draft.version);
  }

  async function changeAddress() {
    if (renaming) return;
    setRenaming(true);
    try {
      const fresh = await changeSlug(entry.id, entry.version, slug.trim());
      setEntry(fresh);
      setSlug(fresh.slug);
      setNotice({ kind: "success", text: en.addressChanged });
    } catch (error) {
      setNotice({ kind: "error", text: errorMessage(error) });
    } finally {
      setRenaming(false);
    }
  }

  const label = (path: string): string => {
    if (path === "title") return en.title;
    if (path.startsWith("fields/")) return schema.properties?.[path.slice(7).split("/")[0]!]?.title ?? en.general;
    if (path.startsWith("seo/")) return ed.page.seo;
    return en.general;
  };
  const target = (path: string): string | null => {
    if (path === "title") return "entry-title";
    if (path.startsWith("fields/")) return fieldId("f", path.slice(7).split("/"));
    if (path.startsWith("seo/")) return `seo-${path.slice(4)}`;
    return null;
  };
  const listed = (entries: Map<string, string>, before?: () => void): ListedError[] =>
    [...entries].map(([path, message]) => {
      const id = target(path);
      return {
        key: path,
        where: label(path),
        message,
        focus: id
          ? () => {
              before?.();
              setView("edit");
              focusField(id);
            }
          : undefined,
      };
    });

  const online = entry.status === "published";
  const offline = entry.status === "draft" && !entry.publish_at;
  const changes = autosave.draftVersion > 0 || autosave.dirty;
  const titleError = serverErrors.get("title");
  return (
    <MediaProvider ids={mediaIdsOf(doc, schema)}>
      <div className={`editor editor--${view}`} onKeyDownCapture={keys}>
        <header className="editor__bar">
          <Link className="button button--ghost" to={paths.entries(collection)}>
            ← {en.back}
          </Link>
          <span className={`badge badge--${entry.status}`}>{ed.status[entry.status]}</span>
          {online && changes && <span className="badge">{ed.status.changes}</span>}
          <SaveIndicator state={save} onRetry={() => void autosave.retry()} />
          <span className="editor__spacer" />
          <button type="button" className="button button--small" disabled={history.past.length === 0} onClick={() => dispatch({ type: "undo" })}>
            {ed.bar.undo}
          </button>
          <button type="button" className="button button--small" disabled={history.future.length === 0} onClick={() => dispatch({ type: "redo" })}>
            {ed.bar.redo}
          </button>
          <div className="editor__toggle" role="group" aria-label={ed.bar.preview}>
            <button type="button" className="button button--small" aria-pressed={view === "edit"} onClick={() => setView("edit")}>
              {ed.bar.edit}
            </button>
            <button type="button" className="button button--small" aria-pressed={view === "preview"} onClick={() => setView("preview")}>
              {ed.bar.preview}
            </button>
          </div>
          {online && entry.url && (
            <a className="button button--small" href={site.url + entry.url} target="_blank" rel="noopener noreferrer">
              {ed.bar.viewOnline}
            </a>
          )}
          {can(Permission.publish) && online && (
            <button type="button" className="button button--small" onClick={() => setConfirm("unpublish")}>
              {ed.bar.unpublish}
            </button>
          )}
          {changes && (
            <button type="button" className="button button--small" onClick={() => setConfirm("discard")}>
              {ed.bar.discard}
            </button>
          )}
          <button type="button" className="button button--small" onClick={() => setVersionsOpen(true)}>
            {ed.versions.button}
          </button>
          {(offline || can(Permission.publish)) && (
            <button type="button" className="button button--small button--danger" onClick={() => setConfirm("trash")}>
              {en.trash}
            </button>
          )}
          {can(Permission.publish) && !(online && !changes) && (
            <button type="button" className="button button--small" onClick={() => setScheduling(true)}>
              {ed.schedule.button}
            </button>
          )}
          {can(Permission.publish) ? (
            <button type="button" className="button button--primary" disabled={(online && !changes) || checking} onClick={() => void askPublish()}>
              {ed.bar.publish}
            </button>
          ) : (
            <span className="hint">{ed.bar.publishNeedsRight}</span>
          )}
        </header>
        <NoticeArea notice={notice} onClose={() => setNotice(null)} />
        {entry.schedule && (
          <div className="notice notice--info schedule-bar">
            <p>
              {ed.schedule.pending(formatZurich(entry.schedule.publish_at))}
              {(entry.schedule.draft_newer || editedAfterSchedule) && <strong> {ed.schedule.newer}</strong>}
            </p>
            {can(Permission.publish) && (
              <button type="button" className="button button--small" onClick={() => setConfirm("unschedule")}>
                {ed.schedule.cancel}
              </button>
            )}
          </div>
        )}
        {viewing && (
          <div className="notice notice--info">
            <p>{ed.versions.viewing(formatZurich(viewing.revision.created_at))}</p>
            <button type="button" className="button button--small" onClick={() => setViewing(null)}>
              {ed.versions.back}
            </button>
          </div>
        )}
        <ErrorList errors={listed(serverErrors)} />
        <div className="editor__body">
          <div className="editor__form">
            <div className={`field${titleError ? " field--error" : ""}`}>
              <label htmlFor="entry-title">{en.title}</label>
              <input
                id="entry-title"
                className="page-settings__title"
                maxLength={200}
                value={doc.title}
                aria-describedby={titleError ? "entry-title-problem" : undefined}
                aria-invalid={titleError ? true : undefined}
                onChange={(event) => {
                  const value = event.target.value;
                  drop("title");
                  edit((d) => setTitle(d, value), "title");
                }}
              />
              {titleError && (
                <p id="entry-title-problem" className="form__error">
                  {titleError}
                </p>
              )}
            </div>
            {offline ? (
              <div className="field">
                <label htmlFor="entry-slug">{en.address}</label>
                <input
                  id="entry-slug"
                  value={slug}
                  autoCapitalize="none"
                  spellCheck={false}
                  aria-describedby="entry-slug-help"
                  onChange={(event) => setSlug(event.target.value)}
                />
                <p id="entry-slug-help" className="hint">
                  {entry.url ?? en.addressMissing} {en.addressHelp}
                </p>
                <button
                  type="button"
                  className="button button--small"
                  disabled={renaming || !slug.trim() || slug.trim() === entry.slug}
                  onClick={() => void changeAddress()}
                >
                  {en.changeAddress}
                </button>
              </div>
            ) : (
              <p className="hint">
                {en.address}: {entry.url ?? en.addressMissing} {en.addressFixed}
              </p>
            )}
            <SchemaForm
              schema={schema}
              data={doc.fields}
              idPrefix="f"
              errors={only(serverErrors, "fields/")}
              unsaved={safe.problems}
              pages={[]}
              onChange={(path: Path, value: unknown) => {
                drop(`fields/${path.join("/")}`);
                edit((d) => ({ ...d, fields: setPath(d.fields, path, value) as Record<string, unknown> }), `fields/${path.join("/")}`);
              }}
            />
            <SeoFields
              seo={doc.seo}
              title={doc.title}
              url={site.url + (entry.url ?? "")}
              errors={serverErrors}
              onSeo={(key, value) => {
                drop(`seo/${key}`);
                edit((d) => setSeo(d, key, value), `seo/${key}`);
              }}
            />
            <TranslationsBox kind="entry" id={entry.id} locale={entry.locale} collection={entry.collection} />
          </div>
          <div className="editor__preview">
            <PreviewPane action={`/_preview/entries/${entry.id}`} doc={viewing?.doc ?? safe.doc} />
          </div>
        </div>
        {save.kind === "conflict" && <ConflictDialog error={save.error} onTheirs={loadTheirs} onMine={keepMine} />}
        {confirm === "publish" && (
          <FormDialog
            title={en.publishTitle}
            submitLabel={warnings.size > 0 ? ed.publish.anyway : ed.publish.confirm}
            onClose={() => setConfirm(null)}
            onSubmit={publish}
          >
            <p>{en.publishQuestion(entry.url ? site.url + entry.url : null)}</p>
            <WarningList warnings={listed(warnings, () => setConfirm(null))} />
          </FormDialog>
        )}
        {confirm === "unpublish" && (
          <FormDialog
            title={en.unpublishTitle}
            submitLabel={ed.unpublish.confirm}
            danger
            onClose={() => setConfirm(null)}
            onSubmit={() => act(() => unpublishEntry(entry.id, entry.version), en.unpublished)}
          >
            <p>{en.unpublishText}</p>
          </FormDialog>
        )}
        {confirm === "unschedule" && (
          <FormDialog
            title={ed.schedule.cancelTitle}
            submitLabel={ed.schedule.cancelConfirm}
            danger
            onClose={() => setConfirm(null)}
            onSubmit={() => act(() => unscheduleEntry(entry.id, entry.version), ed.schedule.cancelled)}
          >
            <p>{ed.schedule.cancelText}</p>
          </FormDialog>
        )}
        {confirm === "discard" && (
          <FormDialog title={ed.discard.title} submitLabel={ed.discard.confirm} danger onClose={() => setConfirm(null)} onSubmit={discard}>
            <p>{en.discardText}</p>
          </FormDialog>
        )}
        {confirm === "trash" && (
          <FormDialog title={en.trashTitle} submitLabel={en.trash} danger onClose={() => setConfirm(null)} onSubmit={trash}>
            <p>{en.trashText}</p>
          </FormDialog>
        )}
        {versionsOpen && (
          <VersionsDialog
            load={loadRevisions}
            onClose={() => setVersionsOpen(false)}
            onLook={(revision) => void look(revision)}
            onRestore={(revision) => {
              setVersionsOpen(false);
              setRestoring(revision);
            }}
          />
        )}
        {restoring && (
          <FormDialog
            title={ed.versions.confirmTitle}
            submitLabel={ed.versions.confirm}
            onClose={() => setRestoring(null)}
            onSubmit={() => restore(restoring)}
          >
            <p>{ed.versions.confirmText}</p>
          </FormDialog>
        )}
        {scheduling && <ScheduleDialog onClose={() => setScheduling(false)} onSchedule={schedule} />}
      </div>
    </MediaProvider>
  );
}

export function EntryEditor({ collection, id }: { collection: string; id: number }) {
  const { site } = useSession();
  const state = useEntryData(collection, id);
  if (state.kind === "loading") return <p role="status">{en.loading}</p>;
  if (state.kind === "failed") {
    const label = site.collections.find((c) => c.key === collection)?.label ?? en.general;
    return (
      <section className="screen">
        <h1 tabIndex={-1}>{label}</h1>
        <p role="alert">{state.message}</p>
        <Link className="button" to={paths.entries(collection)}>
          {en.back}
        </Link>
      </section>
    );
  }
  return <Workspace key={state.data.entry.id} data={state.data} />;
}
