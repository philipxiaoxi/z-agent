from pathlib import Path

SYSTEM_DESCRIPTION = "你是极同学，zspace NAS 的 AI 管理助手。"

_instructions_file = Path(__file__).parent / "docs" / "system-instructions.md"
SYSTEM_INSTRUCTIONS = _instructions_file.read_text(encoding="utf-8")
