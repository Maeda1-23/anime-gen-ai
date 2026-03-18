# コマンドラインインターフェース

import sys
from pathlib import Path

from .utils import load_api_key
from .config import load_or_create_config
from .vlm.gemini_api import GeminiVLM
from .imggen.comfyui import ComfyUIGenerator
from .runner import ExperimentRunner


def run_slide_mode():
    """スライド解析モードを実行"""
    # APIキーの取得
    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        print(".envファイルにGEMINI_API_KEYを設定してください")
        sys.exit(1)

    # VLMクライアントの初期化と接続テスト
    print("Gemini API接続テスト中...")
    vlm = GeminiVLM(api_key)
    if not vlm.test_connection():
        print("[NG] Gemini API接続に失敗しました")
        sys.exit(1)
    print("[OK] Gemini API接続成功")

    # 設定の読み込み
    config = load_or_create_config()

    # 画像生成器の初期化と接続テスト
    print("ComfyUI接続テスト中...")
    imggen = ComfyUIGenerator(config.comfyui_config)
    if not imggen.test_connection():
        print(f"[NG] ComfyUI接続失敗: {config.comfyui_config.server_address}")
        sys.exit(1)
    print(f"[OK] ComfyUI接続成功: {config.comfyui_config.server_address}")

    # 実験の実行
    runner = ExperimentRunner(
        vlm=vlm,
        imggen=imggen,
        config=config,
    )
    runner.run()


def main():
    """メインエントリーポイント"""
    print("プロンプト自動改善システム")
    print("スライドから仕様書を抽出して画像生成・評価・改善を自動実行します")
    run_slide_mode()
