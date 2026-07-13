#!/bin/bash
# Lumina Video Studio - Stop Servers
PID_FILE="/tmp/lumina_pids"

echo "Stopping Lumina Video Studio servers..."

if [ -f "$PID_FILE" ]; then
    while read pid; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo "  ✓ Killed PID $pid"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    echo "  No PID file found, killing by name..."
    pkill -f "uvicorn api.app" 2>/dev/null && echo "  ✓ Stopped FastAPI" || echo "  - FastAPI not running"
    pkill -f "streamlit run" 2>/dev/null && echo "  ✓ Stopped Streamlit" || echo "  - Streamlit not running"
fi

sleep 1
echo "All servers stopped."
