# Bilibili Cookie Bootstrap Design

## Goal

Make local BiliNote installs feel frictionless for Bilibili-authenticated flows by:

- silently attempting to discover a usable local Bilibili cookie at backend startup when no cookie is already configured
- keeping the existing settings-page paste flow as the visible fallback
- parsing pasted content into a standard cookie string on the backend
- validating the cookie before saving it

The main audience is local desktop or local web users who run the backend on their own machine.

## Current Context

BiliNote currently supports Bilibili cookies through two backend paths:

- a saved raw cookie string managed by `CookieConfigManager`
- a `cookies.txt` file used by existing `yt-dlp` helpers

Relevant current code:

- `backend/app/services/cookie_manager.py`
- `backend/app/routers/config.py`
- `backend/app/services/bilibili_request.py`
- `backend/app/services/bilibili_api_client.py`
- `BillNote_frontend/src/components/Form/DownloaderForm/Form.tsx`

The current settings page is a minimal single-line input that stores whatever the user pastes. It does not extract cookies from `Cookie:` headers or `curl` snippets, and it does not validate the cookie before saving.

## User-Approved UX

### Automatic bootstrap

- The backend should attempt Bilibili cookie discovery automatically during local startup.
- This bootstrap only runs when no usable Bilibili cookie already exists through the current priority chain.
- The attempt must be silent and best-effort:
  - no startup failure
  - no toast
  - no user-facing error
  - only backend logs for debugging

### Manual fallback

- The settings page remains the visible recovery path.
- The page keeps the same overall structure and save action.
- The input area becomes larger so users can paste longer content comfortably.
- Users can paste:
  - a raw cookie string
  - a `Cookie: ...` header
  - a full `curl` command that contains a cookie header

### Save-time behavior

- The backend extracts the actual cookie string from the pasted content.
- The backend validates the extracted Bilibili cookie before saving.
- Invalid input returns a clear error instead of saving broken state.

## Non-Goals

- No new `cookies.txt` import UX.
- No user-facing browser picker.
- No startup popups, banners, or warnings when auto-discovery fails.
- No removal of existing backend `cookies.txt` compatibility in this iteration.
- No remote-server cookie discovery support. This feature targets local machines only.
- No generalized browser-cookie bootstrap for non-Bilibili platforms in this iteration.

## Proposed Architecture

Add one focused backend service for Bilibili cookie bootstrap and one focused backend parser/validator flow for manual saves.

Recommended new responsibilities:

- `BilibiliCookieBootstrapService`
  - decides whether startup discovery should run
  - tries supported local browsers in order
  - extracts `.bilibili.com` cookies
  - standardizes them into one raw cookie string
  - validates candidate cookies
  - persists the first valid one

- `bilibili_cookie_parser`
  - extracts a raw cookie string from free-form pasted text
  - normalizes whitespace and separators
  - parses required fields for validation-friendly checks

- `bilibili_cookie_validator`
  - validates a candidate cookie against a lightweight authenticated Bilibili API request
  - returns a normalized cookie string on success
  - raises actionable errors on failure

`CookieConfigManager` should remain a small persistence helper. It should not gain browser-reading or parsing logic.

## Browser Discovery Design

### Dependency choice

Use a local Python browser-cookie library with direct browser readers, rather than shelling out to browser-specific commands. `browser-cookie3` is a good fit because it supports `Chrome`, `Edge`, `Chromium`, `Brave`, and `Safari`, including `Windows` and `macOS`.

The browser integration should be wrapped behind a tiny adapter so the rest of the app is not coupled to the third-party API.

### Browser order

Use OS-specific discovery order:

- Windows:
  - `edge`
  - `chrome`
  - `chromium`
  - `brave`
- macOS:
  - `edge`
  - `chrome`
  - `chromium`
  - `brave`
  - `safari`

### Discovery rules

- Only attempt discovery for `bilibili`.
- Only attempt discovery if `cookie_manager.get('bilibili')` is empty.
- Never overwrite a non-empty configured cookie.
- Never overwrite an environment-provided cookie.
- For each browser:
  - read only local browser cookies
  - filter to `.bilibili.com` and `bilibili.com`
  - build a normalized raw cookie string
  - reject candidates that do not contain the required keys
  - validate the candidate before saving
- Stop on the first validated cookie.
- If all browsers fail, exit silently.

### Required cookie fields

The bootstrap should require:

- `SESSDATA`
- `DedeUserID`

When present, keep additional useful fields in the saved cookie:

- `bili_jct`
- `buvid3`
- `buvid4`
- `DedeUserID__ckMd5`

Other Bilibili cookie pairs may also be preserved if they belong to the selected domain set.

## Startup Behavior

Hook bootstrap into backend startup in a non-blocking way.

Recommended behavior:

- Keep the existing FastAPI `lifespan` entrypoint in `backend/main.py`.
- After existing initialization steps complete, schedule a best-effort background bootstrap task.
- The startup request path must not wait for browser discovery to finish.

Recommended implementation shape:

- startup code checks whether a Bilibili cookie already exists
- if not, it schedules the bootstrap in a background thread or `asyncio.to_thread`
- exceptions are caught inside the bootstrap task and logged at `info` or `warning`

This preserves fast local startup and matches the requirement that failure should stay silent for users.

## Manual Save Flow

Reuse the existing `POST /update_downloader_cookie` route shape so the frontend can stay almost unchanged.

### Request handling

- Keep the current request body fields:
  - `platform`
  - `cookie`
- Interpret `cookie` as free-form pasted content for `platform == 'bilibili'`.
- For non-Bilibili platforms, keep the current simple trimmed save behavior in this iteration.

### Extraction formats

For `bilibili`, support these input shapes:

1. Raw cookie string

```text
SESSDATA=...; DedeUserID=...; bili_jct=...
```

2. Full header line

```text
Cookie: SESSDATA=...; DedeUserID=...; bili_jct=...
```

3. `curl` command containing one or more cookie headers

```bash
curl 'https://api.bilibili.com/x/web-interface/nav' \
  -H 'Cookie: SESSDATA=...; DedeUserID=...'
```

### Save pipeline

For `platform == 'bilibili'`, saving should run this pipeline:

1. Extract raw cookie string from pasted input.
2. Normalize the cookie string.
3. Check required keys are present.
4. Validate it with a lightweight authenticated Bilibili API call.
5. Save the normalized cookie string through `CookieConfigManager`.
6. Return success.

If extraction or validation fails, do not save anything.

## Validation Design

Use a lightweight authenticated Bilibili API request before persisting either:

- an automatically discovered cookie
- a manually pasted cookie

The validation path should reuse the existing Bilibili request style and error mapping patterns already present in:

- `backend/app/services/bilibili_api_client.py`
- `backend/app/services/bilibili_follow_service.py`
- `backend/app/services/bilibili_uploader_video_service.py`

Recommended validation target:

- `https://api.bilibili.com/x/web-interface/nav`

Validation success means:

- HTTP request succeeds
- Bilibili response `code == 0`
- response contains a logged-in identity payload

Validation failure should surface distinct reasons when possible:

- no cookie could be extracted
- required keys missing
- cookie rejected by Bilibili
- browser cookies were unreadable

## Error Handling

### Startup auto-bootstrap

- Any browser read failure is swallowed and logged.
- Any validation failure is swallowed and logged.
- No frontend-visible error is produced.

### Manual save

Return clear business errors for:

- `未从输入内容中提取到 Bilibili Cookie`
- `Bilibili Cookie 缺少 SESSDATA`
- `Bilibili Cookie 缺少 DedeUserID`
- `Bilibili Cookie 已失效，请重新登录后更新`

If the input is syntactically present but malformed, prefer a parsing-specific error instead of a generic save failure.

## Frontend Design

Keep the existing settings page structure and API contract.

Changes to `BillNote_frontend/src/components/Form/DownloaderForm/Form.tsx`:

- replace the single-line input with a larger multiline text area
- keep the same save button and route behavior
- add short helper text for Bilibili explaining supported paste formats:
  - raw cookie
  - `Cookie:` header
  - `curl`

No extra UI is needed for:

- browser selection
- `cookies.txt` import
- startup bootstrap state

## Logging

Startup bootstrap should log enough detail for local debugging without exposing full cookie contents.

Recommended log content:

- whether bootstrap was skipped because a cookie already existed
- which browser source was attempted
- whether extraction failed, validation failed, or save succeeded

Do not log:

- raw cookie values
- full header strings

## Testing

### Backend tests

- bootstrap is skipped when a Bilibili cookie already exists
- startup bootstrap tries browsers in the expected OS-specific order
- bootstrap saves the first validated cookie and stops
- bootstrap ignores unreadable browser sources and validation failures
- parser extracts a raw cookie from:
  - raw cookie input
  - `Cookie:` header input
  - `curl` input
- parser rejects input with no cookie content
- validator rejects cookies missing `SESSDATA`
- validator rejects cookies missing `DedeUserID`
- manual save for `bilibili` validates before persisting
- manual save for non-Bilibili platforms preserves current behavior

### Frontend tests

- downloader settings form renders a multiline field
- Bilibili settings view shows helper text for supported paste formats
- form submit still posts `platform` and `cookie`
- existing success and failure toast behavior still works

## Rollout Notes

- This change should be safe for existing users because it does not override already saved cookies.
- Existing `cookies.txt` backend support can remain in place for download paths, but it is no longer part of the primary UX.
- If browser-cookie auto-discovery proves unreliable on some Windows setups, the manual paste flow remains the stable fallback with no UX redesign required.
