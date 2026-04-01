import React from 'react'
import {
  MousePointerClick,
  Navigation,
  Type,
  ScrollText,
  Brain,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCw,
} from 'lucide-react'
import type { Step } from '../store/agentStore'

const ACTION_ICONS: Record<string, React.ReactNode> = {
  navigate: <Navigation className="w-3.5 h-3.5" />,
  click: <MousePointerClick className="w-3.5 h-3.5" />,
  type: <Type className="w-3.5 h-3.5" />,
  scroll: <ScrollText className="w-3.5 h-3.5" />,
  think: <Brain className="w-3.5 h-3.5" />,
}

function ActionIcon({ type }: { type: string }) {
  return (
    <span className="text-muted">{ACTION_ICONS[type] ?? <Brain className="w-3.5 h-3.5" />}</span>
  )
}

function StatusIcon({ status }: { status: Step['status'] }) {
  if (status === 'running')
    return <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
  if (status === 'success')
    return <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
  return <XCircle className="w-4 h-4 text-red-400 shrink-0" />
}

const STATUS_BORDER: Record<Step['status'], string> = {
  running: 'border-amber-500/30 bg-amber-500/5',
  success: 'border-green-500/20 bg-green-500/5',
  failed: 'border-red-500/30 bg-red-500/10',
}

interface Props {
  step: Step
}

export default function StepCard({ step }: Props) {
  const border = STATUS_BORDER[step.status]

  return (
    <div className={`flex gap-3 p-3 rounded-xl border ${border} transition-colors`}>
      {/* Step number */}
      <div className="flex flex-col items-center gap-1 pt-0.5">
        <span className="text-[10px] font-mono text-muted w-5 text-center">
          {String(step.stepNumber).padStart(2, '0')}
        </span>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        {/* Action type + target */}
        <div className="flex items-center gap-2">
          <ActionIcon type={step.actionType} />
          <span className="text-xs font-semibold text-text-primary capitalize">{step.actionType}</span>
          {step.retryCount > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded-full">
              <RotateCw className="w-2.5 h-2.5" />
              ×{step.retryCount}
            </span>
          )}
        </div>

        {step.target && (
          <p className="text-xs text-text-secondary truncate" title={step.target}>
            {step.target}
          </p>
        )}

        {step.action && step.action !== step.actionType && (
          <p className="text-[11px] text-muted line-clamp-2">{step.action}</p>
        )}

        {step.scope && (
          <p className="text-[11px] text-muted italic">{step.scope}</p>
        )}

        {step.url && (
          <p className="text-[10px] text-muted font-mono truncate opacity-60">{step.url}</p>
        )}
      </div>

      {/* Status icon */}
      <div className="pt-0.5">
        <StatusIcon status={step.status} />
      </div>
    </div>
  )
}
