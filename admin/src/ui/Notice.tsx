import { it } from "../text/it";

export type NoticeKind = "success" | "error" | "info";

export interface NoticeState {
  kind: NoticeKind;
  text: string;
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
