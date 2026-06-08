# Video Download Mode Design

## Goal

Add a first-class video download mode to BiliNote so users can download an authorized Bilibili video as a local MP4 without generating a transcript or calling an LLM. The mode must allow choosing a target resolution.

## Current Context

BiliNote currently focuses on converting authorized media into polished transcripts. The backend already has:

- `yt-dlp` in `backend/requirements.txt`
- platform downloaders, including `BilibiliDownloader.download_video`
- Safari/Bilibili cookie support through existing cookie resolution helpers
- a task queue, status files, and frontend polling

The frontend currently submits only `polished_transcript` tasks. The backend route also rejects every generation mode except `polished_transcript`.

## Proposed UX

On the homepage single-video workflow, add a work mode selector:

- `生成文字稿`
- `下载视频`

When `下载视频` is selected:

- Keep the video URL and platform controls.
- Show a resolution selector with `最佳`, `4K`, `1080P`, `720P`, `480P`, and `360P`.
- Do not require a model selection.
- Submit a normal task and reuse existing task polling.
- On success, show the downloaded MP4 file path and a download/open action where the existing frontend result surface supports it.

Batch creator and followed-dynamics flows stay transcript-only in the first version.

## Backend Design

Add a new generation mode:

- `video_download`

The existing default remains:

- `polished_transcript`

Add a request field:

- `video_resolution`: optional string, default `best`

Allowed resolution values:

- `best`
- `2160`
- `1080`
- `720`
- `480`
- `360`

The route should accept both modes. For `video_download`, the background task should:

1. Resolve the platform.
2. Get the existing downloader.
3. Update status to `DOWNLOADING`.
4. Download only video to the normal data/download directory.
5. Save a task result JSON with mode `video_download`.
6. Mark the task as `SUCCESS`.

It must skip:

- platform subtitle lookup
- audio extraction
- transcription
- LLM polishing or summarization

The saved result should include enough metadata for history and display:

```json
{
  "mode": "video_download",
  "markdown": "",
  "transcript": null,
  "audio_meta": {
    "file_path": "",
    "title": "Video title",
    "duration": 167.8,
    "cover_url": "...",
    "platform": "bilibili",
    "video_id": "BV...",
    "raw_info": {},
    "video_path": "/absolute/path/to/BV....mp4"
  },
  "video_download": {
    "file_path": "/absolute/path/to/BV....mp4",
    "resolution": "2160",
    "filename": "BV....mp4"
  }
}
```

## Downloader Design

Extend Bilibili video download options to accept a target resolution.

Recommended format mapping:

- `best`: best MP4-compatible video plus best audio, merged as MP4
- `2160`: best video with height <= 2160 plus best audio
- `1080`: best video with height <= 1080 plus best audio
- `720`: best video with height <= 720 plus best audio
- `480`: best video with height <= 480 plus best audio
- `360`: best video with height <= 360 plus best audio

The implementation should prefer MP4/H.264-compatible outputs where possible and use `merge_output_format='mp4'`.

## Frontend Design

Update the note service type:

- `GenerationMode = 'polished_transcript' | 'video_download'`

Update homepage form state:

- Add `task_mode`, default `polished_transcript`.
- Add `video_resolution`, default `best`.

Submission behavior:

- If `task_mode === 'video_download'`, send `mode: 'video_download'` and `video_resolution`.
- Do not require model settings for video download.
- Button text changes to `下载视频`.
- Current batch flows keep sending `polished_transcript`.

Task reuse must include `mode` and `video_resolution` so changing resolution creates or retries the correct task rather than reusing a transcript task.

## Error Handling

- Unsupported mode returns a route validation error.
- Unsupported resolution returns a route validation error.
- Downloader failures use the existing failed-task status path.
- If the merged MP4 is missing after `yt-dlp` completes, fail the task with a clear message.

## Testing

Backend tests:

- mode normalization accepts `polished_transcript` and `video_download`
- unsupported mode is rejected
- resolution validation accepts allowed values and rejects unknown values
- video download mode does not call subtitle, transcription, or GPT paths
- Bilibili `yt-dlp` options include the expected format selector for each resolution
- saved video-download result is recognized as a task result

Frontend tests:

- `GenerationMode` includes `video_download`
- NoteForm contains the mode selector and resolution selector
- video download submit path does not require model settings
- task reuse compares mode and resolution

## Non-Goals

- No batch video download in the first version.
- No DRM, paywall, region-lock, or platform restriction bypass.
- No public redistribution workflow.
- No new downloader dependency beyond existing `yt-dlp` and `ffmpeg`.
