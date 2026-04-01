import React, { useEffect, useRef } from 'react'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import StepCard from './StepCard'
import BrowserPreview from './BrowserPreview'
import { useAgentStore, AVAILABLE_MODELS } from '../store/agentStore'

function formatTime(secs: number) {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

interface Props {
  sessionId: string
}

export default function SessionView({ sessionId }: Props) {
  const { sessions, currentSession, elapsedSeconds, currentUrl } = useAgentStore()
  const session =
    currentSession?.id === sessionId
      ? currentSession
      : sessions.find((s) => s.id === sessionId)

  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new steps arrive
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [session?.steps.length])

  if (!session) return null

  const model = AVAILABLE_MODELS.find((m) => m.modelKey === session.modelKey)

  return (
    <div className="flex flex-1 overflow-hidden gap-0">
      {/* Steps pane */}
      <div className="flex flex-col w-[400px] min-w-[340px] border-r border-border">
        {/* Header */}
        <div className="flex flex-col gap-1 px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Execution Feed</span>
            {session.status === 'running' && (
              <span className="flex items-center gap-1.5 text-xs text-amber-400 font-mono">
                <Loader2 className="w-3 h-3 animate-spin" />
                {formatTime(elapsedSeconds)}
              </span>
            )}
            {session.status === 'completed' && (
              <span className="flex items-center gap-1 text-xs text-green-400">
                <CheckCircle2 className="w-3 h-3" /> Done
              </span>
            )}
            {session.status === 'failed' && (
              <span className="flex items-center gap-1 text-xs text-red-400">
                <XCircle className="w-3 h-3" /> Failed
              </span>
            )}
          </div>

          {model && (
            <p className="text-[11px] text-muted">
              {model.displayName} · {model.provider}
            </p>
          )}

          {currentUrl && (
            <p className="text-[10px] text-muted font-mono truncate" title={currentUrl}>
              {currentUrl}
            </p>
          )}
        </div>

        {/* Task */}
        <div className="px-4 py-3 border-b border-border shrink-0">
          <p className="text-xs text-text-secondary line-clamp-3">{session.task}</p>
        </div>

        {/* Steps */}
        <div ref={scrollRef} className="flex flex-col gap-2 px-3 py-3 overflow-y-auto flex-1">
          {session.steps.length === 0 && session.status === 'running' && (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted">
              <Loader2 className="w-6 h-6 animate-spin" />
              <span className="text-xs">Waiting for steps…</span>
            </div>
          )}
          {session.steps.map((step) => (
            <StepCard key={step.id} step={step} />
          ))}

          {/* Completion banner */}
          {session.status === 'completed' && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/20 mt-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-green-400">Task completed</p>
                <p className="text-[11px] text-muted">
                  {session.steps.length} steps · {formatTime(Math.round(((session.endTime ?? 0) - session.startTime) / 1000))}
                </p>
              </div>
            </div>
          )}

          {session.status === 'failed' && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 mt-2">
              <XCircle className="w-4 h-4 text-red-400 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-red-400">Task failed</p>
                <p className="text-[11px] text-muted">Check the last failed step above.</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Browser preview pane */}
      <div className="flex flex-1 overflow-hidden">
        <BrowserPreview />
      </div>
    </div>
  )
}
