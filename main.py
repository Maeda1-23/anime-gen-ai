# アニメ制作自動化システムのメインエントリーポイント

import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    print("警告: python-dotenvがインストールされていません")
    print("インストールコマンド: pip install python-dotenv")
    load_dotenv = None

from gemini_client import GeminiClient, load_api_key
from workflow_manager import run_interactive_workflow

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
            print("✓ Gemini API接続成功")
            return True
        else:
            print("✗ Gemini API接続失敗")
            return False

    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        return False

def interactive_demo(client: GeminiClient):
    """対話的なデモモード

    Args:
        client: GeminiClientインスタンス
    """
    print("\n=== アニメ制作自動化システム - メニュー ===")

    while True:
        print("\n選択してください:")
        print("1. テキスト生成テスト")
        print("2. プロンプト提案テスト")
        print("3. 画像分析テスト（画像パスを指定）")
        print("4. 進化的ワークフロー開始")
        print("5. 終了")

        choice = input("選択 (1-5): ").strip()

        if choice == "1":
            test_text_generation(client)
        elif choice == "2":
            test_prompt_suggestions(client)
        elif choice == "3":
            test_image_analysis(client)
        elif choice == "4":
            run_interactive_workflow(client)
        elif choice == "5":
            print("終了します")
            break
        else:
            print("無効な選択です")

def test_text_generation(client: GeminiClient):
    """テキスト生成機能のテスト"""
    print("\n--- テキスト生成テスト ---")

    prompt = input("プロンプトを入力: ").strip()
    if not prompt:
        prompt = "アニメキャラクターの特徴について説明してください"

    try:
        result = client.generate_text(prompt)
        print(f"\n生成結果:\n{result}")
    except Exception as e:
        print(f"エラー: {e}")

def test_prompt_suggestions(client: GeminiClient):
    """プロンプト提案機能のテスト"""
    print("\n--- プロンプト提案テスト ---")

    description = input("キャラクターの説明を入力: ").strip()
    if not description:
        description = "可愛いアニメの女の子、ショートヘア、制服"

    try:
        suggestions = client.get_image_prompt_suggestions(description)
        print(f"\n提案されたプロンプト:")
        print(f"Positive: {suggestions['positive']}")
        print(f"Negative: {suggestions['negative']}")
    except Exception as e:
        print(f"エラー: {e}")

def test_image_analysis(client: GeminiClient):
    """画像分析機能のテスト"""
    print("\n--- 画像分析テスト ---")

    image_path = input("画像パスを入力: ").strip()
    if not image_path:
        print("パスが入力されませんでした")
        return

    path = Path(image_path)
    if not path.exists():
        print(f"ファイルが見つかりません: {image_path}")
        return

    prompt = input("分析用プロンプトを入力（Enterでデフォルト）: ").strip()
    if not prompt:
        prompt = "この画像を詳しく説明してください"

    try:
        result = client.analyze_image(path, prompt)
        print(f"\n分析結果:\n{result}")
    except Exception as e:
        print(f"エラー: {e}")

def main():
    """メイン関数"""
    print("アニメ制作自動化システムを起動します...")
    print("Gemini APIを活用したアニメ制作ワークフロー自動化システム")

    # 環境変数の読み込み
    if load_dotenv:
        load_dotenv()

    # APIキーの取得
    api_key = load_api_key()

    if not api_key:
        print("\nエラー: .envファイルにGEMINI_API_KEYが設定されていません")
        print("\n以下の手順でAPIキーを設定してください:")
        print("1. Google Cloud Console (https://console.cloud.google.com/) にアクセス")
        print("2. プロジェクトを作成または選択")
        print("3. 'APIs & Services' > 'Credentials' に移動")
        print("4. 'Create Credentials' > 'API Key' をクリック")
        print("5. 生成されたAPIキーをコピー")
        print("6. .envファイルに GEMINI_API_KEY=your_api_key と記述")
        print("\nAPIキーの取得方法:")
        print("- Google AI Studio (https://makersuite.google.com/app/apikey) も使用可能です")
        print("- 無料枠で利用可能です")
        return

    # API接続テスト
    if not test_gemini_connection(api_key):
        print("\nAPI接続に失敗しました。APIキーを確認してください。")
        print("詳細なエラーメッセージを確認の上、再度試してください。")
        return

    # Geminiクライアントの初期化
    client = GeminiClient(api_key)

    # 対話的なデモモード
    interactive_demo(client)

if __name__ == "__main__":
    main()