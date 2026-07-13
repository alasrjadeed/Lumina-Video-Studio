#!/bin/bash
# Lumina Video Studio - Daemon Launcher
# Run this script once. It starts both servers and detaches.
# Usage: bash scripts/start_servers.sh

PROJECT_DIR="/home/oem/Documents/Lumina Video Studio"
VENV="$PROJECT_DIR/.venv"
FASTAPI_LOG="/tmp/lumina_fastapi.log"
STREAMLIT_LOG="/tmp/lumina_streamlit.log"
PID_FILE="/tmp/lumina_pids"

# Kill existing
if [ -f "$PID_FILE" ]; then
    while read pid; do
        kill "$pid" 2>/dev/null
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

sleep 2

# Start FastAPI using setsid so it survives parent exit
setsid "$VENV/bin/python" -m uvicorn api.app:app \
    --host 0.0.0.0 --port 8000 --log-level info \
    > "$FASTAPI_LOG" 2>&1 &
echo $! >> "$PID_FILE"

sleep 4

# Start Streamlit
setsid "$VENV/bin/streamlit" run web/app.py \
    --server.port 8501 --server.headless true --server.address 0.0.0.0 \
    > "$STREAMLIT_LOG" 2>&1 &
echo $! >> "$PID_FILE"

sleep 3

# Verify
FASTAPI_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
STREAMLIT_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 2>/dev/null)

LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Lumina Video Studio - Servers Started"
echo "═══════════════════════════════════════════════════"
echo ""

if [ "$FASTAPI_OK" = "200" ]; then
    echo "  ✓ FastAPI:    http://localhost:8000  (HTTP $FASTAPI_OK)"
else
    echo "  ✗ FastAPI:    Failed (HTTP $FASTAPI_OK) - check $FASTAPI_LOG"
fi

if [ "$STREAMLIT_OK" = "200" ]; then
    echo "  ✓ Streamlit:  http://localhost:8501  (HTTP $STREAMLIT_OK)"
else
    echo "  ✗ Streamlit:  Failed (HTTP $STREAMLIT_OK) - check $STREAMLIT_LOG"
fi

echo ""
echo "  Mobile API:  http://$LOCAL_IP:8000"
echo "  Web UI:      http://$LOCAL_IP:8501"
echo ""
echo "  PIDs saved to $PID_FILE"
echo "  Stop with: bash scripts/stop_servers.sh"
echo "═══════════════════════════════════════════════════"
