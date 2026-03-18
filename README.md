# Anime Gen AI - アニメ制作自動化システム

ComfyUI (Intel ARC GPU) と Gemini API を統合した、アニメキャラクター自動生成・評価システム。

## 機能概要

- **ComfyUI連携**: Intel ARC GPUで動作するComfyUIを使用した高画質アニメ画像生成
- **Gemini APIによる分析**: 生成された画像の自動評価と改善提案
- **プロンプト最適化**: 遺伝的アルゴリズムによる自動プロンプト改善
- **ワークフロー管理**: モジュール化された設計で柔軟な構成変更が可能

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

```bash
cp .env.example .env
```

`.env`ファイルに以下の内容を記述：

```
GEMINI_API_KEY=your_api_key_here
```

### 5. ComfyUIの設定

ComfyUIを以下のアドレスで実行してください：
- デフォルト: `http://127.0.0.1:8188`

ワークフローファイルは `workflow.json` で定義されています。

## 使用方法

### 基本的なテスト

```bash
python main.py
```

テストモードが実行され、以下の処理が行われます：
1. ComfyUIで画像を生成
2. Gemini APIで画像を分析
3. 分析結果を表示

### プログラムからの使用

```python
from gemini_client import GeminiClient, load_api_key
from comfyui_client import ComfyUIClient
from config import load_or_create_config

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
```

## プロジェクト構成

```
anime-gen-ai/
├── main.py              # メインエントリーポイント
├── gemini_client.py     # Gemini APIクライアント
├── comfyui_client.py    # ComfyUI連携クライアント
├── config.py            # 設定管理
├── genetic_algorithm.py # 遺伝的アルゴリズム
├── workflow.json        # ComfyUIワークフローテンプレート
├── config.json          # システム設定ファイル（自動生成）
├── output/              # 生成された画像の出力先
├── logs/                # ログファイル
└── temp/                # 一時ファイル
```

## モジュール詳細

### gemini_client.py

Gemini APIを使用した画像理解と分析機能を提供します。

- `analyze_image(image_path, prompt)`: 画像を分析して説明を生成
- `analyze_image_detailed(image_path)`: 構造化された詳細分析を返す
- `compare_images(image_paths)`: 複数画像の比較評価
- `generate_improvement_suggestions(image_path, current_prompt)`: プロンプト改善案の生成

### comfyui_client.py

ComfyUIとのWebSocket連携による画像生成機能を提供します。

- `generate_image(positive_prompt, negative_prompt, seed, output_dir)`: 画像を生成
- `test_connection()`: ComfyUIとの接続確認

### config.py

システム設定の管理とセッション管理機能を提供します。

- `load_or_create_config()`: 設定ファイルの読み込みまたは作成
- `create_session_dir()`: セッション用ディレクトリの作成
- `save_to_history()`: 生成履歴の保存

## ワークフローカスタマイズ

`workflow.json` を編集することで、使用するモデルやノード構成を変更できます。

```json
{
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 0,
      "steps": 20,
      "cfg": 7.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      ...
    }
  },
  ...
}
```

## ライセンス

MIT License

## 作者

Maeda

## 参考情報

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Gemini API](https://ai.google.dev/gemini-api)
- [Intel ARC GPU](https://ark.intel.com/content/www/us/en/ark/products/series/228628/intel-arc-gpu.html)
