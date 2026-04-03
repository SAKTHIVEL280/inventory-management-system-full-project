/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    'bg-role-admin',
    'bg-role-accounting',
    'bg-role-sales',
    'bg-role-inventory',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#137fec',
        background: {
          light: '#f6f7f8',
          dark: '#101922',
        },
        surface: '#ffffff',
        danger: '#ef4444',
        success: '#10b981',
        warning: '#f59e0b',
        neutral: {
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
        },
        role: {
          admin: '#2563eb',
          accounting: '#059669',
          sales: '#dc2626',
          inventory: '#0ea5e9',
        },
      },
      fontFamily: {
        sans: ['Manrope', 'Inter', 'sans-serif'],
        display: ['Manrope', 'Inter', 'sans-serif'],
      },
      spacing: {
        sidebar: '256px',
        topbar: '64px',
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        card: '0.75rem',
      },
    },
  },
  plugins: [],
}
