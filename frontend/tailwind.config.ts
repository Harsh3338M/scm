import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        // Core brand palette (dark, high-contrast)
        midnight: {
          50:  '#f0f2ff',
          100: '#e4e7ff',
          200: '#cdd3ff',
          300: '#a9b3ff',
          400: '#7f8cff',
          500: '#5a60ff',
          600: '#3d3fff',
          700: '#2d2bee',
          800: '#2323c5',
          900: '#1e1e9c',
          950: '#12115c',
        },
        // Neon cyan for GCP services and data flows
        neon: {
          50:  '#ecffff',
          100: '#cffcff',
          200: '#a4f7ff',
          300: '#63eefd',
          400: '#00d4ff',
          500: '#00bde0',
          600: '#0096b8',
          700: '#007895',
          800: '#075f7a',
          900: '#0a4f66',
        },
        // Amber for security / warnings
        amber: {
          400: '#ffaa00',
          500: '#f59e0b',
          600: '#d97706',
        },
        // Green for healthy services
        emerald: {
          400: '#34d399',
          500: '#10b981',
        },
        // Red for anomalies
        crimson: {
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
        },
        // Purple for AI/ML
        violet: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
      },
      backgroundImage: {
        'grid-midnight': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Cpath d='M0 40L40 0M-5 5L5-5M35 45L45 35' stroke='%231e1e3f' stroke-width='1'/%3E%3C/svg%3E\")",
        'gradient-radial': 'radial-gradient(ellipse at center, var(--tw-gradient-stops))',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgb(0 212 255 / 0.3)' },
          '100%': { boxShadow: '0 0 20px rgb(0 212 255 / 0.8), 0 0 40px rgb(0 212 255 / 0.3)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      boxShadow: {
        'neon-cyan': '0 0 15px rgb(0 212 255 / 0.4), 0 0 30px rgb(0 212 255 / 0.1)',
        'neon-violet': '0 0 15px rgb(139 92 246 / 0.4), 0 0 30px rgb(139 92 246 / 0.1)',
        'neon-crimson': '0 0 15px rgb(239 68 68 / 0.4), 0 0 30px rgb(239 68 68 / 0.1)',
        'glass': '0 4px 24px rgb(0 0 0 / 0.4), inset 0 1px 0 rgb(255 255 255 / 0.05)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}

export default config
