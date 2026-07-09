from pathlib import Path

_docs = Path(__file__).parent / "docs"

SYSTEM_DESCRIPTION = (_docs / "role.md").read_text(encoding="utf-8").strip()
SYSTEM_INSTRUCTIONS = (_docs / "system-instructions.md").read_text(encoding="utf-8").strip()
