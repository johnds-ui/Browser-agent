import React, { useEffect } from 'react'
import { ChevronDown, Settings } from 'lucide-react'
import Sidebar from './components/Sidebar'
import ChatInput from './components/ChatInput'
import SessionView from './components/SessionView'
import SettingsPage from './components/SettingsPage'
import AgentSessionsPage from './components/AgentSessionsPage'
import { useAgentStore } from './store/agentStore'
import { useTaskStream } from './hooks/useTaskStream'

function TopBar() {
  const { currentPage, currentSession, isRunning, elapsedSeconds, currentUrl, selectedModelKey } = useAgentStore()
  const showSessionBar = isRunning && currentSession && currentPage === 'home'

  function formatTime(secs: number) {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0 bg-surface">
      <div className="flex items-center gap-2">
        <button className="flex items-center gap-1.5 text-sm font-medium text-text-primary hover:text-white transition-colors">
          My Project
          <ChevronDown className="w-3.5 h-3.5 text-muted" />
        </button>
      </div>

      <div className="flex items-center gap-4">
        {showSessionBar && (
          <>
            <span className="text-xs font-mono text-amber-400">{formatTime(elapsedSeconds)}</span>
            {currentUrl && (
              <span className="text-[11px] text-muted font-mono truncate max-w-[260px]">{currentUrl}</span>
            )}
            <span className="text-xs text-muted">{selectedModelKey}</span>
          </>
        )}
        <button className="p-1.5 rounded-lg text-muted hover:text-text-primary hover:bg-white/5 transition-colors">
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function HomePage() {
  const { isRunning, currentSession } = useAgentStore()

  if (isRunning && currentSession) {
    return (
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex flex-1 overflow-hidden">
          <SessionView sessionId={currentSession.id} />
        </div>
        <div className="border-t border-border shrink-0">
          <ChatInputWrapper />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Center heading */}
      <div className="flex flex-1 items-center justify-center px-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <h1 className="text-4xl font-semibold text-text-primary tracking-tight">
            What should I do?
          </h1>
          <p className="text-sm text-muted max-w-sm">
            Describe a task and the agent will automate it in a real browser.
          </p>
        </div>
      </div>
      {/* Bottom-anchored input */}
      <ChatInputWrapper />
    </div>
  )
}

function ChatInputWrapper() {
  const { taskInput, selectedModelKey, startTask, stopTask } = useAgentStore()

  async function handleRunTask() {
    if (!taskInput.trim()) return
    await startTask(taskInput.trim(), selectedModelKey)
  }

  function handleStopTask() {
    stopTask()
  }

  return <ChatInput onRunTask={handleRunTask} onStopTask={handleStopTask} />
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <p className="text-muted text-sm">{title} — coming soon</p>
    </div>
  )
}

export default function App() {
  const { currentPage, currentSession, isRunning } = useAgentStore()

  // Mount the WebSocket stream whenever a session is running
  useTaskStream(isRunning && currentSession ? currentSession.id : null)

  function renderPage() {
    switch (currentPage) {
      case 'home':
        return <HomePage />
      case 'sessions':
        return <AgentSessionsPage />
      case 'settings':
        return <SettingsPage />
      case 'session-detail':
        return <SessionDetailPage />
      case 'remote-browsers':
        return <PlaceholderPage title="Remote Browsers" />
      case 'skills':
        return <PlaceholderPage title="Skills" />
      case 'jobs':
        return <PlaceholderPage title="Scheduled Jobs" />
      case 'analytics':
        return <PlaceholderPage title="Analytics" />
      default:
        return <HomePage />
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex flex-1 overflow-hidden">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

function SessionDetailPage() {
  const { viewingSessionId, sessions } = useAgentStore()
  const session = sessions.find((s) => s.id === viewingSessionId)
  if (!session) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted text-sm">Session not found.</p>
      </div>
    )
  }
  return (
    <div className="flex flex-1 overflow-hidden">
      <SessionView sessionId={session.id} />
    </div>
  )
}
