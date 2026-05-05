import { Search } from 'lucide-react'
import { useMemo } from 'react'

interface SearchBarProps {
  query: string
  onChange: (value: string) => void
}

const MOCK_SUGGESTIONS = ['Science City Ahmedabad', 'Iskcon Cross Road', 'South Bopal', 'Sabarmati Riverfront']

export function SearchBar({ query, onChange }: SearchBarProps) {
  const suggestions = useMemo(
    () => MOCK_SUGGESTIONS.filter((item) => item.toLowerCase().includes(query.toLowerCase())).slice(0, 3),
    [query],
  )

  return (
    <div className="w-full max-w-sm">
      <div className="glass flex items-center gap-2 rounded-2xl px-3 py-2">
        <Search className="h-4 w-4 text-slate-300" />
        <input
          value={query}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
          placeholder="Search locations..."
        />
      </div>
      {query.length > 0 && (
        <div className="glass mt-2 rounded-xl p-2">
          {suggestions.map((item) => (
            <button
              key={item}
              onClick={() => onChange(item)}
              className="block w-full rounded-lg px-2 py-1.5 text-left text-sm transition hover:bg-white/10"
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
