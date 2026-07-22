from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import httpx
import pytest
import yaml

from app.core.dify.config import _resolve_env, load_dify_config, DifyWorkflowConfig
from app.core.dify.file_resolver import (
    NasFileResolveError,
    _download_from_nas,
    local_file_for_upload,
    resolve_to_local_file,
)
from app.core.dify.streamer import DifyEventStreamer
from app.core.dify.tools import (
    _build_schema,
    _collect_file_paths,
    _confirm_file_uploads,
    _extract_file_fields,
    _infer_dify_file_type,
)


# ── config.py ──────────────────────────────────────────────────────────────

class TestResolveEnv:
    def test_plain_string(self):
        assert _resolve_env("hello") == "hello"

    def test_env_var_replaced(self):
        os.environ["_TEST_VAR"] = "world"
        assert _resolve_env("hello ${_TEST_VAR}") == "hello world"
        del os.environ["_TEST_VAR"]

    def test_missing_env_var_returns_empty(self):
        assert _resolve_env("hello ${_NONEXISTENT}") == "hello "

    def test_dict_recursive(self):
        value = {"key": "${HOME}"}
        result = _resolve_env(value)
        assert result["key"] == os.environ.get("HOME", "")

    def test_list_recursive(self):
        value = ["a", "${HOME}", "b"]
        result = _resolve_env(value)
        assert result[1] == os.environ.get("HOME", "")

    def test_non_string_non_container(self):
        assert _resolve_env(42) == 42
        assert _resolve_env(None) is None
        assert _resolve_env(True) is True


class TestLoadDifyConfig:
    def test_none_path_returns_empty(self):
        assert load_dify_config(None) == []

    def test_empty_string_returns_empty(self):
        assert load_dify_config("") == []

    def test_nonexistent_file_returns_empty(self):
        assert load_dify_config("/nonexistent/path.yaml") == []

    def test_load_single_workflow(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflows": {
                    "test_wf": {
                        "name": "test_wf",
                        "description": "test workflow",
                        "api_base_url": "https://example.com/v1",
                        "api_key": "sk-test",
                        "enabled": True,
                        "max_execution_time": 30,
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_dify_config(path)
            assert len(configs) == 1
            c = configs[0]
            assert c.name == "test_wf"
            assert c.description == "test workflow"
            assert c.api_base_url == "https://example.com/v1"
            assert c.api_key == "sk-test"
            assert c.enabled is True
            assert c.max_execution_time == 30
        finally:
            os.unlink(path)

    def test_disabled_workflow_still_loaded(self):
        """load_dify_config loads all regardless of enabled; filtering is in pool."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflows": {
                    "disabled_wf": {
                        "name": "disabled_wf",
                        "description": "",
                        "api_base_url": "https://example.com/v1",
                        "api_key": "sk-test",
                        "enabled": False,
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_dify_config(path)
            assert len(configs) == 1
            assert configs[0].enabled is False
        finally:
            os.unlink(path)

    def test_missing_workflows_key_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"other": {}}, f)
            path = f.name

        try:
            assert load_dify_config(path) == []
        finally:
            os.unlink(path)

    def test_env_var_in_api_key(self):
        os.environ["_TEST_DIFY_KEY"] = "sk-env-resolved"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflows": {
                    "test_wf": {
                        "name": "test_wf",
                        "description": "",
                        "api_base_url": "https://example.com/v1",
                        "api_key": "${_TEST_DIFY_KEY}",
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_dify_config(path)
            assert configs[0].api_key == "sk-env-resolved"
        finally:
            os.unlink(path)
            del os.environ["_TEST_DIFY_KEY"]

    def test_base_url_trailing_slash_stripped(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflows": {
                    "test_wf": {
                        "name": "test_wf",
                        "description": "",
                        "api_base_url": "https://example.com/v1/",
                        "api_key": "sk-test",
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_dify_config(path)
            assert configs[0].api_base_url == "https://example.com/v1"
        finally:
            os.unlink(path)

    def test_default_max_execution_time(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "workflows": {
                    "test_wf": {
                        "name": "test_wf",
                        "description": "",
                        "api_base_url": "https://example.com/v1",
                        "api_key": "sk-test",
                    }
                }
            }, f)
            path = f.name

        try:
            configs = load_dify_config(path)
            assert configs[0].max_execution_time == 60
        finally:
            os.unlink(path)


# ── tools.py ───────────────────────────────────────────────────────────────

class TestBuildSchema:
    def test_text_input(self):
        form = [{"text-input": {"variable": "query", "label": "查询内容", "required": True}}]
        schema = _build_schema(form)
        assert schema["type"] == "object"
        assert schema["required"] == ["query"]
        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["query"]["description"] == "查询内容"

    def test_paragraph(self):
        form = [{"paragraph": {"variable": "desc", "label": "描述", "required": False}}]
        schema = _build_schema(form)
        assert "required" not in schema or "desc" not in schema["required"]
        assert schema["properties"]["desc"]["type"] == "string"

    def test_select_with_enum(self):
        form = [{"select": {"variable": "lang", "label": "语言", "required": True, "options": ["en", "zh", "ja"]}}]
        schema = _build_schema(form)
        assert schema["properties"]["lang"]["enum"] == ["en", "zh", "ja"]

    def test_select_without_options(self):
        form = [{"select": {"variable": "lang", "label": "语言", "required": True}}]
        schema = _build_schema(form)
        assert "enum" not in schema["properties"]["lang"]

    def test_file_type(self):
        form = [{"file": {"variable": "img", "label": "图片", "required": True}}]
        schema = _build_schema(form)
        assert schema["properties"]["img"]["type"] == "string"
        assert "NAS" in schema["properties"]["img"]["description"]

    def test_file_list(self):
        form = [{"file-list": {"variable": "files", "label": "附件", "required": False}}]
        schema = _build_schema(form)
        assert schema["properties"]["files"]["type"] == "array"
        assert schema["properties"]["files"]["items"] == {"type": "string"}
        assert "NAS" in schema["properties"]["files"]["description"]

    def test_mixed_types(self):
        form = [
            {"text-input": {"variable": "query", "label": "查询", "required": True}},
            {"select": {"variable": "lang", "label": "语言", "required": True, "options": ["en", "zh"]}},
            {"file": {"variable": "doc", "label": "文档", "required": False}},
        ]
        schema = _build_schema(form)
        assert schema["required"] == ["query", "lang"]
        assert set(schema["properties"].keys()) == {"query", "lang", "doc"}
        assert "enum" in schema["properties"]["lang"]

    def test_empty_form(self):
        assert _build_schema([]) == {"type": "object", "properties": {}}

    def test_unknown_type_defaults_to_string(self):
        form = [{"unknown-type": {"variable": "x", "label": "未知"}}]
        schema = _build_schema(form)
        assert schema["properties"]["x"]["type"] == "string"


class TestExtractFileFields:
    def test_file_field_found(self):
        form = [{"file": {"variable": "img", "label": "图片"}}]
        assert _extract_file_fields(form) == {"img"}

    def test_file_list_field_found(self):
        form = [{"file-list": {"variable": "attachments", "label": "附件"}}]
        assert _extract_file_fields(form) == {"attachments"}

    def test_mixed_fields(self):
        form = [
            {"text-input": {"variable": "query", "label": "查询"}},
            {"file": {"variable": "img", "label": "图片"}},
            {"file-list": {"variable": "files", "label": "附件"}},
        ]
        assert _extract_file_fields(form) == {"img", "files"}

    def test_no_file_fields(self):
        form = [{"text-input": {"variable": "query", "label": "查询"}}]
        assert _extract_file_fields(form) == set()

    def test_empty_form(self):
        assert _extract_file_fields([]) == set()


class TestInferDifyFileType:
    def test_image_extensions(self):
        assert _infer_dify_file_type("/tmp/a.png") == "image"
        assert _infer_dify_file_type("photo.JPG") == "image"
        assert _infer_dify_file_type("x.webp") == "image"

    def test_audio_extensions(self):
        assert _infer_dify_file_type("clip.mp3") == "audio"
        assert _infer_dify_file_type("/data/a.WAV") == "audio"

    def test_video_extensions(self):
        assert _infer_dify_file_type("movie.mp4") == "video"
        assert _infer_dify_file_type("clip.MOV") == "video"

    def test_document_default(self):
        assert _infer_dify_file_type("report.pdf") == "document"
        assert _infer_dify_file_type("notes.txt") == "document"
        assert _infer_dify_file_type("noext") == "document"


# ── streamer.py ────────────────────────────────────────────────────────────

def _make_sse_response(events: list[dict]) -> httpx.Response:
    lines = "\n".join(f"data: {json.dumps(e, ensure_ascii=False)}" for e in events)
    return httpx.Response(200, text=lines)


@pytest.mark.anyio
class TestDifyEventStreamerAccumulate:
    async def test_text_chunks_accumulated(self):
        events = [
            {"event": "workflow_started", "data": {"id": "run_1"}},
            {"event": "node_started", "data": {"id": "node_1"}},
            {"event": "text_chunk", "data": {"text": "Hello"}},
            {"event": "text_chunk", "data": {"text": " World"}},
            {"event": "workflow_finished", "data": {
                "id": "run_1", "status": "succeeded", "outputs": {"result": "Hello World"}
            }},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        # 有 text_chunk 时不重复拼 outputs
        assert result == "Hello World"

    async def test_text_chunks_preferred_over_outputs(self):
        events = [
            {"event": "text_chunk", "data": {"text": "streamed"}},
            {"event": "workflow_finished", "data": {
                "status": "succeeded",
                "outputs": {"result": "from-outputs"},
            }},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "streamed"
        assert "from-outputs" not in result

    async def test_workflow_finished_outputs(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "workflow_finished", "data": {
                "status": "succeeded",
                "outputs": {"translation": "Bonjour le monde", "confidence": 0.95},
            }},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "Bonjour le monde"
        assert "0.95" not in result  # non-string values excluded

    async def test_no_text_chunks_only_outputs(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "workflow_finished", "data": {
                "status": "succeeded",
                "outputs": {"result": "直接输出"},
            }},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "直接输出"

    async def test_error_event_raises(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "error", "data": {"message": "模型调用失败"}},
        ]
        response = _make_sse_response(events)
        with pytest.raises(RuntimeError, match="模型调用失败"):
            await DifyEventStreamer.accumulate(response)

    async def test_failed_status_raises(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "workflow_finished", "data": {
                "status": "failed",
                "error": "节点执行异常",
                "outputs": {},
            }},
        ]
        response = _make_sse_response(events)
        with pytest.raises(RuntimeError, match="节点执行异常"):
            await DifyEventStreamer.accumulate(response)

    async def test_workflow_paused_raises_not_implemented(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "workflow_paused", "data": {"workflow_run_id": "run_1"}},
        ]
        response = _make_sse_response(events)
        with pytest.raises(NotImplementedError, match="人工介入尚未支持"):
            await DifyEventStreamer.accumulate(response)

    async def test_empty_sse(self):
        response = httpx.Response(200, text="")
        result = await DifyEventStreamer.accumulate(response)
        assert result == ""

    async def test_malformed_json_skipped(self):
        events = [
            {"event": "workflow_started", "data": {}},
            "not json",
            {"event": "workflow_finished", "data": {"status": "succeeded", "outputs": {"r": "ok"}}},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "ok"

    async def test_only_non_data_lines(self):
        response = httpx.Response(200, text=":ping\n:ping\n")
        result = await DifyEventStreamer.accumulate(response)
        assert result == ""

    async def test_outputs_non_string_values_skipped(self):
        events = [
            {"event": "workflow_started", "data": {}},
            {"event": "workflow_finished", "data": {
                "status": "succeeded",
                "outputs": {"text": "hello", "count": 42, "valid": True, "nested": {"a": 1}},
            }},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "hello"

    async def test_stream_ended_without_finished_returns_chunks(self):
        events = [
            {"event": "text_chunk", "data": {"text": "partial"}},
        ]
        response = _make_sse_response(events)
        result = await DifyEventStreamer.accumulate(response)
        assert result == "partial"


# ── file upload confirm ────────────────────────────────────────────────────

class TestCollectFilePaths:
    def test_single_and_list(self):
        paths = _collect_file_paths(
            {"img", "docs"},
            {"img": "/a.png", "docs": ["/b.pdf", "/c.pdf"], "query": "x"},
        )
        assert set(paths) == {"/a.png", "/b.pdf", "/c.pdf"}
        assert len(paths) == 3

    def test_dedupe(self):
        paths = _collect_file_paths({"f"}, {"f": ["/a.png", "/a.png"]})
        assert paths == ["/a.png"]

    def test_empty(self):
        assert _collect_file_paths({"f"}, {"f": ""}) == []
        assert _collect_file_paths(set(), {"x": "1"}) == []


@pytest.mark.anyio
class TestConfirmFileUploads:
    async def test_no_paths_skips(self):
        assert await _confirm_file_uploads(None, "dify_x", []) is None

    async def test_approved(self):
        import asyncio

        class FakeConfirm:
            def __init__(self):
                self.payload = None

            def request(self, payload):
                self.payload = payload
                fut = asyncio.get_running_loop().create_future()
                fut.set_result(True)
                return "cid1", fut

            def cleanup(self, confirm_id):
                pass

        confirm = FakeConfirm()
        result = await _confirm_file_uploads(
            confirm, "dify_image_analysis", ["/pool/my/a.png"],
        )
        assert result is None
        assert confirm.payload["type"] == "require_confirm"
        assert confirm.payload["title"] == "Dify 文件上传"
        assert confirm.payload["tool"] == "dify_image_analysis"
        assert confirm.payload["paths"] == ["/pool/my/a.png"]

    async def test_rejected(self):
        import asyncio

        class FakeConfirm:
            def request(self, payload):
                fut = asyncio.get_running_loop().create_future()
                fut.set_result(False)
                return "cid1", fut

            def cleanup(self, confirm_id):
                pass

        result = await _confirm_file_uploads(
            FakeConfirm(), "dify_x", ["/a.png", "/b.png"],
        )
        assert result is not None
        assert result.startswith("❌")
        assert "/a.png" in result


# ── file_resolver.py ───────────────────────────────────────────────────────

@pytest.mark.anyio
class TestResolveToLocalFile:
    async def test_local_file_used_directly(self, tmp_path: Path):
        local = tmp_path / "photo.png"
        local.write_bytes(b"png-bytes")
        resolved, temp_dir = await resolve_to_local_file(str(local))
        assert resolved == local.resolve()
        assert temp_dir is None

    async def test_nas_path_downloads_via_zcli(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_download(nas_path: str, output_dir: str) -> Path:
            dest = Path(output_dir) / Path(nas_path).name
            dest.write_bytes(b"from-nas")
            return dest

        monkeypatch.setattr(
            "app.core.dify.file_resolver._download_from_nas",
            fake_download,
        )
        nas_path = "/sata1/my/data/photo.png"
        resolved, temp_dir = await resolve_to_local_file(nas_path)
        try:
            assert resolved.name == "photo.png"
            assert resolved.read_bytes() == b"from-nas"
            assert temp_dir is not None
            assert temp_dir.is_dir()
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_download_failure_cleans_temp_dir(self, monkeypatch: pytest.MonkeyPatch):
        created: list[Path] = []

        async def fake_download(nas_path: str, output_dir: str) -> Path:
            created.append(Path(output_dir))
            raise NasFileResolveError("boom")

        monkeypatch.setattr(
            "app.core.dify.file_resolver._download_from_nas",
            fake_download,
        )
        with pytest.raises(NasFileResolveError, match="boom"):
            await resolve_to_local_file("/sata1/my/missing.png")
        assert created
        assert not created[0].exists()

    async def test_local_file_for_upload_context_cleans_temp(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_download(nas_path: str, output_dir: str) -> Path:
            dest = Path(output_dir) / Path(nas_path).name
            dest.write_bytes(b"x")
            return dest

        monkeypatch.setattr(
            "app.core.dify.file_resolver._download_from_nas",
            fake_download,
        )
        temp_holder: list[Path] = []
        async with local_file_for_upload("/pool/my/a.jpg") as local:
            temp_holder.append(local.parent)
            assert local.is_file()
        assert temp_holder
        assert not temp_holder[0].exists()

    async def test_zcli_nonzero_exit_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        class FakeProc:
            returncode = 1

            async def communicate(self):
                return b"", b"permission denied"

            def kill(self):
                pass

            async def wait(self):
                return 1

        async def fake_exec(*_args, **_kwargs):
            return FakeProc()

        monkeypatch.setattr(
            "app.core.dify.file_resolver.asyncio.create_subprocess_exec",
            fake_exec,
        )
        with pytest.raises(NasFileResolveError, match="permission denied"):
            await _download_from_nas("/pool/my/a.png", str(tmp_path))
