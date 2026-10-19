import { useId, useState } from "react";
import { at } from "../../text/admin";
import { generatePassword } from "./password";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

/** Password scelta da chi crea l'utente (D-123): Genera, Mostra, Copia. */
export function PasswordField({ value, onChange }: Props) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const id = useId();

  function copy() {
    const clipboard = navigator.clipboard as Clipboard | undefined;
    if (!clipboard) return;
    clipboard.writeText(value).then(
      () => setCopied(true),
      () => setCopied(false),
    );
  }

  return (
    <div className="field">
      <label htmlFor={id}>{at.users.password}</label>
      <div className="password-field">
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete="new-password"
          spellCheck={false}
          value={value}
          maxLength={128}
          aria-describedby={`${id}-help`}
          onChange={(event) => {
            setCopied(false);
            onChange(event.target.value);
          }}
        />
        <button
          type="button"
          className="button button--small"
          onClick={() => {
            setCopied(false);
            onChange(generatePassword());
          }}
        >
          {at.users.generate}
        </button>
        <button type="button" className="button button--small" aria-pressed={visible} onClick={() => setVisible(!visible)}>
          {visible ? at.users.hide : at.users.show}
        </button>
        <button type="button" className="button button--small" disabled={!value} onClick={copy}>
          {at.users.copy}
        </button>
      </div>
      <span id={`${id}-help`} className="hint" aria-live="polite">
        {at.users.passwordHelp} {copied ? at.users.copied : ""}
      </span>
    </div>
  );
}
