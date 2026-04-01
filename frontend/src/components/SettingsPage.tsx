import React, { useState } from 'react'
import { Eye, EyeOff, Save, Loader2, CheckCircle2, XCircle } from 'lucide-react'

interface ApiKeyField {
  id: string
  label: string
  envKey: string
  placeholder?: string
}

const API_KEY_FIELDS: ApiKeyField[] = [
  { id: 'anthropic', label: 'Anthropic API Key', envKey: 'ANTHROPIC_API_KEY', placeholder: 'sk-ant-...' },
  { id: 'azure_endpoint', label: 'Azure OpenAI Endpoint', envKey: 'AZURE_OPENAI_ENDPOINT', placeholder: 'https://your-resource.openai.azure.com' },
  { id: 'azure_key', label: 'Azure OpenAI API Key', envKey: 'AZURE_OPENAI_API_KEY', placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' },
  { id: 'google', label: 'Google API Key', envKey: 'GOOGLE_API_KEY', placeholder: 'AIza...' },
]

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

function ApiKeyInput({ field }: { field: ApiKeyField }) {
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const [saveState, setSaveState] = useState<SaveState>('idle')

  async function handleSave() {
    if (!value.trim()) return
    setSaveState('saving')
    try {
      const res = await fetch('/api/settings/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: field.envKey, value: value.trim() }),
      })
      if (!res.ok) throw new Error('Failed')
      setSaveState('saved')
      setTimeout(() => setSaveState('idle'), 3000)
    } catch {
      setSaveState('error')
      setTimeout(() => setSaveState('idle'), 3000)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-text-secondary">{field.label}</label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={show ? 'text' : 'password'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={field.placeholder}
            className="w-full bg-panel border border-border rounded-lg px-3 pr-10 py-2.5 text-sm text-text-primary placeholder-muted outline-none focus:border-white/30 font-mono"
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-text-secondary transition-colors p-1"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <button
          onClick={handleSave}
          disabled={!value.trim() || saveState === 'saving'}
          className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-sm font-medium bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed min-w-[80px] justify-center"
        >
          {saveState === 'saving' && <Loader2 className="w-4 h-4 animate-spin" />}
          {saveState === 'saved' && <CheckCircle2 className="w-4 h-4" />}
          {saveState === 'error' && <XCircle className="w-4 h-4" />}
          {saveState === 'idle' && <Save className="w-4 h-4" />}
          {saveState === 'idle' ? 'Save' : saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : 'Error'}
        </button>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const [headless, setHeadless] = useState(true)
  const [maxRetries, setMaxRetries] = useState(5)
  const [browserSaveState, setBrowserSaveState] = useState<SaveState>('idle')

  async function handleSaveBrowser() {
    setBrowserSaveState('saving')
    try {
      const res = await fetch('/api/settings/browser', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headless, max_retries: maxRetries }),
      })
      if (!res.ok) throw new Error('Failed')
      setBrowserSaveState('saved')
      setTimeout(() => setBrowserSaveState('idle'), 3000)
    } catch {
      setBrowserSaveState('error')
      setTimeout(() => setBrowserSaveState('idle'), 3000)
    }
  }

  return (
    <div className="flex flex-col flex-1 overflow-y-auto px-8 py-8">
      <div className="max-w-2xl w-full mx-auto flex flex-col gap-10">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
          <p className="text-sm text-muted mt-1">Configure API keys and agent behaviour.</p>
        </div>

        {/* API Keys */}
        <section className="flex flex-col gap-5">
          <div>
            <h2 className="text-base font-semibold text-text-primary">API Keys</h2>
            <p className="text-xs text-muted mt-0.5">Keys are saved to the backend .env file — never stored in the browser.</p>
          </div>
          <div className="flex flex-col gap-5 p-5 rounded-xl bg-panel border border-border">
            {API_KEY_FIELDS.map((field) => (
              <ApiKeyInput key={field.id} field={field} />
            ))}
          </div>
        </section>

        {/* Browser */}
        <section className="flex flex-col gap-5">
          <h2 className="text-base font-semibold text-text-primary">Browser</h2>
          <div className="flex flex-col gap-5 p-5 rounded-xl bg-panel border border-border">
            {/* Headless toggle */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Headless mode</p>
                <p className="text-xs text-muted mt-0.5">Run browser without a visible window</p>
              </div>
              <button
                onClick={() => setHeadless((h) => !h)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  headless ? 'bg-accent' : 'bg-white/10'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    headless ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Max retries */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Max retries</p>
                <p className="text-xs text-muted mt-0.5">Maximum number of retries per failed step</p>
              </div>
              <input
                type="number"
                min={1}
                max={20}
                value={maxRetries}
                onChange={(e) => setMaxRetries(Number(e.target.value))}
                className="w-20 text-center bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary outline-none focus:border-white/30"
              />
            </div>

            {/* Save browser settings */}
            <div className="flex justify-end">
              <button
                onClick={handleSaveBrowser}
                disabled={browserSaveState === 'saving'}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {browserSaveState === 'saving' && <Loader2 className="w-4 h-4 animate-spin" />}
                {browserSaveState === 'saved' && <CheckCircle2 className="w-4 h-4" />}
                {browserSaveState === 'error' && <XCircle className="w-4 h-4" />}
                {browserSaveState === 'idle' ? 'Save browser settings' : browserSaveState === 'saving' ? 'Saving…' : browserSaveState === 'saved' ? 'Saved!' : 'Error'}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
