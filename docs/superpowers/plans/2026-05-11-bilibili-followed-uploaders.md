# Bilibili 关注 UP 主选择与批量转换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `UP 主批量` 流程中新增“从 Bilibili Cookie 读取关注 UP 主列表并选择其视频批量转换”的能力。

**Architecture:** 后端新增一个轻量的 Bilibili 关注服务与对应路由，负责基于已保存的 cookie 拉取关注列表，并复用现有 `batch.py` 中的空间视频预览逻辑按 `mid` 获取视频列表。前端在现有 `NoteForm` 的 `UP 主批量` 模式中新增“手动输入主页 / 从关注列表选择”来源切换，拆出一个关注列表选择组件，复用当前视频勾选、批量提交、状态轮询逻辑。

**Tech Stack:** FastAPI, Pydantic, requests/HTTP client, yt-dlp, React 19, TypeScript, react-hook-form, shadcn/ui, Zustand, pnpm, pytest

---

## File Structure

### Backend

- Create: `backend/app/services/bilibili_follow_service.py`
  - 负责读取 bilibili cookie、请求关注列表接口、标准化关注数据、映射常见错误。
- Create: `backend/app/routers/bilibili.py`
  - 暴露 `/bilibili/followings` 与 `/bilibili/uploader_videos`。
- Modify: `backend/main.py`
  - 注册新 router。
- Modify: `backend/app/routers/batch.py`
  - 提取或复用现有 `preview_bilibili_space` 能力，新增一个 `mid -> space_url` 的公共入口。
- Optional Modify: `backend/app/routers/config.py`
  - 如果要补 `cookie_status`，放在这里或新 router 内处理。
- Create: `backend/tests/test_bilibili_router.py`
  - 覆盖关注列表与按 `mid` 拉视频列表的路由行为。
- Optional Create: `backend/tests/test_bilibili_follow_service.py`
  - 如果服务逻辑较多，单独测试服务层标准化与错误映射。

### Frontend

- Modify: `BillNote_frontend/src/services/downloader.ts`
  - 继续复用 cookie 查询，必要时补 cookie 状态工具函数。
- Modify: `BillNote_frontend/src/services/note.ts`
  - 新增关注列表与按 `mid` 拉视频的 API 封装与类型。
- Create: `BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx`
  - 负责关注列表拉取、搜索、分页、选择 UP 主。
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
  - 新增来源模式、接入关注列表组件、复用现有视频预览区与提交逻辑。
- Optional Modify: `BillNote_frontend/src/types/index.d.ts`
  - 若团队习惯集中类型定义，可抽共用类型。

### Docs

- Already exists: `docs/superpowers/specs/2026-05-11-bilibili-followed-uploaders-design.md`
- This plan: `docs/superpowers/plans/2026-05-11-bilibili-followed-uploaders.md`

## Task 1: Add failing backend router tests for followings list

**Files:**
- Create: `backend/tests/test_bilibili_router.py`
- Reference: `backend/app/routers/config.py`
- Reference: `backend/tests/test_batch_router.py`

- [ ] **Step 1: Write the failing test for missing cookie**

```python
def test_followings_requires_bilibili_cookie(client, monkeypatch):
    monkeypatch.setattr("app.routers.bilibili.cookie_manager.get", lambda platform: "")

    response = client.get("/bilibili/followings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] != 200
    assert "Cookie" in payload["msg"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_bilibili_router.py::test_followings_requires_bilibili_cookie -v`

Expected: FAIL because `/bilibili/followings` route does not exist yet.

- [ ] **Step 3: Write the failing success-path test for followings pagination**

```python
def test_followings_returns_paginated_items(client, monkeypatch):
    monkeypatch.setattr("app.routers.bilibili.cookie_manager.get", lambda platform: "SESSDATA=abc")

    class FakeService:
        def get_followings(self, page, page_size, keyword):
            return {
                "items": [{"mid": "1", "name": "测试UP", "face": "https://img", "sign": "hello"}],
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "total": 1,
            }

    monkeypatch.setattr("app.routers.bilibili.follow_service", FakeService())

    response = client.get("/bilibili/followings?page=2&page_size=10&keyword=test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["items"][0]["mid"] == "1"
    assert payload["data"]["page"] == 2
    assert payload["data"]["page_size"] == 10
```

- [ ] **Step 4: Run both tests to verify they fail for the expected reason**

Run: `cd backend && pytest tests/test_bilibili_router.py -k followings -v`

Expected: FAIL because module/router/service symbols are not implemented yet.

- [ ] **Step 5: Commit the red tests**

```bash
git add backend/tests/test_bilibili_router.py
git commit -m "test: add bilibili followings router coverage"
```

## Task 2: Add failing backend router tests for uploader videos by mid

**Files:**
- Modify: `backend/tests/test_bilibili_router.py`
- Reference: `backend/app/routers/batch.py`

- [ ] **Step 1: Write the failing test for `mid`-based video preview**

```python
def test_uploader_videos_returns_normalized_batch_videos(client, monkeypatch):
    def fake_preview(space_url, limit):
        assert space_url == "https://space.bilibili.com/558268687/upload/video"
        assert limit == 20
        return [{"video_id": "BV1xx", "video_url": "https://www.bilibili.com/video/BV1xx", "title": "视频1"}]

    monkeypatch.setattr("app.routers.bilibili.preview_bilibili_space", fake_preview)

    response = client.get("/bilibili/uploader_videos?mid=558268687&limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["video_id"] == "BV1xx"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_bilibili_router.py::test_uploader_videos_returns_normalized_batch_videos -v`

Expected: FAIL because route does not exist yet.

- [ ] **Step 3: Write the failing validation test for missing `mid`**

```python
def test_uploader_videos_requires_mid(client):
    response = client.get("/bilibili/uploader_videos")
    assert response.status_code in {400, 422}
```

- [ ] **Step 4: Run the uploader video tests**

Run: `cd backend && pytest tests/test_bilibili_router.py -k uploader_videos -v`

Expected: FAIL with missing route failures, not with syntax errors.

- [ ] **Step 5: Commit the red tests**

```bash
git add backend/tests/test_bilibili_router.py
git commit -m "test: cover bilibili uploader video preview route"
```

## Task 3: Implement the backend follow service minimally

**Files:**
- Create: `backend/app/services/bilibili_follow_service.py`
- Reference: `backend/app/services/cookie_manager.py`

- [ ] **Step 1: Write the minimal service skeleton**

```python
class BilibiliFollowService:
    def __init__(self, cookie_getter):
        self.cookie_getter = cookie_getter

    def get_followings(self, page: int, page_size: int, keyword: str | None = None) -> dict:
        raise NotImplementedError
```

- [ ] **Step 2: Implement minimal request helpers and cookie guards**

```python
def _get_cookie(self) -> str:
    cookie = (self.cookie_getter("bilibili") or "").strip()
    if not cookie:
        raise ValueError("请先在设置页填写 Bilibili Cookie")
    return cookie
```

- [ ] **Step 3: Implement response normalization for followings**

```python
def _normalize_following_item(item: dict) -> dict:
    return {
        "mid": str(item.get("mid") or ""),
        "name": item.get("uname") or item.get("name") or "",
        "face": item.get("face") or "",
        "sign": item.get("sign") or "",
    }
```

- [ ] **Step 4: Implement the minimal `get_followings` success path**

Notes:
- Prefer `requests.get(...)` with explicit `User-Agent`, `Referer`, `Origin`, and raw `Cookie`.
- Keep first implementation small.
- If remote API returns a `code` indicating unauthenticated or invalid cookie, raise `ValueError("Bilibili Cookie 已失效，请重新更新")`.
- If `keyword` exists and upstream API does not support it, filter the normalized page items by `name`.

- [ ] **Step 5: Add focused service tests if router tests alone are too weak**

Run: `cd backend && pytest tests/test_bilibili_router.py -k followings -v`

Expected: Still FAIL or partially PASS until router is wired, but failures should now point to missing router integration rather than missing service behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/bilibili_follow_service.py backend/tests/test_bilibili_router.py
git commit -m "feat: add bilibili follow service"
```

## Task 4: Implement backend bilibili router and register it

**Files:**
- Create: `backend/app/routers/bilibili.py`
- Modify: `backend/main.py`
- Reference: `backend/app/utils/response.py`

- [ ] **Step 1: Create the route module with request models / query params**

Endpoints:
- `GET /bilibili/followings`
- `GET /bilibili/uploader_videos`

- [ ] **Step 2: Implement `followings` route with business error handling**

```python
@router.get("/bilibili/followings")
def get_followings(page: int = 1, page_size: int = 20, keyword: str | None = None):
    try:
        data = follow_service.get_followings(page=page, page_size=page_size, keyword=keyword)
    except ValueError as exc:
        return R.error(msg=str(exc))
    return R.success(data=data)
```

- [ ] **Step 3: Implement `uploader_videos` route by composing `mid -> space_url`**

```python
@router.get("/bilibili/uploader_videos")
def get_uploader_videos(mid: str, limit: int = 20):
    space_url = f"https://space.bilibili.com/{mid}/upload/video"
    videos = preview_bilibili_space(space_url, limit)
    return R.success(data=videos)
```

- [ ] **Step 4: Register the router in `backend/main.py`**

Run: `cd backend && pytest tests/test_bilibili_router.py -v`

Expected: PASS for new bilibili router tests, or narrow remaining failures only.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/bilibili.py backend/main.py backend/tests/test_bilibili_router.py
git commit -m "feat: add bilibili followings and uploader routes"
```

## Task 5: Refine backend preview reuse and validation

**Files:**
- Modify: `backend/app/routers/batch.py`
- Modify: `backend/app/routers/bilibili.py`
- Test: `backend/tests/test_batch_router.py`
- Test: `backend/tests/test_bilibili_router.py`

- [ ] **Step 1: Write a failing test for any shared helper you extract**

If extracting helper:

```python
def test_space_url_from_mid():
    assert uploader_space_url("558268687") == "https://space.bilibili.com/558268687/upload/video"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_bilibili_router.py -k space_url -v`

- [ ] **Step 3: Extract only the minimal reusable helper**

Options:
- Keep helper inside `bilibili.py` if no reuse is needed
- Extract to `batch.py` only if it simplifies existing logic

YAGNI note:
- Do not restructure `batch.py` broadly.
- Only extract a helper if two routes need identical logic.

- [ ] **Step 4: Run all related backend tests**

Run: `cd backend && pytest tests/test_bilibili_router.py tests/test_batch_router.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/batch.py backend/app/routers/bilibili.py backend/tests/test_bilibili_router.py backend/tests/test_batch_router.py
git commit -m "refactor: reuse bilibili uploader preview helpers"
```

## Task 6: Add failing frontend service and picker component tests or typed API contracts

**Files:**
- Modify: `BillNote_frontend/src/services/note.ts`
- Optional Create: `BillNote_frontend/src/pages/HomePage/components/__tests__/FollowingUploaderPicker.test.tsx`
- Reference: current frontend test setup if any

- [ ] **Step 1: Inspect whether frontend test tooling exists**

Run: `cd BillNote_frontend && cat package.json`

Expected: confirm whether test scripts exist. If not, keep verification at typecheck/lint/manual level and encode safety with small typed interfaces.

- [ ] **Step 2: Add the failing typed API shape or test for followings**

```ts
export interface FollowingUploader {
  mid: string
  name: string
  face: string
  sign: string
}
```

- [ ] **Step 3: Add API functions that intentionally fail compile or usage until wired**

```ts
export const getBilibiliFollowings = async (...) => request.get('/bilibili/followings', ...)
export const getBilibiliUploaderVideos = async (...) => request.get('/bilibili/uploader_videos', ...)
```

- [ ] **Step 4: Run lint or typecheck to surface integration gaps**

Run: `cd BillNote_frontend && pnpm lint`

Expected: FAIL only if newly added types/usages are incomplete.

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/services/note.ts
git commit -m "test: define bilibili following frontend contracts"
```

## Task 7: Implement the frontend following uploader picker component

**Files:**
- Create: `BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx`
- Modify: `BillNote_frontend/src/services/note.ts`

- [ ] **Step 1: Create a minimal presentational component**

Props should stay narrow:

```ts
interface FollowingUploaderPickerProps {
  enabled: boolean
  selectedMid?: string
  selectedName?: string
  onSelectUploader: (uploader: FollowingUploader) => void
}
```

- [ ] **Step 2: Implement minimal state and the first failing interaction**

State:
- `items`
- `loading`
- `keyword`
- `page`
- `hasMore`
- `error`

Behavior:
- Click “拉取关注列表” loads page 1
- Search resets pagination
- “加载更多” appends items
- Click item calls `onSelectUploader`

- [ ] **Step 3: Use existing shadcn/ui building blocks**

Prefer:
- `Button`
- `Input`
- `Avatar` if available, otherwise simple image block
- small cards / list rows

Keep UI intentionally simple in v1.

- [ ] **Step 4: Run lint to verify component compiles**

Run: `cd BillNote_frontend && pnpm lint`

Expected: PASS or narrow failures pointing to `NoteForm` integration still pending.

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx BillNote_frontend/src/services/note.ts
git commit -m "feat: add following uploader picker component"
```

## Task 8: Integrate following mode into NoteForm without breaking manual batch mode

**Files:**
- Modify: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- Create/Use: `BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx`
- Reference: `BillNote_frontend/src/pages/HomePage/components/BatchVideoPreview.tsx`

- [ ] **Step 1: Add failing form state changes for source mode**

Add:
- `uploader_source_mode: 'manual' | 'followings'`
- local state for selected uploader

Expected initial behavior:
- `UP 主批量` defaults to `manual`
- switching source mode clears stale preview state

- [ ] **Step 2: Run lint to verify the partial integration fails only where expected**

Run: `cd BillNote_frontend && pnpm lint`

Expected: FAIL due to incomplete JSX/state wiring, not syntax errors.

- [ ] **Step 3: Render the new source-mode switch inside batch mode**

UI rules:
- Manual mode shows current space URL input flow.
- Followings mode hides manual URL field and shows `FollowingUploaderPicker`.
- After picker selection, store `selected_uploader_mid` and `selected_uploader_name`.

- [ ] **Step 4: Wire “拉取该 UP 主视频” to existing preview state**

Implementation notes:
- When a following uploader is selected, call `getBilibiliUploaderVideos(mid, limit)`.
- Store results in existing `previewVideos`.
- Clear `selectedBatchVideoIds` before applying new preview results.
- Reuse `previewSignature` but include source mode and selected `mid`.

- [ ] **Step 5: Preserve existing submit behavior**

Submission rules:
- In manual mode, continue using current URL-based preview path.
- In followings mode, only allow submit after a selected uploader has produced a current, non-stale preview list.
- `startBatch` payload remains `videos: selectedPreviewVideos`.

- [ ] **Step 6: Run lint again**

Run: `cd BillNote_frontend && pnpm lint`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx BillNote_frontend/src/services/note.ts
git commit -m "feat: support selecting followed bilibili uploaders"
```

## Task 9: Add empty/error states and cookie guidance

**Files:**
- Modify: `BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx`
- Optional Modify: `BillNote_frontend/src/services/downloader.ts`

- [ ] **Step 1: Add explicit empty state for missing cookie**

Behavior:
- If `getDownloaderCookie('bilibili')` returns empty, show a small warning panel.
- Copy should clearly say to configure Bilibili Cookie in settings.

- [ ] **Step 2: Add empty state for zero followings**

Copy:
- “当前账号暂无可读取的关注 UP 主”

- [ ] **Step 3: Add retryable error state for invalid cookie or remote failures**

Behavior:
- Keep current list if pagination request fails after initial success.
- Show a retry action.

- [ ] **Step 4: Run lint**

Run: `cd BillNote_frontend && pnpm lint`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add BillNote_frontend/src/pages/HomePage/components/FollowingUploaderPicker.tsx BillNote_frontend/src/services/downloader.ts BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx
git commit -m "feat: add bilibili cookie guidance and empty states"
```

## Task 10: Verify the end-to-end behavior and regressions

**Files:**
- No code changes required unless bugs found

- [ ] **Step 1: Run backend targeted tests**

Run: `cd backend && pytest tests/test_bilibili_router.py tests/test_batch_router.py -v`

Expected: PASS

- [ ] **Step 2: Run frontend lint**

Run: `cd BillNote_frontend && pnpm lint`

Expected: PASS

- [ ] **Step 3: Run frontend production build**

Run: `cd BillNote_frontend && pnpm build`

Expected: PASS

- [ ] **Step 4: Manual verification checklist**

Verify:
- `UP 主批量` -> `手动输入主页` still works as before
- `UP 主批量` -> `从关注列表选择` can load followings
- Search and load-more both work
- Selecting a new uploader clears old selected videos
- Video preview and checkbox behavior still work
- Batch submit starts normal batch processing
- Missing cookie guidance appears correctly

- [ ] **Step 5: Final commit for any verification fixes**

```bash
git add -A
git commit -m "test: verify bilibili followed uploader batch flow"
```

## Notes for the implementer

- Keep `NoteForm.tsx` from growing further if you can avoid it. Prefer pushing followings-specific UI state into `FollowingUploaderPicker.tsx`.
- Do not rewrite the existing batch execution model. The safest path is to feed it the same `videos: BatchVideo[]` contract it already understands.
- Be strict about error strings returned to the UI. Users need to know the difference between “没配置 cookie” and “cookie 失效”.
- Reuse `preview_bilibili_space` where possible. Do not invent a second video-list parsing path unless the existing one fundamentally cannot support `mid`.
- If the real Bilibili API shape differs from assumptions, update the spec and this plan before widening implementation.
