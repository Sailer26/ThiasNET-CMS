// Punto focale (D-119): coordinate in percentuale, 0-100, interi.
export interface Focal {
  x: number;
  y: number;
}

const clamp = (n: number) => Math.min(100, Math.max(0, Math.round(n)));

/** Da un clic (coordinate nella finestra) al punto in % dentro il rettangolo dell'immagine. */
export function focalFromClick(clientX: number, clientY: number, rect: { left: number; top: number; width: number; height: number }): Focal {
  if (rect.width <= 0 || rect.height <= 0) return { x: 50, y: 50 };
  return { x: clamp(((clientX - rect.left) / rect.width) * 100), y: clamp(((clientY - rect.top) / rect.height) * 100) };
}

export const ARROW_STEP = 5;
export const FINE_STEP = 1;

/** Frecce: 5 % (Maiusc: 1 %); null per i tasti che non spostano. */
export function focalFromKey(focal: Focal, key: string, fine: boolean): Focal | null {
  const step = fine ? FINE_STEP : ARROW_STEP;
  switch (key) {
    case "ArrowLeft":
      return { ...focal, x: clamp(focal.x - step) };
    case "ArrowRight":
      return { ...focal, x: clamp(focal.x + step) };
    case "ArrowUp":
      return { ...focal, y: clamp(focal.y - step) };
    case "ArrowDown":
      return { ...focal, y: clamp(focal.y + step) };
    default:
      return null;
  }
}

/** "Orizzontale 40 %, verticale 30 %" per i lettori di schermo. */
export function focalText(focal: Focal): string {
  return `Orizzontale ${focal.x} %, verticale ${focal.y} %`;
}
