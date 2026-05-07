import enum


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    SUMMARIZING = "SUMMARIZING"
    FORMATTING = "FORMATTING"
    SAVING = "SAVING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

    @classmethod
    def description(cls, status):
        desc_map = {
            cls.PENDING: "排队中",
            cls.PARSING: "解析链接",
            cls.DOWNLOADING: "下载中",
            cls.TRANSCRIBING: "转写中",
            cls.SUMMARIZING: "总结中",
            cls.FORMATTING: "格式化中",
            cls.SAVING: "保存中",
            cls.CANCELLING: "正在停止",
            cls.CANCELLED: "已取消",
            cls.SUCCESS: "已完成",
            cls.FAILED: "失败",
        }
        return desc_map.get(status, "未知状态")
