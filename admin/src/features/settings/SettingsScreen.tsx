import { useCallback, useEffect, useState, type FormEvent } from "react";
import { fetchSettings, storeSettings, type SettingsScope, type SettingsSection, type SettingsValues } from "../../api/settings";
import { ApiError, errorMessage, isConflict } from "../../api/client";
import { st } from "../../text/settings";
import { NoticeArea, type NoticeState } from "../../ui/Notice";
import { useSession } from "../../session/context";
import { useAction } from "../../ui/useAction";
import { setPath, type Data, type Path } from "../editor/model/document";
import { isFieldErrors } from "../editor/model/errorPaths";
import { SchemaForm } from "../editor/schema/SchemaForm";
import { MediaProvider } from "../media-picker/MediaContext";

const NONE: ReadonlyMap<string, string> = new Map();

interface FormProps {
  scope: SettingsScope;
  title: string;
  help: string;
  initial: SettingsSection;
  onReload: () => void;
}

/** Un gruppo di impostazioni con il suo "Salva" (D-143): nessun salvataggio automatico. */
function SettingsForm({ scope, title, help, initial, onReload }: FormProps) {
  const [values, setValues] = useState<SettingsValues>(initial.values);
  const [version, setVersion] = useState(initial.version);
  const [errors, setErrors] = useState<ReadonlyMap<string, string>>(NONE);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const action = useAction();
  const { renameSite } = useSession();
  const titleId = `settings-${scope}`;
  const logo = values.logo;

  function submit(event: FormEvent) {
    event.preventDefault();
    setNotice(null);
    void action.run(async () => {
      try {
        const saved = await storeSettings(scope, version, values);
        setValues(saved.values);
        setVersion(saved.version);
        setErrors(NONE);
        setNotice({ kind: "success", text: st.saved });
        if (scope === "site" && typeof saved.values.name === "string") renameSite(saved.values.name);
      } catch (error) {
        if (error instanceof ApiError && error.code === "invalid_content" && isFieldErrors(error.details)) {
          setErrors(new Map(error.details.map((detail) => [detail.path, detail.message])));
        }
        if (isConflict(error)) {
          setErrors(NONE);
          setNotice({ kind: "error", text: errorMessage(error), action: { label: st.reload, run: onReload } });
          return;
        }
        throw error;
      }
    });
  }

  return (
    <section className="card" aria-labelledby={titleId}>
      <h2 id={titleId}>{title}</h2>
      <p className="hint">{help}</p>
      <NoticeArea notice={notice} onClose={() => setNotice(null)} />
      <form className="form" onSubmit={submit} noValidate>
        {/* Il logo scelto si vede subito: i media si leggono dai valori del modulo. */}
        <MediaProvider ids={typeof logo === "number" ? [logo] : []}>
          <SchemaForm
            schema={initial.schema}
            data={values as Data}
            idPrefix={titleId}
            errors={errors}
            unsaved={NONE}
            pages={[]}
            onChange={(path: Path, value: unknown) => {
              setValues((current) => setPath(current, path, value) as SettingsValues);
              const key = path.join("/");
              // L'errore di un campo sparisce appena lo si corregge.
              setErrors((current) => (current.has(key) ? new Map([...current].filter(([k]) => k !== key)) : current));
            }}
          />
        </MediaProvider>
        {action.error && (
          <p className="form__error" role="alert">
            {action.error}
          </p>
        )}
        <div className="form__actions">
          <button type="submit" className="button button--primary" disabled={action.busy}>
            {st.save}
          </button>
        </div>
      </form>
    </section>
  );
}

/** Impostazioni (6a, D-14, D-143): dati del sito e scelte d'aspetto dichiarate dal tema. */
export function SettingsScreen() {
  const [sections, setSections] = useState<Record<SettingsScope, SettingsSection> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchSettings().then(
      (found) => {
        setSections(found);
        setError(null);
      },
      (failure: unknown) => setError(errorMessage(failure)),
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="screen" aria-labelledby="settings-title">
      <div className="screen__head">
        <h1 id="settings-title" tabIndex={-1}>
          {st.title}
        </h1>
      </div>
      {error && (
        <p className="notice notice--error" role="alert">
          {error}
        </p>
      )}
      {!sections && !error && <p role="status">{st.loading}</p>}
      {sections && (
        <>
          {/* key con la versione: dopo "Ricarica" il modulo riparte dai valori del server */}
          <SettingsForm key={`site-${sections.site.version}`} scope="site" title={st.site} help={st.siteHelp} initial={sections.site} onReload={load} />
          <SettingsForm
            key={`appearance-${sections.appearance.version}`}
            scope="appearance"
            title={st.appearance}
            help={st.appearanceHelp}
            initial={sections.appearance}
            onReload={load}
          />
        </>
      )}
    </section>
  );
}
