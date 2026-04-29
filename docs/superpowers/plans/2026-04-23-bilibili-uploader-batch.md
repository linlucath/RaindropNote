# Bilibili Uploader Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-pass batch mode that previews recent videos from a Bilibili uploader page and processes them as transcript-only or note tasks.

**Architecture:** Add a backend batch router with in-memory plus file-backed batch state. The preview endpoint uses yt-dlp flat playlist extraction with existing Bilibili cookies. The start endpoint schedules a background worker that reuses the existing single-video `run_note_task` flow for each item, so all generated results still appear in history. The frontend adds an UP主批量 mode to the existing form with preview, start, and progress polling.

**Tech Stack:** FastAPI, yt-dlp, Python unittest, React/Vite, Zustand-compatible task history, react-hook-form, zod.

---

### Task 1: Backend Preview

**Files:**
- Create: `backend/app/routers/batch.py`
- Modify: `backend/app/__init__.py`
- Test: `backend/tests/test_batch_router.py`

- [ ] Write failing tests for normalizing Bilibili space entries and limiting preview count.
- [ ] Implement `fetch_bilibili_space_videos(space_url, limit)` using yt-dlp flat playlist.
- [ ] Add `POST /api/batch/preview` returning `{videos}`.
- [ ] Register the router and run targeted tests.

### Task 2: Backend Batch Runner

**Files:**
- Modify: `backend/app/routers/batch.py`
- Test: `backend/tests/test_batch_router.py`

- [ ] Write failing tests for skip-existing detection and state transitions.
- [ ] Implement `POST /api/batch/start` and `GET /api/batch/status/{batch_id}`.
- [ ] Reuse `run_note_task` for each video item.
- [ ] Persist batch state under `note_results/batches/{batch_id}.json`.
- [ ] Run targeted tests.

### Task 3: Frontend Batch UI

**Files:**
- Modify: `BillNote_frontend/src/services/note.ts`
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`

- [ ] Add batch service functions.
- [ ] Add form mode `single | uploader_batch` separate from generation mode.
- [ ] Add UP 主链接, 最近 N 条, 跳过已处理, preview, start, progress display.
- [ ] Keep single-video behavior unchanged.
- [ ] Run `pnpm build`.

### Task 4: End-to-End Check

**Files:**
- No new files.

- [ ] Restart backend.
- [ ] Preview `https://space.bilibili.com/16385920/upload/video` with limit 10.
- [ ] Start a small batch with limit 2 and mode `transcript`.
- [ ] Verify batch status reaches completed and generated tasks appear in `/api/task_list`.
