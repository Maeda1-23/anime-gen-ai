# 実験実行のメインロジック（VLMベースのプロンプト改善ループ）

import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

from .vlm.base import VLMClient
from .imggen.base import ImageGenerator
from .config import SystemConfig
from .io_manager import ExperimentIO
from .utils import extract_json
from .prompts import (
    SpecPack,
    build_slide_analysis_prompt,
    build_specpack_extraction_prompt,
    build_image_judge_prompt,
    build_prompt_improve_prompt,
    get_base_tags_from_specpack,
    create_default_specpack,
)


# デフォルト定数
QUALITY = "masterpiece, best quality, very aesthetic, absurdres, newest"
NEGATIVE_PROMPT = (
    "worst quality, comic, multiple views, bad quality, low quality, lowres, "
    "displeasing, very displeasing, bad anatomy, bad hands, scan artifacts, "
    "monochrome, greyscale, twitter username, jpeg artifacts, 2koma, 4koma, "
    "guro, extra digits, fewer digits, jaggy lines, unclear"
)


class ExperimentRunner:
    """VLMベースのプロンプト改善ループを実行"""

    def __init__(
        self,
        vlm: VLMClient,
        imggen: ImageGenerator,
        config: SystemConfig,
        slide_dir: Path = Path("slide_images"),
        max_loops: int = 10,
        images_per_loop: int = 3,
        prompt_format: str = "tags",
        supports_negative: bool = True,
    ):
        """初期化

        Args:
            vlm: VLMクライアント
            imggen: 画像生成器
            config: システム設定
            slide_dir: スライド画像ディレクトリ
            max_loops: 最大ループ回数
            images_per_loop: 1ループあたりの生成枚数
            prompt_format: プロンプト形式 ("tags" or "natural")
            supports_negative: ネガティブプロンプトサポート
        """
        self.vlm = vlm
        self.imggen = imggen
        self.config = config
        self.slide_dir = slide_dir
        self.max_loops = max_loops
        self.images_per_loop = images_per_loop
        self.prompt_format = prompt_format
        self.supports_negative = supports_negative

    def run(self):
        """メインの実験ループを実行"""
        print("\n=== スライド解析モード ===")
        print("スライドから仕様書を抽出して画像生成")

        # スライド画像を検索
        slides = self._find_slides()
        if not slides:
            return

        # SpecPackを抽出
        specpack = self._extract_specpack(slides)

        # 基本タグを取得
        base_tags = get_base_tags_from_specpack(specpack)
        print(f"\n基本タグ: {', '.join(base_tags)}")

        # セッションを作成
        io = ExperimentIO(self.config.output_dir)
        io.create_session()

        # SpecPackを保存
        io.write_json(io.session_dir / "specpack.json", specpack.to_dict())
        print(f"SpecPackを保存しました: {io.session_dir / 'specpack.json'}")

        # VLMベースのプロンプト改善ループ
        current_positive = ", ".join(base_tags) + f", {QUALITY}"
        current_negative = NEGATIVE_PROMPT

        for loop_idx in range(self.max_loops):
            loop_dir = io.create_loop_dir(loop_idx)

            print(f"\n--- ループ {loop_idx + 1}/{self.max_loops} ---")
            print(f"現在のプロンプト: {current_positive}")

            # 画像生成と評価
            per_image_results = self._generate_and_evaluate(
                loop_dir, specpack, current_positive, current_negative, io, loop_idx
            )

            # 平均スコアを計算
            avg_scores = self._calculate_avg_scores(per_image_results)

            # 合格条件をチェック
            passed = self._check_pass_condition(avg_scores)

            print(f"\nループ {loop_idx + 1} の結果:")
            print(f"  平均スコア: {avg_scores['total']:.0f}/40")
            print(f"  内訳: キャラクター{avg_scores['character_appearance']:.0f}/10, "
                  f"ポーズ{avg_scores['pose_composition_spatial']:.0f}/10, "
                  f"背景{avg_scores['background_environment_props']:.0f}/10, "
                  f"色・光{avg_scores['color_lighting_atmosphere']:.0f}/10")
            print(f"  合格: {'はい' if passed else 'いいえ'}")

            if passed:
                print(f"\n[合格条件を達成しました！]")
                return

            # VLMによるプロンプト改善
            print("\nVLMによるプロンプト改善を実行中...")
            improvement = self._improve_prompt(
                specpack, current_positive, current_negative,
                per_image_results, avg_scores, passed
            )

            current_positive = improvement["positive"]
            current_negative = improvement["negative"]

            print(f"改善されたプロンプト: {current_positive}")
            if improvement["changes"]:
                changes_str = ", ".join([
                    f"{c['type']}: {c['text']} ({c['reason']})"
                    for c in improvement['changes']
                ])
                print(f"変更: {changes_str}")
            if improvement["notes"]:
                print(f"メモ: {improvement['notes']}")
            if improvement["loop_summary"]:
                print(f"サマリー: 成功={improvement['loop_summary'].get('main_successes', [])}, "
                      f"失敗={improvement['loop_summary'].get('main_failures', [])}")

        print("\n最大ループ回数に達しました")

    def _find_slides(self) -> List[Path]:
        """スライド画像を検索"""
        if not self.slide_dir.exists():
            print(f"エラー: スライドディレクトリが見つかりません: {self.slide_dir}")
            return []

        slide_files = sorted(self.slide_dir.glob("*.png")) + sorted(self.slide_dir.glob("*.jpg"))
        if not slide_files:
            print("エラー: スライド画像が見つかりません")
            return []

        print(f"\nスライド画像を検出: {len(slide_files)}枚")
        for i, slide in enumerate(slide_files):
            print(f"  [{i+1}] {slide.name}")

        return slide_files

    def _extract_specpack(self, slide_paths: List[Path]) -> SpecPack:
        """スライドからSpecPackを抽出"""
        print("\nスライドから仕様書を抽出中...")

        # 各スライドを分析
        slide_descriptions = []
        for i, slide_path in enumerate(slide_paths):
            prompt = build_slide_analysis_prompt(i + 1)
            image = Image.open(slide_path)
            desc = self.vlm.generate(prompt, [image])
            slide_descriptions.append(desc)

        # SpecPack抽出プロンプトを構築
        extraction_prompt = build_specpack_extraction_prompt(slide_descriptions)
        response_text = self.vlm.generate(extraction_prompt, temperature=0.0)
        json_text = extract_json(response_text)

        if json_text:
            spec_dict = json.loads(json_text)
            specpack = SpecPack(**spec_dict)
        else:
            specpack = create_default_specpack()

        # 表示
        print("\n=== 抽出された仕様書 ===")
        print(f"必須項目: {specpack.must}")
        print(f"推奨項目: {specpack.should}")
        print(f"禁止事項: {specpack.prohibited}")
        print(f"初期プロンプト: {specpack.prompt_seed}")

        return specpack

    def _generate_and_evaluate(
        self,
        loop_dir: Path,
        specpack: SpecPack,
        current_positive: str,
        current_negative: str,
        io: ExperimentIO,
        loop_idx: int
    ) -> List[Dict]:
        """画像を生成して評価"""
        per_image_results = []

        for m in range(self.images_per_loop):
            seed = random.randint(0, 2**32 - 1)
            print(f"[{m}] 生成中...")

            try:
                image_path = self.imggen.generate_image(
                    positive_prompt=current_positive,
                    negative_prompt=current_negative,
                    seed=seed,
                    output_dir=loop_dir
                )

                evaluation = self._judge_image(image_path, specpack, current_positive)
                total_score = evaluation.get("total", 0)
                scores = evaluation.get("scores", {})
                passed = evaluation.get("passed", False)
                good_points = evaluation.get("good_points", [])
                bad_points = evaluation.get("bad_points", [])
                critical_mismatches = evaluation.get("critical_mismatches", [])

                character_appearance = scores.get("character_appearance", {}).get("score", 0)
                pose_composition_spatial = scores.get("pose_composition_spatial", {}).get("score", 0)
                background_environment_props = scores.get("background_environment_props", {}).get("score", 0)
                color_lighting_atmosphere = scores.get("color_lighting_atmosphere", {}).get("score", 0)

                result = {
                    "m": m,
                    "seed": seed,
                    "image": f"gen_image_{m}.png",
                    "total_score": total_score,
                    "scores": scores,
                    "passed": passed
                }
                per_image_results.append(result)

                # 履歴に記録
                io.add_history_entry(
                    loop=loop_idx, image_id=m, prompt=current_positive,
                    seed=seed, image_path=image_path,
                    total_score=total_score, passed=passed
                )

                print(f"    -> {image_path}")
                print(f"    スコア: {total_score:.0f}/40 (合格: {'はい' if passed else 'いいえ'})")
                print(f"    内訳: キャラクター{character_appearance:.0f}/10, "
                      f"ポーズ{pose_composition_spatial:.0f}/10, "
                      f"背景{background_environment_props:.0f}/10, "
                      f"色・光{color_lighting_atmosphere:.0f}/10")
                if good_points:
                    print(f"    良い点: {good_points}")
                if bad_points:
                    print(f"    悪い点: {bad_points}")
                if critical_mismatches:
                    print(f"    重大な不一致: {critical_mismatches}")

            except Exception as e:
                print(f"    [NG] エラー: {e}")
                per_image_results.append({
                    "m": m,
                    "seed": seed,
                    "image": f"gen_image_{m}.png",
                    "total_score": 0,
                    "scores": {
                        "character_appearance": {"score": 0, "rationale": "エラー"},
                        "pose_composition_spatial": {"score": 0, "rationale": "エラー"},
                        "background_environment_props": {"score": 0, "rationale": "エラー"},
                        "color_lighting_atmosphere": {"score": 0, "rationale": "エラー"}
                    },
                    "passed": False
                })

        return per_image_results

    def _judge_image(self, image_path: Path, specpack: SpecPack, current_prompt: str) -> Dict:
        """画像をSpecPackに基づいて評価"""
        prompt = build_image_judge_prompt(specpack, current_prompt)
        image = Image.open(image_path)
        response_text = self.vlm.generate(prompt, [image], temperature=0.0)
        json_text = extract_json(response_text)

        if json_text:
            evaluation = json.loads(json_text)
            scores = evaluation.get("scores", {})
            ca = scores.get("character_appearance", {}).get("score", 0)
            pcs = scores.get("pose_composition_spatial", {}).get("score", 0)
            bep = scores.get("background_environment_props", {}).get("score", 0)
            cla = scores.get("color_lighting_atmosphere", {}).get("score", 0)

            passed = (
                ca >= 7 and pcs >= 7 and bep >= 7 and cla >= 7
                and evaluation.get("total", 0) >= 36
            )
            evaluation["passed"] = passed
            return evaluation
        else:
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

    def _calculate_avg_scores(self, per_image_results: List[Dict]) -> Dict:
        """平均スコアを計算"""
        n = max(1, len(per_image_results))
        avg_total = sum(r["total_score"] for r in per_image_results) / n
        avg_ca = sum(r["scores"].get("character_appearance", {}).get("score", 0)
                     for r in per_image_results) / n
        avg_pcs = sum(r["scores"].get("pose_composition_spatial", {}).get("score", 0)
                      for r in per_image_results) / n
        avg_bep = sum(r["scores"].get("background_environment_props", {}).get("score", 0)
                      for r in per_image_results) / n
        avg_cla = sum(r["scores"].get("color_lighting_atmosphere", {}).get("score", 0)
                      for r in per_image_results) / n

        return {
            "total": avg_total,
            "character_appearance": avg_ca,
            "pose_composition_spatial": avg_pcs,
            "background_environment_props": avg_bep,
            "color_lighting_atmosphere": avg_cla
        }

    def _check_pass_condition(self, avg_scores: Dict) -> bool:
        """合格条件をチェック"""
        return (
            avg_scores["character_appearance"] >= 7
            and avg_scores["pose_composition_spatial"] >= 7
            and avg_scores["background_environment_props"] >= 7
            and avg_scores["color_lighting_atmosphere"] >= 7
            and avg_scores["total"] >= 36
        )

    def _improve_prompt(
        self,
        specpack: SpecPack,
        current_positive: str,
        current_negative: Optional[str],
        per_image_results: List[Dict],
        avg_scores: Dict,
        passed: bool
    ) -> Dict:
        """VLMでプロンプトを改善"""
        prompt = build_prompt_improve_prompt(
            specpack=specpack,
            current_positive=current_positive,
            current_negative=current_negative,
            per_image_results=per_image_results,
            avg_scores=avg_scores,
            passed=passed,
            prompt_format=self.prompt_format,
            supports_negative=self.supports_negative,
        )

        response_text = self.vlm.generate(prompt, temperature=0.0)
        json_text = extract_json(response_text)

        if json_text:
            improvement = json.loads(json_text)
            next_prompt = improvement.get("next_prompt", {})
            positive = next_prompt.get("positive", current_positive)
            negative = next_prompt.get("negative", current_negative)

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
