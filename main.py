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

def full_workflow_mode():
    """フルワークフローモード - 遺伝的アルゴリズムによる画像生成と自動改善"""
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

    # VLMを使用するか
    use_vl = input("VLMによる自動選択を使用しますか？ (y/N): ").strip().lower() == "y"

    # クライアントの初期化
    comfyui_client = ComfyUIClient(config.comfyui_config)
    gemini_client = GeminiClient(api_key)

    # 変異プールの作成
    from genetic_algorithm import create_default_mutation_pool
    mutation_pool = create_default_mutation_pool()

    # 初期個体群の作成
    from genetic_algorithm import Population
    population_size = 6
    population = Population.create_random_population(
        size=population_size,
        base_tags=base_tags,
        mutation_pool=mutation_pool,
        quality_suffix="masterpiece, best quality"
    )

    print(f"\n初期個体群: {population_size}個体を作成しました")

    # セッションの作成
    from workflow_manager import WorkflowManager
    workflow = WorkflowManager(
        client=gemini_client,
        base_tags=base_tags,
        mutation_pool=mutation_pool,
        population_size=population_size,
        pair_size=2,
        quality_suffix="masterpiece, best quality"
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
                    negative_prompt="worst quality, low quality, blurry",
                    seed=seed,
                    output_dir=gen_dir
                )

                # Geminiで画像分析
                analysis = gemini_client.analyze_image_detailed(image_path)
                score = analysis.get("quality_assessment", 5.0) / 10.0

                print(f"    -> {image_path}")
                print(f"    スコア: {score:.2f}/10")

                results.append({
                    "individual": indiv,
                    "prompt": prompt,
                    "seed": seed,
                    "image_path": image_path,
                    "score": score,
                    "selected": False
                })

            except Exception as e:
                print(f"    [NG] エラー: {e}")
                results.append({
                    "individual": indiv,
                    "prompt": prompt,
                    "seed": seed,
                    "image_path": None,
                    "score": 0.0,
                    "selected": False
                })

        # 選択フェーズ
        survivors = []

        if use_vl:
            # VLMによる自動選択
            print("\nVLMによる自動選択を実行...")
            sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
            num_survivors = max(2, len(results) // 2)

            for i in range(num_survivors):
                survivors.append(sorted_results[i]["individual"])
                sorted_results[i]["selected"] = True

            print(f"VLMが{num_survivors}個を選択しました")

        else:
            # インタラクティブ選択
            print("\nどちらの画像が良いですか？")

            for i in range(0, len(results), 2):
                if i + 1 >= len(results):
                    break

                r1 = results[i]
                r2 = results[i + 1]

                print(f"\nペア {i // 2}:")
                print(f"  0: {r1['prompt']}")
                print(f"     スコア: {r1['score']:.2f}/10")
                print(f"     画像: {r1['image_path']}")
                print(f"  1: {r2['prompt']}")
                print(f"     スコア: {r2['score']:.2f}/10")
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
    print("2. フルワークフローモード（遺伝的アルゴリズム）")

    choice = input("選択 (1-2): ").strip()

    if choice == "1":
        simple_test_mode()
    elif choice == "2":
        full_workflow_mode()
    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()