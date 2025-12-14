"""Unit tests for ComfyUIAPI client error paths and fallbacks"""
import io
import json
import urllib
from urllib.error import HTTPError, URLError
from unittest.mock import Mock, patch

import pytest
import websocket

from infrastructure.comfy_api.client import ComfyUIAPI
from domain.exceptions import (
    ComfyUIConnectionError,
    WorkflowExecutionError,
    WorkflowLoadError,
)


@pytest.mark.unit
def test_test_connection_handles_comfy_error():
    """Should return connected=False when _get_request raises ComfyUIConnectionError"""
    api = ComfyUIAPI("http://localhost:8188")

    with patch.object(ComfyUIAPI, "_get_request", side_effect=ComfyUIConnectionError("offline")):
        result = api.test_connection()

    assert result["connected"] is False
    assert result["error"] == "offline"


@pytest.mark.unit
def test_update_workflow_params_falls_back_to_legacy():
    """Should fallback to legacy updater if WorkflowUpdater fails"""
    api = ComfyUIAPI("http://localhost:8188")
    api.workflow_updater = Mock()
    api.workflow_updater.update.side_effect = RuntimeError("boom")

    workflow = {
        "1": {"class_type": "SaveImage", "inputs": {"filename_prefix": "orig"}},
        "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 640, "height": 480}},
    }

    updated = api.update_workflow_params(workflow, filename_prefix="new", width=1280, height=720)

    assert updated["1"]["inputs"]["filename_prefix"] == "new"
    assert updated["2"]["inputs"]["width"] == 1280
    assert updated["2"]["inputs"]["height"] == 720
    # Ensure original dict unchanged
    assert workflow["1"]["inputs"]["filename_prefix"] == "orig"


@pytest.mark.unit
def test_monitor_progress_returns_error_on_ws_exception():
    """Should return error status when websocket connection fails"""
    api = ComfyUIAPI("http://localhost:8188")

    with patch("infrastructure.comfy_api.client.websocket.create_connection", side_effect=Exception("ws down")):
        result = api.monitor_progress("pid-1", timeout=1)

    assert result["status"] == "error"
    assert "ws down" in result["error"]


@pytest.mark.unit
def test_get_output_images_returns_empty_after_retries():
    """Should warn and return empty list when no history is available"""
    api = ComfyUIAPI("http://localhost:8188")

    with patch.object(ComfyUIAPI, "get_history", return_value=None) as mock_history:
        images = api.get_output_images("pid-2", retries=1, delay=0)

    assert images == []
    assert mock_history.call_count == 2  # initial + one retry


@pytest.mark.unit
def test_monitor_progress_success_flow_calls_callbacks(monkeypatch):
    """Should process websocket messages and return success with outputs"""
    api = ComfyUIAPI("http://localhost:8188")

    messages = iter([
        json.dumps({"type": "execution_start"}),
        json.dumps({"type": "executing", "data": {"node": "1"}}),
        json.dumps({"type": "executed", "data": {"node": "1"}}),
        json.dumps({"type": "execution_cached"}),
        # Completion signal: executing with node=None and prompt_id matching
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-success"}}),
    ])

    mock_ws = Mock()
    mock_ws.recv.side_effect = lambda: next(messages)

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.websocket.create_connection",
        lambda *_args, **_kwargs: mock_ws
    )
    monkeypatch.setattr(
        ComfyUIAPI,
        "get_output_images",
        lambda self, prompt_id, retries=15, delay=1.0: ["img.png"]
    )

    callbacks = []

    def cb(progress, status):
        callbacks.append((progress, status))

    result = api.monitor_progress("pid-success", callback=cb, timeout=1)

    assert result["status"] == "success"
    assert result["output_images"] == ["img.png"]
    assert callbacks  # callback was invoked


@pytest.mark.unit
def test_monitor_progress_timeout(monkeypatch):
    """Should return error status on timeout"""
    api = ComfyUIAPI("http://localhost:8188")

    mock_ws = Mock()
    mock_ws.recv.side_effect = websocket.WebSocketTimeoutException("timeout")

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.websocket.create_connection",
        lambda *_args, **_kwargs: mock_ws
    )
    monkeypatch.setattr(
        ComfyUIAPI,
        "get_history",
        lambda self, pid: None
    )

    result = api.monitor_progress("pid-timeout", timeout=0)
    assert result["status"] == "error"
    assert "Timeout" in result["error"]


@pytest.mark.unit
def test_get_output_images_downloads_files(tmp_path, monkeypatch):
    """Should download images to output/test directory"""
    api = ComfyUIAPI("http://localhost:8188")

    history = {
        "outputs": {
            "1": {
                "images": [
                    {"filename": "img.png", "subfolder": "sub", "type": "output"}
                ]
            }
        }
    }

    monkeypatch.setattr(
        ComfyUIAPI,
        "get_history",
        lambda self, prompt_id: history
    )
    monkeypatch.setattr(
        ComfyUIAPI,
        "_get_image",
        lambda self, filename, subfolder="", image_type="output": b"data"
    )

    images = api.get_output_images("pid-history", retries=0, delay=0)
    assert images
    for img in images:
        assert img.endswith("img.png")


@pytest.mark.unit
def test_post_request_http_error_includes_body():
    """Should wrap HTTPError with response body into WorkflowExecutionError"""
    api = ComfyUIAPI("http://localhost:8188")
    error_body = b'{"error": "bad request"}'

    http_error = HTTPError(
        url="http://localhost:8188/prompt",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=io.BytesIO(error_body),
    )

    with patch("infrastructure.comfy_api.client.urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(WorkflowExecutionError) as excinfo:
            api._post_request("/prompt", {"prompt": {}})

    assert "HTTP 500" in str(excinfo.value)
    assert "bad request" in str(excinfo.value)


@pytest.mark.unit
def test_get_request_raises_connection_error_on_urlerror():
    """Should raise ComfyUIConnectionError when urlopen fails"""
    api = ComfyUIAPI("http://localhost:8188")

    with patch("infrastructure.comfy_api.client.urllib.request.urlopen", side_effect=URLError("refused")):
        with pytest.raises(ComfyUIConnectionError):
            api._get_request("/system_stats")


@pytest.mark.unit
def test_monitor_progress_timeout_continues_on_missing_history(monkeypatch):
    """Timeout loop should continue when history missing"""
    api = ComfyUIAPI("http://localhost:8188")

    mock_ws = Mock()
    # Two timeouts before we break via injected error to stop loop quickly
    mock_ws.recv.side_effect = [
        websocket.WebSocketTimeoutException("t1"),
        websocket.WebSocketTimeoutException("t2"),
        Exception("stop"),
    ]

    history_calls = {"count": 0}

    def fake_history(self, pid):
        history_calls["count"] += 1
        return None

    monkeypatch.setattr("infrastructure.comfy_api.client.websocket.create_connection", lambda *_a, **_k: mock_ws)
    monkeypatch.setattr(ComfyUIAPI, "get_history", fake_history)

    result = api.monitor_progress("pid-loop", timeout=0.01)
    assert result["status"] == "error"
    assert history_calls["count"] >= 2


@pytest.mark.unit
def test_monitor_progress_timeout_invokes_callback_when_history_exists(monkeypatch):
    """Timeout with history should call callback and succeed"""
    api = ComfyUIAPI("http://localhost:8188")

    mock_ws = Mock()
    mock_ws.recv.side_effect = websocket.WebSocketTimeoutException("wait")

    monkeypatch.setattr("infrastructure.comfy_api.client.websocket.create_connection", lambda *_a, **_k: mock_ws)
    monkeypatch.setattr(ComfyUIAPI, "get_history", lambda self, pid: {"outputs": {}})
    monkeypatch.setattr(ComfyUIAPI, "get_output_images", lambda self, pid, retries=15, delay=1.0: ["ok.png"])

    callbacks = []

    def cb(progress, status):
        callbacks.append((progress, status))

    result = api.monitor_progress("pid-cb", callback=cb, timeout=0.01)

    assert result["status"] == "success"
    assert any(status == "Complete" for _, status in callbacks)


@pytest.mark.unit
def test_get_output_images_handles_outer_exception(monkeypatch):
    """Outer exception should be logged and return empty list"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr(ComfyUIAPI, "get_history", lambda self, pid: (_ for _ in ()).throw(RuntimeError("boom")))

    images = api.get_output_images("pid-exc", retries=0, delay=0)
    assert images == []


@pytest.mark.unit
def test_get_history_returns_none_on_error(monkeypatch, caplog):
    """get_history should swallow errors and return None"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr(ComfyUIAPI, "_get_request", lambda self, endpoint: (_ for _ in ()).throw(RuntimeError("fail")))

    result = api.get_history("pid")
    assert result is None


@pytest.mark.unit
def test_get_history_success(monkeypatch):
    """get_history should return prompt-specific history"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr(ComfyUIAPI, "_get_request", lambda self, endpoint: {"pid": {"outputs": {}}})

    result = api.get_history("pid")
    assert result == {"outputs": {}}


@pytest.mark.unit
def test_get_request_success(monkeypatch):
    """_get_request should parse JSON body"""
    api = ComfyUIAPI("http://localhost:8188")

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(b'{"ok": true}'),
    )

    result = api._get_request("/system_stats")
    assert result == {"ok": True}


@pytest.mark.unit
def test_post_request_success(monkeypatch):
    """_post_request should parse JSON on success"""
    api = ComfyUIAPI("http://localhost:8188")

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(b'{"prompt_id":"123"}'),
    )

    result = api._post_request("/prompt", {"prompt": {}})
    assert result["prompt_id"] == "123"


@pytest.mark.unit
def test_post_request_http_error_with_invalid_json(monkeypatch):
    """HTTPError with non-JSON body should still surface raw body"""
    api = ComfyUIAPI("http://localhost:8188")

    class FakeHTTPError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("url", 500, "boom", hdrs=None, fp=None)
            self.body = b"<!DOCTYPE html>error"

        def read(self):
            return self.body

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(FakeHTTPError()),
    )

    with pytest.raises(WorkflowExecutionError) as excinfo:
        api._post_request("/prompt", {"prompt": {}})

    assert "error" in str(excinfo.value).lower()


@pytest.mark.unit
def test_load_workflow_wraps_unexpected_error(tmp_path, monkeypatch):
    """Should surface unexpected load errors as WorkflowLoadError"""
    api = ComfyUIAPI("http://localhost:8188")
    bad_file = tmp_path / "broken.json"
    bad_file.write_text("{}", encoding="utf-8")

    # Force an unexpected exception from open/read
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(WorkflowLoadError) as excinfo:
        api.load_workflow(str(bad_file))

    assert "Konnte Workflow nicht laden" in str(excinfo.value)


@pytest.mark.unit
def test_legacy_update_workflow_params_covers_all_nodes(monkeypatch):
    """Legacy fallback should touch all supported node types"""
    api = ComfyUIAPI("http://localhost:8188")
    api.workflow_updater = Mock()
    api.workflow_updater.update.side_effect = RuntimeError("fail modern")

    workflow = {
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1, "seed": 2}},
        "ks": {"class_type": "KSampler", "inputs": {"seed": 0, "steps": 1, "cfg": 2}},
        "sched": {"class_type": "BasicScheduler", "inputs": {"steps": 3}},
        "clip": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
        "save": {"class_type": "SaveImage", "inputs": {"filename_prefix": "old"}},
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 10, "height": 10, "W": 5, "H": 5}},
    }

    updated = api.update_workflow_params(
        workflow,
        prompt="hello",
        seed=123,
        steps=7,
        cfg=9.0,
        filename_prefix="new",
        width=640,
        height=480,
    )

    assert updated["noise"]["inputs"]["noise_seed"] == 123
    assert updated["noise"]["inputs"]["seed"] == 123
    assert updated["ks"]["inputs"]["steps"] == 7
    assert updated["ks"]["inputs"]["cfg"] == 9.0
    assert updated["sched"]["inputs"]["steps"] == 7
    assert updated["clip"]["inputs"]["text"] == "hello"
    assert updated["save"]["inputs"]["filename_prefix"] == "new"
    assert updated["latent"]["inputs"]["width"] == 640
    assert updated["latent"]["inputs"]["height"] == 480


@pytest.mark.unit
def test_monitor_progress_checks_history_on_timeout(monkeypatch):
    """Timeouts should consult history and still succeed when history exists"""
    api = ComfyUIAPI("http://localhost:8188")

    mock_ws = Mock()
    mock_ws.recv.side_effect = websocket.WebSocketTimeoutException("sleep")

    monkeypatch.setattr("infrastructure.comfy_api.client.websocket.create_connection", lambda *_a, **_k: mock_ws)
    monkeypatch.setattr(ComfyUIAPI, "get_history", lambda self, pid: {"outputs": {}})
    monkeypatch.setattr(ComfyUIAPI, "get_output_images", lambda self, pid, retries=15, delay=1.0: ["final.png"])

    result = api.monitor_progress("pid-timeout-success", timeout=0.01)
    assert result["status"] == "success"
    assert result["output_images"] == ["final.png"]


@pytest.mark.unit
def test_get_output_images_handles_download_errors(monkeypatch, tmp_path):
    """Download errors should be logged and skipped"""
    api = ComfyUIAPI("http://localhost:8188")
    images = [
        {"filename": "img1.png", "subfolder": "", "type": "output"},
        {"filename": "img2.png", "subfolder": "", "type": "output"},
    ]
    history = {"outputs": {"1": {"images": images}}}

    monkeypatch.setattr(ComfyUIAPI, "get_history", lambda self, pid: history)

    calls = []

    def fake_get_image(self, filename, subfolder="", image_type="output"):
        calls.append(filename)
        if filename == "img1.png":
            raise RuntimeError("fail download")
        return b"bytes"

    monkeypatch.setattr(ComfyUIAPI, "_get_image", fake_get_image)

    downloaded = api.get_output_images("pid-download", retries=0, delay=0)
    assert downloaded  # second image succeeded
    assert any("img2.png" in path for path in downloaded)
    assert calls == ["img1.png", "img2.png"]


@pytest.mark.unit
def test_get_image_reads_bytes(monkeypatch):
    """_get_image should read from urlopen response"""
    api = ComfyUIAPI("http://localhost:8188")

    class FakeResponse:
        def __init__(self, data: bytes):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "infrastructure.comfy_api.client.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(b"img-bytes"),
    )

    data = api._get_image("file.png", "sub", "output")
    assert data == b"img-bytes"


@pytest.mark.unit
def test_queue_prompt_propagates_workflow_execution_error(monkeypatch):
    """queue_prompt should not mask WorkflowExecutionError"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr(ComfyUIAPI, "_post_request", lambda self, endpoint, payload: (_ for _ in ()).throw(WorkflowExecutionError("bad")))

    with pytest.raises(WorkflowExecutionError):
        api.queue_prompt({"nodes": {}})


@pytest.mark.unit
def test_post_request_wraps_generic_error(monkeypatch):
    """Generic errors should be wrapped into WorkflowExecutionError"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr("infrastructure.comfy_api.client.urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(WorkflowExecutionError) as excinfo:
        api._post_request("/prompt", {"prompt": {}})

    assert "boom" in str(excinfo.value)


@pytest.mark.unit
def test_get_request_wraps_generic_error(monkeypatch):
    """Non-URLError exceptions should be wrapped into ComfyUIConnectionError"""
    api = ComfyUIAPI("http://localhost:8188")
    monkeypatch.setattr("infrastructure.comfy_api.client.urllib.request.urlopen", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(ComfyUIConnectionError) as excinfo:
        api._get_request("/system_stats")

    assert "boom" in str(excinfo.value)
