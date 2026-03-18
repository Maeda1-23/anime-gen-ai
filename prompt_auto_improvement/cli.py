# コマンドラインインターフェース

import argparse
import os
import sys
from pathlib import Path

from .utils import load_api_key
from .config import AppConfig, load_config
from .vlm.gemini_api import GeminiVLM
from .imggen.comfyui import ComfyUIGenerator
from .runner import ExperimentRunner


def _build_vlm(app_config: AppConfig):
    """設定からVLMクライアントを構築"""
    vlm_cfg = app_config.vlm

    if vlm_cfg.provider == "gemini":
        api_key_env = vlm_cfg.gemini.api_key_env
        api_key = os.getenv(api_key_env)
        if not api_key:
            api_key = load_api_key()
        if not api_key:
            print(f"エラー: 環境変数 {api_key_env} が設定されていません")
            sys.exit(1)
        return GeminiVLM(api_key, model_name=vlm_cfg.gemini.model)
    else:
        print(f"エラー: 未対応のVLMプロバイダ: {vlm_cfg.provider}")
        sys.exit(1)


def _build_imggen(app_config: AppConfig):
    """設定から画像生成器を構築"""
    ig_cfg = app_config.image_generator

    if ig_cfg.provider == "comfyui":
        return ComfyUIGenerator(ig_cfg.comfyui)
    else:
        print(f"エラー: 未対応の画像生成プロバイダ: {ig_cfg.provider}")
        sys.exit(1)


def run_with_config(config_path: Path):
    """設定ファイルを使って実験を実行"""
    # 環境変数の読み込み
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # 設定の読み込み
    app_config = load_config(config_path)

    # VLMの構築と接続テスト
    vlm = _build_vlm(app_config)
    print("VLM接続テスト中...")
    if not vlm.test_connection():
        print("[NG] VLM接続に失敗しました")
        sys.exit(1)
    print("[OK] VLM接続成功")

    # 画像生成器の構築と接続テスト
    imggen = _build_imggen(app_config)
    print("画像生成器接続テスト中...")
    if not imggen.test_connection():
        print("[NG] 画像生成器接続に失敗しました")
        sys.exit(1)
    print("[OK] 画像生成器接続成功")

    # 実験の実行
    runner = ExperimentRunner.from_app_config(app_config, vlm=vlm, imggen=imggen)
    runner.run()


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="プロンプト自動改善システム"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.toml"),
        help="TOML設定ファイルのパス（デフォルト: configs/default.toml）"
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"エラー: 設定ファイルが見つかりません: {args.config}")
        sys.exit(1)

    print("プロンプト自動改善システム")
    print(f"設定ファイル: {args.config}")
    run_with_config(args.config)
