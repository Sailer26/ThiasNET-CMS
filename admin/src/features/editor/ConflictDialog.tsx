import { useState } from "react";
import { errorMessage, type ApiError } from "../../api/client";
import { ed } from "../../text/editor";
import { FormDialog } from "../../ui/FormDialog";

interface Props {
  error: ApiError;
  onTheirs: () => Promise<void>;
  onMine: () => Promise<void>;
}

/** Qualcun altro ha salvato (D-92): "Carica la sua" oppure "Tieni la mia". */
export function ConflictDialog({ error, onTheirs, onMine }: Props) {
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
