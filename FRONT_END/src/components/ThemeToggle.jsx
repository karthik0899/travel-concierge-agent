import { useEffect, useState } from "react";

// Reads/writes the `.dark` class on <html> and persists the choice.
// The initial class is set by the inline script in index.html (no flash).
export function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <button
      onClick={() => setDark((d) => !d)}
      title={dark ? "Switch to light" : "Switch to dark"}
      aria-label="Toggle theme"
      className="flex h-7 w-7 items-center justify-center rounded-lg border border-strong bg-elevated text-sm text-muted transition hover:text-fg"
    >
      {dark ? "☀️" : "🌙"}
    </button>
  );
}
