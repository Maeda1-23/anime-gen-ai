# Anime Gen AI - アニメ制作自動化システム

ComfyUI (Intel ARC GPU) と Gemini API を統合した、アニメキャラクター自動生成・評価システム。

## 機能概要

- **ComfyUI連携**: Intel ARC GPUで動作するComfyUIを使用した高画質アニメ画像生成
- **Gemini APIによる分析**: 生成された画像の自動評価と改善提案
- **スライド解析**: スライド画像から仕様書(SpecPack)を自動抽出
- **遺伝的アルゴリズム**: プロンプトの進化的改善による最適化
- **ワークフロー管理**: モジュール化された設計で柔軟な構成変更が可能

## 実行モード

### 1. テストモード
ComfyUIでの画像生成とGemini APIでの分析をテストします。

### 2. フルワークフローモード
基本タグを入力して、遺伝的アルゴリズムによる画像生成・改善ループを実行します。

### 3. スライド解析モード
スライド画像を解析して仕様書を抽出し、それに基づいて画像を生成します。

## システム要件

- Python 3.10+
- Intel ARC GPU (またはCUDA対応NVIDIA GPU)
- ComfyUI (ローカル実行)
- Google Gemini APIキー

## インストール手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/Maeda1-23/anime-gen-ai.git
cd anime-gen-ai
```

### 2. 仮想環境の作成

```bash
python -m venv ../venv
# Windows
../venv/Scripts/activate
# Linux/Mac
source ../venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env`ファイルを作成して、APIキーを設定します。

```
GEMINI_API_KEY=your_api_key_here
```

### 5. ComfyUIの設定

ComfyUIを以下のアドレスで実行してください：
- デフォルト: `http://127.0.0.1:8188`

### 6. モデルの配置

アニメ特化モデルをComfyUIのcheckpointsディレクトリに配置します：
- 推奨: `AnythingXL_xl.safetensors`
- 配置場所: `ComfyUI/models/checkpoints/`

## 使用方法

### プログラムの実行

```bash
python main.py
```

実行モードを選択します：
- `1`: テストモード
- `2`: フルワークフローモード（基本タグ入力）
- `3`: スライド解析モード（スライドから仕様書抽出）

### スライド解析モードの使用方法

1. スライド画像を `slide_images/` ディレクトリに配置
2. プログラム実行時にモード3を選択
3. Gemini APIがスライドを解析して仕様書を生成
4. 仕様書に基づいて画像を自動生成・改善

### プログラムからの使用

```python
from gemini_client import GeminiClient, load_api_key
from comfyui_client import ComfyUIClient
from config import load_or_create_config
from spec_pack import SpecPackExtractor

# 設定の読み込み
config = load_or_create_config()
api_key = load_api_key()

# クライアントの初期化
comfyui_client = ComfyUIClient(config.comfyui_config)
gemini_client = GeminiClient(api_key)

# 画像生成
image_path = comfyui_client.generate_image(
    positive_prompt="1girl, anime style, cute, masterpiece",
    negative_prompt="worst quality, low quality",
    seed=12345
)

# 画像分析
analysis = gemini_client.analyze_image_detailed(image_path)
print(analysis['quality_assessment'])

# スライド解析
from pathlib import Path
extractor = SpecPackExtractor(gemini_client)
slide_files = list(Path("slide_images").glob("*.png"))
specpack = extractor.extract_from_slides(slide_files)
```

## プロジェクト構成

```
anime-gen-ai/
├── main.py                 # メインエントリーポイント
├── gemini_client.py        # Gemini APIクライアント
├── comfyui_client.py       # ComfyUI連携クライアント
├── config.py               # 設定管理
├── spec_pack.py            # スライド解析とSpecPack生成
├── genetic_algorithm.py    # 遺伝的アルゴリズム
├── workflow_manager.py     # ワークフロー管理
├── workflow.json           # ComfyUIワークフローテンプレート
├── prompt_tag_pool.csv     # タグプール（変異用）
├── config.json             # システム設定ファイル（自動生成）
├── slide_images/           # スライド画像格納ディレクトリ
├── output/                 # 生成された画像の出力先
├── logs/                   # ログファイル
└── temp/                   # 一時ファイル
```

## 使用モデル

### 画像生成モデル

- **AnythingXL_xl.safetensors**: アニメ特化のStable Diffusion XLモデル
  - ComfyUIサーバー: `http://127.0.0.1:8188`

### テキスト・画像理解モデル

- **gemini-3.1-flash-lite-preview**: Google Gemini API（無料で高性能）

## パラメータ設定

### 画質設定
```python
QUALITY = "masterpiece, best quality, very aesthetic, absurdres, newest"
NEGATIVE_PROMPT = "worst quality, comic, multiple views, bad quality, low quality, lowres, displeasing, very displeasing, bad anatomy, bad hands, scan artifacts, monochrome, greyscale, twitter username, jpeg artifacts, 2koma, 4koma, guro, extra digits, fewer digits, jaggy lines, unclear"
```

### 遺伝的アルゴリズム設定
```python
POP_SIZE = 6      # 個体群サイズ
PAIR_SIZE = 2     # 選択ペアサイズ
MAX_GENERATIONS = 10  # 最大世代数
```

## モジュール詳細

### gemini_client.py

Gemini APIを使用した画像理解と分析機能を提供します。

- `analyze_image(image_path, prompt)`: 画像を分析して説明を生成
- `analyze_image_detailed(image_path)`: 構造化された詳細分析を返す
- `compare_images(image_paths)`: 複数画像の比較評価
- `generate_improvement_suggestions(image_path, current_prompt)`: プロンプト改善案の生成
- `generate_text(prompt, temperature)`: テキスト生成

### spec_pack.py

スライド画像から仕様書(SpecPack)を抽出します。

- `extract_from_slides(slide_paths)`: スライドからSpecPackを生成
- `judge_image_with_specpack(image_path, specpack, current_prompt)`: SpecPackに基づく画像評価
- `get_base_tags_from_specpack(specpack)`: SpecPackから基本タグを取得

### genetic_algorithm.py

遺伝的アルゴリズムによるプロンプト最適化を実装します。

- `load_mutation_pool_csv()`: CSVからタグプールを読み込み
- `Individual`: 個体（プロンプト）を表すクラス
- `Population`: 個体群を管理するクラス

### comfyui_client.py

ComfyUIとのWebSocket連携による画像生成機能を提供します。

- `generate_image(positive_prompt, negative_prompt, seed, output_dir)`: 画像を生成
- `test_connection()`: ComfyUIとの接続確認

### config.py

システム設定の管理とセッション管理機能を提供します。

- `load_or_create_config()`: 設定ファイルの読み込みまたは作成
- `create_session_dir()`: セッション用ディレクトリの作成
- `save_to_history()`: 生成履歴の保存

## ライセンス

MIT License

## 作者

Maeda

## 参考情報

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Intel ARC GPU](https://ark.intel.com/content/www/us/en/ark/products/series/228628/intel-arc-gpu.html)
