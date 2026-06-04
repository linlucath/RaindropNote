import os

from app.downloaders.bilibili_ytdlp_options import (
    DEFAULT_SUBTITLE_LANGS,
    build_audio_ydl_opts,
    build_subtitle_ydl_opts,
    build_video_ydl_opts,
)


def test_build_audio_ydl_opts_matches_current_download_defaults():
    output_path = os.path.join('/tmp/bili', '%(id)s.%(ext)s')

    opts = build_audio_ydl_opts(output_path, skip_download=False)

    assert opts == {
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
        'skip_download': False,
    }


def test_build_audio_ydl_opts_skip_download_keeps_metadata_only_behavior():
    output_path = os.path.join('/tmp/bili', '%(id)s.%(ext)s')

    opts = build_audio_ydl_opts(output_path, skip_download=True)

    assert opts == {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': output_path,
        'noplaylist': True,
        'quiet': True,
        'skip_download': True,
    }


def test_build_video_ydl_opts_matches_current_video_download_defaults():
    output_path = os.path.join('/tmp/bili', '%(id)s.%(ext)s')

    opts = build_video_ydl_opts(output_path)

    assert opts == {
        'format': 'bv*[ext=mp4]/bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'noplaylist': True,
        'quiet': False,
        'merge_output_format': 'mp4',
    }


def test_build_subtitle_ydl_opts_matches_current_subtitle_download_defaults():
    output_dir = '/tmp/bili'

    opts = build_subtitle_ydl_opts(
        output_dir=output_dir,
        video_id='BV1bDCrBrEUP',
        langs=['ai-zh', 'en'],
    )

    assert opts == {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['ai-zh', 'en'],
        'subtitlesformat': 'srt/json3/best',
        'skip_download': True,
        'noplaylist': True,
        'outtmpl': os.path.join(output_dir, 'BV1bDCrBrEUP.%(ext)s'),
        'quiet': True,
    }


def test_default_subtitle_langs_match_downloader_priority_order():
    assert list(DEFAULT_SUBTITLE_LANGS) == ['zh-Hans', 'zh', 'zh-CN', 'ai-zh', 'en', 'en-US']
