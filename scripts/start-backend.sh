#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Starting backend (uvicorn)..."
cd "$ROOT/backend"
uv run uvicorn app.main:app --reload --port 8000 --reload-dir app
