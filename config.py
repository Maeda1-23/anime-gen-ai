# 設定モジュール（互換性ラッパー）
# 実装は prompt_auto_improvement.config に移動しました

from prompt_auto_improvement.config import (
    SystemConfig,
    AppConfig,
    load_config,
    load_or_create_config,
)
from prompt_auto_improvement.imggen.comfyui import (
    ComfyUIConfig,
    create_default_comfyui_config,
    create_custom_comfyui_config,
)

__all__ = [
    "SystemConfig",
    "AppConfig",
    "load_config",
    "load_or_create_config",
    "ComfyUIConfig",
    "create_default_comfyui_config",
    "create_custom_comfyui_config",
]
