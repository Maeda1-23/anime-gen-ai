# ワークフローマネージャー
# 遺伝的アルゴリズムとGemini APIを組み合わせたアニメ制作ワークフロー

import os
import csv
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from gemini_client import GeminiClient
from genetic_algorithm import Individual, Population, GenerationInfo, create_default_mutation_pool

@dataclass
class SelectionResult:
    """選択結果を管理するクラス"""
    individual: Individual
    prompt: str
    image_path: Path
    score: float
    selected: bool

class WorkflowManager:
    """アニメ制作ワークフローの管理クラス"""

    def __init__(
        self,
        client: GeminiClient,
        base_tags: List[str],
        mutation_pool: Dict[str, List[str]] = None,
        population_size: int = 6,
        pair_size: int = 2,
        quality_suffix: str = "masterpiece, best quality"
    ):
        """初期化

        Args:
            client: GeminiClientインスタンス
            base_tags: 基本タグ（キャラクター指定など）
            mutation_pool: 変異プール
            population_size: 個体群サイズ
            pair_size: 選択時のペアサイズ
            quality_suffix: 品質サフィックス
        """
        self.client = client
        self.base_tags = base_tags
        self.mutation_pool = mutation_pool if mutation_pool else create_default_mutation_pool()
        self.population_size = population_size
        self.pair_size = pair_size
        self.quality_suffix = quality_suffix

        # セッション情報
        self.session_dir: Optional[Path] = None
        self.history_file: Optional[Path] = None
        self.current_generation = 0

    def create_session(self, base_dir: Path = Path("output")) -> Path:
        """セッションを作成

        Args:
            base_dir: ベースディレクトリ

        Returns:
            セッションディレクトリパス
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = base_dir / f"session_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 履歴ファイルの作成
        self.history_file = self.session_dir / "history.csv"
        self._init_history_file()

        print(f"セッションディレクトリ: {self.session_dir}")
        return self.session_dir

    def _init_history_file(self):
        """履歴ファイルの初期化"""
        if self.history_file:
            with open(self.history_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "generation", "individual_id", "prompt", "seed",
                    "image_path", "score", "selected"
                ])

    def _add_history_entry(self, generation: int, individual_id: int, prompt: str,
                          seed: int, image_path: Path, score: float, selected: bool):
        """履歴エントリを追加

        Args:
            generation: 世代番号
            individual_id: 個体ID
            prompt: プロンプト
            seed: シード値
            image_path: 画像パス
            score: スコア
            selected: 選択されたか
        """
        if self.history_file:
            with open(self.history_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    generation, individual_id, prompt, seed,
                    str(image_path), score, selected
                ])

    def generate_images_for_generation(self, individuals: List[Individual]) -> List[SelectionResult]:
        """1世代分の画像を生成

        Args:
            individuals: 個体のリスト

        Returns:
            生成結果のリスト
        """
        if not self.session_dir:
            raise RuntimeError("セッションが作成されていません")

        gen_dir = self.session_dir / f"gen_{self.current_generation:03d}"
        gen_dir.mkdir(parents=True, exist_ok=True)

        results: List[SelectionResult] = []

        for i, indiv in enumerate(individuals):
            prompt = indiv.get_prompt()
            seed = random.randint(0, 2**32 - 1)

            # 画像パスの決定
            image_path = gen_dir / f"indiv_{i:02d}_seed_{seed}.png"

            # TODO: 実際の画像生成を実装
            # 現在はダミーの画像生成
            print(f"[{i}] 生成中: {prompt}")
            print(f"    -> {image_path}")

            # ダミーのスコア（実際はVLMで評価）
            score = random.uniform(0.5, 1.0)

            results.append(SelectionResult(
                individual=indiv,
                prompt=prompt,
                image_path=image_path,
                score=score,
                selected=False
            ))

        return results

    def select_survivors(self, results: List[SelectionResult]) -> List[Individual]:
        """ユーザーによる選択を実行

        Args:
            results: 生成結果のリスト

        Returns:
            選択された個体のリスト
        """
        survivors: List[Individual] = []

        # ペアごとに選択
        for i in range(0, len(results), self.pair_size):
            if i + 1 >= len(results):
                break

            pair_start = i // self.pair_size
            print(f"\nペア {pair_start}:")

            # ペアの表示
            for j in range(self.pair_size):
                idx = i + j
                result = results[idx]
                print(f"  {j}: {result.prompt}")
                print(f"     画像: {result.image_path}")
                print(f"     スコア: {result.score:.2f}")

            # 選択
            while True:
                choice = input("どちらが良いですか？ (0-1, qで終了): ").strip().lower()

                if choice == "q":
                    print("終了します")
                    return []

                if choice in ["0", "1"]:
                    selected_idx = i + int(choice)
                    survivors.append(results[selected_idx].individual)
                    results[selected_idx].selected = True
                    break

                print("無効な入力です")

        return survivors

    def ai_assisted_selection(self, results: List[SelectionResult]) -> List[Individual]:
        """AIによる自動選択（Geminiを使用）

        Args:
            results: 生成結果のリスト

        Returns:
            選択された個体のリスト
        """
        # TODO: 実装
        # Geminiを使って画像を分析し、自動で選択
        print("\nAIによる自動選択を実装中...")

        # 今のところはスコアが高いものを選択
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)

        # 上位50%を選択
        num_survivors = max(2, len(results) // 2)
        survivors = [r.individual for r in sorted_results[:num_survivors]]

        for r in sorted_results[:num_survivors]:
            r.selected = True

        print(f"AIが{num_survivors}個を選択しました")
        return survivors

    def run_evolutionary_loop(self, max_generations: int = 10):
        """進化的ループを実行

        Args:
            max_generations: 最大世代数
        """
        print("\n=== アニメ制作進化的ループ ===")

        # 初期個体群の作成
        population = Population.create_random_population(
            size=self.population_size,
            base_tags=self.base_tags,
            mutation_pool=self.mutation_pool,
            quality_suffix=self.quality_suffix
        )

        print(f"初期個体群: {self.population_size}個体を作成しました")

        # 進化的ループ
        for gen in range(max_generations):
            self.current_generation = gen

            print(f"\n--- 第{gen + 1}世代 ---")

            # 画像生成
            results = self.generate_images_for_generation(population.individuals)

            # 履歴の記録
            for i, result in enumerate(results):
                self._add_history_entry(
                    generation=gen,
                    individual_id=i,
                    prompt=result.prompt,
                    seed=0,  # TODO: 実際のシードを設定
                    image_path=result.image_path,
                    score=result.score,
                    selected=result.selected
                )

            # 選択モード
            use_ai = input("AIによる自動選択を使用しますか？ (y/N): ").strip().lower() == "y"

            if use_ai:
                survivors = self.ai_assisted_selection(results)
            else:
                survivors = self.select_survivors(results)

            if not survivors:
                print("終了しました")
                break

            # 次世代の作成
            population = population.create_next_generation(survivors)

            print(f"次世代を{len(population.individuals)}個体作成しました")

            # 継続確認
            cont = input(f"次の世代に進みますか？ (y/N): ").strip().lower()
            if cont != "y":
                print("終了しました")
                break

    def get_session_summary(self) -> Dict[str, Any]:
        """セッションのサマリーを取得

        Returns:
            セッション情報の辞書
        """
        if not self.session_dir:
            return {}

        summary = {
            "session_dir": str(self.session_dir),
            "generation": self.current_generation,
            "history_file": str(self.history_file) if self.history_file else None,
            "base_tags": self.base_tags,
            "population_size": self.population_size,
        }

        return summary

# ユーティリティ関数
def run_interactive_workflow(client: GeminiClient):
    """対話的なワークフローを実行

    Args:
        client: GeminiClientインスタンス
    """
    print("\n=== アニメ制作ワークフローの設定 ===")

    # 基本タグの入力
    base_input = input("基本タグを入力（例: 1girl, solo）: ").strip()
    if not base_input:
        base_tags = ["1girl", "solo"]
    else:
        base_tags = [t.strip() for t in base_input.split(",") if t.strip()]

    print(f"基本タグ: {', '.join(base_tags)}")

    # 変異プールの確認
    mutation_pool = create_default_mutation_pool()
    print(f"変異プールカテゴリ: {list(mutation_pool.keys())}")

    # ワークフローマネージャーの作成
    workflow = WorkflowManager(
        client=client,
        base_tags=base_tags,
        mutation_pool=mutation_pool,
        population_size=6,
        pair_size=2
    )

    # セッションの作成
    workflow.create_session()

    # 進化的ループの実行
    workflow.run_evolutionary_loop(max_generations=10)

    # サマリーの表示
    summary = workflow.get_session_summary()
    print("\n=== セッションサマリー ===")
    for key, value in summary.items():
        print(f"{key}: {value}")