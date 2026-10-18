import { Link } from "../../router/Link";
import { paths } from "../../router/router";
import { it } from "../../text/it";

/** Provvisorio fino alla 5b: l'editor della pagina. */
export function PagePlaceholder() {
  return (
    <section className="screen" aria-labelledby="editor-title">
      <h1 id="editor-title">{it.tree.title}</h1>
      <p>{it.tree.editorSoon}</p>
      <Link className="button" to={paths.pages}>
        {it.shell.backToPages}
      </Link>
    </section>
  );
}
