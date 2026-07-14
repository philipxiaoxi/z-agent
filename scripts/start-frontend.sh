#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Starting frontend (Vite dev server)..."
cd "$ROOT/frontend"
npm run dev
