import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Monitor, Play, Pause, SkipBack, Film } from 'lucide-react'
import { useAgentStore } from '../store/agentStore'

// ---------------------------------------------------------------------------
// Replay Player
// ---------------------------------------------------------------------------
function ReplayPlayer({ sessionId }: { sessionId: string }) {
  const [frames, setFrames] = useState<string[]>([])
  const [current, setCurrent] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Fetch frames once
  useEffect(() => {
    setLoading(true)
    fetch(`/api/task/${sessionId}/replay`)
      .then((r) => r.json())
      .then((data) => {
        setFrames(data.frames ?? [])
        setCurrent(0)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setPlaying(false)
  }, [])

  const play = useCallback(() => {
    if (frames.length === 0) return
    setPlaying(true)
    intervalRef.current = setInterval(() => {
      setCurrent((c) => {
        if (c >= frames.length - 1) {
          // auto-stop at end
          if (intervalRef.current) clearInterval(intervalRef.current)
          intervalRef.current = null
          setPlaying(false)
          return c
        }
        return c + 1
      })
    }, 1000 / 3) // 3 fps
  }, [frames.length])

  const restart = useCallback(() => {
    stop()
    setCurrent(0)
  }, [stop])

  // Cleanup on unmount
  useEffect(() => () => stop(), [stop])

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-2 text-muted">
        <Film className="w-10 h-10 opacity-20" />
        <p className="text-xs">Loading replay…</p>
      </div>
    )
  }

  if (frames.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 text-muted">
        <Film className="w-10 h-10 opacity-20" />
        <p className="text-xs">No replay available</p>
      </div>
    )
  }

  const progressPct = frames.length > 1 ? (current / (frames.length - 1)) * 100 : 100

  return (
    <div className="flex flex-col w-full h-full">
      {/* Frame */}
      <div className="flex flex-1 overflow-hidden relative">
        <img
          src={`data:image/jpeg;base64,${frames[current]}`}
          alt={`Frame ${current + 1}`}
          className="w-full h-full object-contain"
        />
        {/* Replay badge */}
        <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-full">
          <Film className="w-3 h-3" />
          Replay
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-1 px-3 py-2 bg-panel border-t border-border shrink-0">
        {/* Progress bar */}
        <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-400 transition-all duration-100"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={restart}
              className="p-1 rounded text-muted hover:text-white hover:bg-white/10 transition-colors"
              title="Restart"
            >
              <SkipBack className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={playing ? stop : play}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 text-xs font-medium transition-colors"
            >
              {playing ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
              {playing ? 'Pause' : 'Play'}
            </button>
          </div>
          <span className="text-[10px] text-muted font-mono">
            {current + 1} / {frames.length}
          </span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main BrowserPreview
// ---------------------------------------------------------------------------
export default function BrowserPreview() {
  const { currentUrl, isRunning, currentSession } = useAgentStore()
  const [liveFrame, setLiveFrame] = useState<string | null>(null)
  const [showReplay, setShowReplay] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const isDone =
    currentSession &&
    (currentSession.status === 'completed' || currentSession.status === 'failed')

  useEffect(() => {
    // Reset replay state when a new session starts
    if (isRunning) setShowReplay(false)
  }, [isRunning])

  useEffect(() => {
    // Disconnect any existing screencast socket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    if (!isRunning || !currentSession) {
      setLiveFrame(null)
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${protocol}://${host}/api/task/${currentSession.id}/screencast`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string)
        if (data.frame) {
          setLiveFrame(`data:image/jpeg;base64,${data.frame}`)
        }
        if (data.done) {
          ws.close()
        }
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [isRunning, currentSession?.id])

  return (
    <div className="flex flex-col w-full h-full bg-surface">
      {/* Browser chrome bar */}
      <div className="flex items-center gap-2 px-3 py-2 bg-panel border-b border-border shrink-0">
        <div className="flex gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
        </div>
        <div className="flex-1 mx-2">
          <div className="flex items-center bg-surface rounded-md px-3 py-1 border border-border">
            {isRunning && (
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse mr-2 shrink-0" />
            )}
            <span className="text-[11px] text-muted font-mono truncate">
              {currentUrl ?? 'about:blank'}
            </span>
          </div>
        </div>
        {/* Replay button — shown when session is done */}
        {isDone && currentSession && (
          <button
            onClick={() => setShowReplay((v) => !v)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors shrink-0 ${
              showReplay
                ? 'bg-green-500/20 text-green-400'
                : 'bg-white/5 text-muted hover:text-white hover:bg-white/10'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            Replay
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden items-center justify-center relative">
        {showReplay && currentSession ? (
          <ReplayPlayer sessionId={currentSession.id} />
        ) : liveFrame ? (
          <img
            src={liveFrame}
            alt="Live browser preview"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="flex flex-col items-center gap-3 text-muted">
            <Monitor className="w-12 h-12 opacity-20" />
            {isRunning ? (
              <p className="text-xs">Connecting to live browser…</p>
            ) : isDone ? (
              <div className="flex flex-col items-center gap-2">
                <p className="text-xs">Session ended</p>
                {currentSession && (
                  <button
                    onClick={() => setShowReplay(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs font-medium hover:bg-green-500/30 transition-colors"
                  >
                    <Play className="w-3.5 h-3.5" />
                    Watch Replay
                  </button>
                )}
              </div>
            ) : (
              <p className="text-xs">Browser preview will appear here</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


