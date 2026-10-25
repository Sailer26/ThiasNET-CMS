import { useState } from "react";
import type { Catalog } from "../../../api/catalog";
import type { Site } from "../../../api/types";
import { ed } from "../../../text/editor";
import { FormDialog } from "../../../ui/FormDialog";
import type { PageDocument, Seo } from "../model/document";
import { relayout } from "../model/relayout";
import { SeoFields } from "./SeoFields";

const TITLE_MAX = 200;

interface Props {
  doc: PageDocument;
  catalog: Catalog;
  site: Site;
  path: string;
  errors: ReadonlyMap<string, string>;
  onTitle: (title: string) => void;
  onLayout: (doc: PageDocument) => void;
  onSeo: <K extends keyof Seo>(key: K, value: Seo[K] | undefined) => void;
}

function Problem({ id, text }: { id: string; text: string | undefined }) {
  return text ? (
    <p id={id} className="form__error">
      {text}
    </p>
  ) : null;
}

export function PageSettings({ doc, catalog, site, path, errors, onTitle, onLayout, onSeo }: Props) {
  const [pending, setPending] = useState<ReturnType<typeof relayout> | null>(null);

  function chooseLayout(name: string) {
    const result = relayout(doc, catalog, name);
    if (result.dropped.length > 0) setPending(result);
    else onLayout(result.doc);
  }

  return (
    <section className="page-settings" aria-label={ed.page.settings}>
      <div className={`field${errors.get("title") ? " field--error" : ""}`}>
        <label htmlFor="page-title">{ed.page.title}</label>
        <input
          id="page-title"
          className="page-settings__title"
          maxLength={TITLE_MAX}
          value={doc.title}
          aria-describedby={errors.get("title") ? "page-title-problem" : undefined}
          onChange={(event) => onTitle(event.target.value)}
        />
        <Problem id="page-title-problem" text={errors.get("title")} />
      </div>
      <div className="field">
        <label htmlFor="page-layout">{ed.page.layout}</label>
        <select id="page-layout" value={doc.layout} onChange={(event) => chooseLayout(event.target.value)}>
          {Object.entries(catalog.layouts).map(([name, layout]) => (
            <option key={name} value={name}>
              {layout.label}
            </option>
          ))}
        </select>
        <Problem id="page-layout-problem" text={errors.get("layout")} />
      </div>
      <SeoFields seo={doc.seo} title={doc.title} url={site.url + path} errors={errors} onSeo={onSeo} />
      {pending && (
        <FormDialog
          title={ed.page.relayoutTitle}
          submitLabel={ed.page.relayoutConfirm}
          danger
          onClose={() => setPending(null)}
          onSubmit={async () => {
            onLayout(pending.doc);
            setPending(null);
          }}
        >
          <p>{ed.page.relayoutDropped}</p>
          <ul>
            {pending.dropped.map((block) => (
              <li key={block.uid}>{catalog.types[block.type]?.label ?? block.type}</li>
            ))}
          </ul>
        </FormDialog>
      )}
    </section>
  );
}
