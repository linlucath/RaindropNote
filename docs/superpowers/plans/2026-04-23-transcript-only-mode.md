# Transcript Only Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "transcript only" generation mode that produces simplified Chinese readable transcripts without calling the LLM summarizer.

**Architecture:** Extend the existing note generation request with a mode flag. The backend reuses downloader, subtitle, audio metadata, and transcription caches, but branches before GPT summarization to render transcript markdown. The frontend exposes the mode in the existing form, disables model/prompt-only options for transcript mode, and stores the result in the same history model.

**Tech Stack:** FastAPI, Python dataclasses/unittest, React/Vite, Zustand, react-hook-form, zod.

---

### Task 1: Backend transcript renderer

**Files:**
- Modify: `backend/app/services/note.py`
- Test: `backend/tests/test_transcript_only_mode.py`

- [ ] Write a failing unittest proving transcript markdown includes a readable simplified transcript and timestamp section.
- [ ] Implement small helpers in `NoteGenerator` for time formatting, paragraph merging, basic traditional-to-simplified normalization, and markdown rendering.
- [ ] Run the targeted unittest and verify it passes.

### Task 2: Backend mode branch

**Files:**
- Modify: `backend/app/routers/note.py`
- Modify: `backend/app/services/note.py`
- Test: `backend/tests/test_transcript_only_mode.py`

- [ ] Write a failing unittest proving `mode="transcript"` skips `_get_gpt` and `_summarize_text`.
- [ ] Add `mode` to `VideoRequest`, pass it through `run_note_task`, and branch in `NoteGenerator.generate`.
- [ ] Run targeted backend tests and verify they pass.

### Task 3: Frontend mode control

**Files:**
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- Modify: `BillNote_frontend/src/services/note.ts`
- Modify: `BillNote_frontend/src/store/taskStore/index.ts`

- [ ] Add `mode` to form schema/defaults/payload/store formData.
- [ ] Add a two-option mode selector near the submit button.
- [ ] Disable model/style/video understanding/format/extras controls when `mode === "transcript"`.
- [ ] Update submit button labels and request typing.
- [ ] Run `pnpm build` and fix any TypeScript/build errors.

### Task 4: End-to-end verification

**Files:**
- No additional files expected.

- [ ] Run backend targeted tests.
- [ ] Run frontend build.
- [ ] Restart backend LaunchAgent.
- [ ] Submit a transcript-only task against an existing Bilibili URL with `curl`.
- [ ] Verify `/api/task_status/{task_id}` returns `SUCCESS` and markdown contains `## 简体中文文字稿`.
