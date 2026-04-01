import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Model {
  displayName: string
  modelKey: string
  provider: string
}

export const AVAILABLE_MODELS: Model[] = [
  { displayName: 'Claude Sonnet 4.5', modelKey: 'claude-sonnet-4-5', provider: 'Anthropic' },
  { displayName: 'Claude Opus 4.5', modelKey: 'claude-opus-4-5', provider: 'Anthropic' },
  { displayName: 'GPT-4o (Azure)', modelKey: 'azure-gpt-4o', provider: 'Azure OpenAI' },
  { displayName: 'Gemini 2.0 Flash', modelKey: 'gemini-2.0-flash', provider: 'Google' },
  { displayName: 'Llama 3.3 70B (Groq)', modelKey: 'llama-3.3-70b-versatile', provider: 'Groq' },
  { displayName: 'Llama 4 Scout 17B (Groq)', modelKey: 'meta-llama/llama-4-scout-17b-16e-instruct', provider: 'Groq' },
  { displayName: 'Kimi K2 (Groq)', modelKey: 'moonshotai/kimi-k2-instruct', provider: 'Groq' },
]

export type StepStatus = 'running' | 'success' | 'failed'

export interface Step {
  id: string
  stepNumber: number
  action: string
  actionType: string
  target: string
  status: StepStatus
  url: string
  scope: string
  retryCount: number
  screenshotUrl?: string
  timestamp: number
}

export type SessionStatus = 'idle' | 'running' | 'completed' | 'failed'

export interface Session {
  id: string
  name: string
  task: string
  modelKey: string
  status: SessionStatus
  startTime: number
  endTime?: number
  steps: Step[]
}

interface AgentStore {
  // Current task
  taskInput: string
  setTaskInput: (v: string) => void

  // Model selection (persisted)
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void

  // Session state
  currentSession: Session | null
  sessions: Session[]
  currentPage: 'home' | 'sessions' | 'session-detail' | 'remote-browsers' | 'skills' | 'jobs' | 'analytics' | 'settings'
  setCurrentPage: (page: AgentStore['currentPage']) => void

  // Active session detail id
  viewingSessionId: string | null
  setViewingSessionId: (id: string | null) => void

  // Browser preview state
  currentScreenshot: string | null
  currentUrl: string | null

  // Execution control
  isRunning: boolean
  elapsedSeconds: number
  startTask: (task: string, modelKey: string) => Promise<string>
  stopTask: () => void
  addStep: (step: Step) => void
  updateCurrentUrl: (url: string) => void
  updateScreenshot: (dataUrl: string) => void
  finalizeSession: (status: 'completed' | 'failed') => void
  incrementTimer: () => void
  resetTimer: () => void
}

export const useAgentStore = create<AgentStore>()(
  persist(
    (set, get) => ({
      taskInput: '',
      setTaskInput: (v) => set({ taskInput: v }),

      selectedModelKey: 'claude-sonnet-4-5',
      setSelectedModelKey: (key) => set({ selectedModelKey: key }),

      currentSession: null,
      sessions: [],
      currentPage: 'home',
      setCurrentPage: (page) => set({ currentPage: page }),

      viewingSessionId: null,
      setViewingSessionId: (id) => set({ viewingSessionId: id }),

      currentScreenshot: null,
      currentUrl: null,

      isRunning: false,
      elapsedSeconds: 0,

      startTask: async (task, modelKey) => {
        const res = await fetch('/api/task', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task, model_key: modelKey }),
        })
        const data = await res.json()
        const sessionId: string = data.session_id ?? data.id ?? crypto.randomUUID()

        const model = AVAILABLE_MODELS.find((m) => m.modelKey === modelKey)
        const sessionName = task.length > 40 ? task.slice(0, 40) + '…' : task

        const newSession: Session = {
          id: sessionId,
          name: sessionName,
          task,
          modelKey,
          status: 'running',
          startTime: Date.now(),
          steps: [],
        }

        set({
          currentSession: newSession,
          sessions: [newSession, ...get().sessions],
          isRunning: true,
          currentPage: 'home',
          currentScreenshot: null,
          currentUrl: null,
          elapsedSeconds: 0,
        })

        return sessionId
      },

      stopTask: () => {
        const { currentSession, sessions } = get()
        if (!currentSession) return
        const updated = { ...currentSession, status: 'failed' as const, endTime: Date.now() }
        set({
          currentSession: updated,
          sessions: sessions.map((s) => (s.id === updated.id ? updated : s)),
          isRunning: false,
        })
      },

      addStep: (step) => {
        const { currentSession, sessions } = get()
        if (!currentSession) return
        const updated = { ...currentSession, steps: [...currentSession.steps, step] }
        set({
          currentSession: updated,
          sessions: sessions.map((s) => (s.id === updated.id ? updated : s)),
        })
      },

      updateCurrentUrl: (url) => set({ currentUrl: url }),
      updateScreenshot: (dataUrl) => set({ currentScreenshot: dataUrl }),

      finalizeSession: (status) => {
        const { currentSession, sessions } = get()
        if (!currentSession) return
        // Mark any still-running steps as success or failed based on final status
        const finalStepStatus = status === 'completed' ? 'success' : 'failed'
        const finalizedSteps = currentSession.steps.map((s) =>
          s.status === 'running' ? { ...s, status: finalStepStatus as StepStatus } : s
        )
        const updated = { ...currentSession, status, endTime: Date.now(), steps: finalizedSteps }
        set({
          currentSession: updated,
          sessions: sessions.map((s) => (s.id === updated.id ? updated : s)),
          isRunning: false,
        })
      },

      incrementTimer: () => set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 })),
      resetTimer: () => set({ elapsedSeconds: 0 }),
    }),
    {
      name: 'agent-store',
      partialize: (s) => ({
        selectedModelKey: s.selectedModelKey,
        sessions: s.sessions.slice(0, 50),
      }),
    }
  )
)
