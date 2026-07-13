from __future__ import annotations

from app.blocks import serialize_llm_messages
from app.core import session_store
from app.core.config import settings
from app.core.context import ConversationContext


class SessionManager:
    """统一管理会话历史：segments 持久化 + 内存缓存，按需派生 LLM 历史。"""

    def __init__(self, ctx: ConversationContext) -> None:
        self._ctx = ctx
        self._cache: dict[str, list[dict]] = {}

    def load(self, session_id: str) -> list[dict]:
        """重建 LLM 对话历史：从 messages 中的 segments 反序列化为 tool_calling 格式。"""
        cached = self._cache.get(session_id)
        if cached:
            return cached
        data = session_store.get_session(session_id)
        if data is None:
            return []
        history: list[dict] = []
        for msg in data.get("messages", []):
            if msg.get("role") == "user":
                history.append({"role": "user", "content": msg.get("content", "")})
            elif msg.get("role") == "assistant" and msg.get("segments"):
                msgs = serialize_llm_messages(msg["segments"], settings.STORE_THINKING_IN_CONTEXT)
                history.extend(msgs)
        if history:
            self._cache[session_id] = history
        return history or []

    def save(self, session_id: str, *, messages: list[dict]) -> None:
        """持久化 messages（含 segments），不存 LLM 历史。"""
        session_store.save_session_data(session_id, messages=messages)

    def switch(self, session_id: str) -> None:
        """切换会话：缓存当前 → 加载目标 → 更新 ctx。"""
        if self._ctx.session_id:
            self._cache[self._ctx.session_id] = self._ctx.get_history()
        history = self.load(session_id)
        self._ctx.restore_history(history)
        self._ctx.session_id = session_id
