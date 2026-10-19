import { useId, useState } from "react";
import { askThias } from "../../api/support";
import { hp } from "../../text/help";
import { FormDialog } from "../../ui/FormDialog";

interface Props {
  pageId: number | null;
  onClose: () => void;
  onSent: (text: string) => void;
}

/** "Chiedi a Thias" (D-09, D-134): testo libero, pagina e schermata aggiunte da sole. */
export function AskThias({ pageId, onClose, onSent }: Props) {
  const [message, setMessage] = useState("");
  const id = useId();
  return (
    <FormDialog
      title={hp.ask}
      submitLabel={hp.send}
      canSubmit={message.trim().length > 0}
      onClose={onClose}
      onSubmit={async () => {
        await askThias({ message: message.trim(), page_id: pageId, screen: window.location.pathname });
        onSent(hp.sent);
      }}
    >
      <div className="field">
        <label htmlFor={id}>{hp.askLabel}</label>
        <textarea
          id={id}
          rows={6}
          maxLength={hp.maxLength}
          value={message}
          aria-describedby={`${id}-help`}
          onChange={(event) => setMessage(event.target.value)}
        />
        <span id={`${id}-help`} className="hint">
          {hp.askHelp} {pageId !== null && hp.askPage}
        </span>
      </div>
    </FormDialog>
  );
}
