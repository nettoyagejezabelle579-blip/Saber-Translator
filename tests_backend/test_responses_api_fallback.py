"""火山方舟回 400「missing `input.type` parameter」時改用 /responses（使用者回報翻譯全部失敗）。"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.shared import ai_transport
from src.shared.ai_transport import (
    AsyncOpenAICompatibleTransport,
    OpenAICompatibleChatTransport,
    UnifiedChatRequest,
)
from src.shared.openai_options import create_openai_compatible_options

ARK_ERROR = {
    "error": {
        "message": "The request failed because it is missing `input.type` parameter. "
        "Request id: 021791526047972b8b2db5ad8d9605f3baecb70a2647fd873afd7",
        "type": "invalid_request_error",
    }
}


class _ArkLikeServer:
    """chat/completions 一律回方舟的 400；/responses 回方舟格式的答案。"""

    def __init__(self, *, chat_error: dict | None = ARK_ERROR) -> None:
        self.calls: list[tuple[str, dict]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                return None

            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append((self.path, body))
                if self.path.endswith("/chat/completions"):
                    status, payload = 400, chat_error
                else:
                    status, payload = 200, {
                        "id": "resp_1",
                        "output": [
                            {"type": "reasoning", "summary": []},
                            {"type": "message", "role": "assistant", "content": [
                                {"type": "output_text", "text": "勇者來了"},
                            ]},
                        ],
                    }
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "_ArkLikeServer":
        self.thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.server.shutdown()
        self.server.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/api/v3"


def _request(base_url: str, *, stream: bool, json_mode: bool = False) -> UnifiedChatRequest:
    return UnifiedChatRequest(
        provider="volcano",
        api_key="test-key",
        model="deepseek-v4-1-flash-260910",
        base_url=base_url,
        messages=[
            {"role": "system", "content": "翻成繁體中文"},
            {"role": "user", "content": "勇者が来た"},
        ],
        openai_options=create_openai_compatible_options(
            use_stream=stream, transport_retries=0, force_json_output=json_mode
        ),
    )


@pytest.fixture(autouse=True)
def _forget_learned_models():
    ai_transport._RESPONSES_ONLY_MODELS.clear()
    yield
    ai_transport._RESPONSES_ONLY_MODELS.clear()


@pytest.mark.parametrize("stream", [False, True])
def test_input_type_error_retries_with_the_responses_api(stream: bool) -> None:
    with _ArkLikeServer() as server:
        transport = OpenAICompatibleChatTransport()
        assert transport.complete(_request(server.base_url, stream=stream)) == "勇者來了"
        paths = [path for path, _ in server.calls]
        assert paths == ["/api/v3/chat/completions", "/api/v3/responses"]
        body = server.calls[1][1]
        assert body["model"] == "deepseek-v4-1-flash-260910"
        assert body["input"] == [
            {"type": "message", "role": "system", "content": "翻成繁體中文"},
            {"type": "message", "role": "user", "content": "勇者が来た"},
        ]
        # 之後同一模型直接走 /responses，不再先失敗一次
        assert transport.complete(_request(server.base_url, stream=stream)) == "勇者來了"
        assert [path for path, _ in server.calls][2:] == ["/api/v3/responses"]


def test_async_transport_falls_back_too() -> None:
    import asyncio

    with _ArkLikeServer() as server:
        result = asyncio.run(
            AsyncOpenAICompatibleTransport().complete(_request(server.base_url, stream=False, json_mode=True))
        )
        assert result == "勇者來了"
        assert server.calls[-1][1]["text"] == {"format": {"type": "json_object"}}


def test_other_400_errors_are_not_retried() -> None:
    other = {"error": {"message": "The model does not exist", "type": "invalid_request_error"}}
    with _ArkLikeServer(chat_error=other) as server:
        with pytest.raises(ValueError, match="API 错误 400"):
            OpenAICompatibleChatTransport().complete(_request(server.base_url, stream=False))
        assert [path for path, _ in server.calls] == ["/api/v3/chat/completions"]
