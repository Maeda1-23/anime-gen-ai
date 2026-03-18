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

from prompt_auto_improvement.utils import load_api_key
from prompt_auto_improvement.vlm.gemini_api import GeminiVLM
from prompt_auto_improvement.imggen.comfyui import ComfyUIGenerator
from prompt_auto_improvement.config import SystemConfig, load_or_create_config
from prompt_auto_improvement.runner import ExperimentRunner


def test_gemini_connection(api_key: str) -> bool:
    """Gemini API接続をテスト"""
    print("Gemini API接続テスト中...")
    try:
        client = GeminiVLM(api_key)
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
    """ComfyUI接続をテスト"""
    print("ComfyUI接続テスト中...")
    try:
        client = ComfyUIGenerator(config.comfyui_config)
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

    if not test_comfyui_connection(config):
        print("ComfyUI接続に失敗しました")
        return

    # VLMと画像生成器を初期化して実験を実行
    vlm = GeminiVLM(api_key)
    imggen = ComfyUIGenerator(config.comfyui_config)

    runner = ExperimentRunner(
        vlm=vlm,
        imggen=imggen,
        config=config,
    )
    runner.run()


def full_workflow_mode():
    """フルワークフローモード - 遺伝的アルゴリズムによる画像生成と自動改善"""
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
    comfyui_client = ComfyUIGenerator(config.comfyui_config)
    gemini_client = GeminiVLM(api_key)

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
                image_path = comfyui_client.generate_image(
                    positive_prompt=prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    seed=seed,
                    output_dir=gen_dir
                )

                analysis = gemini_client.analyze_image_detailed(image_path)

                quality = analysis.get("quality_assessment", 5.0)
                total_score = int(quality * 4)
                character_appearance = int(quality)
                pose_composition_spatial = int(quality)
                background_environment_props = int(quality)
                color_lighting_atmosphere = int(quality)

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
            print("\nVLMによる自動選択を実行...")
            sorted_results = sorted(results, key=lambda x: x["total_score"], reverse=True)
            num_survivors = max(2, len(results) // 2)

            best_result = sorted_results[0]
            if best_result["passed"]:
                print(f"\n[合格条件を達成しました！]")
                print(f"  合計スコア: {best_result['total_score']}/40")
                return

            for i in range(num_survivors):
                survivors.append(sorted_results[i]["individual"])
                sorted_results[i]["selected"] = True

            print(f"VLMが{num_survivors}個を選択しました")

        if not survivors:
            print("生存者がいません")
            break

        # 次世代の作成
        population = population.create_next_generation(survivors)
        print(f"\n次世代を{len(population.individuals)}個体作成しました")

        cont = input("次の世代に進みますか？ (y/N): ").strip().lower()
        if cont != "y":
            print("終了しました")
            break

    summary = workflow.get_session_summary()
    print("\n=== セッションサマリー ===")
    for key, value in summary.items():
        print(f"{key}: {value}")


def simple_test_mode():
    """簡単なテストモード"""
    print("\n=== テストモード ===")

    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        return

    if not test_gemini_connection(api_key):
        print("Gemini API接続に失敗しました")
        return

    config = load_or_create_config()

    test_prompt = "1girl, solo, anime style, cute, detailed, masterpiece, best quality"
    print(f"\nテストプロンプト: {test_prompt}")

    comfyui_client = ComfyUIGenerator(config.comfyui_config)
    gemini_client = GeminiVLM(api_key)

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
