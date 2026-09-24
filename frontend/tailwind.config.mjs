/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{html,js,ts,jsx,tsx,astro}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        secondary: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        // Mistral design system tokens (mistral.ai "cream paper" look)
        mistral: {
          // Cream surfaces
          surface: '#fbfbf8',        // page background
          band: '#f5f4ef',          // subtle bands, badges, table head
          inset: '#ebe9e0',         // inset panels
          // Hairline borders
          border: '#e4e3de',
          'border-strong': '#c9c9c4',
          // Ink
          ink: '#1a1a1a',
          muted: '#6d6d78',
          // Signature persimmon red
          red: '#f66c60',
          'red-deep': '#e51300',
          // Joy accents (tags + highlights only)
          yellow: '#fec835',
          'yellow-tint': '#fff4d2',
          'yellow-highlight': '#ffe8a2',
          orange: '#ff6523',
          'orange-tint': '#fff0eb',
          pink: '#ff95de',
          'pink-tint': '#ffe1f4',
          green: '#45bf87',
          'green-tint': '#e7f6ee',
          blue: '#0087e9',
          'blue-tint': '#e6f3fd',
          'red-tint': '#ffeae8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"Space Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
