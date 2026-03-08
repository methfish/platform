/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#1a1b23',
          raised: '#22232e',
          overlay: '#2a2b38',
          border: '#363746',
        },
        accent: {
          DEFAULT: '#6366f1',
          hover: '#818cf8',
        },
        profit: '#22c55e',
        loss: '#ef4444',
        warning: '#f59e0b',
      },
    },
  },
  plugins: [],
};
