import os
from collections.abc import Sequence

DEFAULT_SUBTITLE_LANGS = ('zh-Hans', 'zh', 'zh-CN', 'ai-zh', 'en', 'en-US')


def build_audio_ydl_opts(output_path: str, *, skip_download: bool) -> dict:
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64',
            }
        ],
        'noplaylist': True,
        'quiet': False,
        'skip_download': skip_download,
    }
    if skip_download:
        ydl_opts.pop('postprocessors', None)
        ydl_opts['quiet'] = True
    return ydl_opts


def build_video_ydl_opts(output_path: str) -> dict:
    return {
        'format': 'bv*[ext=mp4]/bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'noplaylist': True,
        'quiet': False,
        'merge_output_format': 'mp4',
    }


def build_subtitle_ydl_opts(
    *,
    output_dir: str,
    video_id: str,
    langs: Sequence[str],
) -> dict:
    return {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': list(langs),
        'subtitlesformat': 'srt/json3/best',
        'skip_download': True,
        'noplaylist': True,
        'outtmpl': os.path.join(output_dir, f'{video_id}.%(ext)s'),
        'quiet': True,
    }
