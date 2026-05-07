# Transcript Polish Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dedicated polished transcript mode in the UI with a transcript polish toggle while making backend polished transcript requests always produce polished output.

**Architecture:** Keep the backend request contract compatible by continuing to use `note`, `transcript`, and `polished_transcript` at the API boundary. Implement the new UX entirely in frontend form state, then tighten backend behavior so `polished_transcript` always runs the GPT polishing path.

**Tech Stack:** React 19, TypeScript, Zustand, FastAPI, Python unittest

---

### Task 1: Lock backend polished transcript behavior

**Files:**
- Modify: `backend/tests/test_transcript_only_mode.py`
- Modify: `backend/app/services/note.py`

- [ ] **Step 1: Write the failing test**

Change the subtitle-backed polished transcript test so it expects `## 校对文字稿` and verifies GPT polishing is used.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_transcript_only_mode -v`
Expected: FAIL in the subtitle-backed polished transcript case because the service still bypasses GPT.

- [ ] **Step 3: Write minimal implementation**

Remove the subtitle-source bypass inside `NoteGenerator.generate(..., mode="polished_transcript")` so the service always calls `_polish_transcript(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m unittest tests.test_transcript_only_mode -v`
Expected: PASS.

### Task 2: Keep route validation aligned

**Files:**
- Modify: `backend/tests/test_note_router.py`
- Modify: `backend/app/routers/note.py`

- [ ] **Step 1: Write the failing test**

Change the route test to assert that `polished_transcript` still requires model/provider, while plain transcript does not.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_note_router -v`
Expected: FAIL if route validation no longer matches the intended API contract.

- [ ] **Step 3: Write minimal implementation**

Restore route validation so `mode in {"note", "polished_transcript"}` requires model/provider.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m unittest tests.test_note_router -v`
Expected: PASS.

### Task 3: Implement transcript polish toggle in the form

**Files:**
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`

- [ ] **Step 1: Add the new form field**

Introduce `polish_transcript: boolean` with default `false`.

- [ ] **Step 2: Update validation and UI**

Keep only `note` and `transcript` as visible modes. Show a `是否校对` switch only for transcript mode. Require model selection only when `note` is selected or transcript polishing is enabled.

- [ ] **Step 3: Update submit mapping**

Map `transcript + polish_transcript=true` to backend `mode="polished_transcript"` and `transcript + polish_transcript=false` to `mode="transcript"`.

- [ ] **Step 4: Manually verify code paths**

Review the submit branches for both single and batch generation to ensure both use the same mode mapping.

### Task 4: Persist and restore the toggle

**Files:**
- Modify: `BillNote_frontend/src/store/taskStore/index.ts`

- [ ] **Step 1: Extend stored form data**

Add `polish_transcript?: boolean` to stored task form data.

- [ ] **Step 2: Restore the toggle from saved results**

Map `## 校对文字稿` to `{ mode: "transcript", polish_transcript: true }` and `## 简体中文文字稿` to `{ mode: "transcript", polish_transcript: false }`.

- [ ] **Step 3: Keep retry behavior consistent**

Ensure retried tasks preserve `polish_transcript` in `formData`.

- [ ] **Step 4: Run targeted backend regression tests**

Run:
`./.venv/bin/python -m unittest tests.test_note_router -v`
`./.venv/bin/python -m unittest tests.test_transcript_only_mode -v`
Expected: PASS.
