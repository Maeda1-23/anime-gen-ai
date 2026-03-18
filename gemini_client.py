# Gemini APIクライアント（互換性ラッパー）
# 実装は prompt_auto_improvement.vlm.gemini_api に移動しました

from prompt_auto_improvement.vlm.gemini_api import GeminiVLM as GeminiClient
from prompt_auto_improvement.utils import load_api_key

__all__ = ["GeminiClient", "load_api_key"]
