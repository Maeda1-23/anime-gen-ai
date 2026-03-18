# ユーティリティ関数

import json
import os
import re
from pathlib import Path
from typing import Any, Optional


def extract_json(text: str) -> Optional[str]:
    """テキストからJSONを抽出

    Args:
        text: JSONを含むテキスト

    Returns:
        抽出されたJSON文字列、見つからない場合はNone
    """
    # JSONコードブロックを探す
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1)

    # 最初の { から最後の } までを抽出
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)

    return None


def compact_json(obj: Any) -> str:
    """JSONを一貫した形式に変換

    Args:
        obj: JSON化するオブジェクト

    Returns:
        一貫した形式のJSON文字列
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def load_api_key(env_file: Path = Path(".env")) -> Optional[str]:
    """環境変数からAPIキーを読み込む

    Args:
        env_file: .envファイルのパス

    Returns:
        APIキー、またはNone
    """
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    return os.getenv("GEMINI_API_KEY")
