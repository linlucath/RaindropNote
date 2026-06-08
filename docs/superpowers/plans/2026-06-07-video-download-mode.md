# Video Download Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-video `video_download` mode that downloads an authorized Bilibili video as MP4 with a selectable resolution.

**Architecture:** Reuse the existing FastAPI note task route, task status files, downloader provider, and frontend task polling. Add a download-only branch before subtitle/transcript/LLM work, and return a saved task result that the frontend can display as a downloadable file result.

**Tech Stack:** Python 3 + FastAPI + pytest, `yt-dlp` + FFmpeg, React 19 + Vite + TypeScript + lightweight source-based frontend tests.

---

### Task 1: Backend Mode And Resolution Validation

**Files:**
- Modify: `backend/app/services/task_runtime.py`
- Modify: `backend/app/services/note_tasks.py`
- Modify: `backend/app/routers/note.py`
- Test: `backend/tests/test_note_generation_modes.py`

- [ ] Write failing tests for accepting `polished_transcript` and `video_download`.
- [ ] Write failing tests for rejecting unsupported modes and resolutions.
- [ ] Add constants and normalizers for supported modes and video resolutions.
- [ ] Thread `video_resolution` through the request payload and background task call.
- [ ] Run targeted backend tests.

### Task 2: Bilibili Resolution-Aware Video Download

**Files:**
- Modify: `backend/app/downloaders/base.py`
- Modify: `backend/app/downloaders/bilibili_downloader.py`
- Modify: `backend/app/downloaders/bilibili_ytdlp_options.py`
- Test: `backend/tests/test_bilibili_ytdlp_options.py`
- Test: `backend/tests/test_bilibili_downloader.py`

- [ ] Write failing tests for resolution format selectors.
- [ ] Write failing tests that `download_video` passes the requested resolution.
- [ ] Add optional `resolution` argument to downloader video methods.
- [ ] Build resolution-aware `yt-dlp` options.
- [ ] Run targeted downloader tests.

### Task 3: Download-Only Task Branch

**Files:**
- Create: `backend/app/services/video_download_result.py`
- Modify: `backend/app/services/note.py`
- Modify: `backend/app/services/note_task_results.py`
- Test: `backend/tests/test_video_download_mode.py`

- [ ] Write failing test that `video_download` skips subtitle/GPT paths and calls only `download_video`.
- [ ] Write failing test for saved video download result shape.
- [ ] Implement result payload builder and NoteGenerator branch.
- [ ] Mark task success through existing completion/status helpers.
- [ ] Run targeted task tests.

### Task 4: Frontend Submission And UI

**Files:**
- Modify: `BillNote_frontend/src/services/note.ts`
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- Modify: `BillNote_frontend/src/pages/HomePage/components/taskSubmission.ts`
- Modify: `BillNote_frontend/src/store/homePageStore/persistHomePageState.ts`
- Test: `BillNote_frontend/src/pages/HomePage/components/videoDownloadMode.test.js`
- Test: `BillNote_frontend/src/pages/HomePage/components/taskSubmission.test.ts`

- [ ] Write failing frontend source tests for mode/resolution controls.
- [ ] Write failing task reuse test that includes mode and resolution.
- [ ] Add frontend types for `video_download` and `video_resolution`.
- [ ] Add a mode selector and resolution selector for single-video tasks.
- [ ] Skip model requirement when downloading video.
- [ ] Run targeted frontend tests.

### Task 5: Verification

**Files:**
- Verify backend targeted tests.
- Verify frontend targeted tests.
- Optionally run broader backend/frontend suites if targeted tests are clean.

- [ ] Run backend tests for touched backend modules.
- [ ] Run frontend tests for touched frontend modules.
- [ ] Run a manual or mocked download task if local services are available.
- [ ] Inspect `git diff` for unrelated changes.
