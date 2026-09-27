/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0d1117',
        surface: '#161b22',
        border: '#30363d',
        textMain: '#e6edf3',
        textMuted: '#8b949e',
        healthy: '#2ea043',
        warning: '#d29922',
        critical: '#f85149',
        accent: '#58a6ff',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        radar: {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(2.4)', opacity: '0' },
        },
        wave: {
          '0%, 100%': { height: '8px' },
          '50%': { height: '28px' },
        },
      },
      animation: {
        radar: 'radar 2s cubic-bezier(0, 0.2, 0.8, 1) infinite',
        wave: 'wave 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
