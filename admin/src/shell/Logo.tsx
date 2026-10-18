// Marchio ThiasNET (D-99): disegnato nel codice, nessun file SVG da caricare o servire.
export function Logo() {
  return (
    <span className="logo">
      <svg className="logo__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <rect width="32" height="32" rx="7" className="logo__bg" />
        <path d="M8 9h16v4h-6v12h-4V13H8z" className="logo__t" />
        <circle cx="24" cy="23" r="2.5" className="logo__dot" />
      </svg>
      <span className="logo__text">ThiasNET</span>
    </span>
  );
}
