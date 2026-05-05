/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        ui: {
          bg: 'var(--bg)',
          text: 'var(--text)',
          muted: 'var(--muted)',
          glass: 'var(--glass)',
          border: 'var(--border)',
          accent: 'var(--accent)',
          hover: 'var(--surface-hover)',
        },
        geo: {
          red: '#ef4444',
          yellow: '#f59e0b',
          green: '#22c55e',
        },
      },
      keyframes: {
        fadeSlideIn: {
          '0%': {
            opacity: '0',
            filter: 'blur(8px)',
            transform: 'translateY(12px)',
          },
          '100%': {
            opacity: '1',
            filter: 'blur(0px)',
            transform: 'translateY(0px)',
          },
        },
        slideRightIn: {
          '0%': {
            opacity: '0',
            filter: 'blur(8px)',
            transform: 'translateX(16px)',
          },
          '100%': {
            opacity: '1',
            filter: 'blur(0px)',
            transform: 'translateX(0px)',
          },
        },
        testimonialIn: {
          '0%': {
            opacity: '0',
            filter: 'blur(6px)',
            transform: 'translateY(10px) scale(0.98)',
          },
          '100%': {
            opacity: '1',
            filter: 'blur(0px)',
            transform: 'translateY(0px) scale(1)',
          },
        },
      },
      animation: {
        'fade-slide-in': 'fadeSlideIn 0.65s ease-out forwards',
        'slide-right-in': 'slideRightIn 0.7s ease-out forwards',
        testimonial: 'testimonialIn 0.65s ease-out forwards',
      },
    },
  },
  plugins: [],
}
