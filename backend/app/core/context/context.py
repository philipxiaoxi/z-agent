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

    def get_history(self) -> list[dict]:
        return list(self._messages)

    @property
    def turn_count(self) -> int:
        return len(self._messages) // 2

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        max_n = self._max_turns * 2
        if len(self._messages) > max_n:
            self._messages = self._messages[-max_n:]
