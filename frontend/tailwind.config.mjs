/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
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
        // Cards/floating boxes: pure white on cream (light), steel-900 (dark).
        // Driven by a CSS variable so every bg-white flips with the .dark class.
        white: 'rgb(var(--color-white) / <alpha-value>)',
        // Constant white for icons/text on colored fills (never flips).
        purewhite: '#ffffff',
        // Mistral design system tokens (mistral.ai "cream paper" look).
        // All values are CSS variables so the .dark class flips the whole palette.
        mistral: {
          // Cream surfaces
          surface: 'rgb(var(--color-mistral-surface) / <alpha-value>)',
          band: 'rgb(var(--color-mistral-band) / <alpha-value>)',
          inset: 'rgb(var(--color-mistral-inset) / <alpha-value>)',
          // Hairline borders
          border: 'rgb(var(--color-mistral-border) / <alpha-value>)',
          'border-strong': 'rgb(var(--color-mistral-border-strong) / <alpha-value>)',
          // Ink
          ink: 'rgb(var(--color-mistral-ink) / <alpha-value>)',
          muted: 'rgb(var(--color-mistral-muted) / <alpha-value>)',
          // Signature persimmon red
          red: '#f66c60',
          'red-deep': '#e51300',
          // Joy accents (tags + highlights only)
          yellow: '#fec835',
          'yellow-tint': 'rgb(var(--color-mistral-yellow-tint) / <alpha-value>)',
          orange: '#ff6523',
          'orange-tint': 'rgb(var(--color-mistral-orange-tint) / <alpha-value>)',
          pink: '#ff95de',
          'pink-tint': 'rgb(var(--color-mistral-pink-tint) / <alpha-value>)',
          green: '#45bf87',
          'green-tint': 'rgb(var(--color-mistral-green-tint) / <alpha-value>)',
          blue: '#0087e9',
          'blue-tint': 'rgb(var(--color-mistral-blue-tint) / <alpha-value>)',
          'red-tint': 'rgb(var(--color-mistral-red-tint) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Archivo', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"Space Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
