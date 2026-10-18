import { ed } from "../../text/editor";

export interface ListedError {
  key: string;
  where: string;
  message: string;
  focus: () => void;
}

/** Errori della pubblicazione (D-113) con "Vai al campo". */
export function ErrorList({ errors }: { errors: ListedError[] }) {
  if (errors.length === 0) return null;
  return (
    <section className="notice notice--error error-list" role="alert" aria-labelledby="publish-errors">
      <h2 id="publish-errors">{ed.publish.errorsTitle}</h2>
      <ul>
        {errors.map((error) => (
          <li key={error.key}>
            <strong>{error.where}</strong> · {error.message}{" "}
            <button type="button" className="button button--small" onClick={error.focus}>
              {ed.publish.goTo}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
