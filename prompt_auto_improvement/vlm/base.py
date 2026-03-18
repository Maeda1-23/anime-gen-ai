# VLMクライアントの抽象基底クラス

from abc import ABC, abstractmethod
from typing import List, Optional
from PIL import Image


class VLMClient(ABC):
    """視覚言語モデルクライアントの抽象基底クラス"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        images: Optional[List[Image.Image]] = None,
        temperature: float = 0.7
    ) -> str:
        """プロンプトと画像からテキストを生成

        Args:
            prompt: テキストプロンプト
            images: PIL画像のリスト（省略可）
            temperature: 生成の多様性（0.0-1.0）

        Returns:
            生成されたテキスト
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """接続テスト

        Returns:
            接続成功時はTrue
        """
        pass
