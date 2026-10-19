import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { at } from "../../text/admin";

/** Sezione senza permesso (D-130): il server risponderebbe comunque 403. */
export function NoAccess() {
  return (
    <section className="screen">
      <h1 tabIndex={-1}>{at.noAccess}</h1>
      <Link className="button" to={paths.pages}>
        {at.back}
      </Link>
    </section>
  );
}
