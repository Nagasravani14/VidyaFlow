import type { Config } from "tailwindcss";
export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { navy: { 950: "#050818", 900: "#070b1f", 800: "#0d1330", 700: "#151c42" } },
    fontFamily: { sans: ["var(--font-body)", "system-ui", "sans-serif"], display: ["var(--font-display)", "system-ui", "sans-serif"] },
    boxShadow: { card: "0 1px 2px rgba(15,23,60,.04), 0 8px 24px -12px rgba(49,46,129,.18)", glow: "0 0 32px rgba(99,102,241,.45)" },
  } },
  plugins: [],
} satisfies Config;
