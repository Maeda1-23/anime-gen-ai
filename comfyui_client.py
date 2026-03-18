# ComfyUIクライアント（互換性ラッパー）
# 実装は prompt_auto_improvement.imggen.comfyui に移動しました

from prompt_auto_improvement.imggen.comfyui import (
    ComfyUIConfig,
    ComfyUIGenerator as ComfyUIClient,
    create_default_comfyui_config,
    create_custom_comfyui_config,
)

__all__ = [
    "ComfyUIConfig",
    "ComfyUIClient",
    "create_default_comfyui_config",
    "create_custom_comfyui_config",
]
