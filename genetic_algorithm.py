# 遺伝的アルゴリズムによるプロンプト進化システム

import random
import copy
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path

# プロンプトを構築する際のカテゴリ順序
CATEGORY_ORDER = [
    "character",      # キャラクターの特徴
    "expression",     # 表情・感情
    "pose",           # ポーズ
    "clothing",       # 服装
    "accessory",      # 小物・アクセサリ
    "background",     # 背景／環境
    "angle",          # アングル／カメラ
    "lighting",       # ライティング
    "style",          # 雰囲気／スタイル
    "atmosphere",     # 雰囲気補助
]

@dataclass
class GenerationInfo:
    """世代情報を管理するクラス"""
    generation: int
    individual_id: int
    prompt: str
    seed: int
    image_path: Path
    score: float = 0.0
    selected: bool = False

class Individual:
    """プロンプトを表現する個体クラス"""

    def __init__(
        self,
        base_tags: List[str],
        variable_tags: Dict[str, List[str]] = None,
        mutation_pool: Dict[str, List[str]] = None,
        quality_suffix: str = "masterpiece, best quality"
    ):
        """初期化

        Args:
            base_tags: 常に維持するタグ（キャラクター指定など）
            variable_tags: カテゴリごとの可変タグ
            mutation_pool: 全タグプール（カテゴリ -> タグリスト）
            quality_suffix: プロンプト末尾に付与する品質タグ
        """
        self.base_tags = base_tags.copy()
        self.variable_tags = variable_tags.copy() if variable_tags else {}
        self.mutation_pool = mutation_pool if mutation_pool else {}
        self.quality_suffix = quality_suffix
        self._sanitize_tags()

    def _sanitize_tags(self):
        """重複タグを除き、baseとvariableの重複も排除"""
        seen = set(self.base_tags)
        new_vars: Dict[str, List[str]] = {}

        for cat, tags in self.variable_tags.items():
            clean_list = []
            for t in tags:
                if t not in seen:
                    clean_list.append(t)
                    seen.add(t)
            if clean_list:
                new_vars[cat] = clean_list

        self.variable_tags = new_vars

    def get_prompt(self) -> str:
        """現在のタグ集合からプロンプト文字列を生成

        Returns:
            カンマ区切りのプロンプト文字列
        """
        parts: List[str] = []

        # base_tagsは先頭にそのまま
        parts.extend(self.base_tags)

        # 定められたカテゴリ順でタグを追加
        for cat in CATEGORY_ORDER:
            if cat in self.variable_tags:
                parts.extend(self.variable_tags[cat])

        # 最後に品質サフィックス
        if self.quality_suffix:
            parts.append(self.quality_suffix)

        return ", ".join(parts)

    def mutate(self) -> "Individual":
        """変異操作: ランダムに1カテゴリを選び、タグを操作

        Returns:
            変異後の新しいIndividual
        """
        child = copy.deepcopy(self)

        # 変異操作の種類
        operations = ["add", "remove", "swap"]
        if not self.variable_tags:
            operations = ["add"]

        op = random.choice(operations)

        if op == "add" and self.mutation_pool:
            # ランダムなカテゴリからタグを追加
            cat = random.choice(list(self.mutation_pool.keys()))
            pool = self.mutation_pool[cat]
            candidate = random.choice(pool)

            # 重複チェック
            exists = (candidate in child.base_tags) or \
                    any(candidate in lst for lst in child.variable_tags.values())

            if not exists:
                child.variable_tags.setdefault(cat, []).append(candidate)

        elif op == "remove":
            # variable_tagsからランダムにタグを削除
            all_tags = []
            for cat, tags in child.variable_tags.items():
                for t in tags:
                    all_tags.append((cat, t))

            if all_tags:
                cat_sel, tag_sel = random.choice(all_tags)
                child.variable_tags[cat_sel].remove(tag_sel)

                # 空になったカテゴリは削除
                if not child.variable_tags[cat_sel]:
                    del child.variable_tags[cat_sel]

        elif op == "swap" and self.mutation_pool:
            # variable_tagsの中からタグを置換
            cats_with_tags = [cat for cat, tags in child.variable_tags.items() if tags]

            if cats_with_tags:
                cat = random.choice(cats_with_tags)
                pool = self.mutation_pool.get(cat, [])

                if pool:
                    candidate = random.choice(pool)
                    idx = random.randrange(len(child.variable_tags[cat]))
                    child.variable_tags[cat][idx] = candidate

        child._sanitize_tags()
        return child

    @classmethod
    def crossover(cls, parent1: "Individual", parent2: "Individual") -> "Individual":
        """交叉操作: 両親のvariable_tagsを混ぜて子を作成

        Args:
            parent1: 親1
            parent2: 親2

        Returns:
            子のIndividual
        """
        base = parent1.base_tags.copy()
        pool = parent1.mutation_pool
        quality = parent1.quality_suffix

        child_vars: Dict[str, List[str]] = {}

        # プール内の各カテゴリについて処理
        for cat in pool.keys():
            tags1 = parent1.variable_tags.get(cat, [])
            tags2 = parent2.variable_tags.get(cat, [])
            combined = list(set(tags1 + tags2))
            random.shuffle(combined)

            # 子はランダムな数だけタグを引き継ぐ
            cut = random.randint(0, len(combined))
            child_tags = combined[:cut]

            if child_tags:
                child_vars[cat] = child_tags

        child = cls(base, child_vars, pool, quality)
        child._sanitize_tags()
        return child

class Population:
    """個体群を管理するクラス"""

    def __init__(self, individuals: List[Individual]):
        """初期化

        Args:
            individuals: 個体のリスト
        """
        self.individuals = individuals

    @classmethod
    def create_random_population(
        cls,
        size: int,
        base_tags: List[str],
        mutation_pool: Dict[str, List[str]],
        quality_suffix: str = "masterpiece, best quality"
    ) -> "Population":
        """ランダムな初期個体群を作成

        Args:
            size: 個体群のサイズ
            base_tags: 基本タグ
            mutation_pool: 変異プール
            quality_suffix: 品質サフィックス

        Returns:
            ランダムなPopulation
        """
        individuals = []

        for _ in range(size):
            variable_tags = {}

            # 各カテゴリからランダムにタグを選択
            for cat, pool in mutation_pool.items():
                if random.random() < 0.3:  # 30%の確率でタグを追加
                    tag = random.choice(pool)
                    variable_tags.setdefault(cat, []).append(tag)

            indiv = Individual(
                base_tags=base_tags,
                variable_tags=variable_tags,
                mutation_pool=mutation_pool,
                quality_suffix=quality_suffix
            )
            individuals.append(indiv)

        return cls(individuals)

    def create_next_generation(self, survivors: List[Individual]) -> "Population":
        """生存者から次世代を作成

        Args:
            survivors: 生存した個体のリスト

        Returns:
            次世代のPopulation
        """
        new_individuals: List[Individual] = []

        # 生存者をシャッフル
        random.shuffle(survivors)

        # 交叉
        for i in range(0, len(survivors) - 1, 2):
            p1 = survivors[i]
            p2 = survivors[i + 1]

            # 2つの子を作成
            child1 = Individual.crossover(p1, p2)
            child2 = Individual.crossover(p2, p1)

            # 変異を適用
            child1 = child1.mutate()
            child2 = child2.mutate()

            new_individuals.extend([child1, child2])

        # 奇数の場合は最後の個体も変異
        if len(survivors) % 2 == 1:
            last_survivor = survivors[-1]
            new_individuals.append(last_survivor.mutate())

        # 不足分を補充
        target_size = len(self.individuals)
        while len(new_individuals) < target_size:
            survivor = random.choice(survivors)
            new_individuals.append(survivor.mutate())

        # サイズ調整
        new_individuals = new_individuals[:target_size]

        return Population(new_individuals)

# ユーティリティ関数
def load_mutation_pool_csv(pool_path: Path = Path("prompt_tag_pool.csv")) -> Dict[str, List[str]]:
    """CSVファイルから変異プールを読み込む

    Args:
        pool_path: CSVファイルのパス

    Returns:
        カテゴリごとのタグリスト
    """
    import csv

    pool: Dict[str, List[str]] = {}

    try:
        with open(pool_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag = row.get("tag", "").strip()
                category = row.get("category", "").strip()

                if tag and category:
                    if category not in pool:
                        pool[category] = []
                    pool[category].append(tag)

        print(f"タグプールをCSVから読み込みました: {pool_path}")
        print(f"カテゴリ数: {len(pool)}, タグ数: {sum(len(tags) for tags in pool.values())}")

        return pool

    except FileNotFoundError:
        print(f"警告: タグプールCSVが見つかりません: {pool_path}")
        print("デフォルトのタグプールを使用します")
        return create_default_mutation_pool()

def create_default_mutation_pool() -> Dict[str, List[str]]:
    """デフォルトの変異プールを作成

    Returns:
        カテゴリごとのタグリスト
    """
    return {
        "expression": ["smile", "blush", "angry", "sad", "surprised", "serious", "worried"],
        "pose": ["standing", "sitting", "lying", "jumping", "running", "looking away", "close up"],
        "clothing": ["school uniform", "dress", "casual clothes", "coat", "swimsuit", "maid outfit"],
        "accessory": ["glasses", "hat", "ribbon", "bag", "book", "phone", "jewelry"],
        "background": ["classroom", "park", "beach", "bedroom", "cafe", "street", "sky"],
        "angle": ["front view", "side view", "back view", "high angle", "low angle", "bird's eye view"],
        "lighting": ["natural light", "artificial light", "sunset", "night", "bright", "dark"],
        "style": ["anime style", "manga style", "realistic", "watercolor", "digital art", "oil painting"],
        "atmosphere": ["peaceful", "energetic", "romantic", "mysterious", "cheerful", "melancholic"]
    }