// Errori del server (details[].path, es. "zones/main/0/data/items/2/media_id") → dove mostrarli.
import type { PageDocument } from "./document";

export interface ServerFieldError {
  path: string;
  code: string;
  message: string;
}

export type ErrorTarget =
  | { kind: "page"; field: "title" | "layout" }
  | { kind: "seo"; field: string }
  | { kind: "zone"; zone: string }
  | { kind: "block"; zone: string; index: number; uid: string | null; field: string };

/** Gli indici valgono per la copia inviata (`sent`), non per quella sullo schermo. */
export function locateError(path: string, sent: PageDocument): ErrorTarget {
  const parts = path.split("/");
  if (parts[0] === "seo") return { kind: "seo", field: parts.slice(1).join("/") };
  if (parts[0] !== "zones" || parts.length < 2) return { kind: "page", field: parts[0] === "layout" ? "layout" : "title" };
  const zone = parts[1]!;
  if (parts.length < 3) return { kind: "zone", zone };
  const index = Number(parts[2]);
  const uid = sent.zones[zone]?.[index]?.uid ?? null;
  const field = parts[3] === "data" ? parts.slice(4).join("/") : parts.slice(3).join("/");
  return { kind: "block", zone, index, uid, field };
}

export function isFieldErrors(details: unknown): details is ServerFieldError[] {
  return (
    Array.isArray(details) &&
    details.every((d) => d !== null && typeof d === "object" && typeof (d as ServerFieldError).path === "string")
  );
}
