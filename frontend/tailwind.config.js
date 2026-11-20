/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        obsidian: {
          950: '#07080B',
          900: '#0C0E14',
          850: '#11141C',
          800: '#161A24',
          700: '#202634',
        },
        gold: {
          300: '#EBD395',
          400: '#DFBE70',
          500: '#C9A45C',
          600: '#A58038',
          700: '#856422',
          800: '#6B4F19',
        },
        emerald: {
          400: '#34D399',
          500: '#10B981',
          600: '#059669',
          700: '#047857',
        },
      },
      boxShadow: {
        luxury: '0 20px 50px -18px rgba(0, 0, 0, 0.65)',
        goldGlow: '0 0 0 1px rgba(201, 164, 92, 0.25), 0 12px 30px -10px rgba(201, 164, 92, 0.28)',
      },
    },
  },
  plugins: [],
};
