import { Send, Sparkles, Trash2, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useDashboardStore } from '../../../store/dashboardStore'
import { getLocationInsights } from '../../../services/aiService'

const SUGGESTIONS = [
  'Is this a good location for a restaurant?',
  'What are the main risks here?',
  'Best locations near a metro station?',
  'Sites with low flood risk',
  'High footfall zones analysis',
]

export function AskAIPanel() {
  const [query, setQuery]       = useState('')
  const [messages, setMessages] = useState<{ role: 'user' | 'ai'; text: string }[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const selectedLocationLabel = useDashboardStore((s) => s.selectedLocationLabel)
  const score = useDashboardStore((s) => s.score)
  const selectedCoordinates = useDashboardStore((s) => s.selectedCoordinates)
  const nearby = useDashboardStore((s) => s.nearby)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const trimmed = query.trim()
    if (!trimmed || isLoading) return
    const contextStr = selectedLocationLabel
      ? `[Location: ${selectedLocationLabel}] `
      : ''
      
    setMessages((m) => [
      ...m,
      { role: 'user', text: trimmed }
    ])
    setQuery('')
    setIsLoading(true)

    try {
      if (selectedCoordinates) {
        const { lat, lng } = selectedCoordinates
        const contextData = { score, nearby }
        const insight = await getLocationInsights(lat, lng, trimmed, contextData)
        
        setMessages((m) => [
          ...m,
          { role: 'ai', text: `${contextStr}${insight}` }
        ])
      } else {
        setMessages((m) => [
          ...m,
          {
            role: 'ai',
            text: `${contextStr}Analysing "${trimmed}"… Select a location and run analysis for richer insights.`,
          },
        ])
      }
    } catch (error) {
      setMessages((m) => [
        ...m,
        { role: 'ai', text: `${contextStr}Sorry, there was an error communicating with the AI.` }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-3">

      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ui-muted">
          <Sparkles className="h-3 w-3 text-purple-400" /> Ask AI
        </p>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => setMessages([])}
            className="flex items-center gap-1 text-[10px] text-ui-muted transition hover:text-red-400"
          >
            <Trash2 className="h-3 w-3" /> Clear
          </button>
        )}
      </div>

      {/* Location context pill */}
      {selectedLocationLabel && (
        <div className="rounded-lg border border-purple-500/20 bg-purple-500/8 px-2.5 py-1.5 text-[10px] text-purple-400">
          📍 {selectedLocationLabel}
        </div>
      )}

      {/* Conversation */}
      {messages.length > 0 && (
        <div className="max-h-52 space-y-2 overflow-y-auto rounded-xl border border-ui-border bg-ui-glass/50 p-2 scrollbar-hide">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`text-xs leading-relaxed ${
                m.role === 'user' ? 'text-right' : 'text-left'
              }`}
            >
              <span
                className={`inline-block max-w-[92%] rounded-xl px-3 py-1.5 ${
                  m.role === 'user'
                    ? 'bg-ui-accent/20 text-ui-text'
                    : 'bg-purple-500/10 text-ui-muted'
                }`}
              >
                {m.text}
              </span>
            </div>
          ))}
          {isLoading && (
            <div className="text-xs leading-relaxed text-left">
              <span className="inline-block max-w-[92%] rounded-xl px-3 py-1.5 bg-purple-500/10 text-ui-muted flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin" /> Thinking...
              </span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Suggestions */}
      {messages.length === 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-ui-muted">Try asking:</p>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuery(s)}
              className="w-full rounded-xl border border-ui-border bg-ui-glass/50 px-3 py-2 text-left text-[11px] text-ui-muted transition hover:border-purple-500/30 hover:bg-purple-500/5 hover:text-ui-text"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          disabled={isLoading}
          placeholder={selectedLocationLabel ? 'Ask about this location…' : 'Ask anything about locations…'}
          className="flex-1 rounded-xl border border-ui-border bg-ui-glass px-3 py-2 text-xs text-ui-text outline-none placeholder:text-ui-muted focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 disabled:opacity-50"
        />
        <button
          type="button"
          onClick={send}
          disabled={!query.trim() || isLoading}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-purple-500/20 text-purple-400 transition hover:bg-purple-500/30 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  )
}

