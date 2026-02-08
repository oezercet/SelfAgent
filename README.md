# SelfAgent

**Your AI, Your Computer, Your Rules.**

An open-source AI-powered personal computer assistant. Install it on your machine, add your own API key (or use Ollama for free local models), and get a persistent AI agent that browses the web, manages files, writes code, sends emails, and more — all through a WhatsApp-style chat interface.

<!-- Screenshot placeholder -->
<!-- ![SelfAgent Chat Interface](docs/screenshot.png) -->

---

## Features

### AI & Model Support
- **5 AI providers** — OpenAI, Anthropic (Claude), Google (Gemini), OpenRouter, Ollama
- **Bring your own API key** — no subscriptions, no middleman
- **Free local models with Ollama** — no API key needed, runs entirely on your machine
- **Ollama dynamic management** — check status, see installed models, pull new models from the UI
- **Free cloud models via OpenRouter** — Llama 3.3 70B, Mistral, Qwen3, DeepSeek R1 and more
- **Per-provider API keys** — store keys for all providers, switch instantly
- **Hot-swap models** — change provider/model mid-conversation from the settings panel

### Memory & Intelligence
- **Persistent memory** — remembers conversations across sessions (SQLite)
- **Semantic search** — finds relevant past conversations using ChromaDB + sentence-transformers
- **User profile** — stores your name, email, preferences and applies them automatically
- **Auto-summarization** — old conversations are summarized and stored for future context
- **Task tracking** — persistent task queue with priorities, subtasks, and status management

### Chat Interface
- **WhatsApp-style UI** — dark theme, real-time messaging, typing indicators
- **Markdown rendering** — headings, bold, italic, code blocks, lists, links, blockquotes
- **File upload** — drag & drop or click to attach files to messages
- **Token usage display** — real-time token count and estimated cost per session
- **Tool toggles** — enable/disable individual tools from the settings panel
- **PIN authentication** — optional PIN protection for the chat interface
- **Mobile responsive** — works on phones and tablets

### 19 Built-in Tools
- **Web browsing** — navigate, fill forms, click buttons, extract data, take screenshots
- **Web search** — DuckDuckGo search, no API key needed
- **File management** — read, write, move, delete, search files (sandboxed to home directory)
- **Code writing** — write, run, debug code in 10+ languages with project scaffolding
- **Website building** — generate complete websites from 8 templates with local preview
- **Terminal** — persistent terminal sessions with long-running process support
- **Git & GitHub** — clone, commit, push, pull, branches, PRs, GitHub repo creation
- **Email** — read inbox, search, send (HTML formatted), reply with attachments
- **Database** — SQLite queries, table inspection, CSV/JSON export/import, backups
- **API testing** — HTTP requests, assertions, collections, auto-documentation
- **Screenshot** — full screen and window capture
- **Clipboard** — read and write system clipboard
- **System control** — system info, open apps, manage processes
- **Image editing** — resize, crop, convert, compress, watermark, batch processing
- **PDF** — create from markdown, read, merge, split, convert to images, watermark
- **Data analysis** — load CSV/JSON/Excel, statistics, charts, reports, data cleaning
- **File download** — direct downloads, YouTube videos/audio via yt-dlp
- **Task scheduling** — one-time and cron-style recurring task automation
- **Plugin system** — add custom tools by dropping a Python file in `plugins/`

### Safety & Privacy
- **100% local** — your data never leaves your machine
- **No telemetry** — no analytics, no tracking, no external connections (except your chosen AI API)
- **API keys gitignored** — `config.yaml` and `storage/` are never committed
- **File sandboxing** — file operations restricted to home directory
- **Destructive action confirmation** — delete, send email, etc. require user approval
- **Command blocking** — dangerous commands (`rm -rf /`, `format`, `mkfs`) are blocked
- **Payment/password protection** — never auto-fills payment or password fields on websites

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ozercevikk/SelfAgent.git
cd SelfAgent

# 2. Setup (creates venv, installs deps, Playwright browser)
chmod +x setup.sh && ./setup.sh

# 3. Add your API key
# Edit config.yaml and set your provider + API key
# OR use Ollama for free local models (no API key needed)

# 4. Run
./run.sh
```

Open **http://localhost:8765** in your browser. That's it.

### Using Ollama (Free, Local, No API Key)

```bash
# Install Ollama
brew install ollama

# Pull a model
ollama pull llama3.2

# Start Ollama
ollama serve

# In SelfAgent settings, select "Ollama (Local)" as provider
```

Or pull models directly from the SelfAgent UI — select Ollama, type a model name, and click Pull.

---

## Supported Models

| Provider | Models | API Key | Cost |
|----------|--------|---------|------|
| **OpenAI** | GPT-4o, GPT-4o Mini | [Get key](https://platform.openai.com/api-keys) | Paid |
| **Anthropic** | Claude Sonnet 4, Claude Opus 4 | [Get key](https://console.anthropic.com/) | Paid |
| **Google** | Gemini 2.0 Flash, 2.5 Flash, 2.5 Pro | [Get key](https://aistudio.google.com/apikey) | Free tier available |
| **OpenRouter** | Llama 3.3 70B, Mistral, Qwen3, DeepSeek R1 + more | [Get key](https://openrouter.ai/keys) | Free & Paid models |
| **Ollama** | Llama 3.2, Mistral, Phi-3, Gemma 2, CodeLlama + any | Not needed | Free (local) |

Set your provider and API key in the settings panel (gear icon) or in `config.yaml`.

---

## Built-in Tools (19)

| # | Tool | Description | Key Features |
|---|------|-------------|-------------|
| 1 | **Web Browser** | Playwright-based automation | Navigate, fill forms, click, screenshot, JS eval, 16 actions |
| 2 | **Web Search** | DuckDuckGo search | No API key needed, titles + URLs + snippets |
| 3 | **File Manager** | File system operations | Read, write, move, delete, search — sandboxed to ~/home |
| 4 | **Code Writer** | Multi-language coding | Write, run, debug in Python/JS/Go/Rust/Java + 7 project templates |
| 5 | **Website Builder** | Full website generation | 8 templates (landing, portfolio, blog, e-commerce, etc.) + preview server |
| 6 | **Terminal** | Persistent shell sessions | Long-running processes, multiple sessions, output buffering |
| 7 | **Git** | Version control | Clone, commit, push, pull, branches, PRs, GitHub repo creation |
| 8 | **Email** | IMAP/SMTP email | Read, search, send (HTML), reply, attachments |
| 9 | **Database** | SQL operations | SQLite queries, table inspection, CSV/JSON export/import |
| 10 | **API Tester** | HTTP testing | GET/POST/PUT/DELETE, assertions, collections, auto-docs |
| 11 | **Screenshot** | Screen capture | Full screen + specific window capture |
| 12 | **Clipboard** | System clipboard | Read and write clipboard content |
| 13 | **System Control** | OS interaction | System info, open apps, list/kill processes |
| 14 | **Image** | Image manipulation | Resize, crop, convert, compress, watermark, batch processing |
| 15 | **PDF** | PDF management | Create from markdown, read, merge, split, watermark |
| 16 | **Data Analyzer** | Data analysis | Load CSV/JSON/Excel, statistics, 6 chart types, reports |
| 17 | **Downloader** | File & video download | Direct files, YouTube via yt-dlp, batch download |
| 18 | **Scheduler** | Task automation | One-time + cron-style recurring tasks |
| 19 | **Plugin System** | Extensibility | Drop a Python file in `plugins/` to add new tools |

---

## Architecture

```
User <-> Chat UI (WebSocket) <-> FastAPI Backend
                                      |
                              +-------+--------+
                              |   Agent Core   |
                              |  Think -> Plan |
                              |  Execute ->    |
                              |  Observe       |
                              +-------+--------+
                                      |
                    +-----------------+------------------+
                    |                 |                   |
              Memory System     Tool Registry        Task Manager
              (SQLite +         (19 Tools +           (Persistent
               ChromaDB +        Plugins)              Task Queue)
               User Profile)
```

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.10+ / FastAPI / WebSocket |
| **Frontend** | Vanilla HTML/CSS/JS (no build step, no npm) |
| **AI Calls** | httpx (no vendor SDKs — works with any OpenAI-compatible API) |
| **Memory** | SQLite (short-term) + ChromaDB + sentence-transformers (semantic) |
| **Browser** | Playwright (async, headless) |
| **Database** | aiosqlite |

---

## Configuration

Copy `config.example.yaml` to `config.yaml`:

```yaml
model:
  provider: "openai"               # openai | anthropic | google | openrouter | ollama
  model_name: "gpt-4o"
  temperature: 0.7
  openai_key: "sk-..."            # Per-provider API keys
  anthropic_key: ""
  google_key: ""
  openrouter_key: ""
  # ollama_base_url: "http://localhost:11434"

memory:
  max_short_term: 50               # Messages kept in context
  vector_db: true                  # ChromaDB semantic search
  auto_summarize: true             # Auto-summarize old conversations

email:
  imap_server: "imap.gmail.com"
  smtp_server: "smtp.gmail.com"
  email: "you@gmail.com"
  password: "your-app-password"    # Gmail App Password

browser:
  headless: true
  timeout: 30

safety:
  require_confirmation: true       # Ask before destructive actions
  blocked_commands: ["rm -rf /", "format", "mkfs"]

server:
  host: "127.0.0.1"
  port: 8765
  open_browser: true
  auth_pin: ""                     # Optional PIN protection
```

See `config.example.yaml` for all options.

---

## Project Structure

```
SelfAgent/
├── core/               # Agent core, providers, memory, config, prompts
│   ├── agent.py        # Main agent loop (think -> plan -> execute -> observe)
│   ├── config.py       # YAML configuration management
│   ├── memory.py       # 3-layer memory (short-term, long-term, user profile)
│   ├── model_router.py # Multi-provider model routing
│   ├── providers.py    # OpenAI, OpenRouter, Ollama providers
│   ├── providers_extra.py  # Anthropic (Claude), Google (Gemini) providers
│   ├── prompts.py      # System prompt templates
│   ├── task_manager.py # Persistent task tracking
│   └── vector_store.py # ChromaDB semantic search
├── tools/              # 19 built-in tools
│   ├── base.py         # BaseTool interface
│   ├── registry.py     # Tool registry with enable/disable
│   ├── plugin_loader.py # Plugin auto-discovery
│   ├── web_browser.py  # Playwright browser automation
│   ├── web_search.py   # DuckDuckGo search
│   ├── file_manager.py # File system operations
│   ├── code_writer.py  # Multi-language code execution
│   ├── website_builder.py # Website generation
│   ├── terminal.py     # Persistent terminal sessions
│   ├── git_tool.py     # Git operations + GitHub API
│   ├── email_tool.py   # IMAP/SMTP email
│   ├── database_tool.py # SQLite operations
│   ├── api_tester.py   # HTTP API testing
│   ├── screenshot.py   # Screen capture
│   ├── clipboard.py    # System clipboard
│   ├── system_control.py # OS interaction
│   ├── image_tool.py   # Image manipulation
│   ├── pdf_tool.py     # PDF operations
│   ├── data_analyzer.py # Data analysis + charts
│   ├── downloader.py   # File/video download
│   └── scheduler.py    # Task scheduling
├── chat/               # WebSocket server + chat UI
│   ├── server.py       # FastAPI WebSocket server
│   ├── handlers.py     # Message handlers (chat, config, Ollama)
│   ├── auth.py         # PIN authentication
│   └── static/         # Frontend (HTML/CSS/JS)
├── plugins/            # Custom tool plugins (auto-loaded)
├── tests/              # Test suite (34 tests)
├── storage/            # SQLite databases, uploads (gitignored)
├── config.yaml         # Your configuration (gitignored)
├── config.example.yaml # Example configuration
├── requirements.txt    # Python dependencies
├── setup.sh            # One-command setup
├── run.sh              # One-command start
└── LICENSE             # MIT License
```

---

## Development

```bash
# Run tests
source venv/bin/activate
python3 -m pytest tests/ -v

# Run with auto-reload
uvicorn chat.server:app --reload --port 8765
```

### Creating a Plugin

Create a Python file in `plugins/` with a class that extends `BaseTool`:

```python
# plugins/my_tool.py
from tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "My custom tool"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input text"}
        },
        "required": ["input"]
    }

    async def execute(self, **kwargs):
        return f"Result: {kwargs.get('input', '')}"
```

The plugin is auto-discovered and registered on server start.

---

## Requirements

- Python 3.10+
- macOS (primary), Linux (supported)
- ~200MB disk space (with Playwright browser)
- At least one: API key (OpenAI/Anthropic/Google/OpenRouter) OR Ollama installed

### Python Dependencies

```
fastapi, uvicorn, websockets, httpx, pyyaml, aiosqlite,
playwright, chromadb, sentence-transformers, ddgs, Pillow,
python-multipart, pandas, matplotlib, openpyxl, PyMuPDF, yt-dlp
```

---

## Roadmap

- [x] Phase 1: Foundation (chat UI + multi-model support)
- [x] Phase 2: Persistent memory (SQLite + ChromaDB semantic search)
- [x] Phase 3: Core tools (web browser, files, terminal, search)
- [x] Phase 4: Developer tools (code writer, website builder, git, database, API tester)
- [x] Phase 5: Productivity tools (email, PDFs, scheduler, image, downloader, data analyzer)
- [x] Phase 6: Ollama integration (local models, dynamic model management, status panel)
- [ ] Phase 7: Multi-agent collaboration, voice input, mobile app

---

## Contributing

Contributions are welcome! Please open an issue or submit a PR.

---

## License

[MIT](LICENSE)

---

**SelfAgent** — Your AI, Your Computer, Your Rules.
