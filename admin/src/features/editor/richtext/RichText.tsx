import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";
import { ed } from "../../../text/editor";
import { Dialog } from "../../../ui/Dialog";
import { FieldFrame, type FieldProps } from "../schema/fields";
import { completeUrl, isSafeUrl, normalizeUrl } from "../schema/safeUrl";
import { length } from "../schema/validate";
import { HEADING_LEVELS, richTextExtensions } from "./extensions";

type Level = (typeof HEADING_LEVELS)[number];

function Toolbar({ editor, onLink }: { editor: Editor; onLink: () => void }) {
  const button = (label: string, active: boolean, run: () => void) => (
    <button
      key={label}
      type="button"
      className="toolbar__button"
      aria-pressed={active}
      onMouseDown={(event) => event.preventDefault()} // il cursore resta nel testo
      onClick={run}
    >
      {label}
    </button>
  );
  const chain = () => editor.chain().focus();
  return (
    <div className="toolbar" role="toolbar" aria-label={ed.rich.toolbar}>
      {button(ed.rich.paragraph, editor.isActive("paragraph"), () => chain().setParagraph().run())}
      {HEADING_LEVELS.map((level: Level) =>
        button(ed.rich.heading(level), editor.isActive("heading", { level }), () => chain().toggleHeading({ level }).run()),
      )}
      {button(ed.rich.bold, editor.isActive("bold"), () => chain().toggleBold().run())}
      {button(ed.rich.italic, editor.isActive("italic"), () => chain().toggleItalic().run())}
      {button(ed.rich.bullet, editor.isActive("bulletList"), () => chain().toggleBulletList().run())}
      {button(ed.rich.ordered, editor.isActive("orderedList"), () => chain().toggleOrderedList().run())}
      {button(ed.rich.quote, editor.isActive("blockquote"), () => chain().toggleBlockquote().run())}
      {button(ed.rich.link, editor.isActive("link"), onLink)}
      {editor.isActive("link") && button(ed.rich.unlink, false, () => chain().extendMarkRange("link").unsetLink().run())}
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
    extensions: richTextExtensions(),
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
        "aria-describedby": [spec.description ? `${id}-help` : "", error || unsaved ? `${id}-problem` : ""]
          .filter(Boolean)
          .join(" "),
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
