import { useId } from "react";
import { ApiError } from "../../api/client";
import { wg } from "../../text/widgets";
import { isoToZurich, zurichToIso } from "../editor/schedule/siteTime";

const TIME_STEP_S = 300; // 5 minuti

export interface Until {
  date: string;
  time: string;
}

export const NO_END: Until = { date: "", time: "" };

/** Il "fino al" salvato nei campi del modulo; uno già passato non si propone di nuovo. */
export function untilFields(iso: string | null | undefined, now = Date.now()): Until {
  if (!iso || new Date(iso).getTime() <= now) return NO_END;
  return isoToZurich(iso) ?? NO_END;
}

/** Un "fino al" non toccato resta com'è: correggere il testo non chiede una data nuova. */
export function nextUntil(current: Until, start: Until, saved: string | null | undefined): string | null {
  const untouched = start.date !== "" && current.date === start.date && current.time === start.time;
  return untouched ? (saved ?? null) : untilIso(current);
}

/** "Fino al" del banner → ISO con il fuso (ora svizzera, D-122); vuoto = senza scadenza. */
export function untilIso({ date, time }: Until, now = Date.now()): string | null {
  if (!date && !time) return null;
  const converted = zurichToIso(date, time || "23:59");
  if ("error" in converted) {
    throw new ApiError(422, converted.error, converted.error === "missing_hour" ? wg.untilMissingHour : wg.untilInvalid);
  }
  if (converted.utcMs <= now) throw new ApiError(422, "past", wg.untilPast);
  return converted.iso;
}

interface Props {
  value: Until;
  onChange: (next: Until) => void;
}

export function UntilFields({ value, onChange }: Props) {
  const id = useId();
  return (
    <fieldset className="field">
      <legend>{wg.until}</legend>
      <div className="schedule-fields">
        <div className="field">
          <label htmlFor={`${id}-date`}>{wg.date}</label>
          <input id={`${id}-date`} type="date" value={value.date} aria-describedby={`${id}-help`} onChange={(event) => onChange({ ...value, date: event.target.value })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-time`}>{wg.time}</label>
          <input id={`${id}-time`} type="time" step={TIME_STEP_S} value={value.time} aria-describedby={`${id}-help`} onChange={(event) => onChange({ ...value, time: event.target.value })} />
        </div>
      </div>
      <p id={`${id}-help`} className="hint">
        {wg.untilHelp}
      </p>
    </fieldset>
  );
}
