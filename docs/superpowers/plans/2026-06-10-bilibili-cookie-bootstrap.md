# Bilibili Cookie Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add silent local Bilibili cookie auto-discovery at backend startup, plus save-time parsing and validation for pasted Bilibili cookie content.

**Architecture:** Keep persistence in `CookieConfigManager`, add focused backend services for parsing, validation, and startup bootstrap, then thread those services through the existing config router and FastAPI lifespan hook. Preserve the current settings page shape while upgrading the Bilibili textarea UX and routing all pasted content through backend extraction and validation.

**Tech Stack:** FastAPI, pytest, requests, browser-cookie3, React, react-hook-form, shadcn/ui

---

### Task 1: Add backend tests for cookie parsing and validation helpers

**Files:**
- Create: `backend/tests/test_bilibili_cookie_parser.py`
- Modify: `backend/tests/test_bilibili_api_client.py`
- Create: `backend/app/services/bilibili_cookie_parser.py`
- Modify: `backend/app/services/bilibili_api_client.py`

- [ ] **Step 1: Write the failing parser tests**

Add tests that assert:
- raw cookie input is returned as a normalized cookie string
- `Cookie:` header input extracts the cookie value
- `curl` input extracts the cookie value
- missing cookie content raises a `ValueError`

- [ ] **Step 2: Run parser tests to verify they fail**

Run: `cd backend && pytest tests/test_bilibili_cookie_parser.py -v`
Expected: FAIL because `bilibili_cookie_parser.py` does not exist yet.

- [ ] **Step 3: Write the failing validator test**

Add a new `BilibiliApiClient` test that verifies a lightweight login-state validator rejects cookies missing `SESSDATA` or `DedeUserID`.

- [ ] **Step 4: Run the focused API client test to verify it fails**

Run: `cd backend && pytest tests/test_bilibili_api_client.py -k validator -v`
Expected: FAIL because the validator helper does not exist yet.

- [ ] **Step 5: Implement minimal parser and validator support**

Create `backend/app/services/bilibili_cookie_parser.py` with:
- extraction from raw cookie text
- extraction from `Cookie:` lines
- extraction from `curl -H/--header` snippets
- normalization helper that returns `key=value; key2=value2`

Extend `backend/app/services/bilibili_api_client.py` with:
- required-key validation for `SESSDATA` and `DedeUserID`
- a lightweight `validate_cookie` helper that hits `/x/web-interface/nav`

- [ ] **Step 6: Run the focused backend tests to verify they pass**

Run: `cd backend && pytest tests/test_bilibili_cookie_parser.py tests/test_bilibili_api_client.py -v`
Expected: PASS

### Task 2: Add startup bootstrap service with browser auto-discovery

**Files:**
- Create: `backend/app/services/bilibili_cookie_bootstrap.py`
- Create: `backend/tests/test_bilibili_cookie_bootstrap.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Write the failing bootstrap tests**

Add tests that assert:
- bootstrap skips when a cookie already exists
- browser order is OS-specific
- bootstrap saves the first validated cookie
- bootstrap ignores browser read and validation failures

- [ ] **Step 2: Run bootstrap tests to verify they fail**

Run: `cd backend && pytest tests/test_bilibili_cookie_bootstrap.py -v`
Expected: FAIL because bootstrap service does not exist yet.

- [ ] **Step 3: Implement the minimal bootstrap service**

Create `backend/app/services/bilibili_cookie_bootstrap.py` with:
- browser order helper
- browser-cookie reader adapter
- cookie candidate builder for `.bilibili.com`
- best-effort bootstrap runner that validates then saves

Add `browser-cookie3` to `backend/requirements.txt`.

- [ ] **Step 4: Wire startup bootstrap into FastAPI lifespan**

Update `backend/main.py` so startup:
- checks whether a Bilibili cookie already exists
- schedules bootstrap in a non-blocking background thread
- logs failures without raising

- [ ] **Step 5: Run bootstrap tests to verify they pass**

Run: `cd backend && pytest tests/test_bilibili_cookie_bootstrap.py -v`
Expected: PASS

### Task 3: Route manual Bilibili saves through parsing and validation

**Files:**
- Modify: `backend/app/routers/config.py`
- Create: `backend/tests/test_config_router.py`

- [ ] **Step 1: Write the failing config router tests**

Add tests that assert:
- `POST /api/update_downloader_cookie` for `bilibili` extracts and validates before saving
- invalid Bilibili pasted input returns a business error and does not save
- non-Bilibili platforms preserve current save behavior

- [ ] **Step 2: Run the config router tests to verify they fail**

Run: `cd backend && pytest tests/test_config_router.py -v`
Expected: FAIL because the route still saves raw input directly.

- [ ] **Step 3: Implement the minimal router changes**

Update `backend/app/routers/config.py` so:
- `platform == 'bilibili'` uses parser + validator before saving
- other platforms keep trimmed direct saves
- business errors return existing response wrapper format

- [ ] **Step 4: Run the route tests to verify they pass**

Run: `cd backend && pytest tests/test_config_router.py -v`
Expected: PASS

### Task 4: Upgrade the downloader settings form for Bilibili paste UX

**Files:**
- Modify: `BillNote_frontend/src/components/Form/DownloaderForm/Form.tsx`
- Create: `BillNote_frontend/src/components/Form/DownloaderForm/downloaderFormCookieUx.test.js`

- [ ] **Step 1: Write the failing frontend source-level test**

Add a test that asserts:
- the downloader form uses `Textarea`
- Bilibili helper copy mentions raw cookie, `Cookie:` header, and `curl`

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd BillNote_frontend && pnpm test downloaderFormCookieUx.test.js`
Expected: FAIL because the form still uses `Input`.

- [ ] **Step 3: Implement the minimal frontend changes**

Update `Form.tsx` to:
- replace `Input` with `Textarea`
- keep the same save flow and API contract
- render helper text only for `bilibili`

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `cd BillNote_frontend && pnpm test downloaderFormCookieUx.test.js`
Expected: PASS

### Task 5: Run focused regression verification and commit feature work

**Files:**
- Modify: `docs/superpowers/plans/2026-06-10-bilibili-cookie-bootstrap.md`

- [ ] **Step 1: Run the focused backend regression suite**

Run: `cd backend && pytest tests/test_bilibili_cookie_parser.py tests/test_bilibili_api_client.py tests/test_bilibili_cookie_bootstrap.py tests/test_config_router.py tests/test_youtube_downloader.py -v`
Expected: PASS

- [ ] **Step 2: Run the focused frontend regression suite**

Run: `cd BillNote_frontend && pnpm test downloaderFormCookieUx.test.js`
Expected: PASS

- [ ] **Step 3: Review the final diff**

Run: `git status --short && git diff --stat`
Expected: only intended feature files changed

- [ ] **Step 4: Commit the feature branch changes**

```bash
git add backend/app/services/bilibili_cookie_parser.py \
  backend/app/services/bilibili_cookie_bootstrap.py \
  backend/app/services/bilibili_api_client.py \
  backend/app/routers/config.py \
  backend/main.py \
  backend/requirements.txt \
  backend/tests/test_bilibili_cookie_parser.py \
  backend/tests/test_bilibili_cookie_bootstrap.py \
  backend/tests/test_config_router.py \
  backend/tests/test_bilibili_api_client.py \
  BillNote_frontend/src/components/Form/DownloaderForm/Form.tsx \
  BillNote_frontend/src/components/Form/DownloaderForm/downloaderFormCookieUx.test.js \
  docs/superpowers/plans/2026-06-10-bilibili-cookie-bootstrap.md
git commit -m "feat: bootstrap bilibili cookies locally"
```
