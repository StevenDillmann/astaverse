/** Tokens mirror shadcn/ui's semantic names, so components read as
 *  `bg-background text-muted-foreground` rather than hardcoded colours —
 *  which is also what makes light/dark a token swap rather than a rewrite. */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        // Domain colours. These carry meaning, so they are named for what
        // they mean rather than for what they look like.
        multiverse: "hsl(var(--multiverse))",
        single: "hsl(var(--single))",
        ok: "hsl(var(--ok))",
        warn: "hsl(var(--warn))",
      },
      fontFamily: {
        sans: ["Geist", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["Google Sans Code", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      borderRadius: { lg: "8px", md: "6px", sm: "4px" },
    },
  },
  plugins: [],
};
