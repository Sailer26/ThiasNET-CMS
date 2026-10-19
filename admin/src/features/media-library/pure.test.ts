import { describe, expect, it as test, vi } from "vitest";
import { ApiError } from "../../api/client";
import { focalFromClick, focalFromKey, focalText } from "./focal";
import { formatBytes, usedPercent } from "./format";
import { enqueue, extensionOf, precheck, runQueue, type QueueItem } from "./queue";

const file = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe("pesi e spazio", () => {
  test("pesi leggibili", () => {
    expect(formatBytes(500)).toBe("500 byte");
    expect(formatBytes(1536)).toBe("1,5 kB");
    expect(formatBytes(15 * 1024 * 1024)).toBe("15 MB");
    expect(formatBytes(1.2 * 1024 ** 3)).toBe("1,2 GB");
    expect(usedPercent(50, 200)).toBe(25);
    expect(usedPercent(500, 200)).toBe(100);
    expect(usedPercent(1, 0)).toBe(0);
  });
});

describe("punto focale (D-119)", () => {
  test("dal clic alla percentuale, dentro i bordi", () => {
    const rect = { left: 100, top: 50, width: 200, height: 100 };
    expect(focalFromClick(150, 75, rect)).toEqual({ x: 25, y: 25 });
    expect(focalFromClick(0, 500, rect)).toEqual({ x: 0, y: 100 });
    expect(focalFromClick(1, 1, { left: 0, top: 0, width: 0, height: 0 })).toEqual({ x: 50, y: 50 });
  });
  test("frecce 5 %, Maiusc 1 %, limiti", () => {
    expect(focalFromKey({ x: 50, y: 50 }, "ArrowRight", false)).toEqual({ x: 55, y: 50 });
    expect(focalFromKey({ x: 50, y: 50 }, "ArrowUp", true)).toEqual({ x: 50, y: 49 });
    expect(focalFromKey({ x: 2, y: 98 }, "ArrowLeft", false)).toEqual({ x: 0, y: 98 });
    expect(focalFromKey({ x: 2, y: 98 }, "ArrowDown", false)).toEqual({ x: 2, y: 100 });
    expect(focalFromKey({ x: 2, y: 98 }, "Enter", false)).toBeNull();
    expect(focalText({ x: 40, y: 30 })).toBe("Orizzontale 40 %, verticale 30 %");
  });
});

describe("coda di caricamento (D-118)", () => {
  test("controllo prima dell'invio", () => {
    expect(extensionOf("Foto.JPG")).toBe("jpg");
    expect(extensionOf("senza")).toBe("");
    expect(precheck(file("a.svg"), 100)).toMatch(/Tipo di file non ammesso/);
    expect(precheck(file("a.png", 200), 100)).toBe("File troppo grande: al massimo 100 byte.");
    expect(precheck(file("a.pdf"), 100)).toBeNull();
    const items = enqueue([file("a.png"), file("b.exe")], 100, 1);
    expect(items.map((i) => i.state)).toEqual(["waiting", "error"]);
  });

  test("uno alla volta; doppioni ed errori per riga; stop con spazio esaurito", async () => {
    const media = { id: 1 } as never;
    const upload = vi
      .fn()
      .mockResolvedValueOnce({ media, duplicate: false })
      .mockResolvedValueOnce({ media, duplicate: true })
      .mockRejectedValueOnce(new ApiError(422, "invalid_image", "File danneggiato"))
      .mockRejectedValueOnce(new ApiError(507, "storage_full", "Spazio esaurito: contatta Thias"));
    const updates: QueueItem[][] = [];
    const items = enqueue(["a.png", "b.png", "c.png", "d.png", "e.png"].map((n) => file(n)), 100, 2);
    const result = await runQueue(items, upload, (list) => updates.push(list), () => false);
    expect(result.map((i) => i.state)).toEqual(["done", "duplicate", "error", "error", "skipped"]);
    expect(result[2]!.message).toBe("File danneggiato");
    expect(result[4]!.message).toBe("Spazio esaurito");
    expect(upload).toHaveBeenCalledTimes(4);
    expect(updates[0]!.map((i) => i.state)[0]).toBe("uploading");
  });

  test("Interrompi: il file in corso finisce, gli altri restano fuori", async () => {
    let stop = false;
    const upload = vi.fn(async () => {
      stop = true;
      return { media: { id: 1 } as never, duplicate: false };
    });
    const result = await runQueue(enqueue([file("a.png"), file("b.png")], 100, 3), upload, () => undefined, () => stop);
    expect(result.map((i) => i.state)).toEqual(["done", "skipped"]);
  });
});
