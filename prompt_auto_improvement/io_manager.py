# セッションとファイルの管理

import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class ExperimentIO:
    """実験のセッション管理とファイルI/O"""

    def __init__(self, output_dir: Path = Path("output")):
        """初期化

        Args:
            output_dir: 出力ベースディレクトリ
        """
        self.output_dir = output_dir
        self.session_dir: Optional[Path] = None
        self.history_file: Optional[Path] = None

    def create_session(self) -> Path:
        """セッションディレクトリを作成

        Returns:
            セッションディレクトリのパス
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"session_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.session_dir / "history.csv"
        self._init_history()

        print(f"セッションディレクトリ: {self.session_dir}")
        return self.session_dir

    def _init_history(self):
        """履歴ファイルの初期化"""
        if self.history_file:
            with open(self.history_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "loop", "image_id", "prompt", "seed",
                    "image_path", "total_score", "passed"
                ])

    def add_history_entry(
        self,
        loop: int,
        image_id: int,
        prompt: str,
        seed: int,
        image_path: Path,
        total_score: float,
        passed: bool
    ):
        """履歴エントリを追加"""
        if self.history_file:
            with open(self.history_file, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    loop, image_id, prompt, seed,
                    str(image_path), total_score, passed
                ])

    def create_loop_dir(self, loop_idx: int) -> Path:
        """ループ用のディレクトリを作成"""
        if not self.session_dir:
            raise RuntimeError("セッションが作成されていません")
        loop_dir = self.session_dir / f"loop_{loop_idx:03d}"
        loop_dir.mkdir(parents=True, exist_ok=True)
        return loop_dir

    def write_json(self, path: Path, data: Any):
        """JSONファイルを書き込む"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def write_text(self, path: Path, text: str):
        """テキストファイルを書き込む"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
