import { useCallback, useEffect, useRef, useState } from "react";
import { getMessage, listMessages, markMessage, deleteMessage, type MessageSummary } from "../../api/admin";
import { errorMessage } from "../../api/client";
import { Link } from "../../router/Link";
import { navigate, paths } from "../../router/router";
import { at } from "../../text/admin";
import { FormDialog } from "../../ui/FormDialog";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { formatZurich } from "../editor/schedule/siteTime";
import { refreshUnread } from "./unread";

const SEARCH_PAUSE_MS = 300;

function telLink(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

/** "Mostra altri" con un messaggio arrivato nel frattempo: la stessa riga non compare due volte. */
function appendNew(current: MessageSummary[], more: MessageSummary[]): MessageSummary[] {
  const seen = new Set(current.map((message) => message.id));
  return [...current, ...more.filter((message) => !seen.has(message.id))];
}

function day(iso: string): string {
  return formatZurich(iso).replace(/ alle .*/, "");
}

/** Elenco dei messaggi (D-126). */
export function MessagesScreen() {
  const [query, setQuery] = useState("");
  const [unread, setUnread] = useState(false);
  const [items, setItems] = useState<MessageSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const latest = useRef(0);

  const load = useCallback(
    (pageNo: number) => {
      const request = ++latest.current;
      listMessages({ q: query.trim() || undefined, unread, page: pageNo }).then(
        (result) => {
          if (request !== latest.current) return;
          setItems((current) => (pageNo === 1 || !current ? result.items : appendNew(current, result.items)));
          setTotal(result.total);
          setPage(pageNo);
          setNotice(null);
        },
        (error: unknown) => {
          if (request === latest.current) setNotice({ kind: "error", text: errorMessage(error) });
        },
      );
    },
    [query, unread],
  );

  useEffect(() => {
    const timer = setTimeout(() => load(1), query ? SEARCH_PAUSE_MS : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  useEffect(() => {
    void refreshUnread();
  }, []);

  return (
    <section className="screen" aria-labelledby="messages-title">
      <div className="screen__head">
        <h1 id="messages-title" tabIndex={-1}>
          {at.messages.title}
        </h1>
      </div>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <div className="filters">
        <div className="filters__tabs" role="group" aria-label={at.messages.title}>
          <button type="button" className="button button--small" aria-pressed={!unread} onClick={() => setUnread(false)}>
            {at.messages.all}
          </button>
          <button type="button" className="button button--small" aria-pressed={unread} onClick={() => setUnread(true)}>
            {at.messages.unread}
          </button>
        </div>
        <label className="field">
          <span>{at.messages.search}</span>
          <input type="search" maxLength={100} value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
      </div>
      {items === null && !notice && <p role="status">{at.loading}</p>}
      {items === null && notice && (
        <button type="button" className="button" onClick={() => load(1)}>
          {at.retry}
        </button>
      )}
      {items?.length === 0 && <p className="empty">{at.messages.empty}</p>}
      {items && items.length > 0 && (
        <ul className="messages">
          {items.map((message) => (
            <li key={message.id} className={`messages__item${message.read_at ? "" : " messages__item--unread"}`}>
              <Link to={paths.message(message.id)} className="messages__link">
                <span className="messages__from">
                  {message.name} · {message.email}
                </span>
                <span className="hint">{message.excerpt}</span>
                <span className="hint">
                  {day(message.created_at)}
                  {message.page ? ` · ${message.page.title}` : ""}
                </span>
              </Link>
              {!message.read_at && <span className="badge">{at.messages.unread}</span>}
              {message.delivery === "failed" && <span className="badge badge--error">{at.messages.notSent}</span>}
            </li>
          ))}
        </ul>
      )}
      {items && items.length < total && (
        <button type="button" className="button" onClick={() => load(page + 1)}>
          {at.more}
        </button>
      )}
    </section>
  );
}

/** Un messaggio (D-126): letto all'apertura, Rispondi, Segna come da leggere, Elimina. */
export function MessageScreen({ id }: { id: number }) {
  const [message, setMessage] = useState<MessageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let active = true;
    getMessage(id)
      .then(async (found) => {
        if (active) setMessage(found);
        if (found.read_at) return;
        try {
          const read = await markMessage(id, true);
          if (active) setMessage(read);
          void refreshUnread();
        } catch (failure) {
          // Il messaggio si legge lo stesso; resta "da leggere" e lo si dice sopra il testo.
          if (active) setError(errorMessage(failure));
        }
      })
      .catch((failure: unknown) => {
        if (active) setError(errorMessage(failure));
      });
    return () => {
      active = false;
    };
  }, [id]);

  function markUnread() {
    markMessage(id, false).then(
      () => {
        void refreshUnread();
        void navigate(paths.messages);
      },
      (failure: unknown) => setError(errorMessage(failure)),
    );
  }

  if (error && !message) {
    return (
      <section className="screen">
        <h1 tabIndex={-1}>{at.messages.title}</h1>
        <p role="alert">{error}</p>
        <Link className="button" to={paths.messages}>
          {at.messages.backToList}
        </Link>
      </section>
    );
  }
  if (!message) return <p role="status">{at.loading}</p>;
  const reply = `mailto:${encodeURIComponent(message.email)}?subject=${encodeURIComponent(at.messages.replySubject)}`;
  return (
    <section className="screen message" aria-labelledby="message-title">
      <Link to={paths.messages}>← {at.messages.backToList}</Link>
      <h1 id="message-title" tabIndex={-1}>
        {message.name}
      </h1>
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {message.delivery === "failed" && <p className="notice notice--info">{at.messages.notSentHelp}</p>}
      <dl className="message__meta">
        <dt>{at.messages.from}</dt>
        <dd>{message.email}</dd>
        {message.phone && (
          <>
            <dt>{at.messages.phone}</dt>
            <dd>
              <a href={telLink(message.phone)}>{message.phone}</a>
            </dd>
          </>
        )}
        {message.page && (
          <>
            <dt>{at.messages.page}</dt>
            <dd>
              {message.page.title} {message.page.trashed && at.messages.trashed}
            </dd>
          </>
        )}
        <dt>{at.messages.received}</dt>
        <dd>{formatZurich(message.created_at)}</dd>
      </dl>
      <p className="message__text">{message.message}</p>
      <p className="hint">{at.messages.expires(day(message.expires_at))}</p>
      <div className="form__actions">
        <a className="button button--primary" href={reply}>
          {at.messages.reply}
        </a>
        <button type="button" className="button" onClick={markUnread}>
          {at.messages.markUnread}
        </button>
        <button type="button" className="button button--danger" onClick={() => setConfirming(true)}>
          {at.messages.remove}
        </button>
      </div>
      {confirming && (
        <FormDialog
          title={at.messages.removeTitle}
          submitLabel={at.messages.remove}
          danger
          onClose={() => setConfirming(false)}
          onSubmit={async () => {
            await deleteMessage(id);
            void refreshUnread();
            await navigate(paths.messages);
          }}
        >
          <p>{at.messages.removeText}</p>
        </FormDialog>
      )}
    </section>
  );
}
