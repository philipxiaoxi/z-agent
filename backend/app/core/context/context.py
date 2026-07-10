from uuid import uuid4

MAX_TURNS_DEFAULT = 20


class ConversationContext:
    """管理单个 WebSocket 连接的对话上下文"""

    def __init__(self, max_turns: int = MAX_TURNS_DEFAULT) -> None:
        self.session_id: str = uuid4().hex[:12]
        self.workdir: str = ""
        self._messages: list[dict] = []
        self._max_turns = max_turns

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._trim()

    def append_messages(self, messages: list[dict]) -> None:
        self._messages.extend(messages)
        self._trim()

    def get_history(self) -> list[dict]:
        return list(self._messages)

    @property
    def turn_count(self) -> int:
        return len(self._messages) // 2

    def clear(self) -> None:
        self._messages.clear()

    def restore_history(self, messages: list[dict]) -> None:
        self._messages = list(messages)

    def _trim(self) -> None:
        if len(self._messages) <= self._max_turns * 6:
            return
        # 按整轮（user 消息为界）切除最早的历史
        user_indices = [i for i, m in enumerate(self._messages) if m.get("role") == "user"]
        while user_indices and len(self._messages) - user_indices[0] > self._max_turns * 6:
            end = user_indices[1] if len(user_indices) > 1 else len(self._messages)
            self._messages = self._messages[end:]
            user_indices = [i for i, m in enumerate(self._messages) if m.get("role") == "user"]
