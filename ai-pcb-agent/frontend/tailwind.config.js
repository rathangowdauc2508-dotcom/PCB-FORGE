/** @type {import('tailwindcss').Config} */

/**
 * Blue-glass palette shared by the laptop manufacturing and inspection views.
 * Keep the semantic class names stable so existing workflow components inherit
 * the refreshed workspace styling without changing their behavior.
 */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: {
          50: "#ffffff",
          100: "#192840",
          200: "#2d405c",
          300: "#435774",
          400: "#5e7088",
          500: "#71829a",
          600: "#899ab0",
          700: "#d4dfed",
          800: "#e7eef7",
          850: "#f8faff",
          900: "#ffffff",
          950: "#eaf0f8",
        },
        accent: {
          200: "#42651f",
          300: "#527c2e",
          400: "#8dcc49",
          500: "#a4eb5d",
          600: "#76bd37",
        },
        // Deeper blue reserved for secondary emphasis and progress states.
        gold: {
        400: "#a58af3",
        500: "#8964e8",
        600: "#704bd0",
        },
      },
      fontFamily: {
        display: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "Cascadia Code", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(164,235,93,0.24), 0 12px 38px rgba(93,152,54,0.11)",
        gold: "0 0 0 1px rgba(137,100,232,0.16), 0 12px 38px rgba(137,100,232,0.08)",
      },
      backgroundImage: {
        // Faint technical grid sits behind the frosted workspace surfaces.
        traces:
          "radial-gradient(ellipse at 50% -20%, rgba(104,145,220,0.20), transparent 58%), linear-gradient(rgba(88,125,190,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(88,125,190,0.04) 1px, transparent 1px)",
      },
      backgroundSize: {
        traces: "48px 48px",
      },
    },
  },
  plugins: [],
};
