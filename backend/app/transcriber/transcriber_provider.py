import os
import platform
from enum import Enum
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

class TranscriberType(str, Enum):
    FAST_WHISPER = "fast-whisper"
    MLX_WHISPER = "mlx-whisper"
    BCUT = "bcut"
    KUAISHOU = "kuaishou"
    GROQ = "groq"

MLX_WHISPER_AVAILABLE = False
_MLX_WHISPER_CHECKED = False

logger.info('初始化转录服务提供器')

_TRANSCRIBER_TYPES = (
    TranscriberType.FAST_WHISPER,
    TranscriberType.MLX_WHISPER,
    TranscriberType.BCUT,
    TranscriberType.KUAISHOU,
    TranscriberType.GROQ,
)

# 转录器单例缓存。保留旧全局名，值从“按类型一个实例”扩展为“按构造参数缓存”。
_transcribers: dict[TranscriberType, dict[tuple, Any]] = {key: {} for key in _TRANSCRIBER_TYPES}


def _cache_key(args: tuple, kwargs: dict) -> tuple:
    return args, tuple(sorted(kwargs.items()))


def _transcriber_cache_for(key: TranscriberType) -> dict[tuple, Any]:
    cache = _transcribers.setdefault(key, {})
    if cache is None:
        cache = {}
        _transcribers[key] = cache
    elif not isinstance(cache, dict):
        cache = {_cache_key((), {}): cache}
        _transcribers[key] = cache
    return cache


def is_mlx_whisper_available() -> bool:
    global MLX_WHISPER_AVAILABLE, _MLX_WHISPER_CHECKED
    if _MLX_WHISPER_CHECKED:
        return MLX_WHISPER_AVAILABLE

    if platform.system() != "Darwin":
        _MLX_WHISPER_CHECKED = True
        MLX_WHISPER_AVAILABLE = False
        return MLX_WHISPER_AVAILABLE

    try:
        import mlx_whisper  # noqa: F401
        MLX_WHISPER_AVAILABLE = True
        logger.info("MLX Whisper 可用")
    except ImportError:
        MLX_WHISPER_AVAILABLE = False
        logger.warning("MLX Whisper 导入失败，可能未安装 mlx_whisper")
    _MLX_WHISPER_CHECKED = True
    return MLX_WHISPER_AVAILABLE

# 公共实例初始化函数
def _init_transcriber(key: TranscriberType, cls, *args, **kwargs):
    typed_cache = _transcriber_cache_for(key)
    cache_key = _cache_key(args, kwargs)
    if cache_key not in typed_cache:
        logger.info(f'创建 {cls.__name__} 实例: {key}')
        try:
            typed_cache[cache_key] = cls(*args, **kwargs)
            logger.info(f'{cls.__name__} 创建成功')
        except Exception as e:
            logger.error(f"{cls.__name__} 创建失败: {e}")
            raise
    return typed_cache[cache_key]

# 各类型获取方法
def get_groq_transcriber():
    from app.transcriber.groq import GroqTranscriber

    return _init_transcriber(TranscriberType.GROQ, GroqTranscriber)

def get_whisper_transcriber(model_size="base", device="cuda"):
    from app.transcriber.whisper import WhisperTranscriber

    return _init_transcriber(TranscriberType.FAST_WHISPER, WhisperTranscriber, model_size=model_size, device=device)

def get_bcut_transcriber():
    from app.transcriber.bcut import BcutTranscriber

    return _init_transcriber(TranscriberType.BCUT, BcutTranscriber)

def get_kuaishou_transcriber():
    from app.transcriber.kuaishou import KuaishouTranscriber

    return _init_transcriber(TranscriberType.KUAISHOU, KuaishouTranscriber)

def get_mlx_whisper_transcriber(model_size="base"):
    if not is_mlx_whisper_available():
        logger.warning("MLX Whisper 不可用，请确保在 Apple 平台且已安装 mlx_whisper")
        raise ImportError("MLX Whisper 不可用")
    from app.transcriber.mlx_whisper_transcriber import MLXWhisperTranscriber

    return _init_transcriber(TranscriberType.MLX_WHISPER, MLXWhisperTranscriber, model_size=model_size)

# 通用入口
def get_transcriber(transcriber_type="fast-whisper", model_size="base", device="cuda"):
    """
    获取指定类型的转录器实例

    参数:
        transcriber_type: 支持 "fast-whisper", "mlx-whisper", "bcut", "kuaishou", "groq"
        model_size: 模型大小，适用于 whisper 类
        device: 设备类型（如 cuda / cpu），仅 whisper 使用

    返回:
        对应类型的转录器实例
    """
    logger.info(f'请求转录器类型: {transcriber_type}')

    try:
        transcriber_enum = TranscriberType(transcriber_type)
    except ValueError:
        logger.warning(f'未知转录器类型 "{transcriber_type}"，默认使用 fast-whisper')
        transcriber_enum = TranscriberType.FAST_WHISPER

    whisper_model_size = model_size or os.environ.get("WHISPER_MODEL_SIZE", "base")

    if transcriber_enum == TranscriberType.FAST_WHISPER:
        return get_whisper_transcriber(whisper_model_size, device=device)

    elif transcriber_enum == TranscriberType.MLX_WHISPER:
        if not is_mlx_whisper_available():
            raise RuntimeError(
                "MLX Whisper 不可用：需要 macOS 平台并安装 mlx_whisper 包 (pip install mlx_whisper)。"
                "请在「音频转写配置」页面切换到其他转写引擎。"
            )
        return get_mlx_whisper_transcriber(whisper_model_size)

    elif transcriber_enum == TranscriberType.BCUT:
        return get_bcut_transcriber()

    elif transcriber_enum == TranscriberType.KUAISHOU:
        return get_kuaishou_transcriber()

    elif transcriber_enum == TranscriberType.GROQ:
        return get_groq_transcriber()

    # fallback
    logger.warning(f'未识别转录器类型 "{transcriber_type}"，使用 fast-whisper 作为默认')
    return get_whisper_transcriber(whisper_model_size, device=device)
