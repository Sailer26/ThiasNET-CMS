import { it } from "../text/it";

export type NoticeKind = "success" | "error" | "info";

export interface NoticeState {
  kind: NoticeKind;
  text: string;
}

interface Props extends NoticeState {
  onClose?: () => void;
}

export function Notice({ kind, text, onClose }: Props) {
  return (
    <div className={`notice notice--${kind}`} role={kind === "error" ? "alert" : "status"}>
      <p>{text}</p>
      {onClose && (
        <button type="button" className="notice__close" onClick={onClose} aria-label={it.dialog.close}>
          ×
        </button>
      )}
    </div>
  );
}
