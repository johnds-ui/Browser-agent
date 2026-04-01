import React, { useState, useRef, useEffect } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { useAgentStore, AVAILABLE_MODELS } from '../store/agentStore'

const PROVIDER_COLORS: Record<string, string> = {
  Anthropic: 'text-orange-400 bg-orange-400/10',
  'Azure OpenAI': 'text-blue-400 bg-blue-400/10',
  Google: 'text-yellow-400 bg-yellow-400/10',
  Groq: 'text-purple-400 bg-purple-400/10',
}

interface Props {
  disabled?: boolean
}

export default function ModelDropdown({ disabled }: Props) {
  const { selectedModelKey, setSelectedModelKey } = useAgentStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const selected = AVAILABLE_MODELS.find((m) => m.modelKey === selectedModelKey) ?? AVAILABLE_MODELS[0]

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-white/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span className="font-medium">{selected.displayName}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute bottom-full mb-2 left-0 z-50 min-w-[260px] bg-[#1e1e1e] border border-border rounded-xl shadow-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-border">
            <p className="text-xs text-muted font-medium uppercase tracking-wider">Select Model</p>
          </div>
          <ul className="py-1">
            {AVAILABLE_MODELS.map((model) => {
              const active = model.modelKey === selectedModelKey
              const providerClass = PROVIDER_COLORS[model.provider] ?? 'text-gray-400 bg-gray-400/10'
              return (
                <li key={model.modelKey}>
                  <button
                    onClick={() => {
                      setSelectedModelKey(model.modelKey)
                      setOpen(false)
                    }}
                    className={`flex items-center justify-between w-full px-3 py-2.5 text-sm text-left transition-colors ${
                      active ? 'bg-white/5 text-text-primary' : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${providerClass}`}>
                        {model.provider}
                      </span>
                      <span>{model.displayName}</span>
                    </span>
                    {active && <Check className="w-3.5 h-3.5 text-accent shrink-0" />}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
