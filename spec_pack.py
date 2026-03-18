# SpecPack生成モジュール
# スライド画像から仕様書と評価基準を抽出する

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


def _compact_json(obj: Any) -> str:
    """JSONを一貫した形式に変換（キャッシュや再現性のために空白を削除）

    Args:
        obj: JSON化するオブジェクト

    Returns:
        一貫した形式のJSON文字列
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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

    def __init__(self, gemini_client, prompt_format: str = "tags", supports_negative: bool = True):
        """初期化

        Args:
            gemini_client: GeminiClientインスタンス
            prompt_format: プロンプト形式 ("tags" or "natural")
            supports_negative: ネガティブプロンプトをサポートするか
        """
        self.client = gemini_client
        self.prompt_format = prompt_format
        self.supports_negative = supports_negative

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

# スコア基準（厳格に評価）
- 各項目は0.0〜1.0の範囲で評価
- must項目が1つでも欠けている場合は重大な減点（0.2以下）
- prohibited項目が1つでもある場合はanti_noiseを0.0とする
- 品質が非常に良い場合でも1.0を超えることはない
- 平均的な品質は0.4〜0.6程度
- 優れた品質は0.7〜0.8程度
"""

        # GeminiでJSONを生成（温度0で決定的）
        response_text = self.client.generate_text(prompt, temperature=0.0)
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
        spec_json = _compact_json(specpack.to_dict())

        prompt = f"""
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

        # Geminiで評価（温度0で決定的）
        response_text = self.client.generate_text(prompt, temperature=0.0)
        json_text = self._extract_json(response_text)

        if json_text:
            evaluation = json.loads(json_text)
            # 合格条件のチェック
            scores = evaluation.get("scores", {})
            character_appearance = scores.get("character_appearance", {}).get("score", 0)
            pose_composition_spatial = scores.get("pose_composition_spatial", {}).get("score", 0)
            background_environment_props = scores.get("background_environment_props", {}).get("score", 0)
            color_lighting_atmosphere = scores.get("color_lighting_atmosphere", {}).get("score", 0)

            passed = (
                character_appearance >= 7 and
                pose_composition_spatial >= 7 and
                background_environment_props >= 7 and
                color_lighting_atmosphere >= 7 and
                evaluation.get("total", 0) >= 36
            )

            evaluation["passed"] = passed
            return evaluation
        else:
            # デフォルト評価
            return {
                "total": 20,
                "scores": {
                    "character_appearance": {"score": 5, "rationale": "JSON解析失敗"},
                    "pose_composition_spatial": {"score": 5, "rationale": "JSON解析失敗"},
                    "background_environment_props": {"score": 5, "rationale": "JSON解析失敗"},
                    "color_lighting_atmosphere": {"score": 5, "rationale": "JSON解析失敗"}
                },
                "good_points": ["解析失敗"],
                "bad_points": ["解析失敗"],
                "critical_mismatches": ["JSON解析失敗"],
                "passed": False
            }

    def apply_tag_patch(
        self,
        current_prompt: str,
        patch: dict,
        mutation_pool: dict[str, list[str]],
        base_tags: list[str],
        quality_tags: list[str] = None
    ) -> list[str]:
        """tag_patchをプロンプトに適用

        Args:
            current_prompt: 現在のプロンプト
            patch: 評価結果のtag_patch
            mutation_pool: タグプール
            base_tags: 基本タグ
            quality_tags: 品質タグ

        Returns:
            修正後のタグリスト
        """
        if quality_tags is None:
            quality_tags = []

        allowed = set()
        for tags in mutation_pool.values():
            allowed.update(tags)
        allowed.update(base_tags)

        # prompt -> list[str]
        cur_tags = [t.strip() for t in current_prompt.split(",") if t.strip()]
        # qualityタグを除外
        cur_tags = [t for t in cur_tags if t not in quality_tags]

        remove = set(patch.get("remove", []) or [])
        add = patch.get("add", []) or []
        repl = patch.get("replace", []) or []

        # remove
        cur_tags = [t for t in cur_tags if t not in remove]

        # replace
        for r in repl:
            f = (r or {}).get("from")
            t = (r or {}).get("to")
            if not f or not t:
                continue
            cur_tags = [t if x == f else x for x in cur_tags]

        # add
        for t in add:
            if t and t not in cur_tags:
                cur_tags.append(t)

        # base_tags を強制的に先頭に揃える
        out = []
        seen = set()
        for t in base_tags:
            if t not in seen:
                out.append(t)
                seen.add(t)
        for t in cur_tags:
            if t in seen:
                continue
            # allowed だけ通す（未知タグは落とす）
            if t in allowed:
                out.append(t)
                seen.add(t)

        return out

    def improve_prompt_with_vlm(
        self,
        specpack: SpecPack,
        current_positive: str,
        current_negative: Optional[str],
        per_image_results: List[Dict],
        avg_scores: Dict,
        passed: bool
    ) -> Dict[str, Optional[str]]:
        """VLMを使用してプロンプトを改善

        Args:
            specpack: SpecPackオブジェクト
            current_positive: 現在のポジティブプロンプト
            current_negative: 現在のネガティブプロンプト
            per_image_results: 各画像の評価結果リスト
            avg_scores: 平均スコア
            passed: 合格しているか

        Returns:
            改善されたプロンプトの辞書 {"positive": str, "negative": str|None}
        """
        spec_json = _compact_json(specpack.to_dict())
        per_image_json = _compact_json(per_image_results)
        avg_scores_json = _compact_json(avg_scores)

        pass_note = (
            "合格条件を達成しました。重大な不一致が残っていない限り、プロンプトを変更しないでください。"
            if passed
            else "合格条件を達成していません。チェックリストに従うようにプロンプトを改善してください。"
        )

        neg_rule = ""
        if self.supports_negative:
            neg_rule = "- ネガティブプロンプトを調整しても構いません。\n"
        else:
            neg_rule = "- ネガティブプロンプトは出力しないでください（nullに設定）。\n"

        format_hint = ""
        if self.prompt_format == "tags":
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

        prompt = f"""
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

        # Geminiでプロンプト改善（温度0で決定的）
        response_text = self.client.generate_text(prompt, temperature=0.0)
        json_text = self._extract_json(response_text)

        if json_text:
            improvement = json.loads(json_text)
            next_prompt = improvement.get("next_prompt", {})
            positive = next_prompt.get("positive", current_positive)
            negative = next_prompt.get("negative", current_negative)

            # ネガティブプロンプトがサポートされていない場合はNoneに設定
            if not self.supports_negative:
                negative = None

            return {
                "positive": positive,
                "negative": negative,
                "changes": improvement.get("changes", []),
                "notes": improvement.get("notes", ""),
                "loop_summary": improvement.get("loop_summary", {})
            }
        else:
            # デフォルト改善（元のプロンプトを返す）
            return {
                "positive": current_positive,
                "negative": current_negative if self.supports_negative else None,
                "changes": [],
                "notes": "プロンプト改善に失敗しました。元のプロンプトを維持します。",
                "loop_summary": {
                    "main_successes": [],
                    "main_failures": ["プロンプト改善に失敗"]
                }
            }

