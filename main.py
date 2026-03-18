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

def slide_workflow_mode():
    """スライド解析モード - スライドから仕様書を抽出して画像生成"""
    # ajiokaのシステムと同じパラメータ
    QUALITY = "masterpiece, best quality, very aesthetic, absurdres, newest"
    NEGATIVE_PROMPT = "worst quality, comic, multiple views, bad quality, low quality, lowres, displeasing, very displeasing, bad anatomy, bad hands, scan artifacts, monochrome, greyscale, twitter username, jpeg artifacts, 2koma, 4koma, guro, extra digits, fewer digits, jaggy lines, unclear"
    POP_SIZE = 6
    PAIR_SIZE = 2

    print("\n=== スライド解析モード ===")
    print("スライドから仕様書を抽出して画像生成")

    # APIキーの取得
    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        return

    # 接続テスト
    if not test_gemini_connection(api_key):
        print("Gemini API接続に失敗しました")
        return

    config = load_or_create_config()

    # スライド画像のパスを取得
    slide_dir = Path("slide_images")
    if not slide_dir.exists():
        print(f"エラー: スライドディレクトリが見つかりません: {slide_dir}")
        return

    slide_files = sorted(slide_dir.glob("*.png")) + sorted(slide_dir.glob("*.jpg"))
    if not slide_files:
        print("エラー: スライド画像が見つかりません")
        return

    print(f"\nスライド画像を検出: {len(slide_files)}枚")
    for i, slide in enumerate(slide_files):
        print(f"  [{i+1}] {slide.name}")

    # クライアントの初期化
    comfyui_client = ComfyUIClient(config.comfyui_config)
    gemini_client = GeminiClient(api_key)

    # SpecPackを抽出
    from spec_pack import SpecPackExtractor
    extractor = SpecPackExtractor(
        gemini_client,
        prompt_format="tags",
        supports_negative=True
    )

    print("\nスライドから仕様書を抽出中...")
    specpack = extractor.extract_from_slides(slide_files)

    # SpecPackの表示
    print("\n=== 抽出された仕様書 ===")
    print(f"必須項目: {specpack.must}")
    print(f"推奨項目: {specpack.should}")
    print(f"禁止事項: {specpack.prohibited}")
    print(f"初期プロンプト: {specpack.prompt_seed}")

    # 基本タグをSpecPackから取得
    base_tags = extractor.get_base_tags_from_specpack(specpack)
    print(f"\n基本タグ: {', '.join(base_tags)}")

    # セッションの作成
    from workflow_manager import WorkflowManager
    workflow = WorkflowManager(
        client=gemini_client,
        base_tags=base_tags,
        mutation_pool={},
        population_size=1,
        pair_size=PAIR_SIZE,
        quality_suffix=QUALITY
    )
    workflow.create_session()

    # SpecPackを保存
    import json
    specpack_path = workflow.session_dir / "specpack.json"
    with open(specpack_path, "w", encoding="utf-8") as f:
        json.dump(specpack.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"SpecPackを保存しました: {specpack_path}")

    # VLMベースのプロンプト改善ループ
    max_loops = 10
    images_per_loop = 3

    # 初期プロンプト
    current_positive = ", ".join(base_tags) + f", {QUALITY}"
    current_negative = NEGATIVE_PROMPT

    for loop_idx in range(max_loops):
        workflow.current_generation = loop_idx
        loop_dir = workflow.session_dir / f"loop_{loop_idx:03d}"
        loop_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--- ループ {loop_idx + 1}/{max_loops} ---")
        print(f"現在のプロンプト: {current_positive}")

        # 画像生成
        results = []
        per_image_results = []

        for m in range(images_per_loop):
            seed = random.randint(0, 2**32 - 1)

            print(f"[{m}] 生成中...")

            try:
                # ComfyUIで画像生成
                image_path = comfyui_client.generate_image(
                    positive_prompt=current_positive,
                    negative_prompt=current_negative,
                    seed=seed,
                    output_dir=loop_dir
                )

                # Geminiで画像分析（SpecPackに基づいた評価）
                try:
                    evaluation = extractor.judge_image_with_specpack(
                        image_path=image_path,
                        specpack=specpack,
                        current_prompt=current_positive
                    )
                    total_score = evaluation.get("total", 0)
                    scores = evaluation.get("scores", {})
                    passed = evaluation.get("passed", False)
                    good_points = evaluation.get("good_points", [])
                    bad_points = evaluation.get("bad_points", [])
                    critical_mismatches = evaluation.get("critical_mismatches", [])

                    # 各カテゴリのスコアを取得
                    character_appearance = scores.get("character_appearance", {}).get("score", 0)
                    pose_composition_spatial = scores.get("pose_composition_spatial", {}).get("score", 0)
                    background_environment_props = scores.get("background_environment_props", {}).get("score", 0)
                    color_lighting_atmosphere = scores.get("color_lighting_atmosphere", {}).get("score", 0)

                    # 各画像の評価結果を記録
                    per_image_results.append({
                        "m": m,
                        "seed": seed,
                        "image": f"gen_image_{m}.png",
                        "total_score": total_score,
                        "scores": scores,
                        "passed": passed
                    })
                except Exception as e:
                    print(f"    [警告] SpecPack評価失敗: {e}、デフォルト評価を使用")
                    analysis = gemini_client.analyze_image_detailed(image_path)
                    total_score = analysis.get("quality_assessment", 5.0) * 4  # 0-40点に変換
                    character_appearance = analysis.get("quality_assessment", 5.0)
                    pose_composition_spatial = analysis.get("quality_assessment", 5.0)
                    background_environment_props = analysis.get("quality_assessment", 5.0)
                    color_lighting_atmosphere = analysis.get("quality_assessment", 5.0)
                    passed = False
                    good_points = []
                    bad_points = ["解析失敗"]
                    critical_mismatches = []

                    # 各画像の評価結果を記録
                    per_image_results.append({
                        "m": m,
                        "seed": seed,
                        "image": f"gen_image_{m}.png",
                        "total_score": total_score,
                        "scores": {
                            "character_appearance": {"score": character_appearance, "rationale": "解析失敗"},
                            "pose_composition_spatial": {"score": pose_composition_spatial, "rationale": "解析失敗"},
                            "background_environment_props": {"score": background_environment_props, "rationale": "解析失敗"},
                            "color_lighting_atmosphere": {"score": color_lighting_atmosphere, "rationale": "解析失敗"}
                        },
                        "passed": passed
                    })

                print(f"    -> {image_path}")
                print(f"    スコア: {total_score:.0f}/40 (合格: {'はい' if passed else 'いいえ'})")
                print(f"    内訳: キャラクター{character_appearance:.0f}/10, ポーズ{pose_composition_spatial:.0f}/10, 背景{background_environment_props:.0f}/10, 色・光{color_lighting_atmosphere:.0f}/10")
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

        # 平均スコアを計算
        n = max(1, len(per_image_results))
        avg_total = sum(r["total_score"] for r in per_image_results) / n
        avg_character_appearance = sum(r["scores"].get("character_appearance", {}).get("score", 0) for r in per_image_results) / n
        avg_pose_composition_spatial = sum(r["scores"].get("pose_composition_spatial", {}).get("score", 0) for r in per_image_results) / n
        avg_background_environment_props = sum(r["scores"].get("background_environment_props", {}).get("score", 0) for r in per_image_results) / n
        avg_color_lighting_atmosphere = sum(r["scores"].get("color_lighting_atmosphere", {}).get("score", 0) for r in per_image_results) / n

        avg_scores = {
            "total": avg_total,
            "character_appearance": avg_character_appearance,
            "pose_composition_spatial": avg_pose_composition_spatial,
            "background_environment_props": avg_background_environment_props,
            "color_lighting_atmosphere": avg_color_lighting_atmosphere
        }

        # 合格条件をチェック
        passed = (
            avg_character_appearance >= 7 and
            avg_pose_composition_spatial >= 7 and
            avg_background_environment_props >= 7 and
            avg_color_lighting_atmosphere >= 7 and
            avg_total >= 36
        )

        print(f"\nループ {loop_idx + 1} の結果:")
        print(f"  平均スコア: {avg_total:.0f}/40")
        print(f"  内訳: キャラクター{avg_character_appearance:.0f}/10, ポーズ{avg_pose_composition_spatial:.0f}/10, 背景{avg_background_environment_props:.0f}/10, 色・光{avg_color_lighting_atmosphere:.0f}/10")
        print(f"  合格: {'はい' if passed else 'いいえ'}")

        if passed:
            print(f"\n[合格条件を達成しました！]")
            return  # 合格した場合は終了

        # VLMによるプロンプト改善
        print("\nVLMによるプロンプト改善を実行中...")
        improvement = extractor.improve_prompt_with_vlm(
            specpack=specpack,
            current_positive=current_positive,
            current_negative=current_negative,
            per_image_results=per_image_results,
            avg_scores=avg_scores,
            passed=passed
        )

        # 改善されたプロンプトを適用
        current_positive = improvement["positive"]
        current_negative = improvement["negative"]

        print(f"改善されたプロンプト: {current_positive}")
        if improvement["changes"]:
            print(f"変更: {[f\"{c['type']}: {c['text']} ({c['reason']})\" for c in improvement['changes']]}")
        if improvement["notes"]:
            print(f"メモ: {improvement['notes']}")
        if improvement["loop_summary"]:
            print(f"サマリー: 成功={improvement['loop_summary'].get('main_successes', [])}, 失敗={improvement['loop_summary'].get('main_failures', [])}")

    print("\n最大ループ回数に達しました")

def full_workflow_mode():
    """フルワークフローモード - 遺伝的アルゴリズムによる画像生成と自動改善"""
    # ajiokaのシステムと同じパラメータ
    QUALITY = "masterpiece, best quality, very aesthetic, absurdres, newest"
    NEGATIVE_PROMPT = "worst quality, comic, multiple views, bad quality, low quality, lowres, displeasing, very displeasing, bad anatomy, bad hands, scan artifacts, monochrome, greyscale, twitter username, jpeg artifacts, 2koma, 4koma, guro, extra digits, fewer digits, jaggy lines, unclear"
    POP_SIZE = 6
    PAIR_SIZE = 2

    print("\n=== フルワークフローモード ===")
    print("遺伝的アルゴリズムによる画像生成と自動改善ループ")

    # APIキーの取得
    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        return

    # 接続テスト
    if not test_gemini_connection(api_key):
        print("Gemini API接続に失敗しました")
        return

    config = load_or_create_config()

    # 基本タグの入力
    print("\n基本タグを入力してください")
    base_input = input("基本タグ（例: 1girl, solo）: ").strip()
    if not base_input:
        base_tags = ["1girl", "solo"]
    else:
        base_tags = [t.strip() for t in base_input.split(",") if t.strip()]

    print(f"基本タグ: {', '.join(base_tags)}")

    # VLMを使用するか（デフォルト: 使用する）
    use_vl = True
    print("VLMによる自動選択を使用します")

    # クライアントの初期化
    comfyui_client = ComfyUIClient(config.comfyui_config)
    gemini_client = GeminiClient(api_key)

    # 変異プールの作成（CSVから読み込み）
    from genetic_algorithm import load_mutation_pool_csv, Population
    mutation_pool = load_mutation_pool_csv()

    # 初期個体群の作成
    population = Population.create_random_population(
        size=POP_SIZE,
        base_tags=base_tags,
        mutation_pool=mutation_pool,
        quality_suffix=QUALITY
    )

    print(f"\n初期個体群: {POP_SIZE}個体を作成しました")

    # セッションの作成
    from workflow_manager import WorkflowManager
    workflow = WorkflowManager(
        client=gemini_client,
        base_tags=base_tags,
        mutation_pool=mutation_pool,
        population_size=POP_SIZE,
        pair_size=PAIR_SIZE,
        quality_suffix=QUALITY
    )
    workflow.create_session()

    # 進化的ループ
    max_generations = 10
    for generation in range(max_generations):
        workflow.current_generation = generation
        gen_dir = workflow.session_dir / f"gen_{generation:03d}"
        gen_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--- 第{generation + 1}世代 ---")

        # 画像生成
        results = []
        for i, indiv in enumerate(population.individuals):
            prompt = indiv.get_prompt()
            seed = random.randint(0, 2**32 - 1)

            print(f"[{i}] 生成中: {prompt}")

            try:
                # ComfyUIで画像生成
                image_path = comfyui_client.generate_image(
                    positive_prompt=prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    seed=seed,
                    output_dir=gen_dir
                )

                # Geminiで画像分析（ajiokaの4カテゴリ評価）
                analysis = gemini_client.analyze_image_detailed(image_path)

                # quality_assessmentから4カテゴリのスコアを推定
                quality = analysis.get("quality_assessment", 5.0)
                total_score = int(quality * 4)  # 0-40点に変換
                character_appearance = int(quality)
                pose_composition_spatial = int(quality)
                background_environment_props = int(quality)
                color_lighting_atmosphere = int(quality)

                # 合格条件のチェック
                passed = (
                    character_appearance >= 7 and
                    pose_composition_spatial >= 7 and
                    background_environment_props >= 7 and
                    color_lighting_atmosphere >= 7 and
                    total_score >= 36
                )

                print(f"    -> {image_path}")
                print(f"    スコア: {total_score}/40 (合格: {'はい' if passed else 'いいえ'})")
                print(f"    内訳: キャラクター{character_appearance}/10, ポーズ{pose_composition_spatial}/10, 背景{background_environment_props}/10, 色・光{color_lighting_atmosphere}/10")

                results.append({
                    "individual": indiv,
                    "prompt": prompt,
                    "seed": seed,
                    "image_path": image_path,
                    "total_score": total_score,
                    "passed": passed,
                    "selected": False,
                    "character_appearance": character_appearance,
                    "pose_composition_spatial": pose_composition_spatial,
                    "background_environment_props": background_environment_props,
                    "color_lighting_atmosphere": color_lighting_atmosphere
                })

            except Exception as e:
                print(f"    [NG] エラー: {e}")
                results.append({
                    "individual": indiv,
                    "prompt": prompt,
                    "seed": seed,
                    "image_path": None,
                    "total_score": 0,
                    "passed": False,
                    "selected": False,
                    "character_appearance": 0,
                    "pose_composition_spatial": 0,
                    "background_environment_props": 0,
                    "color_lighting_atmosphere": 0
                })

        # 選択フェーズ
        survivors = []

        if use_vl:
            # VLMによる自動選択
            print("\nVLMによる自動選択を実行...")
            sorted_results = sorted(results, key=lambda x: x["total_score"], reverse=True)
            num_survivors = max(2, len(results) // 2)

            # 合格条件をチェック
            best_result = sorted_results[0]
            if best_result["passed"]:
                print(f"\n[合格条件を達成しました！]")
                print(f"  合計スコア: {best_result['total_score']}/40")
                print(f"  キャラクター: {best_result['character_appearance']}/10")
                print(f"  ポーズ: {best_result['pose_composition_spatial']}/10")
                print(f"  背景: {best_result['background_environment_props']}/10")
                print(f"  色・光: {best_result['color_lighting_atmosphere']}/10")
                return  # 合格した場合は終了

            for i in range(num_survivors):
                survivors.append(sorted_results[i]["individual"])
                sorted_results[i]["selected"] = True

            print(f"VLMが{num_survivors}個を選択しました")

        else:
            # インタラクティブ選択
            print("\nどちらの画像が良いですか？")

            for i in range(0, len(results), PAIR_SIZE):
                if i + PAIR_SIZE > len(results):
                    break

                r1 = results[i]
                r2 = results[i + 1]

                print(f"\nペア {i // PAIR_SIZE}:")
                print(f"  0: {r1['prompt']}")
                print(f"     合計スコア: {r1['total_score']:.0f}/40")
                print(f"     合格: {'はい' if r1['passed'] else 'いいえ'}")
                print(f"     画像: {r1['image_path']}")
                print(f"  1: {r2['prompt']}")
                print(f"     合計スコア: {r2['total_score']:.0f}/40")
                print(f"     合格: {'はい' if r2['passed'] else 'いいえ'}")
                print(f"     画像: {r2['image_path']}")

                choice = input("選択 (0-1, qで終了): ").strip().lower()

                if choice == "q":
                    print("終了します")
                    return

                if choice == "0":
                    survivors.append(r1["individual"])
                    r1["selected"] = True
                elif choice == "1":
                    survivors.append(r2["individual"])
                    r2["selected"] = True

        if not survivors:
            print("生存者がいません")
            break

        # 履歴の記録
        for i, result in enumerate(results):
            workflow._add_history_entry(
                generation=generation,
                individual_id=i,
                prompt=result["prompt"],
                seed=result["seed"],
                image_path=result["image_path"] or gen_dir / f"indiv_{i:02d}.png",
                score=result["score"],
                selected=result["selected"]
            )

        # 次世代の作成
        population = population.create_next_generation(survivors)
        print(f"\n次世代を{len(population.individuals)}個体作成しました")

        # 継続確認
        cont = input("次の世代に進みますか？ (y/N): ").strip().lower()
        if cont != "y":
            print("終了しました")
            break

    # サマリーの表示
    summary = workflow.get_session_summary()
    print("\n=== セッションサマリー ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

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
    print("2. フルワークフローモード（基本タグ入力）")
    print("3. スライド解析モード（スライドから仕様書抽出）")

    choice = input("選択 (1-3): ").strip()

    if choice == "1":
        simple_test_mode()
    elif choice == "2":
        full_workflow_mode()
    elif choice == "3":
        slide_workflow_mode()
    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()