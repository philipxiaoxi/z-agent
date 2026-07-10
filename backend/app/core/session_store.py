import json
import uuid
import time
from pathlib import Path

DATA_DIR = Path("data/sessions")


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(session_id: str) -> Path:
    return DATA_DIR / f"{session_id}.json"


def list_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    for f in sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "id": data["id"],
                "name": data["name"],
                "createdAt": data.get("createdAt", 0),
                "messageCount": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return sessions


def get_session(session_id: str) -> dict | None:
    p = _path(session_id)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def create_session(name: str = "") -> dict:
    session = {
        "id": uuid.uuid4().hex[:12],
        "name": name or f"会话 {time.strftime('%m/%d %H:%M')}",
        "createdAt": time.time(),
        "messages": [],
    }
    _ensure_dir()
    _path(session["id"]).write_text(json.dumps(session, ensure_ascii=False))
    return session


def delete_session(session_id: str) -> bool:
    p = _path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False


def rename_session(session_id: str, name: str) -> bool:
    p = _path(session_id)
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    data["name"] = name
    p.write_text(json.dumps(data, ensure_ascii=False))
    return True


def append_messages(session_id: str, messages: list[dict]) -> bool:
    p = _path(session_id)
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    data.setdefault("messages", []).extend(messages)
    p.write_text(json.dumps(data, ensure_ascii=False))
    return True


def save_history(session_id: str, history: list[dict]) -> bool:
    p = _path(session_id)
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    data["llm_history"] = history
    p.write_text(json.dumps(data, ensure_ascii=False))
    return True


def load_history(session_id: str) -> list[dict] | None:
    p = _path(session_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    history = data.get("llm_history")
    if history is not None:
        return history
    # 兼容旧文件：从 rich messages 重建
    messages = data.get("messages", [])
    if not messages:
        return None
    result: list[dict] = []
    for m in messages:
        if m["role"] == "user":
            texts = [b["content"] for b in m["blocks"] if b["type"] == "text"]
            if texts:
                result.append({"role": "user", "content": "\n".join(texts)})
        elif m["role"] == "assistant":
            parts = []
            for b in m["blocks"]:
                if b["type"] == "text":
                    parts.append(b["content"])
                elif b["type"] == "tool_call":
                    parts.append(f"\n[调用工具: {b['tool']}]\n参数: {json.dumps(b['args'], ensure_ascii=False)}")
                elif b["type"] == "tool_result":
                    parts.append(f"返回: {b['result']}\n")
            content = "\n".join(parts).strip()
            if content:
                result.append({"role": "assistant", "content": content})
    return result if result else None
