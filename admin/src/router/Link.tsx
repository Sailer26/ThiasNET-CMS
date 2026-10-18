import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { navigate } from "./router";

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string };

export function Link({ to, onClick, children, ...rest }: Props) {
  function handle(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    const elsewhere = rest.target !== undefined && rest.target !== "_self";
    if (event.defaultPrevented || event.button !== 0 || modified || elsewhere) return;
    event.preventDefault();
    void navigate(to);
  }
  return (
    <a {...rest} href={to} onClick={handle}>
      {children}
    </a>
  );
}
