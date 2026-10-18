// Dopo la build: il pannello compilato deve rispettare la CSP (D-88).
// Fallisce con script o stili inline, attributi style, data: o indirizzi esterni.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DIST = fileURLToPath(new URL("../dist/", import.meta.url));
const ALLOWED_URLS = new Set(["http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink", "http://www.w3.org/1998/Math/MathML"]);
const problems = [];

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

let files;
try {
  files = walk(DIST);
} catch {
  console.error("dist/ mancante: esegui prima la build");
  process.exit(1);
}

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const ext = extname(file);
  if (ext === ".html") {
    if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(text)) problems.push(`${file}: script inline`);
    if (/<style[\s>]/i.test(text)) problems.push(`${file}: stile inline`);
    if (/\sstyle=/i.test(text)) problems.push(`${file}: attributo style`);
    if (/\son[a-z]+=/i.test(text)) problems.push(`${file}: gestore di evento inline`);
  }
  if ([".html", ".css"].includes(ext) && /data:/i.test(text)) problems.push(`${file}: data:`);
  if ([".html", ".css"].includes(ext)) {
    for (const url of text.match(/https?:\/\/[^\s"'`)]+/g) ?? []) {
      if (!ALLOWED_URLS.has(url)) problems.push(`${file}: indirizzo esterno ${url}`);
    }
  }
}

if (problems.length) {
  console.error("La build non rispetta la CSP del pannello:\n" + problems.join("\n"));
  process.exit(1);
}
console.info(`check-dist: ${files.length} file controllati, nessun problema`);
