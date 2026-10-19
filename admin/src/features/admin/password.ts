// Password iniziale generata nel pannello (D-123): 16 caratteri senza lettere ambigue.
const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_";
export const GENERATED_LENGTH = 16;

export function generatePassword(length = GENERATED_LENGTH): string {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  // 256 non è multiplo di 58: si scarta la parte che sbilancerebbe le probabilità.
  const limit = 256 - (256 % ALPHABET.length);
  let out = "";
  for (const byte of bytes) {
    if (byte < limit) out += ALPHABET[byte % ALPHABET.length];
  }
  return out.length >= length ? out.slice(0, length) : out + generatePassword(length - out.length);
}
