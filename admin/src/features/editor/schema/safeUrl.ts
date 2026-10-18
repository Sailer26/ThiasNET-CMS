// Specchio di app/services/sanitize.py::is_safe_url e normalize_url (casi condivisi nei test).
const MAX_URL_LENGTH = 2048;
const SCHEMES = new Set(["http", "https", "mailto", "tel"]);
const TEL_RE = /^\+?[0-9().-]{3,30}$/;
const ANCHOR_RE = /^#[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/;
const CONTROL_OR_SPACE = /[\s\p{C}]/u;

export function normalizeUrl(value: string): string {
  const trimmed = value.trim();
  if (trimmed.slice(0, 4).toLowerCase() === "tel:") return "tel:" + trimmed.slice(4).replace(/\s+/g, "");
  return trimmed;
}

export function isSafeUrl(value: string): boolean {
  if (!value || [...value].length > MAX_URL_LENGTH || value.includes("\\")) return false;
  if (CONTROL_OR_SPACE.test(value)) return false;
  if (value.startsWith("/")) return !value.startsWith("//");
  if (value.startsWith("#")) return ANCHOR_RE.test(value);
  const colon = value.indexOf(":");
  if (colon < 0) return false;
  const scheme = value.slice(0, colon).toLowerCase();
  const rest = value.slice(colon + 1);
  if (!SCHEMES.has(scheme) || !rest) return false;
  if (scheme === "http" || scheme === "https") {
    try {
      return new URL(value).hostname !== "";
    } catch {
      return false;
    }
  }
  if (scheme === "tel") return TEL_RE.test(rest);
  return true;
}

/** Un indirizzo che comincia con "www." riceve "https://" davanti quando si esce dal campo. */
export function completeUrl(value: string): string {
  const clean = normalizeUrl(value);
  return /^www\.[^\s/]+\.[^\s]+$/i.test(clean) ? `https://${clean}` : clean;
}
