# SpecPackモジュール（互換性ラッパー）
# 実装は prompt_auto_improvement.prompts に移動しました

from prompt_auto_improvement.prompts import (
    SpecPack,
    get_base_tags_from_specpack,
    create_default_specpack,
)
from prompt_auto_improvement.utils import extract_json, compact_json


class SpecPackExtractor:
    """互換性ラッパー - 新しいコードでは ExperimentRunner を使用してください"""

    def __init__(self, gemini_client, prompt_format: str = "tags", supports_negative: bool = True):
        self.client = gemini_client
        self.prompt_format = prompt_format
        self.supports_negative = supports_negative

    def extract_from_slides(self, slide_paths, max_new_tokens=1024):
        from prompt_auto_improvement.prompts import (
            build_slide_analysis_prompt,
            build_specpack_extraction_prompt,
        )
        import json

        slide_descriptions = []
        for i, slide_path in enumerate(slide_paths):
            desc = self.client.analyze_image(
                slide_path,
                build_slide_analysis_prompt(i + 1)
            )
            slide_descriptions.append(desc)

        prompt = build_specpack_extraction_prompt(slide_descriptions)
        response_text = self.client.generate_text(prompt, temperature=0.0)
        json_text = extract_json(response_text)

        if json_text:
            spec_dict = json.loads(json_text)
            return SpecPack(**spec_dict)
        else:
            return create_default_specpack()

    def get_base_tags_from_specpack(self, specpack):
        return get_base_tags_from_specpack(specpack)

    def judge_image_with_specpack(self, image_path, specpack, current_prompt):
        from prompt_auto_improvement.prompts import build_image_judge_prompt
        import json

        prompt = build_image_judge_prompt(specpack, current_prompt)
        response_text = self.client.generate_text(prompt, temperature=0.0)
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

    def improve_prompt_with_vlm(self, specpack, current_positive, current_negative,
                                 per_image_results, avg_scores, passed):
        from prompt_auto_improvement.prompts import build_prompt_improve_prompt
        import json

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

        response_text = self.client.generate_text(prompt, temperature=0.0)
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

    def apply_tag_patch(self, current_prompt, patch, mutation_pool, base_tags, quality_tags=None):
        if quality_tags is None:
            quality_tags = []

        allowed = set()
        for tags in mutation_pool.values():
            allowed.update(tags)
        allowed.update(base_tags)

        cur_tags = [t.strip() for t in current_prompt.split(",") if t.strip()]
        cur_tags = [t for t in cur_tags if t not in quality_tags]

        remove = set(patch.get("remove", []) or [])
        add = patch.get("add", []) or []
        repl = patch.get("replace", []) or []

        cur_tags = [t for t in cur_tags if t not in remove]

        for r in repl:
            f = (r or {}).get("from")
            t = (r or {}).get("to")
            if not f or not t:
                continue
            cur_tags = [t if x == f else x for x in cur_tags]

        for t in add:
            if t and t not in cur_tags:
                cur_tags.append(t)

        out = []
        seen = set()
        for t in base_tags:
            if t not in seen:
                out.append(t)
                seen.add(t)
        for t in cur_tags:
            if t in seen:
                continue
            if t in allowed:
                out.append(t)
                seen.add(t)

        return out
