# Gemini APIクライアント
# 画像生成と画像理解のためのAPIラッパー

import google.generativeai as genai
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image
import io

class GeminiClient:
    """Gemini APIの統合クライアント"""

    def __init__(self, api_key: str):
        """初期化

        Args:
            api_key: Google Gemini APIキー
        """
        self.api_key = api_key
        genai.configure(api_key=api_key)

        # テキスト生成用モデル
        self.text_model = genai.GenerativeModel('gemini-pro')
        # 画像理解用モデル（ビジョン）
        self.vision_model = genai.GenerativeModel('gemini-pro-vision')

        print("Gemini APIクライアントを初期化しました")

    def test_connection(self) -> bool:
        """API接続テスト

        Returns:
            接続成功時はTrue、失敗時はFalse
        """
        try:
            response = self.text_model.generate_content("Hello, are you working?")
            return "hello" in response.text.lower() or "yes" in response.text.lower()
        except Exception as e:
            print(f"API接続エラー: {e}")
            return False

    def analyze_image(self, image_path: Path, prompt: str = "この画像を詳しく説明してください") -> str:
        """画像を分析して説明を生成

        Args:
            image_path: 分析対象の画像パス
            prompt: 分析用のプロンプト

        Returns:
            画像の説明テキスト
        """
        try:
            # 画像を読み込み
            image = Image.open(image_path)

            # 画像とテキストを含むリクエストを送信
            response = self.vision_model.generate_content([
                prompt,
                image
            ])

            return response.text

        except Exception as e:
            print(f"画像分析エラー: {e}")
            raise

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        """テキスト生成

        Args:
            prompt: 生成プロンプト
            temperature: 生成の多様性（0.0-1.0）

        Returns:
            生成されたテキスト
        """
        try:
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
            )

            response = self.text_model.generate_content(
                prompt,
                generation_config=generation_config
            )

            return response.text

        except Exception as e:
            print(f"テキスト生成エラー: {e}")
            raise

    def get_image_prompt_suggestions(self, base_description: str) -> Dict[str, str]:
        """画像生成用のプロンプト提案を取得

        Args:
            base_description: 基本となる説明

        Returns:
            改善されたプロンプトの辞書
        """
        prompt = f"""
以下のアニメキャラクターの説明から、画像生成AI用の英語タグプロンプトを作成してください。
Danbooruスタイルの英語タグを使用し、カンマ区切りで出力してください。

基本説明: {base_description}

出力形式（JSON）:
{{
    "positive": "positive tags here",
    "negative": "negative tags here"
}}

※ positiveにはキャラクターの特徴、表情、ポーズなど
※ negativeには品質を下げる要素（worst quality, low qualityなど）
"""

        try:
            response = self.text_model.generate_content(prompt)
            # JSONレスポンスをパース
            import json
            return json.loads(response.text)
        except Exception as e:
            print(f"プロンプト提案エラー: {e}")
            # フォールバック
            return {
                "positive": "1girl, solo, anime style",
                "negative": "worst quality, low quality"
            }

# ユーティリティ関数
def load_api_key(env_file: Path = Path(".env")) -> Optional[str]:
    """環境変数からAPIキーを読み込む

    Args:
        env_file: .envファイルのパス

    Returns:
        APIキー、またはNone
    """
    if env_file.exists():
        import os
        from dotenv import load_dotenv
        load_dotenv(env_file)
        return os.getenv("GEMINI_API_KEY")
    return None