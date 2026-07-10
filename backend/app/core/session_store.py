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
