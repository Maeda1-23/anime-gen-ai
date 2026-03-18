# ComfyUIクライアント
# Intel ARC GPUで動くComfyUIとの連携用クライアント

import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import websocket


@dataclass
class ComfyUIConfig:
    """ComfyUIの設定"""
    server_address: str = "127.0.0.1:8188"
    workflow_json_path: str = "C:\\Users\\T25ma\\artwork\\ComfyUI\\workflows\\illustrious_template.json"
    positive_prompt_node_id: str = "6"
    positive_prompt_input_key: str = "text"
    negative_prompt_node_id: str = "7"
    negative_prompt_input_key: str = "text"
    seed_node_id: str = "3"
    seed_input_key: str = "seed"
    output_node_id: str = "9"
    timeout_sec: int = 600


class ComfyUIClient:
    """ComfyUIとの連携クライアント

    Intel ARC GPUで動くComfyUIに接続し、画像生成を管理します
    """

    def __init__(self, config: ComfyUIConfig = None):
        """初期化

        Args:
            config: ComfyUI設定。Noneの場合はデフォルト設定を使用
        """
        if config is None:
            config = ComfyUIConfig()

        self.config = config
        self.server = self.config.server_address.rstrip("/")
        self.client_id = str(uuid.uuid4())
        self._workflow_template = self._load_workflow_template()

        print(f"ComfyUIクライアントを初期化しました: {self.server}")

    def _http_to_ws(self, server: str) -> str:
        """HTTPアドレスをWebSocketアドレスに変換

        Args:
            server: HTTPアドレス

        Returns:
            WebSocketアドレス
        """
        u = urllib.parse.urlparse(f"http://{server}")
        scheme = "ws" if u.scheme == "http" else "wss"
        return f"{scheme}://{u.netloc}"

    def _load_workflow_template(self) -> Dict[str, Any]:
        """ワークフローテンプレートを読み込む

        Returns:
            ワークフローの辞書
        """
        try:
            with open(self.config.workflow_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: ワークフローファイルが見つかりません: {self.config.workflow_json_path}")
            return {}
        except Exception as e:
            print(f"エラー: ワークフローの読み込みに失敗: {e}")
            return {}

    def _patch_workflow(self, workflow: Dict[str, Any], node_id: str, key: str, value: Any) -> Dict[str, Any]:
        """ワークフローに値をセット

        Args:
            workflow: ワークフロー辞書
            node_id: ノードID
            key: 入力キー
            value: 設定する値

        Returns:
            更新されたワークフロー辞書
        """
        workflow = json.loads(json.dumps(workflow))  # Deep copy
        nid = str(node_id)

        if nid not in workflow:
            raise KeyError(f"ノードID {nid} がワークフローに見つかりません")

        node = workflow[nid]
        inputs = node.get("inputs", {})

        if not isinstance(inputs, dict):
            raise TypeError(f"ノード {nid} の inputs が辞書ではありません")

        inputs[key] = value
        node["inputs"] = inputs

        return workflow

    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        output_dir: Path = Path("output")
    ) -> Path:
        """画像を生成する

        Args:
            positive_prompt: positiveプロンプト
            negative_prompt: negativeプロンプト
            seed: シード値（Noneの場合はランダム）
            output_dir: 出力ディレクトリ

        Returns:
            生成された画像のパス

        Raises:
            RuntimeError: 生成に失敗した場合
            TimeoutError: タイムアウトした場合
        """
        # ワークフローを作成
        workflow = self._load_workflow_template()
        workflow = self._patch_workflow(workflow, self.config.positive_prompt_node_id,
                                       self.config.positive_prompt_input_key, positive_prompt)

        if negative_prompt:
            workflow = self._patch_workflow(workflow, self.config.negative_prompt_node_id,
                                           self.config.negative_prompt_input_key, negative_prompt)

        if seed is not None:
            workflow = self._patch_workflow(workflow, self.config.seed_node_id,
                                           self.config.seed_input_key, int(seed))

        # プロンプトをキューに入れる
        payload = {"prompt": workflow, "client_id": self.client_id}
        data = json.dumps(payload).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"http://{self.server}/prompt",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                response = json.loads(resp.read().decode("utf-8"))
                prompt_id = response.get("prompt_id")

                if not prompt_id:
                    raise RuntimeError(f"ComfyUIプロンプト送信失敗: {response}")

                print(f"プロンプトID: {prompt_id}")

        except Exception as e:
            raise RuntimeError(f"ComfyUI接続エラー: {e}")

        # WebSocketで完了を待つ
        ws_url = f"{self._http_to_ws(self.server)}/ws?clientId={urllib.parse.quote(self.client_id)}"
        ws = websocket.WebSocket()
        ws.settimeout(self.config.timeout_sec)

        try:
            ws.connect(ws_url)
            print("WebSocket接続完了、生成を待っています...")

            t0 = time.time()
            while True:
                if time.time() - t0 > self.config.timeout_sec:
                    raise TimeoutError(f"ComfyUIタイムアウト（{self.config.timeout_sec}秒）")

                msg = ws.recv()
                if not msg:
                    continue

                try:
                    evt = json.loads(msg)
                except Exception:
                    continue

                # 生成完了イベントを待つ
                if evt.get("type") in ("execution_success", "executed"):
                    data = evt.get("data", {}) or {}
                    if data.get("prompt_id") == prompt_id:
                        print("画像生成完了")
                        break

        except Exception as e:
            raise RuntimeError(f"WebSocketエラー: {e}")
        finally:
            try:
                ws.close()
            except Exception:
                pass

        # 履歴から画像情報を取得
        try:
            history_url = f"http://{self.server}/history/{prompt_id}"
            with urllib.request.urlopen(history_url, timeout=60) as resp:
                history = json.loads(resp.read().decode("utf-8"))

            outputs = history.get(prompt_id, {}).get("outputs", {})
            images = []

            # 出力ノードから画像を取得
            if self.config.output_node_id in outputs:
                out = outputs[self.config.output_node_id]
                imgs = out.get("images", [])
                for img in imgs:
                    images.append(img)
            else:
                # 全ノードを走査
                for node_id, node_out in outputs.items():
                    if isinstance(node_out, dict):
                        imgs = node_out.get("images", [])
                        for img in imgs:
                            images.append(img)

            if not images:
                raise RuntimeError(f"画像が見つかりません（prompt_id: {prompt_id}）")

            # 先頭の画像を取得して保存
            img0 = images[0]
            filename = img0.get("filename")
            subfolder = img0.get("subfolder", "")
            img_type = img0.get("type", "output")

            if not filename:
                raise RuntimeError(f"無効な画像エントリ: {img0}")

            # 画像データを取得
            params = urllib.parse.urlencode({
                "filename": filename,
                "subfolder": subfolder,
                "type": img_type
            })

            view_url = f"http://{self.server}/view?{params}"
            with urllib.request.urlopen(view_url, timeout=60) as resp:
                image_data = resp.read()

            # ファイルを保存
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename

            with open(output_path, "wb") as f:
                f.write(image_data)

            print(f"画像を保存しました: {output_path}")
            return output_path

        except Exception as e:
            raise RuntimeError(f"画像取得エラー: {e}")

    def test_connection(self) -> bool:
        """ComfyUIとの接続をテスト

        Returns:
            接続成功時はTrue、失敗時はFalse
        """
        try:
            url = f"http://{self.server}/system_stats"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "queue_remaining" in data
        except Exception as e:
            print(f"ComfyUI接続テストエラー: {e}")
            return False


# ユーティリティ関数
def create_default_comfyui_config() -> ComfyUIConfig:
    """デフォルトのComfyUI設定を作成

    Returns:
        デフォルト設定
    """
    return ComfyUIConfig()


def create_custom_comfyui_config(
    server_address: str = "127.0.0.1:8188",
    workflow_path: str = None
) -> ComfyUIConfig:
    """カスタムComfyUI設定を作成

    Args:
        server_address: ComfyUIのアドレス
        workflow_path: ワークフローファイルパス

    Returns:
        カスタム設定
    """
    config = ComfyUIConfig(server_address=server_address)

    if workflow_path:
        config.workflow_json_path = workflow_path

    return config