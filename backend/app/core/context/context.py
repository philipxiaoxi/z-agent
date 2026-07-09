from pathlib import Path
from uuid import uuid4

_docs = Path(__file__).parent / "docs"

_WORKDIR_SET = (_docs / "workdir-set.md").read_text(encoding="utf-8").strip()
_WORKDIR_UNSET = (_docs / "workdir-unset.md").read_text(encoding="utf-8").strip()
_TAIL = (_docs / "tail.md").read_text(encoding="utf-8").strip()

MAX_TURNS_DEFAULT = 30


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

    def build_messages(self) -> list[dict]:
        history = self.get_history()
        if self.workdir:
            body = _WORKDIR_SET.format(workdir=self.workdir)
        else:
            body = _WORKDIR_UNSET
        history = history + [{"role": "system", "content": f"{body}；{_TAIL}"}]
        return history

    @property
    def turn_count(self) -> int:
        return len(self._messages) // 2

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        max_n = self._max_turns * 2
        if len(self._messages) > max_n:
            self._messages = self._messages[-max_n:]
