import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, errorMessage } from "../../api/client";
import { discardDraft, fetchDraft, publishPage, saveDraft, unpublishPage, type Draft } from "../../api/drafts";
import type { Page } from "../../api/types";
import { Link } from "../../router/Link";
import { paths, setNavigationGuard } from "../../router/router";
import { Permission } from "../../session/can";
import { useSession } from "../../session/context";
import { ed } from "../../text/editor";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { MediaProvider, mediaIdsIn } from "../media-picker/MediaContext";
import { ErrorList, type ListedError } from "./ErrorList";
import { Autosave, type SaveState } from "./model/autosave";
import {
  addBlock,
  duplicateBlock,
  hasRoom,
  locate,
  moveBlock,
  newBlock,
  normalize,
  removeBlock,
  setSeo,
  setTitle,
  setVariant,
  shiftBlock,
  uids,
  updateField,
  type PageDocument,
  type Path,
} from "./model/document";
import { draftSafe, problemKey } from "./model/draftSafe";
import { isFieldErrors, locateError } from "./model/errorPaths";
import { newUid } from "./model/uid";
import { PageSettings } from "./page/PageSettings";
import { PreviewPane } from "./preview/PreviewPane";
import { fieldId } from "./schema/SchemaForm";
import { SaveIndicator } from "./SaveIndicator";
import { useEditorData, type Loaded } from "./useEditorData";
import { useEditorState } from "./useEditorState";
import { ZoneList, type ZoneActions } from "./zones/ZoneList";

type Confirm = "publish" | "unpublish" | "discard" | null;

function byBlock(entries: Iterable<[string, string]>): Map<string, Map<string, string>> {
  const out = new Map<string, Map<string, string>>();
  for (const [key, message] of entries) {
    const at = key.indexOf(":");
    const owner = key.slice(0, at);
    const inner = out.get(owner) ?? new Map<string, string>();
    inner.set(key.slice(at + 1), message);
    out.set(owner, inner);
  }
  return out;
}

/** Dopo "Aggiungi blocco": il cursore va nel primo campo del blocco nuovo. */
function focusFirstField(uid: string) {
  requestAnimationFrame(() =>
    document
      .querySelector<HTMLElement>(`[data-uid="${uid}"] .block-row__body :is(input, textarea, select, [contenteditable="true"])`)
      ?.focus(),
  );
}

function focusField(id: string) {
  // Il modulo del blocco si apre al render successivo.
  requestAnimationFrame(() => document.getElementById(id)?.focus());
}

function Workspace({ data }: { data: Loaded }) {
  const { site, can, reloadKey } = useSession();
  const { catalog } = data;
  const [page, setPage] = useState<Page>(data.page);
  const editor = useEditorState(data.draft.data);
  const { doc, selected } = editor;
  const [save, setSave] = useState<SaveState>({ kind: "saved", at: null });
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [serverErrors, setServerErrors] = useState<Map<string, string>>(new Map());
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [view, setView] = useState<"edit" | "preview">("edit");
  // Ultima versione salvata, per l'ultimo valore valido dei campi (D-104): la tiene Autosave.
  const [saved, setSaved] = useState<PageDocument>(data.draft.data);
  // Un salvataggio per pagina caricata (Workspace ha key = id): ricaricare usa reset().
  const [autosave] = useState(
    () =>
      new Autosave(
        async (current, version, base) => {
          const safe = draftSafe(current, catalog, base).doc;
          return { version: await saveDraft(data.page.id, version, safe), saved: safe };
        },
        data.draft.version,
        data.draft.data,
      ),
  );

  useEffect(
    () =>
      autosave.subscribe((state) => {
        setSave(state);
        setSaved(autosave.base);
      }),
    [autosave],
  );
  useEffect(() => autosave.change(doc), [autosave, doc]);

  // Uscita dall'editor: si finisce di salvare anche dopo che la schermata è sparita.
  useEffect(
    () => () => {
      void autosave.flush().finally(() => autosave.dispose());
    },
    [autosave],
  );

  // Dopo un nuovo accesso si risalva senza ricaricare (D-104).
  const firstKey = useRef(reloadKey);
  useEffect(() => {
    if (reloadKey !== firstKey.current) void autosave.retry();
  }, [reloadKey, autosave]);

  useEffect(() => {
    setNavigationGuard(async () => (await autosave.flush()) || window.confirm(ed.save.leave));
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!autosave.dirty) return;
      event.preventDefault();
      event.returnValue = ""; // Safari e browser meno recenti
    }
    function hidden() {
      if (document.visibilityState === "hidden") void autosave.flush();
    }
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      setNavigationGuard(null);
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [autosave]);

  const safe = useMemo(() => draftSafe(doc, catalog, saved), [doc, catalog, saved]);
  const unsaved = useMemo(() => byBlock(safe.problems), [safe]);
  const errors = useMemo(() => byBlock(serverErrors), [serverErrors]);
  const pageErrors = errors.get("page") ?? new Map<string, string>();

  const dropError = useCallback((key: string) => {
    setServerErrors((current) => {
      if (!current.has(key)) return current;
      const next = new Map(current);
      next.delete(key);
      return next;
    });
  }, []);

  const actions: ZoneActions = {
    select: editor.select,
    add: (zone, type) => {
      const uid = newUid(uids(doc));
      editor.update((d) => (hasRoom(d, catalog, zone) ? addBlock(d, zone, newBlock(catalog, type, uid)) : d), null, uid);
      focusFirstField(uid);
    },
    shift: (uid, delta) => editor.update((d) => shiftBlock(d, uid, delta)),
    reorder: (uid, zone, index) => editor.update((d) => moveBlock(d, uid, zone, index)),
    moveTo: (uid, zone) =>
      editor.update((d) => (hasRoom(d, catalog, zone) ? moveBlock(d, uid, zone, d.zones[zone]?.length ?? 0) : d)),
    duplicate: (uid) => {
      const copy = newUid(uids(doc));
      // La zona può avere un massimo (D-110): oltre, il server rifiuterebbe ogni salvataggio.
      editor.update((d) => {
        const found = locate(d, uid);
        return found && hasRoom(d, catalog, found.zone) ? duplicateBlock(d, uid, copy) : d;
      }, null, copy);
    },
    remove: (uid) => {
      const label = catalog.types[locate(doc, uid)?.block.type ?? ""]?.label ?? "";
      editor.update((d) => removeBlock(d, uid), null, selected === uid ? null : selected);
      setNotice({
        kind: "info",
        text: ed.zones.removed(label),
        action: { label: ed.zones.undoRemove, run: editor.undo },
      });
    },
    setVariant: (uid, variant) => editor.update((d) => setVariant(d, uid, variant)),
    // Più campi insieme (aiuti "incolla il link"): un passo solo di annulla.
    patchData: (uid, patch) => {
      Object.keys(patch).forEach((key) => dropError(problemKey(uid, [key])));
      editor.update((d) => Object.entries(patch).reduce((acc, [key, value]) => updateField(acc, uid, [key], value), d));
    },
    editField: (uid: string, path: Path, value: unknown) => {
      dropError(problemKey(uid, path));
      editor.update((d) => updateField(d, uid, path, value), problemKey(uid, path));
    },
  };

  // Annulla/ripristina da tastiera, anche dentro i campi (D-105).
  function keys(event: React.KeyboardEvent) {
    const mod = event.ctrlKey || event.metaKey;
    if (!mod || (event.target as Element).closest("dialog")) return;
    const key = event.key.toLowerCase();
    if (key === "z" && !event.shiftKey) {
      event.preventDefault();
      editor.undo();
    } else if (key === "y" || (key === "z" && event.shiftKey)) {
      event.preventDefault();
      editor.redo();
    }
  }

  async function loadTheirs() {
    const draft: Draft = await fetchDraft(page.id);
    const fresh = normalize(draft.data, catalog, site.default_layout);
    autosave.reset(draft.version, fresh);
    editor.replace(fresh);
  }

  async function keepMine() {
    const draft = await fetchDraft(page.id);
    await autosave.keepMine(draft.version);
  }

  function listErrors(details: unknown, sent: PageDocument): Map<string, string> {
    const found = new Map<string, string>();
    if (!isFieldErrors(details)) return found;
    for (const error of details) {
      const target = locateError(error.path, sent);
      if (target.kind === "block") {
        if (target.uid) found.set(`${target.uid}:${target.field}`, error.message);
      } else if (target.kind === "zone") found.set(`zone:${target.zone}:${error.code}`, error.message);
      else if (target.kind === "seo") found.set(`page:seo/${target.field}`, error.message);
      else found.set(`page:${target.field}`, error.message);
    }
    return found;
  }

  async function publish() {
    const sent = safe.doc;
    try {
      const published = await publishPage(page.id, autosave.draftVersion);
      setPage(published);
      setServerErrors(new Map());
      autosave.reset(0, sent); // la bozza è diventata la pagina online
      setConfirm(null);
      setNotice({ kind: "success", text: ed.publish.done });
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_content") {
        setServerErrors(listErrors(error.details, sent));
        setConfirm(null);
        return;
      }
      throw error;
    }
  }

  async function askPublish() {
    if (!(await autosave.flush())) {
      setNotice({ kind: "error", text: ed.publish.notSaved });
      return;
    }
    setConfirm("publish");
  }

  async function unpublish() {
    setPage(await unpublishPage(page.id, page.version));
    setConfirm(null);
    setNotice({ kind: "success", text: ed.unpublish.done });
  }

  async function discard() {
    await autosave.flush();
    await discardDraft(page.id, autosave.draftVersion);
    await loadTheirs();
    setConfirm(null);
    setServerErrors(new Map());
    setNotice({ kind: "success", text: ed.discard.done });
  }

  const listed: ListedError[] = [...serverErrors.entries()].map(([key, message]) => {
    const at = key.indexOf(":");
    const owner = key.slice(0, at);
    const field = key.slice(at + 1);
    const block = owner !== "page" && owner !== "zone" ? locate(doc, owner) : null;
    const label = block ? `${catalog.types[block.block.type]?.label ?? ""} n. ${block.index + 1}` : owner === "zone" ? field.split(":")[0]! : ed.page.title;
    return {
      key,
      where: label,
      message,
      focus: () => {
        if (block) {
          editor.select(owner);
          focusField(fieldId(`f-${owner}`, field.split("/")));
        } else if (owner === "page") focusField(field.startsWith("seo/") ? `seo-${field.slice(4)}` : field === "layout" ? "page-layout" : "page-title");
      },
    };
  });

  const online = page.status === "published";
  const changes = autosave.draftVersion > 0 || autosave.dirty;
  const mediaIds = [...mediaIdsIn(doc)];
  return (
    <MediaProvider ids={mediaIds}>
    <div className={`editor editor--${view}`} onKeyDownCapture={keys}>
      <header className="editor__bar">
        <Link className="button button--ghost" to={paths.pages}>
          ← {ed.back}
        </Link>
        <span className={`badge badge--${page.status}`}>{ed.status[page.status]}</span>
        {online && changes && <span className="badge">{ed.status.changes}</span>}
        <SaveIndicator state={save} onRetry={() => void autosave.retry()} />
        <span className="editor__spacer" />
        <button type="button" className="button button--small" disabled={!editor.canUndo} onClick={editor.undo}>
          {ed.bar.undo}
        </button>
        <button type="button" className="button button--small" disabled={!editor.canRedo} onClick={editor.redo}>
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
        <a className="button button--small" href={`/_preview/${page.id}`} target="_blank" rel="noopener noreferrer" onClick={() => void autosave.flush()}>
          {ed.bar.openPreview}
        </a>
        {online && (
          <a className="button button--small" href={site.url + page.path} target="_blank" rel="noopener noreferrer">
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
        {can(Permission.publish) ? (
          <button
            type="button"
            className="button button--primary"
            disabled={online && !changes}
            onClick={() => void askPublish()}
          >
            {ed.bar.publish}
          </button>
        ) : (
          <span className="hint">{ed.bar.publishNeedsRight}</span>
        )}
      </header>
      <p className="phone-only hint">{ed.phoneNotice}</p>
      <NoticeArea
        notice={notice}
        onClose={() => setNotice(null)}
      />
      <ErrorList errors={listed} />
      <div className="editor__body">
        <div className="editor__form">
          <h1 className="visually-hidden" tabIndex={-1}>
            {doc.title}
          </h1>
          <PageSettings
            doc={doc}
            catalog={catalog}
            site={site}
            path={page.path}
            errors={pageErrors}
            onTitle={(title) => {
              dropError("page:title");
              editor.update((d) => setTitle(d, title), "page:title");
            }}
            onLayout={(next) => editor.edit(next)}
            onSeo={(key, value) => {
              dropError(`page:seo/${key}`);
              editor.update((d) => setSeo(d, key, value), `page:seo/${key}`);
            }}
          />
          <ZoneList doc={doc} catalog={catalog} selected={selected} errors={errorsWithZones(errors)} unsaved={unsaved} pages={data.pages} actions={actions} />
        </div>
        <div className="editor__preview">
          <PreviewPane pageId={page.id} doc={safe.doc} selected={selected} onSelect={editor.select} />
        </div>
      </div>
      {save.kind === "conflict" && (
        <ConflictDialog error={save.error} onTheirs={loadTheirs} onMine={keepMine} />
      )}
      {confirm === "publish" && (
        <FormDialog title={ed.publish.title} submitLabel={ed.publish.confirm} onClose={() => setConfirm(null)} onSubmit={publish}>
          <p>{ed.publish.question(site.url + page.path)}</p>
        </FormDialog>
      )}
      {confirm === "unpublish" && (
        <FormDialog title={ed.unpublish.title} submitLabel={ed.unpublish.confirm} danger onClose={() => setConfirm(null)} onSubmit={unpublish}>
          <p>{ed.unpublish.question}</p>
        </FormDialog>
      )}
      {confirm === "discard" && (
        <FormDialog title={ed.discard.title} submitLabel={ed.discard.confirm} danger onClose={() => setConfirm(null)} onSubmit={discard}>
          <p>{ed.discard.question}</p>
        </FormDialog>
      )}
    </div>
    </MediaProvider>
  );
}

/** Errori di zona ("zone:main:codice") raggruppati sotto "zone:main" per la lista delle zone. */
function errorsWithZones(errors: Map<string, Map<string, string>>): Map<string, Map<string, string>> {
  const zone = errors.get("zone");
  if (!zone) return errors;
  const out = new Map(errors);
  for (const [key, message] of zone) {
    const name = key.split(":")[0]!;
    const inner = new Map(out.get(`zone:${name}`) ?? []);
    inner.set(key, message);
    out.set(`zone:${name}`, inner);
  }
  return out;
}

function ConflictDialog({ error, onTheirs, onMine }: { error: ApiError; onTheirs: () => Promise<void>; onMine: () => Promise<void> }) {
  const details = (error.details ?? {}) as { updated_by_name?: string };
  const [failure, setFailure] = useState<string | null>(null);
  const run = (action: () => Promise<void>) => () => {
    setFailure(null);
    action().catch((problem: unknown) => setFailure(errorMessage(problem)));
  };
  return (
    <FormDialog title={ed.conflict.title} submitLabel={ed.conflict.theirs} onClose={() => undefined} onSubmit={onTheirs}>
      <p>{ed.conflict.text(details.updated_by_name ?? "un altro utente")}</p>
      <p className="hint">{ed.conflict.theirsHelp}</p>
      <p className="hint">{ed.conflict.mineHelp}</p>
      <button type="button" className="button" onClick={run(onMine)}>
        {ed.conflict.mine}
      </button>
      {failure && <p className="form__error">{failure}</p>}
    </FormDialog>
  );
}

export function EditorScreen({ pageId }: { pageId: number }) {
  const { site } = useSession();
  const { state } = useEditorData(pageId, site.default_locale, site.default_layout);
  if (state.kind === "loading") return <p role="status">{ed.loading}</p>;
  if (state.kind === "failed") {
    return (
      <section className="screen">
        <h1 tabIndex={-1}>{ed.back}</h1>
        <p role="alert">{state.message}</p>
        <Link className="button" to={paths.pages}>
          {ed.back}
        </Link>
      </section>
    );
  }
  return <Workspace key={state.data.page.id} data={state.data} />;
}
