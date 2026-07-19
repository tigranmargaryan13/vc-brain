#!/usr/bin/env bash
# Rebuild the deduped funnel from Memory, then serve it to the UI on :8000.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m sourcing.export                                   # deduped funnel -> data/frontend_data.json
exec python -m uvicorn backend.main:app --reload --port 8000
