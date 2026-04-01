import React from 'react'
import { CheckCircle2, XCircle, Loader2, Clock, ExternalLink } from 'lucide-react'
import { useAgentStore, AVAILABLE_MODELS } from '../store/agentStore'
import type { Session } from '../store/agentStore'

function formatDuration(startTime: number, endTime?: number): string {
  const ms = (endTime ?? Date.now()) - startTime
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const remainS = s % 60
  if (m > 0) return `${m}m ${remainS}s`
  return `${s}s`
}

function formatDate(ts: number): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(ts))
}

function StatusBadge({ status }: { status: Session['status'] }) {
  if (status === 'running') {
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-amber-400 bg-amber-400/10 px-2 py-1 rounded-full">
        <Loader2 className="w-3 h-3 animate-spin" />
        Running
      </span>
    )
  }
  if (status === 'completed') {
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-green-400 bg-green-400/10 px-2 py-1 rounded-full">
        <CheckCircle2 className="w-3 h-3" />
        Completed
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-red-400 bg-red-400/10 px-2 py-1 rounded-full">
        <XCircle className="w-3 h-3" />
        Failed
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 text-xs font-medium text-muted bg-white/5 px-2 py-1 rounded-full">
      <Clock className="w-3 h-3" />
      Idle
    </span>
  )
}

function SessionRow({ session, onClick }: { session: Session; onClick: () => void }) {
  const model = AVAILABLE_MODELS.find((m) => m.modelKey === session.modelKey)

  return (
    <tr
      onClick={onClick}
      className="group border-b border-border hover:bg-white/[0.03] cursor-pointer transition-colors"
    >
      <td className="px-5 py-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-text-primary group-hover:text-white transition-colors truncate max-w-xs">
            {session.name}
          </span>
          <span className="text-[11px] text-muted line-clamp-1">{session.task}</span>
        </div>
      </td>
      <td className="px-5 py-4">
        {model ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-text-secondary">{model.displayName}</span>
            <span className="text-[11px] text-muted">{model.provider}</span>
          </div>
        ) : (
          <span className="text-xs text-muted">{session.modelKey}</span>
        )}
      </td>
      <td className="px-5 py-4">
        <StatusBadge status={session.status} />
      </td>
      <td className="px-5 py-4">
        <span className="text-xs text-text-secondary">{formatDate(session.startTime)}</span>
      </td>
      <td className="px-5 py-4">
        <span className="text-xs text-text-secondary font-mono">
          {formatDuration(session.startTime, session.endTime)}
        </span>
      </td>
      <td className="px-5 py-4 text-right">
        <span className="text-xs text-muted">{session.steps.length} steps</span>
      </td>
      <td className="px-5 py-4 text-right">
        <ExternalLink className="w-3.5 h-3.5 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </td>
    </tr>
  )
}

export default function AgentSessionsPage() {
  const { sessions, setViewingSessionId, setCurrentPage } = useAgentStore()

  function handleSessionClick(session: Session) {
    setViewingSessionId(session.id)
    setCurrentPage('session-detail')
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Page header */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-border shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Agent Sessions</h1>
          <p className="text-sm text-muted mt-0.5">
            {sessions.length} session{sessions.length !== 1 ? 's' : ''} total
          </p>
        </div>
      </div>

      {/* Table */}
      {sessions.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-center">
            <Clock className="w-10 h-10 text-muted opacity-30" />
            <p className="text-sm text-muted">No sessions yet. Run a task to get started.</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Session
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Model
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Started
                </th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-5 py-3 text-right text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Steps
                </th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <SessionRow
                  key={session.id}
                  session={session}
                  onClick={() => handleSessionClick(session)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
