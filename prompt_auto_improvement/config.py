# 設定モジュール - TOML形式の設定ファイルを読み込む

import tomllib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

from .imggen.comfyui import ComfyUIConfig, create_default_comfyui_config


# --- データクラス定義 ---

@dataclass
class ExperimentConfig:
    """実験設定"""
    name: str = "default"
    slides_dir: Path = field(default_factory=lambda: Path("slide_images"))


@dataclass
class OutputConfig:
    """出力設定"""
    root_dir: Path = field(default_factory=lambda: Path("output"))


@dataclass
class LoopConfig:
    """ループ設定"""
    max_loops: int = 10
    images_per_loop: int = 3
    seed_policy: str = "random"
    master_seed: Optional[int] = None
    fixed_seeds: Optional[List[int]] = None


@dataclass
class ImageGeneratorConfig:
    """画像生成器設定"""
    provider: str = "comfyui"
    prompt_format: str = "tags"
    supports_negative_prompt: bool = True
    supports_seed: bool = True
    comfyui: ComfyUIConfig = field(default_factory=create_default_comfyui_config)


@dataclass
class VLMGeminiConfig:
    """Gemini VLM設定"""
    model: str = "gemini-3.1-flash-lite-preview"
    api_key_env: str = "GEMINI_API_KEY"


@dataclass
class VLMConfig:
    """VLM設定"""
    provider: str = "gemini"
    gemini: VLMGeminiConfig = field(default_factory=VLMGeminiConfig)


@dataclass
class AppConfig:
    """アプリケーション全体の設定"""
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    image_generator: ImageGeneratorConfig = field(default_factory=ImageGeneratorConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)

    def __post_init__(self):
        """初期化後の処理"""
        self.output.root_dir.mkdir(parents=True, exist_ok=True)
        print(f"設定を読み込みました（実験名: {self.experiment.name}）")
        print(f"出力ディレクトリ: {self.output.root_dir}")
        print(f"画像生成: {self.image_generator.provider}")
        print(f"VLM: {self.vlm.provider}")


# --- SystemConfig（後方互換性） ---

@dataclass
class SystemConfig:
    """システム全体の設定（後方互換性用）

    AppConfigから変換して使用できます。
    """
    output_dir: Path = field(default_factory=lambda: Path("output"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    comfyui_config: ComfyUIConfig = field(default_factory=create_default_comfyui_config)
    image_width: int = 1024
    image_height: int = 1024
    default_steps: int = 28
    default_cfg: float = 7.0
    default_sampler: str = "euler_ancestral"
    session_dir: Optional[Path] = None
    history_file: Optional[Path] = None

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_app_config(cls, app_config: AppConfig) -> 'SystemConfig':
        """AppConfigからSystemConfigを生成"""
        return cls(
            output_dir=app_config.output.root_dir,
            comfyui_config=app_config.image_generator.comfyui,
        )


# --- TOML読み込み ---

def _req(d: dict, key: str, section: str = ""):
    """必須フィールドを取得"""
    if key not in d:
        loc = f"[{section}]" if section else ""
        raise KeyError(f"設定ファイルに必須フィールド {loc}.{key} がありません")
    return d[key]


def load_config(config_path: Path) -> AppConfig:
    """TOML設定ファイルを読み込む

    Args:
        config_path: TOMLファイルのパス

    Returns:
        AppConfig オブジェクト
    """
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    # --- experiment ---
    exp_raw = raw.get("experiment", {})
    experiment = ExperimentConfig(
        name=exp_raw.get("name", "default"),
        slides_dir=Path(exp_raw.get("slides_dir", "slide_images")),
    )

    # --- output ---
    out_raw = raw.get("output", {})
    output = OutputConfig(
        root_dir=Path(out_raw.get("root_dir", "output")),
    )

    # --- loop ---
    loop_raw = raw.get("loop", {})
    loop = LoopConfig(
        max_loops=loop_raw.get("max_loops", 10),
        images_per_loop=loop_raw.get("images_per_loop", 3),
        seed_policy=loop_raw.get("seed_policy", "random"),
        master_seed=loop_raw.get("master_seed"),
        fixed_seeds=loop_raw.get("fixed_seeds"),
    )

    # --- image_generator ---
    ig_raw = raw.get("image_generator", {})
    provider = ig_raw.get("provider", "comfyui")
    prompt_format = ig_raw.get("prompt_format", "tags")
    supports_negative = ig_raw.get("supports_negative_prompt", True)
    supports_seed = ig_raw.get("supports_seed", True)

    comfyui_config = create_default_comfyui_config()
    if provider == "comfyui":
        comfy_raw = ig_raw.get("comfyui", {})
        comfyui_config = ComfyUIConfig(
            server_address=comfy_raw.get("server", comfyui_config.server_address),
            workflow_json_path=comfy_raw.get("workflow_json", comfyui_config.workflow_json_path),
            positive_prompt_node_id=comfy_raw.get("positive_prompt_node_id", comfyui_config.positive_prompt_node_id),
            negative_prompt_node_id=comfy_raw.get("negative_prompt_node_id", comfyui_config.negative_prompt_node_id),
            seed_node_id=comfy_raw.get("seed_node_id", comfyui_config.seed_node_id),
            output_node_id=comfy_raw.get("output_node_id", comfyui_config.output_node_id),
            timeout_sec=comfy_raw.get("timeout_sec", comfyui_config.timeout_sec),
        )

    image_generator = ImageGeneratorConfig(
        provider=provider,
        prompt_format=prompt_format,
        supports_negative_prompt=supports_negative,
        supports_seed=supports_seed,
        comfyui=comfyui_config,
    )

    # --- vlm ---
    vlm_raw = raw.get("vlm", {})
    vlm_provider = vlm_raw.get("provider", "gemini")

    gemini_vlm = VLMGeminiConfig()
    if vlm_provider == "gemini":
        gemini_raw = vlm_raw.get("gemini", {})
        gemini_vlm = VLMGeminiConfig(
            model=gemini_raw.get("model", gemini_vlm.model),
            api_key_env=gemini_raw.get("api_key_env", gemini_vlm.api_key_env),
        )

    vlm = VLMConfig(
        provider=vlm_provider,
        gemini=gemini_vlm,
    )

    return AppConfig(
        experiment=experiment,
        output=output,
        loop=loop,
        image_generator=image_generator,
        vlm=vlm,
    )


def load_or_create_config(config_path: Path = None) -> SystemConfig:
    """設定ファイルを読み込む（後方互換性用）

    TOML → JSON の順で探索します。
    """
    # TOMLを優先
    toml_path = config_path or Path("configs/default.toml")
    if toml_path.exists():
        try:
            app_config = load_config(toml_path)
            return SystemConfig.from_app_config(app_config)
        except Exception as e:
            print(f"TOML設定ファイルの読み込みに失敗しました: {e}")

    # JSONにフォールバック
    json_path = Path("config.json")
    if json_path.exists():
        try:
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)

            comfyui_config = create_default_comfyui_config()
            if "comfyui" in config_dict:
                comfy_dict = config_dict["comfyui"]
                comfyui_config.server_address = comfy_dict.get("server_address", comfyui_config.server_address)
                comfyui_config.workflow_json_path = comfy_dict.get("workflow_json_path", comfyui_config.workflow_json_path)

            config = SystemConfig(
                comfyui_config=comfyui_config,
                output_dir=Path(config_dict.get("output_dir", "output")),
            )
            print(f"JSON設定ファイルを読み込みました: {json_path}")
            return config
        except Exception as e:
            print(f"JSON設定ファイルの読み込みに失敗しました: {e}")

    # デフォルト設定
    print("デフォルト設定を使用します")
    return SystemConfig()
