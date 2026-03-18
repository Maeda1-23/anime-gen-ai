# Gemini APIを使用したVLMクライアント

import json
import google.generativeai as genai
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image

from .base import VLMClient


class GeminiVLM(VLMClient):
    """Gemini APIクライアント

    VLMClientインターフェースを実装し、テキスト生成と画像理解を提供します。
    """

    def __init__(self, api_key: str, model_name: str = "gemini-3.1-flash-lite-preview"):
        """初期化

        Args:
            api_key: Google Gemini APIキー
            model_name: 使用するモデル名
        """
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        print(f"Gemini APIクライアントを初期化しました（モデル: {model_name}）")

    def generate(
        self,
        prompt: str,
        images: Optional[List[Image.Image]] = None,
        temperature: float = 0.7
    ) -> str:
        """プロンプトと画像からテキストを生成

        Args:
            prompt: テキストプロンプト
            images: PIL画像のリスト（省略可）
            temperature: 生成の多様性（0.0-1.0）

        Returns:
            生成されたテキスト
        """
        config = genai.types.GenerationConfig(temperature=temperature)
        content = [prompt] + list(images) if images else [prompt]
        response = self.model.generate_content(content, generation_config=config)
        return response.text

    def test_connection(self) -> bool:
        """API接続テスト"""
        try:
            response = self.model.generate_content("こんにちは。動作していますか？")
            return "はい" in response.text or "yes" in response.text.lower()
        except Exception as e:
            print(f"API接続エラー: {e}")
            return False

    # --- 互換性メソッド（既存コードからの呼び出し用） ---

    def analyze_image(self, image_path: Path, prompt: str = "この画像を詳しく説明してください") -> str:
        """画像を分析して説明を生成"""
        image = Image.open(image_path)
        return self.generate(prompt, [image])

    def analyze_image_detailed(self, image_path: Path) -> Dict[str, Any]:
        """画像を詳細に分析して構造化データを返す"""
        image = Image.open(image_path)

        analysis_prompt = """
このアニメキャラクターの画像を分析してください。
以下の情報をJSON形式で返してください：

{
  "character_features": "キャラクターの特徴（髪型、服装など）",
  "expression": "表情",
  "pose": "ポーズ",
  "background": "背景",
  "artistic_style": "芸術的スタイル",
  "quality_assessment": 5,
  "suggestions": ["改善提案1", "改善提案2"],
  "danbooru_tags": {
    "positive": "positive tags",
    "negative": "negative tags"
  }
}

※ 必ず有効なJSON形式で、余分なテキストを含めずに返してください
"""

        try:
            response_text = self.generate(analysis_prompt, [image], temperature=0.0)

            # マークダウンコードブロックからJSONを抽出
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()

            return json.loads(response_text)

        except Exception as e:
            print(f"詳細な画像分析エラー: {e}")
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
        """複数の画像を比較評価"""
        images = [Image.open(path) for path in image_paths]

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
"""

        try:
            response_text = self.generate(comparison_prompt, images, temperature=0.0)
            return json.loads(response_text)
        except Exception as e:
            print(f"画像比較エラー: {e}")
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
        """テキスト生成（互換性メソッド）"""
        return self.generate(prompt, temperature=temperature)

    def generate_improvement_suggestions(self, image_path: Path, current_prompt: str) -> Dict[str, Any]:
        """画像分析に基づいてプロンプト改善案を生成"""
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

        try:
            response_text = self.generate(prompt, [image], temperature=0.0)
            return json.loads(response_text)
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
