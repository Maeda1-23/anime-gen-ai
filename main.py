# アニメ制作自動化システムのメインエントリーポイント
# ComfyUI（Intel ARC GPU）とGemini APIを統合した完全なワークフロー

import os
import sys
import random
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    from dotenv import load_dotenv
except ImportError:
    print("警告: python-dotenvがインストールされていません")
    print("インストールコマンド: pip install python-dotenv")
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

def get_initial_prompt_from_user(config: SystemConfig) -> Tuple[str, str]:
    """ユーザーから初期プロンプトを取得

    Args:
        config: システム設定

    Returns:
        (positive_prompt, negative_prompt) のタプル
    """
    print("\n=== 初期プロンプトの設定 ===")

    # 基本タグの入力
    base_tags_input = input("基本タグを入力してください (例: 1girl, solo) [デフォルト: 1girl, solo]: ").strip()
    if not base_tags_input:
        base_tags = "1girl, solo"
    else:
        base_tags = base_tags_input

    # Negativeプロンプト
    negative_input = input("Negativeプロンプトを入力してください [デフォルト: worst quality, low quality]: ").strip()
    if not negative_input:
        negative_prompt = "worst quality, low quality"
    else:
        negative_prompt = negative_input

    # 詳細な説明を追加
    detail_input = input("詳細な説明を追加してください (例: 可愛い, ショートヘア, 制服) [デフォルト: なし]: ").strip()
    if detail_input:
        # 詳細を英語タグに変換（ここでは単純に追加）
        base_tags = f"{base_tags}, {detail_input}"

    return base_tags, negative_prompt

def generate_images_with_comfyui(
    config: SystemConfig,
    comfyui_client: ComfyUIClient,
    prompts: List[str],
    negative_prompt: str
) -> List[Tuple[str, Path]]:
    """ComfyUIで画像を一括生成

    Args:
        config: システム設定
        comfyui_client: ComfyUIクライアント
        prompts: プロンプトリスト
        negative_prompt: Negativeプロンプト

    Returns:
        [(プロンプト, 画像パス)] のリスト
    """
    results = []

    print(f"\n=== 画像生成開始（{len(prompts)}枚）===")

    for i, prompt in enumerate(prompts):
        try:
            print(f"[{i+1}/{len(prompts)}] 生成中: {prompt[:50]}...")

            # シード値をランダムに設定
            seed = random.randint(0, 2**32 - 1)

            # 出力先のディレクトリを作成
            output_dir = config.output_dir / "temp_gen"
            output_dir.mkdir(parents=True, exist_ok=True)

            # ComfyUIで画像生成
            image_path = comfyui_client.generate_image(
                positive_prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                output_dir=output_dir
            )

            print(f"[{i+1}/{len(prompts)}] 保存: {image_path}")
            results.append((prompt, image_path))

            # 少し待機（ComfyUIの負荷軽減のため）
            time.sleep(0.5)

        except Exception as e:
            print(f"[{i+1}/{len(prompts)}] エラー: {e}")
            # エラーの場合でも処理を続ける

    print(f"\n=== 画像生成完了: {len(results)}枚 ===")
    return results

def analyze_images_with_gemini(
    gemini_client: GeminiClient,
    image_results: List[Tuple[str, Path]]
) -> List[Dict[str, Any]]:
    """Gemini APIで画像を一括分析

    Args:
        gemini_client: Geminiクライアント
        image_results: 画像生成結果のリスト

    Returns:
        分析結果のリスト
    """
    analyses = []

    print(f"\n=== 画像分析開始（{len(image_results)}枚）===")

    for i, (prompt, image_path) in enumerate(image_results):
        try:
            print(f"[{i+1}/{len(image_results)}] 分析中: {image_path.name}...")

            # Gemini APIで画像分析
            result = gemini_client.analyze_image_detailed(image_path)

            analyses.append({
                "prompt": prompt,
                "image_path": str(image_path),
                "analysis": result
            })

            print(f"[{i+1}/{len(image_results)}] 分析完了: 品質 {result.get('quality_assessment', 'N/A')}/10")

            # 少し待機（APIレート制限を考慮）
            time.sleep(0.3)

        except Exception as e:
            print(f"[{i+1}/{len(image_results)}] 分析エラー: {e}")
            # エラー情報を記録
            analyses.append({
                "prompt": prompt,
                "image_path": str(image_path),
                "analysis": {
                    "character_features": "分析に失敗しました",
                    "expression": "不明",
                    "pose": "不明",
                    "background": "不明",
                    "artistic_style": "不明",
                    "quality_assessment": 0,
                    "suggestions": ["再試行してください"],
                    "danbooru_tags": {
                        "positive": prompt,
                        "negative": "worst quality, low quality"
                    }
                }
            })

    print(f"\n=== 画像分析完了: {len(analyses)}枚 ===")
    return analyses

def display_analysis_results(analyses: List[Dict[str, Any]]):
    """分析結果を表示

    Args:
        analyses: 分析結果のリスト
    """
    print("\n" + "=" * 60)
    print("分析結果サマリー")
    print("=" * 60)

    for i, result in enumerate(analyses):
        analysis = result["analysis"]
        print(f"\n画像 {i+1}:")
        print(f"  プロンプト: {result['prompt'][:60]}...")
        print(f"  ファイル: {Path(result['image_path']).name}")
        print(f"  品質スコア: {analysis.get('quality_assessment', 'N/A')}/10")
        print(f"  キャラクターの特徴: {analysis.get('character_features', 'N/A')[:40]}...")
        print(f"  表情: {analysis.get('expression', 'N/A')}")
        print(f"  ポーズ: {analysis.get('pose', 'N/A')}")

        # 改善提案がある場合
        suggestions = analysis.get('suggestions', [])
        if suggestions:
            print(f"  改善提案: {', '.join(suggestions[:2])}")

    print("\n" + "=" * 60)

def select_best_image(analyses: List[Dict[str, Any]]) -> int:
    """ユーザーが最良の画像を選択

    Args:
        analyses: 分析結果のリスト

    Returns:
        選択された画像のインデックス
    """
    print("\n=== 画像選択 ===")

    for i, result in enumerate(analyses):
        analysis = result["analysis"]
        score = analysis.get('quality_assessment', 0)

        print(f"[{i+1}] {Path(result['image_path']).name}")
        print(f"    品質スコア: {score}/10")
        print(f"    特徴: {analysis.get('character_features', 'N/A')[:30]}...")

    print("\n最も品質が高かった画像の番号を入力してください（qで終了）:")
    choice = input("> ").strip()

    if choice.lower() == 'q':
        return -1

    try:
        selected_idx = int(choice) - 1
        if 0 <= selected_idx < len(analyses):
            print(f"\n選択された画像: 選択 {selected_idx + 1}")
            return selected_idx
        else:
            print(f"\n無効な選択です: 1から{len(analyses)}の間")
            return select_best_image(analyses)
    except ValueError:
        print("\n無効な入力です。数字を入力してください。")
        return select_best_image(analyses)

def generate_improved_prompts(
    gemini_client: GeminiClient,
    analyses: List[Dict[str, Any]]
) -> List[str]:
    """Gemini APIを使って改善プロンプトを生成

    Args:
        gemini_client: Geminiクライアント
        analyses: 分析結果のリスト

    Returns:
        改善されたプロンプトリスト
    """
    improved_prompts = []

    print(f"\n=== プロンプト改善提案生成（{len(analyses)}枚）===")

    for i, result in enumerate(analyses):
        try:
            prompt = result['prompt']
            image_path = Path(result['image_path'])

            print(f"[{i+1}/{len(analyses)}] 改善案生成中...")

            # Gemini APIで改善提案を取得
            improvement = gemini_client.generate_improvement_suggestions(
                image_path=image_path,
                current_prompt=prompt
            )

            improved_prompt = improvement.get('improved_prompt', prompt)
            improved_prompts.append(improved_prompt)

            # 問題点を表示
            current_issues = improvement.get('current_issues', [])
            if current_issues:
                print(f"[{i+1}/{len(analyses)}] 問題点: {', '.join(current_issues[:2])}")

            print(f"[{i+1}/{len(analyses)}] 改善完了")

            # 少し待機（APIレート制限を考慮）
            time.sleep(0.3)

        except Exception as e:
            print(f"[{i+1}/{len(analyses)}] 改善生成エラー: {e}")
            # エラーの場合は元のプロンプトを使用
            improved_prompts.append(result['prompt'])

    print(f"\n=== プロンプト改善完了: {len(improved_prompts)}枚 ===")
    return improved_prompts

def save_session_results(
    config: SystemConfig,
    analyses: List[Dict[str, Any]],
    improved_prompts: List[str],
    selected_idx: int
):
    """セッション結果を保存

    Args:
        config: システム設定
        analyses: 分析結果のリスト
        improved_prompts: 改善されたプロンプトリスト
        selected_idx: 選択されたインデックス
    """
    if not config.session_dir:
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_result_dir = config.session_dir / "results"
    session_result_dir.mkdir(parents=True, exist_ok=True)

    # 分析結果をCSVに保存
    csv_file = session_result_dir / "analysis_results.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        f.write("index,prompt,image_path,quality_score,selected\n")

        for i, (analysis_result, improved_prompt) in enumerate(zip(analyses, improved_prompts)):
            analysis = analysis_result["analysis"]
            is_selected = (i == selected_idx)
            score = analysis.get('quality_assessment', 0)

            f.write(f"{i},{analysis_result['prompt']},{analysis_result['image_path']},{score},{is_selected}\n")

    # 選択された画像をメインディレクトリにコピー
    if selected_idx >= 0 and selected_idx < len(analyses):
        selected_result = analyses[selected_idx]
        selected_path = Path(selected_result['image_path'])

        if selected_path.exists():
            best_image_dir = config.output_dir / "best_images"
            best_image_dir.mkdir(parents=True, exist_ok=True)

            import shutil
            dest_path = best_image_dir / f"best_{timestamp}.png"
            shutil.copy2(selected_path, dest_path)
            print(f"\n最良の画像を保存: {dest_path}")

    # 改善されたプロンプトを保存
    prompts_file = session_result_dir / "improved_prompts.txt"
    with open(prompts_file, "w", encoding="utf-8") as f:
        for i, prompt in enumerate(improved_prompts):
            f.write(f"Prompt {i+1}:\n{prompt}\n\n")

    print(f"\nセッション結果を保存しました: {session_result_dir}")
    print(f"  - 分析結果: {csv_file}")
    print(f"  - 改善プロンプト: {prompts_file}")

def run_full_workflow(config: SystemConfig, max_generations: int = 3):
    """完全なワークフローを実行

    Args:
        config: システム設定
        max_generations: 最大世代数
    """
    print("\n" + "=" * 60)
    print("アニメ制作自動化ワークフロー開始")
    print("=" * 60)

    # セッションディレクトリを作成
    session_dir = config.create_session_dir()
    print(f"\nセッションディレクトリ: {session_dir}")

    # ComfyUIクライアントの初期化
    comfyui_client = ComfyUIClient(config.comfyui_config)

    # Geminiクライアントの初期化
    api_key = load_api_key()
    if not api_key:
        print("エラー: GEMINI_API_KEYが設定されていません")
        return

    gemini_client = GeminiClient(api_key)

    # 最初のプロンプトを取得
    positive_prompt, negative_prompt = get_initial_prompt_from_user(config)

    # 初期プロンプトリスト（複数のバリエーションを作成）
    prompts = [
        positive_prompt,
        f"{positive_prompt}, cute",
        f"{positive_prompt}, beautiful",
        f"{positive_prompt}, detailed",
    ]

    # 世代ループ
    for generation in range(max_generations):
        print("\n" + "=" * 60)
        print(f"第 {generation + 1} 世代")
        print("=" * 60)

        # ステップ1: ComfyUIで画像生成
        image_results = generate_images_with_comfyui(
            config=config,
            comfyui_client=comfyui_client,
            prompts=prompts,
            negative_prompt=negative_prompt
        )

        # ステップ2: Gemini APIで画像分析
        analyses = analyze_images_with_gemini(
            gemini_client=gemini_client,
            image_results=image_results
        )

        # ステップ3: 分析結果を表示
        display_analysis_results(analyses)

        # ステップ4: ユーザーが選択
        selected_idx = select_best_image(analyses)

        if selected_idx < 0:
            print("\n終了します")
            break

        # ステップ5: 結果を保存
        save_session_results(
            config=config,
            analyses=analyses,
            improved_prompts=prompts,
            selected_idx=selected_idx
        )

        # ステップ6: 改善されたプロンプトで次世代のプロンプトリストを作成
        if generation < max_generations - 1:
            print("\n次世代のためのプロンプトを生成中...")
            prompts = generate_improved_prompts(
                gemini_client=gemini_client,
                analyses=analyses
            )

            # いくつかの元の良いプロンプトを残す
            if selected_idx < len(prompts):
                # 選択されたものは優先して残す
                best_prompt = prompts[selected_idx]
                prompts[0] = best_prompt
        else:
            # 最終世代なので、すべてのプロンプトを使用
            pass

    print("\n" + "=" * 60)
    print("ワークフロー完了")
    print("=" * 60)

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

    # ComfyUI接続テスト
    if not test_comfyui_connection(config):
        print("ComfyUI接続に失敗しました")
        print("ComfyUIを起動してください: C:\\Users\\T25ma\\artwork\\run_comfyui_arc.bat")
        return

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

    # メニューの表示
    print("\n選択してください:")
    print("1. 完全なワークフロー実行（推奨）")
    print("2. 簡単なテストモード")
    print("3. 設定チェック")
    print("4. 終了")

    choice = input("選択 (1-4): ").strip()

    if choice == "1":
        # 完全なワークフロー
        config = load_or_create_config()

        # 最大世代数の入力
        max_gen_input = input("最大世代数を入力してください [デフォルト: 3]: ").strip()
        max_generations = int(max_gen_input) if max_gen_input else 3

        # 世代数を確認
        print(f"\n{max_generations}世代のワークフローを実行します")
        confirm = input("実行しますか？ (y/N): ").strip().lower()

        if confirm == 'y':
            run_full_workflow(config, max_generations=max_generations)
        else:
            print("キャンセルしました")

    elif choice == "2":
        # 簡単なテストモード
        simple_test_mode()

    elif choice == "3":
        # 設定チェック
        config = load_or_create_config()
        print("\n現在の設定:")
        print(f"  ComfyUIサーバー: {config.comfyui_config.server_address}")
        print(f"  出力ディレクトリ: {config.output_dir}")
        print(f"  画像サイズ: {config.image_width}x{config.image_height}")
        print(f"  デフォルトステップ: {config.default_steps}")
        print(f"  デフォルトCFG: {config.default_cfg}")

    elif choice == "4":
        print("終了します")

    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()