/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Re-Skin abgemiked.de: Tailwind-Standardpalette (gray-950-Grund, purple-600-Akzent),
      // Inter. Token-NAMEN bleiben erhalten (Komponenten unverändert), nur die Werte neu.
      colors: {
        canvas: "#030712",      // gray-950 — Seiten-/Content-Grund
        sidebar: "#111827",     // gray-900 — Sidebar, Header
        surface: "#111827",     // gray-900 — Karten/Panels
        surface2: "#111827",
        raised: "#1f2937",      // gray-800
        input: "rgba(31,41,55,.6)",  // gray-800/60 — Eingaben
        hover: "rgba(31,41,55,.5)",  // gray-800/50 — Nav-Hover
        line: "#1f2937",        // gray-800 — Ränder
        line2: "#374151",       // gray-700 — Input-/Divider-Ränder
        linedim: "#1f2937",
        accent: "#9333ea",      // purple-600 — Primär/Toggle
        accent2: "#7e22ce",     // purple-700 — Avatar-Admin/Badge-Rand
        magenta: "#7e22ce",     // (kein Magenta mehr → purple-700)
        accentsoft: "#c084fc",  // purple-400 — Links/aktiv/„Bearbeiten“
        ink: "#ffffff",         // Überschriften/aktiv
        ink2: "#ffffff",
        muted: "#9ca3af",       // gray-400 — Fließtext/Muted
        muted2: "#9ca3af",
        faint: "#6b7280",       // gray-500 — dezent
        faint2: "#6b7280",
        success: "#86efac",     // green-300
        danger: "#fca5a5",      // red-300
        danger2: "#fca5a5",
        warning: "#fcd34d",     // amber-300
        discord: "#5865f2",
      },
      fontFamily: {
        // Alles Inter (abgemiked.de). Mono nur für Code/Secret-Keys.
        sans: ["Inter", "system-ui", "sans-serif"],
        sora: ["Inter", "system-ui", "sans-serif"],
        jakarta: ["Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 20px 50px -30px rgba(0,0,0,.5)",
        glow: "0 10px 24px -14px rgba(0,0,0,.6)",
      },
      keyframes: {
        fIn: { from: { transform: "translateY(8px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        mIn: { from: { transform: "translateY(12px) scale(.98)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        tIn: { from: { transform: "translateY(10px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
      },
      animation: {
        fIn: "fIn .25s ease",
        mIn: "mIn .3s ease",
        tIn: "tIn .22s ease",
      },
    },
  },
  plugins: [],
};
