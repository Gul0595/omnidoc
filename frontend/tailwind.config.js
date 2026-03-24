/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
  safelist: [
    { pattern: /bg-(green|teal|purple|red|amber|blue)-(50|100|500|600)/ },
    { pattern: /text-(green|teal|purple|red|amber|blue)-(600|700|800)/ },
    { pattern: /border-(green|teal|purple|red|amber|blue)-(200|300|400|500)/ },
    { pattern: /ring-(green|teal|purple|red|amber|blue)-(400|500)/ },
  ],
};
