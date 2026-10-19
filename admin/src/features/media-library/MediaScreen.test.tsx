import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it as test, vi } from "vitest";
import { App } from "../../App";
import { setCsrfToken } from "../../api/client";
import type { Folder, Media, MediaDetail } from "../../api/media";
import { fakeApi, signedIn, type FakeApi } from "../../test/fakeApi";

function media(id: number, extra: Partial<Media> = {}): Media {
  return {
    id,
    kind: "image",
    name: `foto-${id}.jpg`,
    ext: "jpg",
    alt: `Foto ${id}`,
    width: 800,
    height: 600,
    size_bytes: 2048,
    focal_x: 50,
    focal_y: 50,
    folder_id: null,
    version: 1,
    url: `/media/k${id}/r1-master.jpg`,
    thumbnail_url: `/media/k${id}/r1-_panel-400.webp`,
    ...extra,
  };
}

const FOLDERS: Folder[] = [
  { id: 3, name: "Eventi", parent_id: null, count: 2, children: [{ id: 4, name: "2026", parent_id: 3, count: 0, children: [] }] },
];

function setup(): { api: FakeApi; user: ReturnType<typeof userEvent.setup> } {
  const api = fakeApi();
  signedIn(api);
  api.on("GET", "/media", { data: [media(1), media(2, { alt: "" })], meta: { total: 2 } });
  api.on("GET", "/media/folders", { data: FOLDERS });
  api.on("GET", "/media/usage", {
    data: { used_bytes: 4.6 * 1024 ** 3, quota_bytes: 5 * 1024 ** 3, max_upload_bytes: 15 * 1024 ** 2, count: 2 },
  });
  render(<App />);
  return { api, user: userEvent.setup() };
}

describe("pagina Media (D-117 … D-120)", () => {
  beforeEach(() => {
    setCsrfToken("tok");
    window.history.replaceState(null, "", "/admin/media");
  });

  test("cartelle con il numero dei file, spazio usato, filtri", async () => {
    const { api, user } = setup();
    expect(await screen.findByText("foto-1.jpg")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eventi 2" })).toBeInTheDocument();
    expect(await screen.findByText("Usati 4,6 GB di 5,0 GB")).toBeInTheDocument();
    expect(screen.getByText("Lo spazio sta per finire: contatta Thias.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Senza cartella" }));
    await waitFor(() => expect(api.calls.some((c) => c.path.includes("folder_id=none"))).toBe(true));
    await user.click(screen.getByLabelText("Manca il testo alternativo"));
    await waitFor(() => expect(api.calls.some((c) => c.path.includes("missing_alt=1"))).toBe(true));
    await user.selectOptions(screen.getByLabelText("Tipo"), "document");
    await waitFor(() => expect(api.calls.some((c) => c.path.includes("kind=document"))).toBe(true));
  });

  test("nuova cartella dentro quella aperta; una cartella piena non si elimina", async () => {
    const { api, user } = setup();
    api.on("POST", "/media/folders", { status: 201, data: { id: 9, name: "Foto", parent_id: 3 } });
    await user.click(await screen.findByRole("button", { name: "Eventi 2" }));
    await user.click(screen.getByRole("button", { name: "Elimina cartella" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Per eliminarla svuotala prima.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nuova cartella" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nome della cartella"), "Foto");
    expect(within(dialog).getByLabelText("Dove la metto?")).toHaveValue("3");
    await user.click(within(dialog).getByRole("button", { name: "Crea" }));
    await waitFor(() => expect(api.callsTo("POST", "/media/folders")[0]?.body).toEqual({ name: "Foto", parent_id: 3 }));
  });

  test("caricamento multiplo in coda, poi invito al testo alternativo", async () => {
    const { api, user } = setup();
    api.on(
      "POST",
      "/media",
      { status: 201, data: media(10, { alt: "" }) },
      { status: 422, error: { code: "invalid_image", message: "File danneggiato" } },
    );
    await screen.findByText("foto-1.jpg");
    const files = [
      new File(["a"], "a.png", { type: "image/png" }),
      new File(["b"], "b.png", { type: "image/png" }),
      new File(["c"], "c.svg", { type: "image/svg+xml" }),
    ];
    await userEvent.setup({ applyAccept: false }).upload(screen.getByLabelText("Carica file"), files);
    expect(await screen.findByText("1 immagine non ha il testo alternativo.")).toBeInTheDocument();
    const queue = screen.getByRole("region", { name: "Caricamento" });
    expect(within(queue).getByText("File danneggiato")).toBeInTheDocument();
    expect(within(queue).getByText(/Tipo di file non ammesso/)).toBeInTheDocument();
    expect(api.callsTo("POST", "/media")).toHaveLength(2); // l'SVG non parte nemmeno
    await user.click(screen.getByRole("button", { name: "Aggiungilo ora" }));
    expect(screen.getByLabelText("Manca il testo alternativo")).toBeChecked();
  });

  test("dettaglio: testo alternativo, punto focale da tastiera, usato in, elimina con 409", async () => {
    const { api, user } = setup();
    const detail: MediaDetail = { ...media(1), used_by: [{ page_id: 7, title: "Chi siamo", path: "/chi-siamo", where: "published" }] };
    api.on("GET", "/media/1", { data: detail });
    api.on("PATCH", "/media/1", { data: { ...media(1), version: 2 } });
    api.on("DELETE", "/media/1", { status: 409, error: { code: "media_in_use", message: "In uso", details: detail.used_by } });
    await user.click(await screen.findByRole("button", { name: /foto-1\.jpg/ }));
    const panel = await screen.findByRole("complementary", { name: "foto-1.jpg" });
    expect(within(panel).getByRole("link", { name: "Chi siamo" })).toHaveAttribute("href", "/admin/pagine/7");
    await user.clear(within(panel).getByLabelText("Testo alternativo"));
    await user.type(within(panel).getByLabelText("Testo alternativo"), "Lago");
    await user.click(within(panel).getByRole("button", { name: "Salva" }));
    await waitFor(() =>
      expect(api.callsTo("PATCH", "/media/1")[0]?.body).toEqual({ version: 1, name: "foto-1.jpg", alt: "Lago" }),
    );

    const marker = await within(panel).findByRole("slider", { name: "Punto da non tagliare" });
    act(() => marker.focus());
    fireEvent.keyDown(marker, { key: "ArrowRight" });
    fireEvent.keyDown(marker, { key: "ArrowUp", shiftKey: true });
    expect(marker).toHaveAttribute("aria-valuetext", "Orizzontale 55 %, verticale 49 %");
    await user.click(within(panel).getByRole("button", { name: "Salva punto" }));
    await waitFor(() => expect(api.callsTo("PATCH", "/media/1")[1]?.body).toEqual({ version: 1, focal_x: 55, focal_y: 49 }));

    await user.click(within(panel).getByRole("button", { name: "Elimina" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Elimina" }));
    expect(await within(panel).findByText("Non si può eliminare: è usato in queste pagine.")).toBeInTheDocument();
  });

  test("sostituisci file", async () => {
    const { api, user } = setup();
    api.on("GET", "/media/2", { data: { ...media(2, { kind: "document", ext: "pdf", thumbnail_url: null }), used_by: [] } });
    api.on("POST", "/media/2/file", { data: media(2, { version: 2 }) });
    await user.click(await screen.findByRole("button", { name: /foto-2\.jpg/ }));
    const panel = await screen.findByRole("complementary", { name: "foto-2.jpg" });
    expect(within(panel).getByText(/Il link del documento resta lo stesso/)).toBeInTheDocument();
    await user.upload(within(panel).getByLabelText("Sostituisci file"), new File(["%PDF"], "nuovo.pdf", { type: "application/pdf" }));
    expect(await within(panel).findByText("File sostituito.")).toBeInTheDocument();
    const sent = api.callsTo("POST", "/media/2/file")[0]!.body as FormData;
    expect(sent.get("version")).toBe("1");
  });

  test("un secondo rilascio durante un caricamento è ignorato; anteprima locale dei file", async () => {
    const { api } = setup();
    let finish: () => void = () => undefined;
    api.on("POST", "/media", { status: 201, data: media(20) });
    const original = globalThis.fetch;
    vi.stubGlobal("fetch", (input: string, init?: RequestInit) =>
      String(input).endsWith("/api/admin/media") && init?.method === "POST"
        ? new Promise<Response>((resolve) => {
            finish = () => void original(input, init).then(resolve);
          })
        : original(input, init),
    );
    await screen.findByText("foto-1.jpg");
    const section = screen.getByRole("heading", { name: "Media" }).closest("section")!;
    const drop = (name: string) =>
      fireEvent.drop(section, { dataTransfer: { files: [new File(["x"], name, { type: "image/png" })] } });
    drop("primo.png");
    const queue = await screen.findByRole("region", { name: "Caricamento" });
    expect(within(queue).getByText("primo.png")).toBeInTheDocument();
    expect(queue.querySelector("img.queue__thumb")?.getAttribute("src")).toMatch(/^blob:/);
    drop("secondo.png");
    expect(within(queue).queryByText("secondo.png")).not.toBeInTheDocument();
    finish();
    await waitFor(() => expect(within(queue).getByText("Fatto")).toBeInTheDocument());
  });
});
