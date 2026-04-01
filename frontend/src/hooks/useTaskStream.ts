import { useEffect, useRef, useCallback } from 'react'
import { useAgentStore, Step } from '../store/agentStore'

interface BrowserState {
  step?: number
  url?: string
  last_action?: string | Record<string, unknown>
  last_action_result?: string | Record<string, unknown>
  scope?: string
  retry_count?: number
  screenshot?: string // base64
  status?: 'running' | 'done' | 'failed'
  error?: string
}

function parseAction(raw: BrowserState['last_action']): { actionType: string; target: string } {
  if (!raw) return { actionType: 'think', target: '' }
  if (typeof raw === 'string') {
    return { actionType: raw, target: '' }
  }
  const keys = Object.keys(raw)
  const actionType = keys[0] ?? 'action'
  const payload = (raw as Record<string, unknown>)[actionType]
  const target =
    typeof payload === 'string'
      ? payload
      : typeof payload === 'object' && payload !== null
      ? JSON.stringify(payload).slice(0, 120)
      : ''
  return { actionType, target }
}

export function useTaskStream(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { addStep, updateCurrentUrl, updateScreenshot, finalizeSession, incrementTimer, isRunning } = useAgentStore()

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!sessionId || !isRunning) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${protocol}://${host}/api/task/${sessionId}/stream`

    const ws = new WebSocket(url)
    wsRef.current = ws

    timerRef.current = setInterval(() => {
      incrementTimer()
    }, 1000)

    ws.onmessage = (event: MessageEvent) => {
      try {
        const state: BrowserState = JSON.parse(event.data as string)

        if (state.url) updateCurrentUrl(state.url)
        if (state.screenshot) updateScreenshot(`data:image/png;base64,${state.screenshot}`)

        const { actionType, target } = parseAction(state.last_action)
        const resultRaw = state.last_action_result
        const resultStr =
          typeof resultRaw === 'string'
            ? resultRaw
            : resultRaw
            ? JSON.stringify(resultRaw)
            : ''

        const status: Step['status'] =
          state.status === 'failed' || resultStr.toLowerCase().includes('error')
            ? 'failed'
            : state.status === 'done'
            ? 'success'
            : 'running'

        const step: Step = {
          id: crypto.randomUUID(),
          stepNumber: state.step ?? Date.now(),
          action: resultStr || actionType,
          actionType,
          target,
          status,
          url: state.url ?? '',
          scope: state.scope ?? '',
          retryCount: state.retry_count ?? 0,
          timestamp: Date.now(),
        }

        addStep(step)

        if (state.status === 'done') {
          finalizeSession('completed')
          disconnect()
        } else if (state.status === 'failed') {
          finalizeSession('failed')
          disconnect()
        }
      } catch {
        // Non-JSON frames are ignored
      }
    }

    ws.onerror = () => {
      finalizeSession('failed')
      disconnect()
    }

    ws.onclose = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }

    return () => disconnect()
  }, [sessionId, isRunning]) // eslint-disable-line react-hooks/exhaustive-deps

  return { disconnect }
}
