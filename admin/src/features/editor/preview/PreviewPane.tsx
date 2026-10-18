import { useEffect, useRef, useState } from "react";
import { getCsrfToken } from "../../../api/client";
import { ed } from "../../../text/editor";
import { UID_RE } from "../model/uid";
import type { PageDocument } from "../model/document";
import { transport } from "./transport";

export const PREVIEW_DELAY_MS = 500;
const STALE_CHECK_MS = 300;

interface Frame {
  name: string;
  json: string;
}

interface Props {
  pageId: number;
  doc: PageDocument;
  selected: string | null;
  onSelect: (uid: string) => void;
}

let counter = 0;

/** Anteprima live (D-107): a ogni aggiornamento un iframe nuovo dietro quello visibile; si
 * scambiano quando il nuovo dice "pronto". Niente voci nella storia del browser. */
export function PreviewPane({ pageId, doc, selected, onSelect }: Props) {
  const [active, setActive] = useState<Frame | null>(null);
  const [pending, setPending] = useState<Frame | null>(null);
  const [stale, setStale] = useState(false);
  const frames = useRef(new Map<string, HTMLIFrameElement>());
  const json = JSON.stringify(doc);
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    selectedRef.current = selected;
    onSelectRef.current = onSelect;
  }, [selected, onSelect]);

  // Documento cambiato: dopo una pausa breve, un iframe nuovo (vale solo l'ultimo).
  useEffect(() => {
    const timer = setTimeout(
      () => {
        if (active?.json === json) return;
        counter += 1;
        setPending({ name: `cms-preview-${counter}`, json });
      },
      active ? PREVIEW_DELAY_MS : 0,
    );
    return () => clearTimeout(timer);
  }, [json, active]);

  // L'iframe nuovo esiste nel DOM: gli si manda il documento.
  useEffect(() => {
    if (!pending) return;
    transport.submit(pending.name, `/_preview/${pageId}`, {
      csrf_token: getCsrfToken() ?? "",
      document: pending.json,
    });
  }, [pending, pageId]);

  useEffect(() => {
    function receive(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      const data = (event.data ?? {}) as { type?: unknown; uid?: unknown };
      const from = (name: string | undefined) => name !== undefined && event.source === frames.current.get(name)?.contentWindow;
      if (data.type === "cms:ready" && pending && from(pending.name)) {
        setActive(pending);
        setPending(null);
        setStale(false);
        const uid = selectedRef.current;
        if (uid) frames.current.get(pending.name)?.contentWindow?.postMessage({ type: "cms:highlight", uid, scroll: false }, window.location.origin);
      } else if (data.type === "cms:block-click" && from(active?.name) && typeof data.uid === "string" && UID_RE.test(data.uid)) {
        onSelectRef.current(data.uid);
      }
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [pending, active]);

  // Blocco scelto nel modulo: evidenziato (e portato in vista) nell'anteprima.
  useEffect(() => {
    if (!active || !selected) return;
    frames.current.get(active.name)?.contentWindow?.postMessage({ type: "cms:highlight", uid: selected, scroll: true }, window.location.origin);
  }, [selected, active]);

  function loaded(name: string) {
    // Caricato ma non "pronto" (errore o pagina non valida): resta l'anteprima precedente.
    setTimeout(() => {
      setPending((current) => {
        if (current?.name !== name) return current;
        setStale(true);
        return null;
      });
    }, STALE_CHECK_MS);
  }

  const shown = [active, pending].filter((frame): frame is Frame => frame !== null);
  return (
    <div className="preview">
      {stale && <p className="notice notice--info preview__stale">{ed.preview.stale}</p>}
      <div className="preview__frames">
        {shown.map((frame) => (
          <iframe
            key={frame.name}
            name={frame.name}
            title={ed.preview.title}
            className={frame === active ? "preview__frame" : "preview__frame preview__frame--loading"}
            ref={(element) => {
              if (element) frames.current.set(frame.name, element);
              else frames.current.delete(frame.name);
            }}
            onLoad={() => loaded(frame.name)}
          />
        ))}
      </div>
    </div>
  );
}
