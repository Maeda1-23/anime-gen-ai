# 画像生成器の抽象基底クラス

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ImageGenerator(ABC):
    """画像生成器の抽象基底クラス"""

    @abstractmethod
    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        output_dir: Path = Path("output")
    ) -> Path:
        """画像を生成

        Args:
            positive_prompt: ポジティブプロンプト
            negative_prompt: ネガティブプロンプト
            seed: シード値（Noneの場合はランダム）
            output_dir: 出力ディレクトリ

        Returns:
            生成された画像のパス
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """接続テスト

        Returns:
            接続成功時はTrue
        """
        pass
