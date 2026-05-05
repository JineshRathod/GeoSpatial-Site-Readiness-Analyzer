import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

export function ProfileMenu() {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative">
      <button onClick={() => setOpen((value) => !value)} className="glass flex items-center gap-2 rounded-full px-2 py-1">
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-cyan-400 to-indigo-500" />
        <ChevronDown className="h-4 w-4 text-slate-200" />
      </button>
      {open && (
        <div className="glass absolute right-0 mt-2 w-40 rounded-xl p-2 text-sm">
          {['Account', 'Settings', 'Logout'].map((item) => (
            <button key={item} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-white/10">
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
