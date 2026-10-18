import { useId, useState } from "react";
import { ApiError } from "../../../api/client";
import { ed } from "../../../text/editor";
import { FormDialog } from "../../../ui/FormDialog";
import { zurichToday, zurichToIso } from "./siteTime";

const DAY_MS = 86_400_000;
const YEAR_DAYS = 365;
const TIME_STEP_S = 300; // 5 minuti

interface Props {
  onSchedule: (iso: string) => Promise<void>;
  onClose: () => void;
}

/** Programmazione (D-47, D-122): data e ora native, sempre nell'ora svizzera. */
export function ScheduleDialog({ onSchedule, onClose }: Props) {
  const [opened] = useState(() => Date.now()); // l'ora di apertura fissa i limiti del campo
  const today = zurichToday(opened);
  const [date, setDate] = useState(() => zurichToday(opened + DAY_MS));
  const [time, setTime] = useState("08:00");
  const dateId = useId();
  const timeId = useId();
  const last = zurichToday(opened + YEAR_DAYS * DAY_MS);
  return (
    <FormDialog
      title={ed.schedule.title}
      submitLabel={ed.schedule.confirm}
      canSubmit={Boolean(date && time)}
      onClose={onClose}
      onSubmit={async () => {
        const converted = zurichToIso(date, time);
        if ("error" in converted) {
          throw new ApiError(422, converted.error, converted.error === "missing_hour" ? ed.schedule.missingHour : ed.schedule.invalid);
        }
        if (converted.utcMs <= Date.now()) throw new ApiError(422, "past", ed.schedule.past);
        await onSchedule(converted.iso);
      }}
    >
      <div className="schedule-fields">
        <div className="field">
          <label htmlFor={dateId}>{ed.schedule.date}</label>
          <input id={dateId} type="date" min={today} max={last} value={date} onChange={(event) => setDate(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={timeId}>{ed.schedule.time}</label>
          <input id={timeId} type="time" step={TIME_STEP_S} value={time} onChange={(event) => setTime(event.target.value)} />
        </div>
      </div>
      <p className="hint">{ed.schedule.zone}</p>
    </FormDialog>
  );
}
