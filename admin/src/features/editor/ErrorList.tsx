import { ed } from "../../text/editor";

export interface ListedError {
  key: string;
  where: string;
  message: string;
  /** Assente quando non c'è un campo da raggiungere (es. pagina senza blocchi). */
  focus?: (() => void) | undefined;
}

function Items({ errors, goLabel }: { errors: ListedError[]; goLabel: string }) {
  return (
    <ul>
      {errors.map((error) => (
        <li key={error.key}>
          <strong>{error.where}</strong> · {error.message}{" "}
          {error.focus && (
            <button type="button" className="button button--small" onClick={error.focus}>
              {goLabel}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Avvisi del controllo prima di pubblicare (D-135): non bloccano. */
export function WarningList({ warnings, goLabel = ed.publish.goTo }: { warnings: ListedError[]; goLabel?: string }) {
  if (warnings.length === 0) return null;
  return (
    <section className="notice notice--info error-list" aria-labelledby="publish-warnings">
      <h3 id="publish-warnings">{ed.publish.warningsTitle}</h3>
      <Items errors={warnings} goLabel={goLabel} />
    </section>
  );
}

/** Errori della pubblicazione (D-113) con "Vai al campo". */
export function ErrorList({ errors }: { errors: ListedError[] }) {
  if (errors.length === 0) return null;
  return (
    <section className="notice notice--error error-list" role="alert" aria-labelledby="publish-errors">
      <h2 id="publish-errors">{ed.publish.errorsTitle}</h2>
      <Items errors={errors} goLabel={ed.publish.goTo} />
    </section>
  );
}
