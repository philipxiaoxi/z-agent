#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Building frontend..."
cd "$ROOT/frontend"
npm run build

echo "✓ Done. Backend is ready to serve at backend/static/"
