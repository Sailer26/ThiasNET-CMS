import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it as test, vi } from "vitest";
import type { FieldSchema } from "../../../api/catalog";
import { SchemaForm } from "./SchemaForm";
import { fieldProblem, isDate, isDateTime } from "./validate";

const NONE: ReadonlyMap<string, string> = new Map();
const SCHEMA: FieldSchema = {
  type: "object",
  properties: {
    date: { type: "string", title: "Data", "x-date": true, maxLength: 10 },
    start: { type: "string", title: "Inizio", "x-datetime": true, maxLength: 40 },
    summary: { type: "string", title: "Riassunto", "x-multiline": true, maxLength: 150 },
  },
};

function form(data: Record<string, unknown>, onChange = vi.fn()) {
  render(<SchemaForm schema={SCHEMA} data={data} idPrefix="t" errors={NONE} unsaved={NONE} pages={[]} onChange={onChange} />);
  return onChange;
}

describe("date nei moduli (7b)", () => {
  test("giorni veri, come il server", () => {
    expect(isDate("2026-10-25")).toBe(true);
    expect(isDate("2026-02-31")).toBe(false);
    expect(isDate("25.10.2026")).toBe(false);
    expect(isDateTime("2026-10-25T08:00:00+01:00")).toBe(true);
    expect(isDateTime("2026-10-25T08:00:00")).toBe(false);
    expect(fieldProblem(SCHEMA.properties!.date!, "2026-13-01")).toBe("Data non valida");
  });

  test("campo data: il selettore del browser, vuoto toglie il valore", async () => {
    const onChange = form({ date: "2026-10-25" });
    const input = screen.getByLabelText(/^Data/);
    expect(input).toHaveAttribute("type", "date");
    expect(input).toHaveValue("2026-10-25");
    await userEvent.clear(input);
    expect(onChange).toHaveBeenLastCalledWith(["date"], undefined);
  });

  test("data e ora: l'istante arriva solo quando ci sono tutte e due, con il fuso svizzero", async () => {
    const onChange = form({});
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Giorno"), "2099-01-10");
    expect(onChange).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Ora"), "08:00");
    expect(onChange).toHaveBeenLastCalledWith(["start"], "2099-01-10T08:00:00+01:00");
  });

  test("testo lungo in un'area di testo anche sotto i 200 caratteri", () => {
    form({ summary: "Ciao" });
    expect(screen.getByLabelText(/Riassunto/).tagName).toBe("TEXTAREA");
  });
});
