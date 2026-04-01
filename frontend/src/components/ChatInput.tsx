import React, { useRef, useEffect, KeyboardEvent } from 'react'
import {
  Plus,
  Bot,
  Globe,
  Settings2,
  Code2,
  Play,
  Square,
  Lightbulb,
} from 'lucide-react'
import ModelDropdown from './ModelDropdown'
import { useAgentStore } from '../store/agentStore'

interface Props {
  onRunTask: () => void
  onStopTask: () => void
}

export default function ChatInput({ onRunTask, onStopTask }: Props) {
  const { taskInput, setTaskInput, isRunning } = useAgentStore()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [taskInput])

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !isRunning) {
      e.preventDefault()
      if (taskInput.trim()) onRunTask()
    }
  }

  const SUGGESTIONS = [
    'Search and summarize top news',
    'Fill out a web form',
    'Screenshot a page',
    'Navigate and extract data',
  ]

  return (
    <div className="flex flex-col items-center w-full gap-3 px-4 pb-6">
      {/* Main input card */}
      <div
        className={`w-full max-w-3xl rounded-2xl border transition-colors ${
          isRunning ? 'border-accent/30 bg-panel' : 'border-border bg-panel hover:border-white/20'
        }`}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={taskInput}
          onChange={(e) => setTaskInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isRunning}
          placeholder="Send a message..."
          rows={1}
          className="w-full bg-transparent resize-none text-text-primary placeholder-muted text-sm px-4 pt-4 pb-2 outline-none leading-relaxed disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ minHeight: 52, maxHeight: 200 }}
        />

        {/* Toolbar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          {/* Left tools */}
          <div className="flex items-center gap-0.5">
            <ToolBtn icon={<Plus className="w-4 h-4" />} title="Attach" disabled={isRunning} />
            <ToolBtn icon={<Bot className="w-4 h-4" />} title="Agent persona" disabled={isRunning} />
            <ToolBtn icon={<Settings2 className="w-4 h-4" />} title="Browser config" disabled={isRunning} />
            <ToolBtn icon={<Globe className="w-4 h-4" />} title="Web" disabled={isRunning} />
            <ModelDropdown disabled={isRunning} />
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-2">
            <button
              disabled={isRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-text-secondary border border-border hover:bg-white/5 hover:text-text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Code2 className="w-3.5 h-3.5" />
              Get code
            </button>

            {isRunning ? (
              <button
                onClick={onStopTask}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                <Square className="w-3.5 h-3.5" fill="currentColor" />
                Stop
              </button>
            ) : (
              <button
                onClick={onRunTask}
                disabled={!taskInput.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Play className="w-3.5 h-3.5" fill="currentColor" />
                Run task
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Helper row */}
      <div className="flex flex-col items-center gap-3">
        <button className="flex items-center gap-1.5 text-xs text-muted hover:text-text-secondary transition-colors">
          <Plus className="w-3 h-3" />
          Connect integrations
        </button>

        {/* Suggestion chips */}
        <div className="flex items-center gap-2 flex-wrap justify-center">
          <span className="flex items-center gap-1 text-xs text-muted">
            <Lightbulb className="w-3 h-3" /> Ideas
          </span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => !isRunning && setTaskInput(s)}
              disabled={isRunning}
              className="text-xs px-3 py-1 rounded-full border border-border text-text-secondary hover:border-white/30 hover:text-text-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ToolBtn({
  icon,
  title,
  disabled,
}: {
  icon: React.ReactNode
  title: string
  disabled?: boolean
}) {
  return (
    <button
      title={title}
      disabled={disabled}
      className="p-2 rounded-lg text-muted hover:text-text-primary hover:bg-white/5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {icon}
    </button>
  )
}
