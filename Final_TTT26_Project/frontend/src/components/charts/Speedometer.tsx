import { motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

interface SpeedometerProps {
  score: number
}

const clamp = (v: number) => Math.max(0, Math.min(100, v))

export function Speedometer({ score }: SpeedometerProps) {
  const s = clamp(score)
  const [animatedScore, setAnimatedScore] = useState(0)
  // Keep a ref to cancel the rAF loop on unmount / score change — prevents memory leak
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const end = s
    const duration = 1200
    const startTime = performance.now()
    const startVal = 0

    const step = (now: number) => {
      const p = Math.min((now - startTime) / duration, 1)
      const easeOut = 1 - Math.pow(1 - p, 4)
      setAnimatedScore(Math.round(startVal + (end - startVal) * easeOut))
      if (p < 1) {
        rafRef.current = requestAnimationFrame(step)
      }
    }
    rafRef.current = requestAnimationFrame(step)

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [s])

  const radius = 64
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (s / 100) * circumference

  // Colour: green ≥70, amber 40–69, red <40
  const ringColor =
    s >= 70 ? 'url(#scoreGradientGreen)' :
    s >= 40 ? 'url(#scoreGradientAmber)' :
              'url(#scoreGradientRed)'

  const scoreLabel =
    s >= 70 ? 'High Potential' :
    s >= 40 ? 'Moderate Potential' :
              'Low Potential'

  return (
    <div className="relative mx-auto flex h-44 w-44 flex-col items-center justify-center">
      <svg
        className="absolute inset-0 h-full w-full -rotate-90 transform"
        viewBox="0 0 160 160"
        aria-hidden
      >
        <defs>
          <linearGradient id="scoreGradientGreen" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#124E66" />
            <stop offset="100%" stopColor="#86EFAC" />
          </linearGradient>
          <linearGradient id="scoreGradientAmber" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#92400e" />
            <stop offset="100%" stopColor="#fbbf24" />
          </linearGradient>
          <linearGradient id="scoreGradientRed" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7f1d1d" />
            <stop offset="100%" stopColor="#f87171" />
          </linearGradient>
        </defs>

        {/* Background ring */}
        <circle
          cx="80" cy="80" r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth="6"
        />

        {/* Value ring */}
        <motion.circle
          cx="80" cy="80" r={radius}
          fill="none"
          stroke={ringColor}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </svg>

      <div className="z-10 flex flex-col items-center justify-center pt-1 text-center">
        <span className="text-5xl font-bold tracking-tighter text-ui-text drop-shadow-md">
          {animatedScore}
        </span>
        <span className="mt-1 text-[10px] font-medium uppercase tracking-widest text-ui-muted">
          {scoreLabel}
        </span>
      </div>
    </div>
  )
}
