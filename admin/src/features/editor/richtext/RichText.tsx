import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ed } from "../../../text/editor";
import { Dialog } from "../../../ui/Dialog";
import { FieldFrame, type FieldProps } from "../schema/fields";
import { completeUrl, isSafeUrl, normalizeUrl } from "../schema/safeUrl";
import { length } from "../schema/validate";
import { HEADING_LEVELS, RICH_TEXT_EXTENSIONS } from "./extensions";

type Level = (typeof HEADING_LEVELS)[number];

interface ToolbarItem {
  label: string;
  pressed: boolean;
  run: () => void;
}

const MOVES: Record<string, (current: number, count: number) => number> = {
  ArrowRight: (current) => current + 1,
  ArrowLeft: (current) => current - 1,
  Home: () => 0,
  End: (_current, count) => count - 1,
};

/** Barra con un solo punto di tabulazione (roving tabindex): frecce, Inizio e Fine. */
function Toolbar({ editor, onLink }: { editor: Editor; onLink: () => void }) {
  const [active, setActive] = useState(0);
  const chain = () => editor.chain().focus();
  const items: ToolbarItem[] = [
    { label: ed.rich.paragraph, pressed: editor.isActive("paragraph"), run: () => chain().setParagraph().run() },
    ...HEADING_LEVELS.map((level: Level) => ({
      label: ed.rich.heading(level),
      pressed: editor.isActive("heading", { level }),
      run: () => chain().toggleHeading({ level }).run(),
    })),
    { label: ed.rich.bold, pressed: editor.isActive("bold"), run: () => chain().toggleBold().run() },
    { label: ed.rich.italic, pressed: editor.isActive("italic"), run: () => chain().toggleItalic().run() },
    { label: ed.rich.bullet, pressed: editor.isActive("bulletList"), run: () => chain().toggleBulletList().run() },
    { label: ed.rich.ordered, pressed: editor.isActive("orderedList"), run: () => chain().toggleOrderedList().run() },
    { label: ed.rich.quote, pressed: editor.isActive("blockquote"), run: () => chain().toggleBlockquote().run() },
  ];
  // Il link si mette su un testo selezionato (o si modifica quello esistente).
  if (!editor.state.selection.empty || editor.isActive("link")) {
    items.push({ label: ed.rich.link, pressed: editor.isActive("link"), run: onLink });
  }
  if (editor.isActive("link")) {
    items.push({ label: ed.rich.unlink, pressed: false, run: () => chain().extendMarkRange("link").unsetLink().run() });
  }
  const current = Math.min(active, items.length - 1);

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const step = MOVES[event.key];
    if (!step) return;
    event.preventDefault();
    const next = (step(current, items.length) + items.length) % items.length;
    setActive(next);
    event.currentTarget.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();
  }

  return (
    <div className="toolbar" role="toolbar" aria-label={ed.rich.toolbar} onKeyDown={move}>
      {items.map((item, index) => (
        <button
          key={item.label}
          type="button"
          className="toolbar__button"
          aria-pressed={item.pressed}
          tabIndex={index === current ? 0 : -1}
          onFocus={() => setActive(index)}
          onMouseDown={(event) => event.preventDefault()} // il cursore resta nel testo
          onClick={item.run}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function LinkDialog({ initial, onSave, onClose }: { initial: string; onSave: (href: string) => void; onClose: () => void }) {
  const [href, setHref] = useState(initial);
  const clean = normalizeUrl(completeUrl(href));
  const valid = isSafeUrl(clean);
  return (
    <Dialog title={ed.rich.linkTitle} onClose={onClose}>
      <form
        className="form"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) onSave(clean);
        }}
      >
        <label className="field">
          <span>{ed.rich.linkLabel}</span>
          <input value={href} onChange={(event) => setHref(event.target.value)} autoCapitalize="none" spellCheck={false} />
        </label>
        <p className="hint">{ed.rich.linkHelp}</p>
        {href && !valid && <p className="form__error">{ed.rich.linkInvalid}</p>}
        <div className="form__actions">
          <button type="submit" className="button button--primary" disabled={!valid}>
            {ed.rich.linkSubmit}
          </button>
          <button type="button" className="button" onClick={onClose}>
            {ed.zones.close}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/** Testo formattato (D-108). Editor vuoto = campo assente; annulla del pannello, non di TipTap. */
export function RichTextField({ id, spec, value, onChange, required, error, unsaved }: FieldProps<string>) {
  const emitted = useRef(value ?? "");
  const [linking, setLinking] = useState(false);
  const editor = useEditor({
    extensions: RICH_TEXT_EXTENSIONS,
    content: value ?? "",
    injectCSS: false,
    immediatelyRender: true,
    shouldRerenderOnTransaction: true,
    editorProps: {
      attributes: {
        id,
        class: "rich__content",
        role: "textbox",
        "aria-multiline": "true",
        "aria-labelledby": `${id}-label`,
      },
    },
    onUpdate: ({ editor: current }) => {
      const html = current.isEmpty ? "" : current.getHTML();
      emitted.current = html;
      onChange(html === "" ? undefined : html);
    },
  });

  // Annulla/ripristina del pannello cambiano il valore dall'esterno: solo allora si riscrive.
  useEffect(() => {
    const next = value ?? "";
    if (editor && next !== emitted.current) {
      emitted.current = next;
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [editor, value]);

  // Errori e suggerimenti collegati al campo anche quando cambiano dopo la creazione.
  const describedBy = [spec.description ? `${id}-help` : "", error || unsaved ? `${id}-problem` : ""]
    .filter(Boolean)
    .join(" ");
  useEffect(() => {
    const dom = editor?.view.dom;
    if (!dom) return;
    if (describedBy) dom.setAttribute("aria-describedby", describedBy);
    else dom.removeAttribute("aria-describedby");
    if (error || unsaved) dom.setAttribute("aria-invalid", "true");
    else dom.removeAttribute("aria-invalid");
  }, [editor, describedBy, error, unsaved]);

  const html = value ?? "";
  return (
    <FieldFrame
      id={id}
      spec={spec}
      required={required}
      error={error}
      unsaved={unsaved}
      extra={
        spec.maxLength !== undefined && length(html) > spec.maxLength * 0.8 ? (
          <span className="field__counter">{ed.fields.counter(length(html), spec.maxLength)}</span>
        ) : null
      }
    >
      <div className="rich">
        {editor && <Toolbar editor={editor} onLink={() => setLinking(true)} />}
        <EditorContent editor={editor} />
      </div>
      {linking && editor && (
        <LinkDialog
          initial={String(editor.getAttributes("link").href ?? "")}
          onClose={() => setLinking(false)}
          onSave={(href) => {
            editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
            setLinking(false);
          }}
        />
      )}
    </FieldFrame>
  );
}
