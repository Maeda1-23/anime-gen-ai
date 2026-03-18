# 設定モジュール
# システム全体の設定を管理するクラス

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from comfyui_client import ComfyUIConfig, create_default_comfyui_config, create_custom_comfyui_config


@dataclass
class SystemConfig:
    """システム全体の設定

    ComfyUIとGemini APIを統合した設定を管理します
    """
    # 基本設定
    output_dir: Path = field(default_factory=lambda: Path("output"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))

    # ComfyUI設定
    comfyui_config: ComfyUIConfig = field(default_factory=create_default_comfyui_config)

    # 生成設定
    image_width: int = 1024
    image_height: int = 1024
    default_steps: int = 28
    default_cfg: float = 7.0
    default_sampler: str = "euler_ancestral"

    # セッション設定
    session_dir: Optional[Path] = None
    history_file: Optional[Path] = None

    def __post_init__(self):
        """初期化後の処理"""
        # ディレクトリを作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        print(f"システム設定を初期化しました")
        print(f"出力ディレクトリ: {self.output_dir}")
        print(f"ComfyUIサーバー: {self.comfyui_config.server_address}")

    def create_session_dir(self, base_dir: Optional[Path] = None) -> Path:
        """セッション用のディレクトリを作成

        Args:
            base_dir: 基準ディレクトリ（Noneの場合はoutput_dirを使用）

        Returns:
            セッションディレクトリのパス
        """
        from datetime import datetime

        base = base_dir if base_dir else self.output_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = base / f"session_{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=True)

        # 履歴ファイルの作成
        history_file = session_dir / "history.csv"
        self._init_history_file(history_file)

        self.session_dir = session_dir
        self.history_file = history_file

        print(f"セッションディレクトリを作成しました: {session_dir}")
        return session_dir

    def _init_history_file(self, history_file: Path):
        """履歴ファイルの初期化

        Args:
            history_file: 履歴ファイルパス
        """
        with open(history_file, "w", encoding="utf-8", newline="") as f:
            f.write("generation,individual_id,prompt,seed,image_path,score,selected\n")

    def save_to_history(self, generation: int, individual_id: int, prompt: str,
                   seed: int, image_path: Path, score: float, selected: bool):
        """履歴にデータを保存

        Args:
            generation: 世代番号
            individual_id: 個体ID
            prompt: プロンプト
            seed: シード値
            image_path: 画像パス
            score: スコア
            selected: 選択されたか
        """
        if not self.history_file:
            return

        with open(self.history_file, "a", encoding="utf-8", newline="") as f:
            f.write(f"{generation},{individual_id},{prompt},{seed},{image_path},{score},{selected}\n")

    def load_from_json(self, config_path: Path) -> 'SystemConfig':
        """JSONファイルから設定を読み込む

        Args:
            config_path: 設定ファイルパス

        Returns:
            読み込まれた設定
        """
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

        # ComfyUI設定の復元
        comfyui_config = ComfyUIConfig()

        if "comfyui" in config_dict:
            comfy_dict = config_dict["comfyui"]
            comfyui_config.server_address = comfy_dict.get("server_address", comfyui_config.server_address)
            comfyui_config.workflow_json_path = comfy_dict.get("workflow_json_path", comfyui_config.workflow_json_path)

        return SystemConfig(
            comfyui_config=comfyui_config,
            output_dir=Path(config_dict.get("output_dir", str(self.output_dir))),
            **{k: v for k, v in config_dict.items() if k != "comfyui" and k != "output_dir"}
        )

    def save_to_json(self, config_path: Path):
        """設定をJSONファイルに保存

        Args:
            config_path: 保存先のパス
        """
        config_dict = {
            "comfyui": {
                "server_address": self.comfyui_config.server_address,
                "workflow_json_path": self.comfyui_config.workflow_json_path
            },
            "output_dir": str(self.output_dir),
            "image_width": self.image_width,
            "image_height": self.image_height,
            "default_steps": self.default_steps,
            "default_cfg": self.default_cfg,
            "default_sampler": self.default_sampler,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        print(f"設定を保存しました: {config_path}")


# ユーティリティ関数
def load_or_create_config(config_path: Path = Path("config.json")) -> SystemConfig:
    """設定ファイルを読み込む、またはデフォルト設定を作成

    Args:
        config_path: 設定ファイルパス

    Returns:
        システム設定
    """
    if config_path.exists():
        try:
            config = SystemConfig().load_from_json(config_path)
            print(f"設定ファイルを読み込みました: {config_path}")
            return config
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            print("デフォルト設定を使用します")

    # デフォルト設定を作成
    config = SystemConfig()
    config.save_to_json(config_path)
    return config