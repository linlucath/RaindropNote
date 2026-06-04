import unittest
from types import SimpleNamespace

from app.enmus.note_enums import DownloadQuality
from app.services import batch_task_payloads


class TestBatchTaskPayloads(unittest.TestCase):
    def test_run_note_task_payload_preserves_single_task_options(self):
        payload = batch_task_payloads.build_run_note_task_payload(
            task_id="task-123",
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            link=True,
            screenshot=True,
            model_name="deepseek-chat",
            provider_id="provider-1",
            _format=["toc", "summary"],
            style="minimal",
            extras="保留关键时间点",
            video_understanding=True,
            video_interval=8,
            grid_size=[3, 2],
            mode="polished_transcript",
        )

        self.assertEqual(payload, {
            "task_id": "task-123",
            "video_url": "https://www.bilibili.com/video/BV123",
            "platform": "bilibili",
            "quality": DownloadQuality.fast,
            "link": True,
            "screenshot": True,
            "model_name": "deepseek-chat",
            "provider_id": "provider-1",
            "_format": ["toc", "summary"],
            "style": "minimal",
            "extras": "保留关键时间点",
            "video_understanding": True,
            "video_interval": 8,
            "grid_size": [3, 2],
            "mode": "polished_transcript",
        })

    def test_create_batch_payload_uses_supplied_platform_inference(self):
        request = SimpleNamespace(
            mode="polished_transcript",
            videos=[
                SimpleNamespace(
                    video_id="custom-1",
                    video_url="https://example.com/watch/custom-1",
                    title="自定义平台视频",
                    platform=None,
                )
            ],
        )

        payload = batch_task_payloads.create_batch_payload(
            batch_id="batch-custom",
            request=request,
            infer_platform=lambda _url: "custom-platform",
        )

        self.assertEqual(payload["source_label"], "未知来源")
        self.assertEqual(payload["items"][0]["platform"], "custom-platform")


if __name__ == "__main__":
    unittest.main()
