# VLMクライアントパッケージ

from .base import VLMClient
from .gemini_api import GeminiVLM

__all__ = ["VLMClient", "GeminiVLM", "create_vlm"]


def create_vlm(provider: str, **kwargs) -> VLMClient:
    """プロバイダ名からVLMクライアントを生成するファクトリ関数

    Args:
        provider: プロバイダ名（"gemini"）
        **kwargs: プロバイダ固有のパラメータ

    Returns:
        VLMClientインスタンス

    Raises:
        ValueError: 未対応のプロバイダ
    """
    if provider == "gemini":
        api_key = kwargs.get("api_key")
        model_name = kwargs.get("model_name", "gemini-3.1-flash-lite-preview")
        if not api_key:
            raise ValueError("Gemini VLMにはapi_keyが必要です")
        return GeminiVLM(api_key=api_key, model_name=model_name)
    else:
        raise ValueError(
            f"未対応のVLMプロバイダ: {provider}（対応: gemini）"
        )
