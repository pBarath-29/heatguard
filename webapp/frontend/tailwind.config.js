/** @type {import('tailwindcss').Config} */
const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const v = (name) => Object.fromEntries(SHADES.map((s) => [s, `rgb(var(--${name}-${s}) / <alpha-value>)`]));

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"] },
      colors: {
        surface: "rgb(var(--surface) / <alpha-value>)",
        ink: v("ink"), brand: v("brand"), emerald: v("emerald"), amber: v("amber"), red: v("red"), sky: v("sky"), violet: v("violet"), indigo: v("indigo"),
        telegram: "#229ED9",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)",
        lift: "0 10px 30px -12px rgba(15,23,42,0.18)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
        "sheet-in": { from: { transform: "translateY(16px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: { "fade-in": "fade-in .25s ease-out both", "sheet-in": "sheet-in .2s ease-out both" },
    },
  },
  plugins: [],
};
