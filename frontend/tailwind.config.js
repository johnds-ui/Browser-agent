/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: '#0f0f0f',
        'sidebar-hover': '#1a1a1a',
        surface: '#141414',
        panel: '#1c1c1c',
        border: '#2a2a2a',
        accent: '#f97316',
        'accent-hover': '#ea6c0a',
        muted: '#6b7280',
        'text-primary': '#f3f4f6',
        'text-secondary': '#9ca3af',
      },
    },
  },
  plugins: [],
}
