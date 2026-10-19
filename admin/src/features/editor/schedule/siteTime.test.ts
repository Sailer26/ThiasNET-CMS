import { describe, expect, it as test } from "vitest";
import { formatZurich, zurichOffset, zurichToIso, zurichToday } from "./siteTime";

describe("ora svizzera (D-122)", () => {
  test("inverno +01:00, estate +02:00", () => {
    expect(zurichToIso("2026-11-01", "08:00")).toMatchObject({ iso: "2026-11-01T08:00:00+01:00" });
    expect(zurichToIso("2027-07-01", "08:00")).toMatchObject({ iso: "2027-07-01T08:00:00+02:00" });
    expect(zurichOffset(Date.UTC(2027, 0, 1))).toBe(60);
  });

  test("ora che non esiste (marzo) e ora doppia (ottobre)", () => {
    expect(zurichToIso("2027-03-28", "02:30")).toEqual({ error: "missing_hour" });
    const doubled = zurichToIso("2026-10-25", "02:30");
    expect(doubled).toMatchObject({ iso: "2026-10-25T02:30:00+02:00" }); // la prima delle due
    expect("utcMs" in doubled && doubled.utcMs).toBe(Date.UTC(2026, 9, 25, 0, 30));
  });

  test("valori non validi", () => {
    expect(zurichToIso("1.11.2026", "08:00")).toEqual({ error: "invalid" });
    expect(zurichToIso("2026-11-01", "8")).toEqual({ error: "invalid" });
    expect(zurichToIso("2026-02-31", "08:00")).toEqual({ error: "invalid" });
    expect(zurichToIso("2026-11-01", "25:00")).toEqual({ error: "invalid" });
  });

  test("date leggibili nell'ora svizzera", () => {
    expect(formatZurich("2026-11-01T07:00:00+00:00")).toBe("domenica 1 novembre 2026 alle 08:00");
    expect(formatZurich("non una data")).toBe("");
    expect(zurichToday(Date.UTC(2026, 9, 18, 23, 30))).toBe("2026-10-19");
  });
});
