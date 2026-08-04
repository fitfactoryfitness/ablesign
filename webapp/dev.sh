#!/usr/bin/env bash
# webapp/dev.sh - starts the backend (FastAPI/uvicorn) and frontend (Vite)
# together, localhost-only (this app runs entirely on your own machine -
# no need to expose it to the network). Ctrl+C stops both.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

cleanup() {
  echo ""
  echo "Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

(cd backend && python3 -m uvicorn main:app --reload --port 8000) &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait
