// Disegni dei tipi di blocco (D-115): nel codice del pannello, uguali per tutti i siti.
// Solo forme semplici con le classi di panel.css (niente stili inline, D-88).
import type { ReactNode } from "react";

const LINE = "icon__line";
const FILL = "icon__fill";
const SOFT = "icon__soft";

function lines(x: number, y: number, widths: number[]): ReactNode[] {
  return widths.map((w, i) => <rect key={`${x}-${y}-${i}`} className={LINE} x={x} y={y + i * 7} width={w} height={3} rx={1.5} />);
}

function photo(x: number, y: number, w: number, h: number): ReactNode {
  return (
    <g key={`p${x}${y}`}>
      <rect className={SOFT} x={x} y={y} width={w} height={h} rx={3} />
      <path className={FILL} d={`M${x + 3} ${y + h - 3} l${w / 3} ${-h / 2.2} l${w / 4} ${h / 4} l${w / 6} ${-h / 6} l${w / 4 - 6} ${h / 2.2 + h / 6 - h / 4 + 0.5}z`} />
    </g>
  );
}

const DRAWINGS: Record<string, ReactNode> = {
  hero: [photo(4, 6, 72, 40), <rect key="t" className={FILL} x={14} y={20} width={44} height={5} rx={2} />, <rect key="b" className={LINE} x={14} y={30} width={22} height={7} rx={3} />],
  heading: [<rect key="h" className={FILL} x={6} y={18} width={56} height={8} rx={2} />, ...lines(6, 34, [40])],
  text: lines(6, 10, [68, 64, 68, 50, 66]),
  image: [photo(10, 6, 60, 32), ...lines(22, 42, [36])],
  text_image: [photo(4, 10, 32, 30), ...lines(42, 12, [34, 30, 34, 22])],
  gallery: [photo(4, 6, 22, 18), photo(29, 6, 22, 18), photo(54, 6, 22, 18), photo(4, 27, 22, 18), photo(29, 27, 22, 18), photo(54, 27, 22, 18)],
  cta: [<rect key="r" className={SOFT} x={4} y={8} width={72} height={36} rx={4} />, ...lines(14, 16, [40]), <rect key="b" className={FILL} x={26} y={28} width={28} height={9} rx={4} />],
  quote: [<path key="q" className={FILL} d="M8 12h8v8l-4 8h-4l3-8h-3zM20 12h8v8l-4 8h-4l3-8h-3z" />, ...lines(34, 14, [40, 36, 26])],
  video: [<rect key="v" className={SOFT} x={6} y={6} width={68} height={40} rx={4} />, <path key="p" className={FILL} d="M34 17l14 9-14 9z" />],
  files: [0, 1, 2].map((i) => (
    <g key={i}>
      <path className={SOFT} d={`M${8 + i * 24} 8h12l6 6v26h-18z`} />
      <rect className={FILL} x={10 + i * 24} y={30} width={12} height={4} rx={1} />
    </g>
  )),
  map: [<rect key="m" className={SOFT} x={4} y={6} width={72} height={40} rx={4} />, <path key="l" className={LINE} d="M4 30 L30 18 L50 34 L76 20 V24 L50 38 L30 22 L4 34z" />, <path key="pin" className={FILL} d="M40 10a7 7 0 0 1 7 7c0 6-7 13-7 13s-7-7-7-13a7 7 0 0 1 7-7z" />],
  contacts: [<circle key="c" className={FILL} cx={14} cy={16} r={6} />, ...lines(26, 13, [40]), <rect key="f" className={SOFT} x={6} y={28} width={68} height={18} rx={3} />],
  divider: [<rect key="d" className={FILL} x={6} y={24} width={68} height={3} rx={1.5} />],
};

export function BlockIcon({ type }: { type: string }) {
  return (
    <svg className="block-icon" viewBox="0 0 80 52" aria-hidden="true" focusable="false">
      {DRAWINGS[type] ?? lines(6, 10, [68, 60, 64])}
    </svg>
  );
}
