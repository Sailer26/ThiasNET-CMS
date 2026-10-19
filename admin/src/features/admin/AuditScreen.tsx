import { useEffect, useRef, useState } from "react";
import { AUDIT_PAGE_SIZE, listAudit, listUsers, type AuditEntry, type AuditQuery } from "../../api/admin";
import { errorMessage } from "../../api/client";
import type { User } from "../../api/types";
import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { at } from "../../text/admin";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { formatZurich } from "../editor/schedule/siteTime";
import { actionLabel, CATEGORY_LABELS, diffLines } from "./actions";

function objectName(entry: AuditEntry) {
  if (!entry.entity_label) return null;
  if (entry.entity === "page" && entry.entity_id && /^\d{1,9}$/.test(entry.entity_id)) {
    return <Link to={paths.page(Number(entry.entity_id))}>{entry.entity_label}</Link>;
  }
  return <span>{entry.entity_label}</span>;
}

/** Registro attività (D-124): solo owner; 50 righe per pagina, dettagli come testo. */
export function AuditScreen() {
  const [filters, setFilters] = useState<AuditQuery>({});
  const [page, setPage] = useState(1);
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [people, setPeople] = useState<User[]>([]);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loadedFor, setLoadedFor] = useState("");
  const latest = useRef(0);
  const badRange = Boolean(filters.since && filters.until && filters.since > filters.until);
  const requestKey = JSON.stringify({ filters, page, attempt });
  const loading = entries !== null && !badRange && loadedFor !== requestKey;

  useEffect(() => {
    if (badRange) return; // si segnala sotto i filtri: il server non serve
    const request = ++latest.current;
    const key = JSON.stringify({ filters, page, attempt });
    listAudit({ ...filters, page }).then(
      (result) => {
        if (request !== latest.current) return;
        setEntries(result.items);
        setTotal(result.total);
        setNotice(null);
        setLoadedFor(key);
      },
      (error: unknown) => {
        if (request === latest.current) setNotice({ kind: "error", text: errorMessage(error) });
      },
    );
  }, [filters, page, attempt, badRange]); // "attempt" cresce con "Riprova"

  useEffect(() => {
    // L'elenco delle persone è solo un aiuto per il filtro: senza, si filtra lo stesso.
    listUsers().then(
      (found) => setPeople(found.items),
      () => undefined,
    );
  }, []);

  const change = (patch: Partial<AuditQuery>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };
  const pages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE));

  return (
    <section className="screen" aria-labelledby="audit-title">
      <div className="screen__head">
        <h1 id="audit-title" tabIndex={-1}>
          {at.audit.title}
        </h1>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <div className="filters">
        <label className="field">
          <span>{at.audit.who}</span>
          <select
            value={filters.user_id ?? ""}
            onChange={(event) => change({ user_id: event.target.value ? Number(event.target.value) : undefined })}
          >
            <option value="">{at.audit.everyone}</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.email}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{at.audit.type}</span>
          <select value={filters.category ?? ""} onChange={(event) => change({ category: event.target.value || undefined })}>
            <option value="">{at.audit.allTypes}</option>
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{at.audit.since}</span>
          <input type="date" value={filters.since ?? ""} onChange={(event) => change({ since: event.target.value || undefined })} />
        </label>
        <label className="field">
          <span>{at.audit.until}</span>
          <input type="date" value={filters.until ?? ""} onChange={(event) => change({ until: event.target.value || undefined })} />
        </label>
        {filters.entity && (
          <button type="button" className="button button--small" onClick={() => change({ entity: undefined, entity_id: undefined })}>
            {at.audit.clearObject}
          </button>
        )}
      </div>
      {badRange && (
        <p className="form__error" role="alert">
          {at.audit.badRange}
        </p>
      )}
      <p role="status" className="hint">
        {loading ? at.loading : ""}
      </p>
      {entries === null && !notice && <p role="status">{at.loading}</p>}
      {entries === null && notice && (
        <button type="button" className="button" onClick={() => setAttempt(attempt + 1)}>
          {at.retry}
        </button>
      )}
      {entries?.length === 0 && <p className="empty">{at.audit.empty}</p>}
      {entries && entries.length > 0 && (
        <ul className="audit" aria-busy={loading}>
          {entries.map((entry) => (
            <AuditRow key={entry.id} entry={entry} onObject={(entity, entityId) => change({ entity, entity_id: entityId })} />
          ))}
        </ul>
      )}
      {pages > 1 && (
        <div className="form__actions">
          <button type="button" className="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            {at.audit.newer}
          </button>
          <button type="button" className="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            {at.audit.older}
          </button>
        </div>
      )}
    </section>
  );
}

interface RowProps {
  entry: AuditEntry;
  onObject: (entity: string, entityId: string) => void;
}

function AuditRow({ entry, onObject }: RowProps) {
  const lines = diffLines(entry.diff);
  const { entity, entity_id: entityId } = entry;
  return (
    <li className="audit__item">
      <span className="hint">{formatZurich(entry.created_at)}</span>
      <span>
        <strong>{entry.actor_email ?? at.audit.system}</strong> · {actionLabel(entry.action)} {objectName(entry)}
      </span>
      {entity && entityId && (
        <button type="button" className="button button--small" onClick={() => onObject(entity, entityId)}>
          {at.audit.object}
        </button>
      )}
      {lines.length > 0 && (
        <details>
          <summary>{at.audit.details}</summary>
          <ul>
            {lines.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}
