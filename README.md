# SelfAgent

**Your AI, Your Computer, Your Rules.**

An open-source AI-powered personal computer assistant. Install it on your machine, add your own API key, and get a persistent AI agent that browses the web, manages files, writes code, sends emails, and more — all through a WhatsApp-style chat interface.

<!-- Screenshot placeholder -->
<!-- ![SelfAgent Chat Interface](docs/screenshot.png) -->

---

## Features

- **Bring your own API key** — no subscriptions, no middleman
- **Never forgets your tasks** — persistent memory across sessions
- **Browses the web** — fills forms, signs up for services, compares prices
- **Writes code** — creates, runs, and debugs code in any language
- **Builds websites** — generates full sites from a single prompt
- **Git workflow** — clone, commit, push, create PRs
- **Analyzes data** — CSV/JSON analysis, charts, reports
- **Reads and sends emails** — IMAP/SMTP integration
- **Controls your computer** — file management, system commands, screenshots
- **Downloads files and videos** — yt-dlp integration
- **Schedules tasks** — cron-like recurring automation
- **100% local** — your data never leaves your machine
- **Lightweight** — runs on a 2015 MacBook Pro
- **Pluggable tools** — easy to add new capabilities via plugin system
- **18 built-in tools** — works with any OpenAI, Claude, or Gemini model
- **Semantic memory** — ChromaDB vector search remembers past conversations

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/[username]/selfagent.git
cd selfagent

# 2. Setup (creates venv, installs deps)
./setup.sh

# 3. Add your API key
# Edit config.yaml and set your API key

# 4. Run
./run.sh
```

Open **http://localhost:8765** in your browser. That's it.

---

## Supported Models

| Provider | Models | Vision | API Key |
|----------|--------|--------|---------|
| **OpenAI** | GPT-4o, GPT-4o Mini | Yes | [Get key](https://platform.openai.com/api-keys) |
| **Anthropic** | Claude Sonnet 4, Claude Opus 4 | Yes | [Get key](https://console.anthropic.com/) |
| **Google** | Gemini 2.0 Flash, Gemini 2.5 Flash, Gemini 2.5 Pro | Yes | [Get key](https://aistudio.google.com/apikey) |
| **OpenRouter** | Any model on OpenRouter | Varies | [Get key](https://openrouter.ai/keys) |

Set your provider and API key in `config.yaml` or through the settings panel in the chat UI.

---

## Built-in Tools

| Tool | Description | Status |
|------|-------------|--------|
| Web Browser | Playwright-based browsing, form filling, screenshots, cookie auto-dismiss | Working |
| Web Search | DuckDuckGo search (no API key needed) | Working |
| File Manager | Read, write, move, delete, search files | Working |
| Code Writer | Write, run, debug code in any language | Working |
| Website Builder | Generate complete websites from prompts | Working |
| Terminal | Interactive terminal sessions | Working |
| Git | Clone, commit, push, PRs | Working |
| Email | IMAP/SMTP read, send, search, reply with attachments | Working |
| Database | SQLite/MySQL/PostgreSQL queries | Working |
| API Tester | REST API testing (like Postman) | Working |
| Screenshot | Screen and window capture | Working |
| Clipboard | Read/write clipboard | Working |
| System Control | Safe system commands | Working |
| Image | Resize, crop, convert, compress | Working |
| PDF | Create (markdown-formatted), read, merge, split PDFs | Working |
| Data Analyzer | CSV/JSON analysis, charts | Working |
| Downloader | Files, videos (yt-dlp) | Working |
| Scheduler | Recurring task automation | Working |

---

## Architecture

```
User <-> Chat UI (WebSocket) <-> FastAPI Backend
                                      |
                              +-------+--------+
                              |   Agent Core   |
                              |  (Think->Plan->|
                              |   Execute->    |
                              |   Observe)     |
                              +-------+--------+
                                      |
                    +-----------------+------------------+
                    |                 |                   |
              Memory System     Tool Registry        Task Manager
              (SQLite +         (Pluggable           (Persistent
               ChromaDB)         Tools)               Task Queue)
```

- **Backend:** Python + FastAPI + WebSocket
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **AI Calls:** httpx (no vendor SDKs)
- **Memory:** SQLite + ChromaDB + sentence-transformers for semantic search
- **Browser:** Playwright (async, headless by default)

---

## Configuration

Copy `config.example.yaml` to `config.yaml`:

```yaml
model:
  provider: "openai"
  api_key: "sk-your-key-here"
  model_name: "gpt-4o"
  max_tokens: 4096
  temperature: 0.7

server:
  host: "127.0.0.1"
  port: 8765
  open_browser: true

safety:
  require_confirmation: true
```

See `config.example.yaml` for all options.

---

## Safety & Privacy

- All data stays on your machine
- API keys stored in local `config.yaml` (gitignored)
- File operations sandboxed to home directory
- Destructive actions require user confirmation
- System commands are whitelist-based
- Payment and password fields are never auto-filled
- No telemetry, no analytics, no external connections (except your chosen AI API)

---

## Project Structure

```
SelfAgent/
├── core/           # Agent core, model router, memory, config
├── tools/          # All 18 built-in tools + plugin loader
├── chat/           # WebSocket server + static chat UI
├── tests/          # Test suite
├── config.yaml     # Your configuration (gitignored)
├── setup.sh        # One-command setup
└── run.sh          # One-command start
```

---

## Development

```bash
# Run tests
source venv/bin/activate
pytest tests/

# Run with auto-reload
uvicorn chat.server:app --reload --port 8765
```

---

## Roadmap

- [x] Phase 1: Foundation (chat UI + multi-model support)
- [x] Phase 2: Persistent memory (SQLite + ChromaDB semantic search)
- [x] Phase 3: Core tools (web browser, files, terminal, search)
- [x] Phase 4: Developer tools (code writer, website builder, git, database, API tester)
- [x] Phase 5: Productivity tools (email, PDFs, scheduler, image, downloader, data analyzer)
- [ ] Phase 6: Polish (comprehensive tests, documentation, plugin ecosystem)

---

## Contributing

Contributions are welcome! Please open an issue or submit a PR.

---

## License

[MIT](LICENSE)

---

**SelfAgent** — Your AI, Your Computer, Your Rules.
