# 🤖 Browser Agent

> An AI-powered browser automation agent that executes natural language tasks in a real Chromium browser using the Chrome DevTools Protocol (CDP). Features multi-LLM support, live browser streaming, step-by-step execution feed, and session replay — all through a sleek React UI.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Multi-LLM Support** | Groq (Llama 3.3 70B, Llama 4 Scout, Kimi K2), Google Gemini, Anthropic Claude, Azure GPT-4o |
| 🌐 **Real Browser Automation** | Playwright + raw CDP hybrid — full Chromium control |
| 📡 **Live Browser Stream** | Watch the agent work in real-time via WebSocket screencast |
| 🎬 **Session Replay** | Play back every action as a video after the task completes |
| 📋 **Execution Feed** | Step-by-step action log with status, retries, and reasoning |
| 🔧 **Self-Healing** | Automatically recovers from broken element selectors |
| ⚙️ **Settings UI** | Configure API keys and browser preferences from the UI |
| 💾 **Session History** | Persisted session list with task names, models, and durations |

---

## 🖥️ Screenshots

### Live Execution
The agent navigates, clicks, and types while you watch the browser live on the right panel.

### Session Replay
After a task completes, click **Replay** to watch everything the agent did — frame by frame with playback controls.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                       │
│  Sidebar │ Execution Feed │ Live Browser Preview / Replay   │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTP + WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend                           │
│  POST /api/task  │  WS /stream  │  WS /screencast          │
│  GET /api/replay │  POST /stop  │  POST /settings          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Agent Orchestrator                        │
│                                                             │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌────────┐  │
│  │ Browser │ → │   DOM    │ → │    LLM    │ → │  CDP  │  │
│  │ Session │   │Extractor │   │  Planner  │   │Executor│  │
│  └─────────┘   └──────────┘   └───────────┘   └────────┘  │
│                                    ↑                        │
│                              Self-Heal on failure           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (free) or any other supported LLM key

---

### 1. Clone the repo

```bash
git clone https://github.com/johnds-ui/Browser-agent.git
cd Browser-agent
```

### 2. Set up the Python backend

```bash
pip install -r browser_agent/requirements.txt
playwright install chromium
```

### 3. Configure environment variables

```bash
cp browser_agent/.env.template browser_agent/.env
```

Edit `browser_agent/.env` and fill in your API keys:

```env
# Pick at least one provider

# Groq (free tier — recommended for getting started)
GROQ_API_KEY=gsk_...

# Google Gemini
GOOGLE_API_KEY=AIza...

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-azure-key>
```

### 4. Start the backend

```bash
python run_server.py
# Server starts on http://0.0.0.0:8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:3000
```

---

## 🤖 Supported Models

| Provider | Model | Key Required | Notes |
|---|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` | Free tier, best reasoning |
| **Groq** | `meta-llama/llama-4-scout-17b-16e-instruct` | `GROQ_API_KEY` | Free tier, fast + large context |
| **Groq** | `moonshotai/kimi-k2-instruct` | `GROQ_API_KEY` | Free tier, 60 RPM |
| **Google** | `gemini-2.0-flash` | `GOOGLE_API_KEY` | Fast and capable |
| **Anthropic** | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` | Best overall quality |
| **Anthropic** | `claude-opus-4-5` | `ANTHROPIC_API_KEY` | Most powerful |
| **Azure** | `gpt-4o` | `AZURE_OPENAI_*` | Enterprise Azure deployment |

---

## 📁 Project Structure

```
Browser-agent/
├── run_server.py                  # Entry point
├── browser_agent/
│   ├── server.py                  # FastAPI app — HTTP + WebSocket API
│   ├── agent/
│   │   └── orchestrator.py        # Main agent loop
│   ├── browser/
│   │   └── session.py             # Playwright + CDP browser session
│   ├── dom/
│   │   └── extractor.py           # Interactive element extraction
│   ├── executor/
│   │   ├── cdp_executor.py        # Action executor (navigate, click, type…)
│   │   └── self_heal.py           # Broken selector recovery
│   ├── llm/
│   │   ├── providers.py           # LLM provider implementations
│   │   ├── registry.py            # Model key → provider mapping
│   │   └── planner.py             # Prompt builder + LLM caller
│   ├── models/
│   │   ├── browser_state.py       # BrowserState snapshot model
│   │   ├── cdp_action.py          # CDPAction model
│   │   └── element.py             # ElementFingerprint model
│   └── state/
│       └── builder.py             # State builder after each action
└── frontend/
    └── src/
        ├── App.tsx                # Root layout
        ├── components/
        │   ├── BrowserPreview.tsx # Live stream + replay player
        │   ├── SessionView.tsx    # Execution feed + preview layout
        │   ├── StepCard.tsx       # Individual step UI card
        │   ├── ChatInput.tsx      # Task input bar
        │   ├── ModelDropdown.tsx  # Model selector
        │   ├── Sidebar.tsx        # Navigation sidebar
        │   └── SettingsPage.tsx   # API key + browser settings
        ├── hooks/
        │   └── useTaskStream.ts   # WebSocket state stream hook
        └── store/
            └── agentStore.ts      # Zustand global state
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/task` | Start a new agent task |
| `WS` | `/api/task/{id}/stream` | Stream BrowserState snapshots |
| `WS` | `/api/task/{id}/screencast` | Stream live JPEG frames (3fps) |
| `GET` | `/api/task/{id}/replay` | Fetch all recorded frames for replay |
| `POST` | `/api/task/{id}/stop` | Cancel a running task |
| `POST` | `/api/settings/env` | Update an environment variable |
| `POST` | `/api/settings/browser` | Update headless / max_retries |
| `GET` | `/api/health` | Health check |

---

## ⚙️ How It Works

1. **Task received** — User types a natural language task (e.g. *"Go to amazon.com and search for laptops"*)
2. **Browser launched** — Playwright starts a Chromium instance (headless or visible)
3. **State captured** — DOM is extracted, interactive elements are indexed `[0]..[N]`
4. **LLM plans** — The planner sends current browser state + history to the LLM, which returns the next CDP action as JSON
5. **Action executed** — The executor runs the action (navigate / click / type / scroll / key_press)
6. **Self-heal** — If an action fails, the self-healer tries to find the correct element by similarity
7. **Repeat** — Loop until the LLM returns `{"action": "done"}` or max retries reached
8. **Replay saved** — All frames captured during the session are stored for post-session playback

---

## 🛠️ Configuration

### Browser Settings (via UI or API)

| Setting | Default | Description |
|---|---|---|
| `headless` | `true` | Run browser without a visible window |
| `max_retries` | `5` | Max failed steps before giving up |

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
