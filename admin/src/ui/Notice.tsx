import { it } from "../text/it";

export type NoticeKind = "success" | "error" | "info";

export interface NoticeState {
  kind: NoticeKind;
  text: string;
  /** Azione accanto al testo, es. "Annulla" dopo un'eliminazione. */
  action?: { label: string; run: () => void };
}

interface Props {
  notice: NoticeState | null;
  onClose?: () => void;
}

/** Zona avvisi sempre presente: i lettori di schermo annunciano ogni testo nuovo.
 * Gli errori usano role=alert, che si annuncia subito. */
export function NoticeArea({ notice, onClose }: Props) {
  return (
    <div className="notice-area" aria-live="polite">
      {notice && (
        <div
          className={`notice notice--${notice.kind}`}
          role={notice.kind === "error" ? "alert" : undefined}
        >
          <p>{notice.text}</p>
          {notice.action && (
            <button
              type="button"
              className="button button--small"
              onClick={() => {
                notice.action?.run();
                onClose?.();
              }}
            >
              {notice.action.label}
            </button>
          )}
          {onClose && (
            <button
              type="button"
              className="notice__close"
              onClick={onClose}
              aria-label={it.dialog.close}
            >
              ×
            </button>
          )}
        </div>
      )}
    </div>
  );
}
