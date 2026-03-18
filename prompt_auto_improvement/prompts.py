# VLMプロンプトテンプレートとSpecPack定義

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from .utils import compact_json


@dataclass
class SpecPack:
    """スライドから抽出した仕様書と評価基準"""
    must: Dict[str, List[str]]
    should: Dict[str, List[str]]
    prohibited: List[str]
    judge_rubric: List[Dict[str, Any]]
    prompt_seed: Dict[str, str]

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return asdict(self)


def build_slide_analysis_prompt(slide_index: int) -> str:
    """スライド分析用のプロンプトを構築"""
    return (
        f"スライド{slide_index}の内容を説明してください。"
        "キャラクター、背景、雰囲気などの重要な要素を箇条書きで教えてください。"
    )


def build_specpack_extraction_prompt(slide_descriptions: List[str]) -> str:
    """スライド内容からSpecPack抽出用のプロンプトを構築"""
    all_content = "\n\n".join([
        f"=== スライド{i+1} ===\n{desc}"
        for i, desc in enumerate(slide_descriptions)
    ])

    return f"""
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

# スコア基準（厳格に評価）
- 各項目は0.0〜1.0の範囲で評価
- must項目が1つでも欠けている場合は重大な減点（0.2以下）
- prohibited項目が1つでもある場合はanti_noiseを0.0とする
- 品質が非常に良い場合でも1.0を超えることはない
- 平均的な品質は0.4〜0.6程度
- 優れた品質は0.7〜0.8程度
"""


def build_image_judge_prompt(specpack: SpecPack, current_prompt: str) -> str:
    """画像評価用のプロンプトを構築"""
    spec_json = compact_json(specpack.to_dict())

    return f"""
あなたは画像生成の検査官です。与えられたSpecPackを唯一の正解基準として、画像を採点し、修正案を返してください。

SpecPack(JSON):
{spec_json}

現在のprompt(tags):
{current_prompt}

# 出力は JSONのみ（説明文禁止）
スキーマ:
{{
  "total": 0,
  "scores": {{
    "character_appearance": {{"score": 0, "rationale": ""}},
    "pose_composition_spatial": {{"score": 0, "rationale": ""}},
    "background_environment_props": {{"score": 0, "rationale": ""}},
    "color_lighting_atmosphere": {{"score": 0, "rationale": ""}}
  }},
  "good_points": ["..."],
  "bad_points": ["..."],
  "critical_mismatches": ["..."]
}}

# スコア基準（厳格に評価）
- 各カテゴリは0〜10の範囲で評価
- totalは4カテゴリの合計（0〜40）
- 合格条件: 各カテゴリ7点以上、かつ合計36点以上
- must項目が1つでも欠けている場合は重大な減点（3点以下）
- prohibited項目が1つでもある場合は該当カテゴリを下げる
- 平均的な品質は各カテゴリ4〜6点程度
- 優れた品質は各カテゴリ7〜8点程度
- 完璧な品質は各カテゴリ9〜10点程度
"""


def build_prompt_improve_prompt(
    specpack: SpecPack,
    current_positive: str,
    current_negative: Optional[str],
    per_image_results: List[Dict],
    avg_scores: Dict,
    passed: bool,
    prompt_format: str = "tags",
    supports_negative: bool = True
) -> str:
    """プロンプト改善用のプロンプトを構築"""
    spec_json = compact_json(specpack.to_dict())
    per_image_json = compact_json(per_image_results)
    avg_scores_json = compact_json(avg_scores)

    pass_note = (
        "合格条件を達成しました。重大な不一致が残っていない限り、プロンプトを変更しないでください。"
        if passed
        else "合格条件を達成していません。チェックリストに従うようにプロンプトを改善してください。"
    )

    if supports_negative:
        neg_rule = "- ネガティブプロンプトを調整しても構いません。\n"
    else:
        neg_rule = "- ネガティブプロンプトは出力しないでください（nullに設定）。\n"

    if prompt_format == "tags":
        format_hint = (
            "プロンプト形式要件:\n"
            "- ポジティブプロンプトをカンマ区切りのタグで出力してください。\n"
            "- 完全な文章を使用しないでください。\n"
            "- ピリオドを使用しないでください。\n"
        )
    else:
        format_hint = (
            "プロンプト形式要件:\n"
            "- ポジティブプロンプトを画像生成に適した自然な英語で出力してください。\n"
        )

    return f"""
あなたはプロンプトエンジニアリングとアートディレクションの専門家です。

以下の情報が提供されます:
- 仕様書から作成されたチェックリスト (JSON)
- 現在の生成プロンプト
- 各画像の評価結果 (JSONリスト)
- 平均スコア (JSON)

目標:
- チェックリストへの準拠を改善するために、次の改善されたプロンプト（ポジティブとネガティブ）を提案してください。
- チェックリストでサポートされていない創造的な詳細を追加しないでください。
- 欠けているまたは繰り返し失敗している視覚的制約を強調してください。
- 矛盾を引き起こす用語を削除または緩和してください。

{pass_note}

{format_hint}

チェックリスト JSON:
{spec_json}

現在のポジティブプロンプト:
{current_positive}

現在のネガティブプロンプト:
{current_negative or "なし"}

平均スコア:
{avg_scores_json}

各画像の評価:
{per_image_json}

有効なJSONのみを出力してください。
以下のJSONスキーマを使用してください:

{{
  "loop_summary": {{
    "main_successes": ["成功点1", "成功点2"],
    "main_failures": ["失敗点1", "失敗点2"]
  }},
  "next_prompt": {{
    "positive": "改善されたポジティブプロンプト",
    "negative": "改善されたネガティブプロンプト" | null
  }},
  "changes": [
    {{"type": "add|remove|modify", "text": "変更内容", "reason": "理由"}}
  ],
  "notes": "追加のメモ"
}}

{neg_rule}
"""


def get_base_tags_from_specpack(specpack: SpecPack) -> List[str]:
    """SpecPackから基本タグを取得"""
    base_tags = []

    if specpack.must.get("character"):
        base_tags.extend(specpack.must["character"])

    if specpack.must.get("style"):
        base_tags.extend(specpack.must["style"])

    if specpack.prompt_seed.get("positive_tags"):
        seed_tags = [t.strip() for t in specpack.prompt_seed["positive_tags"].split(",")]
        for tag in seed_tags:
            if tag and tag not in base_tags:
                base_tags.append(tag)

    return base_tags


def create_default_specpack() -> SpecPack:
    """デフォルトのSpecPackを作成"""
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
            "text_in_image", "logo", "watermark",
            "ui_elements", "document_layout"
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
