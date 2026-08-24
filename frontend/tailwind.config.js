/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        healthy: "#22c55e",
        degraded: "#f59e0b",
        maintenance: "#ef4444",
        critical: "#dc2626",
      }
    },
  },
  plugins: [],
}
