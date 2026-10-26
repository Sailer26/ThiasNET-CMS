// Riquadro "Traduzioni" degli editor (7c, D-151, D-159): si apre su richiesta, una riga per lingua.
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { fetchTranslations, translate, type Translation, type TranslationKind } from "../../api/translations";
import { navigate, paths } from "../../router/router";
import { usePanelLocale } from "../../session/localeContext";
import { languageName } from "../../text/languages";
import { tr } from "../../text/translations";

interface Props {
  kind: TranslationKind;
  id: number;
  /** Lingua di questa pagina o notizia. */
  locale: string;
  collection?: string;
}

export function TranslationsBox({ kind, id, locale, collection = "" }: Props) {
  const { locales, setLocale } = usePanelLocale();
  const [rows, setRows] = useState<Translation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  if (locales.length < 2) return null;

  const target = (other: number) => (kind === "page" ? paths.page(other) : paths.entry(collection, other));

  function load() {
    setError(null);
    fetchTranslations(kind, id).then(setRows, (failure: unknown) => setError(errorMessage(failure)));
  }

  /** Aprire una traduzione porta il pannello in quella lingua (D-159), se l'editor la lascia andare. */
  async function openOther(other: number, language: string) {
    const to = target(other);
    await navigate(to);
    if (window.location.pathname === to) setLocale(language);
  }

  async function create(language: string) {
    setBusy(true);
    setError(null);
    try {
      const created = await translate(kind, id, language);
      await openOther(created.id, language);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="translations">
      <button
        type="button"
        className="translations__toggle"
        aria-expanded={expanded}
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded && rows === null) load();
        }}
      >
        {tr.title}
      </button>
      {expanded && <p className="hint">{tr.intro}</p>}
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {expanded && !rows && !error && <p role="status">{tr.loading}</p>}
      {expanded && rows && (
        <ul className="translations__list">
          {rows
            .filter((row) => row.locale !== locale)
            .map((row) => {
              const language = languageName(row.locale);
              const other = row.id;
              return (
                <li key={row.locale}>
                  <span className="translations__language">{language}</span>
                  {other === null ? (
                    <button type="button" className="button button--small" disabled={busy} onClick={() => void create(row.locale)}>
                      {tr.create(language)}
                    </button>
                  ) : (
                    <>
                      <span className="hint">{tr.status[row.status ?? ""] ?? ""}</span>
                      <button type="button" className="button button--small button--ghost" onClick={() => void openOther(other, row.locale)}>
                        {tr.open(language)}
                      </button>
                    </>
                  )}
                </li>
              );
            })}
        </ul>
      )}
    </section>
  );
}
