// TipTap con le sole voci dell'allowlist di D-49 (D-108): ciò che non è caricato non si può
// scrivere né incollare. Il server ripulisce comunque con nh3.
import type { Extensions } from "@tiptap/core";
import Blockquote from "@tiptap/extension-blockquote";
import Bold from "@tiptap/extension-bold";
import Document from "@tiptap/extension-document";
import HardBreak from "@tiptap/extension-hard-break";
import Heading from "@tiptap/extension-heading";
import Italic from "@tiptap/extension-italic";
import Link from "@tiptap/extension-link";
import { BulletList, ListItem, ListKeymap, OrderedList } from "@tiptap/extension-list";
import Paragraph from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import { isSafeUrl, normalizeUrl } from "../schema/safeUrl";

export const HEADING_LEVELS = [2, 3, 4] as const;

/** Nessun attributo oltre a href e rel: target e class incollati non sopravvivono (D-108). */
const DROPPED = { default: null, parseHTML: () => null, renderHTML: () => ({}) };
const REL = "noopener noreferrer";
const SafeLink = Link.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      target: DROPPED,
      class: DROPPED,
      // rel sempre lo stesso: un rel incollato (es. "opener") non sopravvive
      rel: { default: REL, parseHTML: () => REL, renderHTML: () => ({ rel: REL }) },
    };
  },
});

export function richTextExtensions(): Extensions {
  return [
    Document,
    Paragraph,
    Text,
    Heading.configure({ levels: [...HEADING_LEVELS] }),
    Bold,
    Italic,
    BulletList,
    OrderedList,
    ListItem,
    ListKeymap,
    Blockquote,
    HardBreak,
    SafeLink.configure({
      openOnClick: false,
      autolink: false,
      linkOnPaste: true,
      HTMLAttributes: { target: null, class: null },
      isAllowedUri: (url) => isSafeUrl(normalizeUrl(url)),
    }),
  ];
}

/** Un solo elenco per tutta l'app: non si ricrea a ogni battuta. */
export const RICH_TEXT_EXTENSIONS: Extensions = richTextExtensions();
