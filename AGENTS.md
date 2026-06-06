# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

雨滴笔记助手 is an AI study-note tool for turning user-authorized video, audio, and local media into polished transcripts and structured Markdown notes. Full-stack app with a FastAPI backend, React frontend, and optional Tauri desktop packaging.

## Development Commands

### Backend (Python 3.11 + FastAPI)
```bash
cd backend
pip install -r requirements.txt
python main.py                    # Starts on 0.0.0.0:8483
```

### Frontend (React 19 + Vite + TypeScript)
```bash
cd BillNote_frontend
pnpm install
pnpm dev          # Dev server on port 3015, proxies /api to backend
pnpm build        # Production build
pnpm lint         # ESLint
```

### Docker
```bash
docker-compose up                              # Web stack (backend + frontend + nginx)
docker-compose -f docker-compose.gpu.yml up    # GPU variant
```

### Desktop (Tauri)
```bash
cd backend && ./build.sh          # Build PyInstaller backend binary
cd BillNote_frontend && pnpm tauri build
```

## Architecture

**Backend** (`backend/`) — FastAPI app, entry point `main.py`:
- `app/routers/` — API routes: `note.py` (generation), `provider.py`, `model.py`, `config.py`
- `app/services/` — Business logic: `note.py` (NoteGenerator orchestrates the full pipeline), `task_serial_executor.py` (task queue)
- `app/downloaders/` — Platform adapters (bilibili, youtube, douyin, kuaishou, local) with shared `base.py` interface
- `app/transcriber/` — Speech-to-text engines (fast-whisper, groq, bcut, kuaishou, mlx-whisper) with factory in `transcriber_provider.py`
- `app/gpt/` — LLM integration with factory pattern (`gpt_factory.py`), prompt templates (`prompt.py`, `prompt_builder.py`), and `request_chunker.py` for long transcripts
- `app/db/` — SQLite + SQLAlchemy: DAO pattern (`provider_dao.py`, `model_dao.py`, `video_task_dao.py`), models in `models/`
- `app/utils/` — `response.py` (ResponseWrapper for consistent JSON), `video_helper.py` (screenshots via FFmpeg), `export.py` (PDF/DOCX)
- `events/` (root level) — Blinker signal system for post-processing (e.g., temp file cleanup after transcription)

**Frontend** (`BillNote_frontend/src/`) — React 19 + Vite + Tailwind + shadcn/ui:
- `pages/HomePage/` — Main note generation UI: `NoteForm.tsx` (input), `MarkdownViewer.tsx` (preview)
- `pages/SettingPage/` — LLM provider management, system monitoring, transcriber config
- `store/` — Zustand stores: `taskStore`, `modelStore`, `configStore`, `providerStore`
- `services/` — Axios API clients matching backend routes
- `hooks/useTaskPolling.ts` — Polls task status every 3 seconds
- `components/ui/` — shadcn/ui (Radix-based) components
- Path alias: `@` → `./src`

**Core Workflow**: User submits authorized media → task queued → prepare media/audio (FFmpeg) → transcribe (Whisper/Groq/etc) → generate notes (LLM) → frontend polls for completion → display Markdown.

## Key Configuration

- **Ports**: Backend 8483, Frontend dev 3015, Docker maps 3015→80
- **Environment**: Root `.env` (copy from `.env.example`). LLM API keys are configured through the UI, not env vars.
- **Database**: SQLite default `raindrop_note.db`, auto-initialized on first run
- **FFmpeg**: Required system dependency for video/audio processing
- **Vite proxy**: Dev server proxies `/api` and `/static` to backend (configured in `vite.config.ts`, reads env from parent dir)

## Agent Workflow Preferences

- **Prefer local-first debugging and testing**: When investigating frontend or backend issues, use local terminal commands, repo scripts, direct HTTP requests, and browser automation that runs from the repository first.
- **Avoid MCP unless necessary**: If the task can be completed reliably without MCP, do not use MCP. Only use MCP when local tooling cannot reach the required surface, or when the user explicitly asks for it.
- **Frontend smoke tests**: For UI interaction bugs, prefer adding or running a local smoke test before guessing. See `docs/runbooks/frontend-smoke-debugging.md` for the recommended workflow.

## Code Style

- **Frontend**: ESLint + Prettier (2 spaces, single quotes, 100 char width, Tailwind plugin). TypeScript strict mode.
- **Backend**: Python with type hints. No configured linter. Uses Pydantic models for validation.
- **Note**: The frontend directory is still named `BillNote_frontend` for compatibility; this is a historical path name, not the product brand.
