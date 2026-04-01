import React from 'react'
import {
  Plus,
  LayoutDashboard,
  Monitor,
  Zap,
  CalendarClock,
  BarChart2,
  Settings,
  Bot,
  ChevronRight,
  Clock,
} from 'lucide-react'
import { useAgentStore } from '../store/agentStore'
import type { Session } from '../store/agentStore'

const NAV_ITEMS = [
  { id: 'home' as const, label: 'New Session', icon: Plus },
  { id: 'sessions' as const, label: 'Agent Sessions', icon: LayoutDashboard },
  { id: 'remote-browsers' as const, label: 'Remote Browsers', icon: Monitor },
  { id: 'skills' as const, label: 'Skills', icon: Zap },
  { id: 'jobs' as const, label: 'Scheduled Jobs', icon: CalendarClock },
  { id: 'analytics' as const, label: 'Analytics', icon: BarChart2 },
  { id: 'settings' as const, label: 'Settings', icon: Settings },
]

function StatusDot({ status }: { status: Session['status'] }) {
  const color =
    status === 'running'
      ? 'bg-amber-400'
      : status === 'completed'
      ? 'bg-green-400'
      : status === 'failed'
      ? 'bg-red-400'
      : 'bg-gray-500'
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${color} shrink-0`} />
}

export default function Sidebar() {
  const { currentPage, setCurrentPage, sessions, setViewingSessionId } = useAgentStore()

  const recentSessions = sessions.slice(0, 8)

  function handleSessionClick(session: Session) {
    setViewingSessionId(session.id)
    setCurrentPage('session-detail')
  }

  return (
    <aside className="flex flex-col w-[280px] min-w-[280px] h-screen bg-sidebar border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <span className="text-text-primary font-semibold text-base tracking-tight">Browser Agent</span>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-0.5 px-3 pt-4">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = currentPage === id
          return (
            <button
              key={id}
              onClick={() => setCurrentPage(id)}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors w-full text-left ${
                active
                  ? 'bg-sidebar-hover text-text-primary'
                  : 'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </button>
          )
        })}
      </nav>

      {/* Recent Sessions */}
      {recentSessions.length > 0 && (
        <div className="flex flex-col flex-1 overflow-hidden mt-5 px-3">
          <div className="flex items-center justify-between px-2 mb-2">
            <span className="text-xs font-medium text-muted uppercase tracking-wider">Recent</span>
            <Clock className="w-3 h-3 text-muted" />
          </div>
          <ul className="flex flex-col gap-0.5 overflow-y-auto">
            {recentSessions.map((session) => (
              <li key={session.id}>
                <button
                  onClick={() => handleSessionClick(session)}
                  className="flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-left hover:bg-sidebar-hover transition-colors group"
                >
                  <StatusDot status={session.status} />
                  <span className="text-xs text-text-secondary truncate flex-1 group-hover:text-text-primary">
                    {session.name}
                  </span>
                  <ChevronRight className="w-3 h-3 text-muted opacity-0 group-hover:opacity-100 shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex-1" />

      {/* User */}
      <div className="flex items-center gap-3 px-4 py-4 border-t border-border">
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-accent/20 text-accent font-semibold text-sm shrink-0">
          U
        </div>
        <div className="flex flex-col overflow-hidden">
          <span className="text-text-primary text-sm font-medium truncate">User</span>
          <span className="text-muted text-xs truncate">user@example.com</span>
        </div>
      </div>
    </aside>
  )
}
