# Transcript Polish Toggle Design

**Goal:** Replace the separate "校对" mode with a single "文字稿" mode plus an explicit "是否校对" toggle, defaulting to off.

**Problem**

The current product exposes three modes: `note`, `transcript`, and `polished_transcript`. That creates two issues:

1. The UI asks the user to choose between two transcript-like modes instead of expressing the real intent: "generate transcript" and optionally "polish it".
2. The backend currently contains hidden behavior around subtitle-backed transcript generation, so the visible mode does not always match the actual output.

**Desired UX**

- The mode selector shows only `笔记` and `文字稿`.
- When `文字稿` is selected, a `是否校对` switch appears.
- The switch defaults to off.
- `文字稿 + 关闭` means fast raw transcript output.
- `文字稿 + 打开` means always run transcript polishing and always output `## 校对文字稿`.

**Compatibility Strategy**

- Keep the existing backend `mode` values for now: `note`, `transcript`, `polished_transcript`.
- Add a frontend-only boolean field `polish_transcript`.
- Map form state to backend request state on submit:
  - `note` -> `note`
  - `transcript + polish_transcript=false` -> `transcript`
  - `transcript + polish_transcript=true` -> `polished_transcript`
- When restoring saved tasks, infer:
  - `## 校对文字稿` -> `mode=transcript`, `polish_transcript=true`
  - `## 简体中文文字稿` -> `mode=transcript`, `polish_transcript=false`
  - otherwise `mode=note`

**Backend Behavior**

- `transcript` stays unchanged and returns raw transcript markdown.
- `polished_transcript` must always run the polishing path, even if the source is platform subtitles.
- The existing route-level requirement for model/provider remains:
  - `note` requires model/provider
  - `polished_transcript` requires model/provider
  - plain `transcript` does not

**Files In Scope**

- `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
  - collapse transcript UI into one mode with a polish toggle
- `BillNote_frontend/src/store/taskStore/index.ts`
  - persist and restore `polish_transcript`
- `backend/app/services/note.py`
  - remove subtitle-specific bypass in polished transcript mode
- `backend/tests/test_transcript_only_mode.py`
  - update transcript-polish behavior expectations
- `backend/tests/test_note_router.py`
  - cover route validation for polished transcript mode

**Testing**

- Backend tests:
  - polished transcript with subtitle source returns `## 校对文字稿`
  - plain transcript still returns `## 简体中文文字稿`
  - polished transcript without model/provider is rejected at route entry
- Frontend checks:
  - the mode buttons show only `笔记` and `文字稿`
  - `文字稿` reveals the polish toggle
  - submit payload maps to the correct backend mode
  - restored tasks recover the toggle correctly
