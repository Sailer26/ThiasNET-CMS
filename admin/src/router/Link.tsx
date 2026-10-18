import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { navigate } from "./router";

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string };

export function Link({ to, onClick, children, ...rest }: Props) {
  function handle(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    if (event.defaultPrevented || event.button !== 0 || modified) return;
    event.preventDefault();
    navigate(to);
  }
  return (
    <a href={to} onClick={handle} {...rest}>
      {children}
    </a>
  );
}
