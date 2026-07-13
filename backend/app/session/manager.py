from __future__ import annotations

from app.core import session_store
from app.core.context import ConversationContext


class SessionManager:
    """统一管理会话历史的内存缓存与磁盘持久化。"""

    def __init__(self, ctx: ConversationContext) -> None:
        self._ctx = ctx
        self._cache: dict[str, list[dict]] = {}

    def load(self, session_id: str) -> list[dict]:
        return self._cache.get(session_id) or session_store.load_history(session_id) or []

    def save(self, session_id: str, *, history: list[dict], messages: list[dict]) -> None:
        self._cache[session_id] = history
        session_store.save_session_data(session_id, history=history, messages=messages)

    def switch(self, session_id: str) -> None:
        if self._ctx.session_id:
            self._cache[self._ctx.session_id] = self._ctx.get_history()
        history = self.load(session_id)
        self._ctx.restore_history(history)
        self._ctx.session_id = session_id
