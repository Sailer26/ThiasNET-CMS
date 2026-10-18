// Aiuti "incolla il link" (D-112): dal link che il cliente copia dal browser ai campi del blocco.
// Funzioni pure: nessuna richiesta verso YouTube, Vimeo o mappe.

export interface VideoData {
  provider: "youtube" | "vimeo";
  video_id: string;
  /** Solo Vimeo privato (D-129); `undefined` toglie un codice rimasto da prima. */
  video_hash: string | undefined;
}

export interface MapData {
  lat: number;
  lng: number;
  zoom?: number;
}

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
const VIMEO_ID = /^[0-9]{1,12}$/;
const VIMEO_HASH = /^[0-9a-f]{6,20}$/;
const SHORT_MAP_HOSTS = new Set(["maps.app.goo.gl", "goo.gl"]);
const YOUTUBE_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"]);
const MAX_ZOOM = 19;

function parse(text: string): URL | null {
  const raw = text.trim();
  try {
    return new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
  } catch {
    return null;
  }
}

export function videoFromLink(text: string): VideoData | null {
  const url = parse(text);
  if (!url) return null;
  const host = url.hostname.toLowerCase();
  const parts = url.pathname.split("/").filter(Boolean);
  let id: string | undefined;
  if (host === "youtu.be") id = parts[0];
  else if (YOUTUBE_HOSTS.has(host)) {
    id = url.searchParams.get("v") ?? (["embed", "shorts", "live", "v"].includes(parts[0] ?? "") ? parts[1] : undefined);
  }
  if (id && YOUTUBE_ID.test(id)) return { provider: "youtube", video_id: id, video_hash: undefined };
  if (host === "vimeo.com" || host === "www.vimeo.com" || host === "player.vimeo.com") {
    const at = parts.findIndex((part) => VIMEO_ID.test(part));
    if (at >= 0) {
      // Video non in elenco: vimeo.com/123/abcdef1234 oppure player.vimeo.com/video/123?h=abcdef1234
      const hash = url.searchParams.get("h") ?? parts[at + 1];
      return { provider: "vimeo", video_id: parts[at]!, video_hash: hash && VIMEO_HASH.test(hash) ? hash : undefined };
    }
  }
  return null;
}

function coordinates(lat: number, lng: number, zoom?: number): MapData | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  const rounded = (n: number) => Math.round(n * 1e6) / 1e6;
  const result: MapData = { lat: rounded(lat), lng: rounded(lng) };
  if (zoom !== undefined && Number.isFinite(zoom)) result.zoom = Math.min(MAX_ZOOM, Math.max(1, Math.round(zoom)));
  return result;
}

/** Link brevi di Google Maps: il pannello non li apre (niente richieste verso l'esterno, D-129). */
export function isShortMapLink(text: string): boolean {
  const url = parse(text);
  return url !== null && SHORT_MAP_HOSTS.has(url.hostname.toLowerCase());
}

/** OpenStreetMap (#map=z/lat/lng, ?mlat=&mlon=), Google Maps (@lat,lng,zoomz) o "46.0, 8.95". */
export function placeFromLink(text: string): MapData | null {
  const plain = /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/.exec(text);
  if (plain) return coordinates(Number(plain[1]), Number(plain[2]));
  const url = parse(text);
  if (!url) return null;
  const hash = /map=(\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/.exec(url.hash);
  if (hash) return coordinates(Number(hash[2]), Number(hash[3]), Number(hash[1]));
  const mlat = url.searchParams.get("mlat");
  const mlon = url.searchParams.get("mlon");
  if (mlat && mlon) return coordinates(Number(mlat), Number(mlon));
  const google = /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,(\d+(?:\.\d+)?)z)?/.exec(url.pathname);
  if (google) return coordinates(Number(google[1]), Number(google[2]), google[3] ? Number(google[3]) : undefined);
  return null;
}
