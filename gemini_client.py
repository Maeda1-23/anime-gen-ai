# Gemini APIクライアント
# 画像理解とテキスト生成のためのAPIラッパー
# gemini-3.1-flash-lite-previewモデルを使用（無料で最も高性能）

import google.generativeai as genai
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image
import json

class GeminiClient:
    """Gemini APIの統合クライアント"""

    def __init__(self, api_key: str, model_name: str = "gemini-3.1-flash-lite-preview"):
        """初期化

        Args:
            api_key: Google Gemini APIキー
            model_name: 使用するモデル名（デフォルト: gemini-3.1-flash-lite-preview）
        """
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)

        # テキスト生成用モデル（gemini-3.1-flash-lite-previewを使用）
        self.text_model = genai.GenerativeModel(model_name)
        # 画像理解用モデルも同じモデル（ビジョン機能付き）
        self.vision_model = genai.GenerativeModel(model_name)

        print(f"Gemini APIクライアントを初期化しました（モデル: {model_name}）")

    def test_connection(self) -> bool:
        """API接続テスト

        Returns:
            接続成功時はTrue、失敗時はFalse
        """
        try:
            response = self.text_model.generate_content("こんにちは。動作していますか？")
            return "はい" in response.text or "yes" in response.text.lower()
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

    def analyze_image_detailed(self, image_path: Path) -> Dict[str, Any]:
        """画像を詳細に分析して構造化データを返す

        Args:
            image_path: 分析対象の画像パス

        Returns:
            画像の詳細な分析情報を含む辞書
        """
        try:
            # 画像を読み込み
            image = Image.open(image_path)

            # 詳細な分析プロンプト
            analysis_prompt = """
このアニメキャラクターの画像を分析してください。
以下の情報をJSON形式で返してください：

{
  "character_features": "キャラクターの特徴（髪型、服装など）",
  "expression": "表情",
  "pose": "ポーズ",
  "background": "背景",
  "artistic_style": "芸術的スタイル",
  "quality_assessment": "品質評価（1-10）",
  "suggestions": ["改善提案1", "改善提案2"],
  "danbooru_tags": {
    "positive": "positive tags",
    "negative": "negative tags"
  }
}

※ positiveタグにはキャラクターの特徴、表情、ポーズなど
※ negativeタグには品質を下げる要素（worst quality, low qualityなど）
"""

            response = self.vision_model.generate_content([
                analysis_prompt,
                image
            ])

            # JSONレスポンスをパース
            return json.loads(response.text)

        except Exception as e:
            print(f"詳細な画像分析エラー: {e}")
            # フォールバック
            return {
                "character_features": "分析に失敗しました",
                "expression": "不明",
                "pose": "不明",
                "background": "不明",
                "artistic_style": "不明",
                "quality_assessment": 0,
                "suggestions": ["再試行してください"],
                "danbooru_tags": {
                    "positive": "1girl, solo, anime style",
                    "negative": "worst quality, low quality"
                }
            }

    def compare_images(self, image_paths: List[Path]) -> Dict[str, Any]:
        """複数の画像を比較評価

        Args:
            image_paths: 比較対象の画像パスのリスト

        Returns:
            各画像の評価結果を含む辞書
        """
        try:
            # 画像を読み込み
            images = [Image.open(path) for path in image_paths]

            # 比較プロンプト
            comparison_prompt = f"""
提供された{len(images)}枚のアニメキャラクターの画像を比較してください。
各画像について以下の基準で評価し、JSON形式で返してください：

{{
  "evaluations": [
    {{
      "image_id": 0,
      "quality_score": 1.0,
      "aesthetic_score": 1.0,
      "anime_style_score": 1.0,
      "strengths": ["強み1", "強み2"],
      "weaknesses": ["弱み1", "弱み2"],
      "overall_rating": "良/悪/普通"
    }}
  ],
  "best_image_id": 0,
  "comparison_summary": "全体的な比較結果"
}}

※ スコアは0.0-1.0の範囲で評価
※ image_idは0から始まる整数
"""

            content = [comparison_prompt] + images
            response = self.vision_model.generate_content(content)

            # JSONレスポンスをパース
            return json.loads(response.text)

        except Exception as e:
            print(f"画像比較エラー: {e}")
            # フォールバック
            return {
                "evaluations": [
                    {
                        "image_id": i,
                        "quality_score": 0.5,
                        "aesthetic_score": 0.5,
                        "anime_style_score": 0.5,
                        "strengths": ["分析失敗"],
                        "weaknesses": ["分析失敗"],
                        "overall_rating": "不明"
                    }
                    for i in range(len(image_paths))
                ],
                "best_image_id": 0,
                "comparison_summary": "分析に失敗しました"
            }

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
            return json.loads(response.text)
        except Exception as e:
            print(f"プロンプト提案エラー: {e}")
            # フォールバック
            return {
                "positive": "1girl, solo, anime style",
                "negative": "worst quality, low quality"
            }

    def generate_improvement_suggestions(self, image_path: Path, current_prompt: str) -> Dict[str, Any]:
        """画像分析に基づいてプロンプト改善案を生成

        Args:
            image_path: 分析対象の画像パス
            current_prompt: 現在のプロンプト

        Returns:
            改善提案を含む辞書
        """
        try:
            image = Image.open(image_path)

            prompt = f"""
現在のプロンプトと生成された画像を分析し、プロンプトの改善案を提供してください。

現在のプロンプト:
{current_prompt}

出力形式（JSON）:
{{
  "analysis": "現在の画像の分析結果",
  "current_issues": ["問題点1", "問題点2"],
  "improvement_suggestions": {{
    "add_tags": ["追加すべきタグ1", "追加すべきタグ2"],
    "remove_tags": ["削除すべきタグ1"],
    "modify_tags": [{{"from": "古いタグ", "to": "新しいタグ"}}]
  }},
  "improved_prompt": "改善されたプロンプト"
}}
"""

            response = self.vision_model.generate_content([prompt, image])
            return json.loads(response.text)

        except Exception as e:
            print(f"改善提案エラー: {e}")
            return {
                "analysis": "分析に失敗しました",
                "current_issues": ["分析失敗"],
                "improvement_suggestions": {
                    "add_tags": [],
                    "remove_tags": [],
                    "modify_tags": []
                },
                "improved_prompt": current_prompt
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