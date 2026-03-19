# 画像生成器パッケージ

from .base import ImageGenerator
from .comfyui import ComfyUIGenerator, ComfyUIConfig

__all__ = ["ImageGenerator", "ComfyUIGenerator", "ComfyUIConfig", "create_imggen"]


def create_imggen(provider: str, **kwargs) -> ImageGenerator:
    """プロバイダ名から画像生成器を生成するファクトリ関数

    Args:
        provider: プロバイダ名（"comfyui"）
        **kwargs: プロバイダ固有のパラメータ

    Returns:
        ImageGeneratorインスタンス

    Raises:
        ValueError: 未対応のプロバイダ
    """
    if provider == "comfyui":
        config = kwargs.get("config")
        return ComfyUIGenerator(config)
    else:
        raise ValueError(
            f"未対応の画像生成プロバイダ: {provider}（対応: comfyui）"
        )
