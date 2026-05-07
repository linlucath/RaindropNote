# Task Progress Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated task progress page that shows active and recent tasks, exposes stage-based progress for single and batch jobs, and supports soft-cancel for both task types.

**Architecture:** Extend the backend task model first so both single tasks and batch jobs have explicit lifecycle metadata, cancel semantics, and a unified progress overview endpoint. Then extend the frontend service and Zustand state to consume the overview, add a dedicated `任务进度` route with focused task/batch cards, and finally wire the existing homepage polling and actions to understand `CANCELLING` and `CANCELLED` as terminal states where appropriate.

**Tech Stack:** FastAPI, Python unittest/pytest, file-backed task status JSON, React 19, Vite, TypeScript, Zustand, react-router, shadcn/ui, react-hook-form.

---

### Task 1: Introduce Shared Progress State Helpers

**Files:**
- Create: `backend/app/services/progress_state.py`
- Test: `backend/tests/test_progress_state.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

```python
def test_write_task_status_persists_metadata_and_updated_at():
    ...

def test_request_task_cancel_marks_cancelling_idempotently():
    ...

def test_progress_state_reads_missing_files_safely():
    ...
```

The tests must exercise real helper functions, not local dict literals.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_progress_state.py -q`

Expected: FAIL because the helper module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement a shared helper module for:

- writing task status payloads with:
  - `status`
  - `message`
  - `updated_at`
  - `created_at`
  - `title`
  - `platform`
- requesting task cancel intention
- reading status payloads safely
- determining whether a task is terminal

This helper becomes the only place that knows the single-task status file schema.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_progress_state.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/progress_state.py backend/tests/test_progress_state.py
git commit -m "feat: add shared progress state helpers"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 2: Define Task and Batch Progress States

**Files:**
- Modify: `backend/app/enmus/task_status_enums.py`
- Modify: `backend/app/routers/batch.py`
- Test: `backend/tests/test_batch_router.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

```python
def test_task_status_description_includes_cancelling_and_cancelled():
    assert TaskStatus.description(TaskStatus.CANCELLING) == "正在停止"
    assert TaskStatus.description(TaskStatus.CANCELLED) == "已取消"

def test_new_batch_payload_contains_progress_metadata():
    batch = create_batch_payload(...)
    assert batch["status"] == "PENDING"
    assert batch["cancel_requested"] is False
    assert batch["current_item_title"] is None
    assert batch["current_item_index"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_batch_router.py -q`

Expected: FAIL because `TaskStatus` lacks the new states and batch metadata expectations are not yet implemented.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- `TaskStatus.CANCELLING`
- `TaskStatus.CANCELLED`
- description labels for both
- batch state fields in the persisted batch payload:
  - `title`
  - `source_label`
  - `created_at`
  - `updated_at`
  - `cancel_requested`
  - `current_item_title`
  - `current_item_index`

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_batch_router.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/enmus/task_status_enums.py backend/app/routers/batch.py backend/tests/test_batch_router.py
git commit -m "feat: add progress lifecycle states"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 3: Add Single-Task Cancel Intention and Status Metadata

**Files:**
- Modify: `backend/app/services/progress_state.py`
- Modify: `backend/app/services/note.py`
- Modify: `backend/app/routers/note.py`
- Test: `backend/tests/test_audio_transcription_confirmation.py`
- Create: `backend/tests/test_task_cancel_flow.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

```python
def test_cancel_task_marks_status_file_as_cancelling():
    ...

def test_cancelled_task_returns_success_payload_with_cancelled_status():
    ...

def test_note_generator_respects_cancel_marker_before_next_stage():
    ...
```

Test expectations:

- `POST /cancel_task` writes a cancel marker or updates status to `CANCELLING`
- `GET /task_status/{task_id}` returns a success envelope with `status="CANCELLED"` once the task is cancelled
- a running task exits at a safety checkpoint and persists `CANCELLED`

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_task_cancel_flow.py -q`

Expected: FAIL because the route and cancel checks do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- `note.py` and `NoteGenerator` should use the shared `progress_state` helper instead of ad-hoc status file writes
- a single-task cancel marker strategy using the shared helper
- `POST /cancel_task`
- a helper in `NoteGenerator` that checks cancel intention:
  - after parsing
  - after download
  - after transcription
  - after summarizing
  - before saving
- `GET /task_status/{task_id}` returns `CANCELLING` / `CANCELLED` via `R.success(...)`, not the error branch

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_task_cancel_flow.py -q
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/note.py backend/app/routers/note.py backend/tests/test_task_cancel_flow.py backend/tests/test_audio_transcription_confirmation.py
git commit -m "feat: add single-task soft cancel flow"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 4: Add Batch Cancel Flow and Child-Task Propagation

**Files:**
- Modify: `backend/app/services/progress_state.py`
- Modify: `backend/app/routers/batch.py`
- Modify: `backend/app/routers/note.py`
- Test: `backend/tests/test_batch_router.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

```python
def test_cancel_batch_marks_batch_as_cancelling():
    ...

def test_cancel_batch_marks_pending_items_cancelled():
    ...

def test_cancel_batch_propagates_cancel_to_current_child_task():
    ...
```

Expected behaviors:

- `POST /batch/cancel` sets `status="CANCELLING"` and `cancel_requested=True`
- pending children become `CANCELLED` when the batch stops
- if a current child has `task_id`, the child receives a cancel intention too

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_batch_router.py -q`

Expected: FAIL because no batch cancel route or propagation exists yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- `POST /batch/cancel`
- batch router should reuse the shared `progress_state` helper for current child cancellation instead of duplicating file logic
- helper to update batch `updated_at`, `current_item_title`, `current_item_index`
- `run_batch(...)` checks `cancel_requested` before starting each child
- pending children become `CANCELLED`
- running child with a `task_id` receives a cancel intention through the same backend cancel helper used by single tasks
- batch terminal state resolves to:
  - `CANCELLED` if cancellation was requested
  - `SUCCESS` if all items are `SUCCESS` or `SKIPPED`
  - `FAILED` otherwise

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_batch_router.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/batch.py backend/app/routers/note.py backend/tests/test_batch_router.py
git commit -m "feat: add batch cancel lifecycle"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 5: Add Progress Overview API and Query Helpers

**Files:**
- Modify: `backend/app/services/progress_state.py`
- Create: `backend/app/services/progress_query.py`
- Modify: `backend/app/routers/note.py`
- Modify: `backend/app/routers/batch.py`
- Create: `backend/tests/test_progress_overview.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

```python
def test_progress_overview_returns_summary_active_and_recent_terminal_groups():
    ...

def test_progress_overview_counts_skipped_batch_items_as_completed_semantics_only():
    ...
```

Test expectations:

- `GET /progress/overview` returns:
  - `summary`
  - `tasks.active`
  - `tasks.recent_terminal`
  - `batches.active`
  - `batches.recent_terminal`
- overview includes persisted titles/platforms/timestamps
- `SKIPPED` is not a top-level status bucket

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_progress_overview.py -q`

Expected: FAIL because the endpoint does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- query helpers that gather:
  - active single tasks
  - recent terminal single tasks
  - active batches
  - recent terminal batches
- `GET /progress/overview`
- task aggregation from:
  - status files
  - result files
  - in-memory batch state plus persisted batch JSON
- grouping rule:
  - active = all non-terminal tasks/batches
  - recent terminal = latest 20 terminal tasks/batches
- summary rule:
  - `pending`
  - `running`
  - `cancelling`
  - `success`
  - `failed`
  - `cancelled`

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_progress_overview.py -q
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/progress_state.py backend/app/services/progress_query.py backend/app/routers/note.py backend/app/routers/batch.py backend/tests/test_progress_overview.py
git commit -m "feat: add progress overview endpoint"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 6: Extend Frontend Services and Shared Task Types

**Files:**
- Modify: `BillNote_frontend/src/services/note.ts`
- Modify: `BillNote_frontend/src/store/taskStore/index.ts`
- Test: `BillNote_frontend/src/services/note.ts` (type-level validation via build)

- [ ] **Step 1: Write the failing type or usage target**

Document the new frontend shapes in code first:

```ts
export type TaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLING'
  | 'CANCELLED'
```

And service signatures:

```ts
export const cancelTask = async (taskId: string) => ...
export const cancelBatch = async (batchId: string) => ...
export const getProgressOverview = async () => ...
```

- [ ] **Step 2: Run build to verify the current code fails or lacks the new contracts**

Run: `pnpm build`

Expected: FAIL after introducing references to the new contracts or missing consumers.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- service methods for:
  - `cancelTask`
  - `cancelBatch`
  - `getProgressOverview`
- expand `TaskStatus`
- store helpers for:
  - terminal state recognition including `CANCELLED`
  - syncing active progress metadata into local tasks without breaking history

- [ ] **Step 4: Run build to verify it passes**

Run:

```bash
pnpm exec eslint src/services/note.ts src/store/taskStore/index.ts
pnpm build
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/services/note.ts BillNote_frontend/src/store/taskStore/index.ts
git commit -m "feat: add task progress service contracts"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 7: Add the Task Progress Page and Route

**Files:**
- Create: `BillNote_frontend/src/pages/TaskProgressPage/TaskProgressPage.tsx`
- Create: `BillNote_frontend/src/pages/TaskProgressPage/components/TaskOverviewBar.tsx`
- Create: `BillNote_frontend/src/pages/TaskProgressPage/components/TaskProgressCard.tsx`
- Create: `BillNote_frontend/src/pages/TaskProgressPage/components/BatchProgressCard.tsx`
- Create: `BillNote_frontend/src/pages/TaskProgressPage/components/BatchProgressDetails.tsx`
- Modify: `BillNote_frontend/src/App.tsx`
- Modify: `BillNote_frontend/src/layouts/RootLayout.tsx`
- Modify: `BillNote_frontend/src/layouts/HomeLayout.tsx` (only if the nav entry belongs here)
- Create: `BillNote_frontend/src/pages/TaskProgressPage/TaskProgressPage.test.tsx` (or colocated equivalent if test infra exists)

- [ ] **Step 1: Write the failing UI target**

Add real failing behavior tests or, if no frontend test runner exists, create an executable verification harness before production code changes. Preferred test cases:

```tsx
it('renders summary buckets from overview data', ...)
it('shows active tasks by default and can filter to active only', ...)
it('expands a batch card to reveal child items', ...)
```

- [ ] **Step 2: Run build to verify it fails**

Run one of:

```bash
pnpm test TaskProgressPage
# or, if no frontend test runner exists:
pnpm build
```

Expected: FAIL because the new route or behavior under test does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- a dedicated `任务进度` page
- top summary bar with six buckets:
  - 排队中
  - 进行中
  - 正在停止
  - 已完成
  - 已失败
  - 已取消
- default list sections:
  - active tasks
  - recent terminal tasks
- lightweight filter:
  - `只看活跃任务`
- batch cards with expand/collapse behavior

Keep the visual language consistent with the existing calm dashboard style already used on the homepage.

- [ ] **Step 4: Run verification**

Run:

```bash
pnpm exec eslint src/pages/TaskProgressPage src/App.tsx src/layouts/RootLayout.tsx src/layouts/HomeLayout.tsx
pnpm build
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/pages/TaskProgressPage BillNote_frontend/src/App.tsx BillNote_frontend/src/layouts/RootLayout.tsx BillNote_frontend/src/layouts/HomeLayout.tsx
git commit -m "feat: add task progress page"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 8: Wire Polling, Cancel Actions, and Cross-Page Consistency

**Files:**
- Modify: `BillNote_frontend/src/hooks/useTaskPolling.ts`
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteHistory.tsx`
- Modify: `BillNote_frontend/src/pages/HomePage/Home.tsx`
- Modify: `BillNote_frontend/src/pages/TaskProgressPage/TaskProgressPage.tsx`
- Modify: `BillNote_frontend/src/pages/TaskProgressPage/components/TaskProgressCard.tsx`
- Modify: `BillNote_frontend/src/pages/TaskProgressPage/components/BatchProgressCard.tsx`
- Modify: `BillNote_frontend/src/store/taskStore/index.ts`

- [ ] **Step 1: Write the failing behavior target**

Add real failing tests or an executable verification harness for:

- homepage should treat `CANCELLED` as terminal
- progress page cancel button should flip to `正在停止`
- cancelled tasks should stop being polled as active
- progress page action buttons should reuse existing result-opening behavior
- current batch child should not appear as a duplicated “active task” card if the UX chooses deduplication

- [ ] **Step 2: Run targeted lint/build to confirm the old behavior still exists**

Run:

```bash
pnpm exec eslint src/hooks/useTaskPolling.ts src/pages/HomePage/components/NoteForm.tsx src/pages/HomePage/components/NoteHistory.tsx src/pages/HomePage/Home.tsx src/pages/TaskProgressPage src/store/taskStore/index.ts
```

Expected: Current code still lacks cancel-aware behavior and/or the new tests fail.

- [ ] **Step 3: Write the minimal implementation**

Implement:

- `useTaskPolling` recognizes:
  - `CANCELLING`
  - `CANCELLED`
- homepage loading state treats `CANCELLED` as terminal
- note history badges render `已取消` and `正在停止`
- batch cards or homepage batch panels can surface stop actions without breaking existing batch preview behavior

- [ ] **Step 4: Run verification**

Run:

```bash
pnpm exec eslint src/hooks/useTaskPolling.ts src/pages/HomePage/components/NoteForm.tsx src/pages/HomePage/components/NoteHistory.tsx src/pages/HomePage/Home.tsx src/pages/TaskProgressPage src/store/taskStore/index.ts
pnpm build
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/hooks/useTaskPolling.ts BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx BillNote_frontend/src/pages/HomePage/components/NoteHistory.tsx BillNote_frontend/src/pages/HomePage/Home.tsx BillNote_frontend/src/pages/TaskProgressPage BillNote_frontend/src/store/taskStore/index.ts
git commit -m "feat: make task UI cancel-aware"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.

### Task 9: End-to-End Verification

**Files:**
- No new files.

- [ ] **Step 1: Restart backend and frontend if needed**

Run the existing local services or restart them if they are stale.

- [ ] **Step 2: Verify backend behavior**

Run:

```bash
curl -s http://127.0.0.1:8483/api/progress/overview
curl -s -X POST http://127.0.0.1:8483/api/cancel_task -H 'Content-Type: application/json' -d '{"task_id":"..."}'
curl -s -X POST http://127.0.0.1:8483/api/batch/cancel -H 'Content-Type: application/json' -d '{"batch_id":"..."}'
```

Expected:

- overview returns the grouped payload
- cancel routes return success envelopes

- [ ] **Step 3: Verify frontend behavior**

Check in a browser:

- `任务进度` route loads
- active task cards show stage labels
- batch cards expand and show child items
- cancelling a single task moves it through `正在停止` -> `已取消`
- stopping a batch prevents later children from starting
- homepage and history no longer treat cancelled items as running
- refreshing the progress page still shows active tasks and recent terminal items from `/progress/overview`
- cancelling an already-completed task is idempotent and does not break the page
- cancelling an already-cancelled batch is idempotent and leaves the page stable

- [ ] **Step 4: Run final automated verification**

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
python3 -m py_compile backend/app/routers/note.py backend/app/routers/batch.py backend/app/services/note.py
pnpm exec eslint src
pnpm build
```

Expected:

- backend tests pass
- py_compile passes
- targeted frontend lint/build pass

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add task progress management"
```

If this workspace is not a git repository, skip the commit and note that in the handoff.
