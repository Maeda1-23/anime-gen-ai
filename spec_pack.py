# SpecPack生成モジュール
# スライド画像から仕様書と評価基準を抽出する

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class SpecPack:
    """スライドから抽出した仕様書と評価基準"""
    # 必須項目
    must: Dict[str, List[str]]
    # 推奨項目
    should: Dict[str, List[str]]
    # 禁止事項
    prohibited: List[str]
    # 評価基準
    judge_rubric: List[Dict[str, any]]
    # 初期プロンプト
    prompt_seed: Dict[str, str]

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return asdict(self)


class SpecPackExtractor:
    """スライド画像からSpecPackを抽出するクラス"""

    def __init__(self, gemini_client):
        """初期化

        Args:
            gemini_client: GeminiClientインスタンス
        """
        self.client = gemini_client

    def extract_from_slides(
        self,
        slide_paths: List[Path],
        max_new_tokens: int = 1024
    ) -> SpecPack:
        """スライド画像からSpecPackを抽出

        Args:
            slide_paths: スライド画像のパスリスト
            max_new_tokens: 最大トークン数

        Returns:
            SpecPackオブジェクト
        """
        # スライド画像を1つのプロンプトで処理
        slide_descriptions = []
        for i, slide_path in enumerate(slide_paths):
            desc = self.client.analyze_image(
                slide_path,
                f"スライド{i+1}の内容を説明してください。キャラクター、背景、雰囲気などの重要な要素を箇条書きで教えてください。"
            )
            slide_descriptions.append(desc)

        # 全スライドの内容を結合
        all_content = "\n\n".join([
            f"=== スライド{i+1} ===\n{desc}"
            for i, desc in enumerate(slide_descriptions)
        ])

        # SpecPackを生成
        prompt = f"""
あなたは「アニメイラスト制作仕様書（スライド）」から、生成評価に使えるSpecPack(JSON)を作るアシスタントです。

以下のスライドの内容を分析して、SpecPackを作成してください。

スライド内容:
{all_content}

# 出力: JSONのみ（説明文禁止、Markdown禁止）
スキーマ:
{{
  "must": {{
    "character": [],
    "appearance": [],
    "expression": [],
    "pose": [],
    "composition": [],
    "background": [],
    "style": [],
    "unknown": []
  }},
  "should": {{
    "appearance": [],
    "expression": [],
    "pose": [],
    "composition": [],
    "background": [],
    "style": [],
    "unknown": []
  }},
  "prohibited": ["text_in_image", "logo", "watermark", "ui_elements", "document_layout"],
  "judge_rubric": [
    {{"key": "appearance", "weight": 3, "check": "must/shouldに基づき属性が一致している"}},
    {{"key": "expression", "weight": 2, "check": "表情が一致している"}},
    {{"key": "pose", "weight": 3, "check": "ポーズ/構図/アングルが一致している"}},
    {{"key": "background", "weight": 1, "check": "背景が一致している"}},
    {{"key": "anti_noise", "weight": 1, "check": "文字・ロゴ・透かし等が描かれていない"}}
  ],
  "prompt_seed": {{
    "positive_tags": "",
    "negative_tags": ""
  }}
}}

# ルール
- must/should の配列はユニーク化し、各配列は最大8項目
- スライドの宛名/会社名/管理ID/ページ番号等は prohibited に寄せる
- prompt_seed.positive_tags はDanbooru風の英語タグに寄せて短く
- prompt_seed.negative_tags は文字混入防止を中心に短く
"""

        # GeminiでJSONを生成
        response_text = self.client.generate_text(prompt, temperature=0.3)
        json_text = self._extract_json(response_text)

        if json_text:
            spec_dict = json.loads(json_text)
            return SpecPack(**spec_dict)
        else:
            # JSON抽出失敗時はデフォルトを返す
            return self._create_default_specpack(all_content)

    def _extract_json(self, text: str) -> Optional[str]:
        """テキストからJSONを抽出

        Args:
            text: JSONを含むテキスト

        Returns:
            抽出されたJSON文字列、見つからない場合はNone
        """
        import re

        # JSONコードブロックを探す
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # 最初の { から最後の } までを抽出
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)

        return None

    def _create_default_specpack(self, content: str) -> SpecPack:
        """デフォルトのSpecPackを作成

        Args:
            content: スライド内容

        Returns:
            デフォルトSpecPack
        """
        return SpecPack(
            must={
                "character": ["1girl", "solo"],
                "appearance": [],
                "expression": [],
                "pose": [],
                "composition": [],
                "background": [],
                "style": ["anime style"],
                "unknown": []
            },
            should={
                "appearance": [],
                "expression": [],
                "pose": [],
                "composition": [],
                "background": [],
                "style": [],
                "unknown": []
            },
            prohibited=[
                "text_in_image",
                "logo",
                "watermark",
                "ui_elements",
                "document_layout"
            ],
            judge_rubric=[
                {"key": "appearance", "weight": 3, "check": "must/shouldに基づき属性が一致している"},
                {"key": "expression", "weight": 2, "check": "表情が一致している"},
                {"key": "pose", "weight": 3, "check": "ポーズ/構図/アングルが一致している"},
                {"key": "background", "weight": 1, "check": "背景が一致している"},
                {"key": "anti_noise", "weight": 1, "check": "文字・ロゴ・透かし等が描かれていない"}
            ],
            prompt_seed={
                "positive_tags": "1girl, solo, anime style",
                "negative_tags": "text, logo, watermark"
            }
        )

    def get_base_tags_from_specpack(self, specpack: SpecPack) -> List[str]:
        """SpecPackから基本タグを取得

        Args:
            specpack: SpecPackオブジェクト

        Returns:
            基本タグのリスト
        """
        base_tags = []

        # mustのcharacterを優先
        if specpack.must.get("character"):
            base_tags.extend(specpack.must["character"])

        # mustのstyleを追加
        if specpack.must.get("style"):
            base_tags.extend(specpack.must["style"])

        # prompt_seed.positive_tagsも考慮
        if specpack.prompt_seed.get("positive_tags"):
            seed_tags = [t.strip() for t in specpack.prompt_seed["positive_tags"].split(",")]
            for tag in seed_tags:
                if tag and tag not in base_tags:
                    base_tags.append(tag)

        return base_tags

    def judge_image_with_specpack(
        self,
        image_path: Path,
        specpack: SpecPack,
        current_prompt: str
    ) -> Dict:
        """SpecPackに基づいて画像を評価

        Args:
            image_path: 画像パス
            specpack: SpecPackオブジェクト
            current_prompt: 現在のプロンプト

        Returns:
            評価結果の辞書
        """
        spec_json = json.dumps(specpack.to_dict(), ensure_ascii=False, indent=2)

        prompt = f"""
あなたは画像生成の検査官です。与えられたSpecPackを唯一の正解基準として、画像を採点し、修正案を返してください。

SpecPack(JSON):
{spec_json}

現在のprompt(tags):
{current_prompt}

# 出力は JSONのみ（説明文禁止）
スキーマ:
{{
  "total_score": 0.0,
  "breakdown": {{
    "appearance": 0,
    "expression": 0,
    "pose": 0,
    "background": 0,
    "anti_noise": 0
  }},
  "violations": ["..."],
  "tag_patch": {{
    "add": ["tag1", "tag2"],
    "remove": ["tag3"],
    "replace": [{{"from": "tag_old", "to": "tag_new"}}]
  }}
}}

# ルール
- total_score は 0.0〜1.0（高いほど良い）
- violations は最大8件、短く
- tag_patch は「最小修正」で。追加/削除/置換のどれかは必ず入れる
- prohibited が破られている（文字/ロゴ/透かし等）場合は anti_noise を下げ、remove/negative寄りの修正を提案
"""

        # Geminiで評価
        response_text = self.client.generate_text(prompt, temperature=0.3)
        json_text = self._extract_json(response_text)

        if json_text:
            return json.loads(json_text)
        else:
            # デフォルト評価
            return {
                "total_score": 0.5,
                "breakdown": {
                    "appearance": 0.5,
                    "expression": 0.5,
                    "pose": 0.5,
                    "background": 0.5,
                    "anti_noise": 0.5
                },
                "violations": ["JSON解析失敗"],
                "tag_patch": {
                    "add": [],
                    "remove": [],
                    "replace": []
                }
            }
