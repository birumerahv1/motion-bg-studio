import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b0c10",
          subtle: "#11131a",
          panel: "#161823",
          raised: "#1d2030",
          border: "#262a3a",
        },
        brand: {
          50: "#eef3ff",
          100: "#dbe5ff",
          200: "#b9caff",
          300: "#8da6ff",
          400: "#6781ff",
          500: "#4a63ff",
          600: "#3548f5",
          700: "#2937d4",
          800: "#1f2aa6",
          900: "#172078",
        },
        accent: {
          DEFAULT: "#a855f7",
          glow: "#7c3aed",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(74,99,255,.35), 0 8px 30px rgba(74,99,255,.25)",
        soft: "0 6px 20px rgba(0,0,0,.35)",
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(1200px 600px at 80% -10%, rgba(124,58,237,.18), transparent), radial-gradient(900px 500px at -10% 110%, rgba(74,99,255,.18), transparent)",
      },
    },
  },
  plugins: [],
};

export default config;
