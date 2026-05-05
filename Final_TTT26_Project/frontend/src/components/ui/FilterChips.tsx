import { motion } from 'framer-motion'

const FILTERS = ['Restaurants', 'Competitors', 'Transport', 'Population', 'Risk']

export function FilterChips() {
  return (
    <div className="glass flex max-w-[min(92vw,560px)] gap-2 overflow-x-auto rounded-2xl px-3 py-2">
      {FILTERS.map((label) => (
        <motion.button
          key={label}
          whileTap={{ scale: 0.95 }}
          className="whitespace-nowrap rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-slate-200 transition hover:bg-white/15"
        >
          {label}
        </motion.button>
      ))}
    </div>
  )
}
