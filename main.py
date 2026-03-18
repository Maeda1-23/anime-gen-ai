# アニメ制作自動化システムのメインエントリーポイント
# ComfyUI（Intel ARC GPU）とGemini APIを統合した完全なワークフロー

import os
import random
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("警告: python-dotenvがインストールされていません")
    load_dotenv = None

from gemini_client import GeminiClient, load_api_key
from comfyui_client import ComfyUIClient, create_custom_comfyui_config
from config import SystemConfig, load_or_create_config

def test_gemini_connection(api_key: str) -> bool:
    """Gemini API接続をテスト

    Args:
        api_key: Google Gemini APIキー

    Returns:
        接続成功時はTrue、失敗時はFalse
    """
    print("Gemini API接続テスト中...")

    try:
        client = GeminiClient(api_key)
        result = client.test_connection()

        if result:
            print("[OK] Gemini API接続成功")
            return True
        else:
            print("[NG] Gemini API接続失敗")
            return False

    except Exception as e:
        print(f"[NG] エラーが発生しました: {e}")
        return False

def test_comfyui_connection(config: SystemConfig) -> bool:
    """ComfyUI接続をテスト

    Args:
        config: システム設定

    Returns:
        接続成功時はTrue、失敗時はFalse
    """
    print("ComfyUI接続テスト中...")

    try:
        from comfyui_client import ComfyUIClient
        client = ComfyUIClient(config.comfyui_config)
        result = client.test_connection()

        if result:
            print(f"[OK] ComfyUI接続成功: {config.comfyui_config.server_address}")
            return True
        else:
            print(f"[NG] ComfyUI接続失敗: {config.comfyui_config.server_address}")
            return False

    except Exception as e:
        print(f"[NG] ComfyUI接続エラー: {e}")
        return False

def simple_test_mode():
    """簡単なテストモード"""
    print("\n=== テストモード ===")

    # APIキーの取得
    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        return

    # 接続テスト
    if not test_gemini_connection(api_key):
        print("Gemini API接続に失敗しました")
        return

    # 設定の読み込み
    config = load_or_create_config()

    # テスト用のプロンプト
    test_prompt = "1girl, solo, anime style, cute, detailed, masterpiece, best quality"

    print(f"\nテストプロンプト: {test_prompt}")

    # ComfyUIで画像生成
    comfyui_client = ComfyUIClient(config.comfyui_config)
    gemini_client = GeminiClient(api_key)

    try:
        print("\nComfyUIで画像生成中...")
        image_path = comfyui_client.generate_image(
            positive_prompt=test_prompt,
            negative_prompt="worst quality, low quality",
            seed=12345,
            output_dir=config.output_dir
        )
        print(f"画像を保存しました: {image_path}")

        print("\nGemini APIで画像分析中...")
        analysis = gemini_client.analyze_image_detailed(image_path)

        print("\n分析結果:")
        print(f"キャラクターの特徴: {analysis.get('character_features', 'N/A')}")
        print(f"表情: {analysis.get('expression', 'N/A')}")
        print(f"ポーズ: {analysis.get('pose', 'N/A')}")
        print(f"品質評価: {analysis.get('quality_assessment', 'N/A')}/10")
        print(f"改善提案: {', '.join(analysis.get('suggestions', []))}")
        print(f"提案されたタグ: {analysis.get('danbooru_tags', {}).get('positive', 'N/A')}")

        print("\n=== テスト完了 ===")

    except Exception as e:
        print(f"\nテスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

def main():
    """メイン関数"""
    print("アニメ制作自動化システムを起動します...")
    print("ComfyUI (Intel ARC GPU) と Gemini APIを統合した完全なワークフロー")

    # 環境変数の読み込み
    if load_dotenv:
        load_dotenv()

    print("\n選択してください:")
    print("1. 簡単なテストモード")

    choice = input("選択 (1): ").strip()

    if choice == "1":
        simple_test_mode()
    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()