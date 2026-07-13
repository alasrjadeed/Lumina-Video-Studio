#!/bin/bash
# ============================================================
# Lumina Video Studio - Server Startup Script
# Starts both Streamlit (Web UI) and FastAPI (REST API + Mobile)
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/oem/Documents/Lumina Video Studio"
VENV_DIR="$PROJECT_DIR/.venv"
STREAMLIT_PORT=8501
FASTAPI_PORT=8000

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║           🎬  Lumina Video Studio  🎬                       ║"
echo "║                                                              ║"
echo "║   Web UI:      http://localhost:$STREAMLIT_PORT              ║"
echo "║   Mobile API:  http://localhost:$FASTAPI_PORT                ║"
echo "║   API Docs:    http://localhost:$FASTAPI_PORT/docs           ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_DIR${NC}"
    exit 1
fi

# Kill existing processes
echo -e "${YELLOW}Stopping existing servers...${NC}"
pkill -f "streamlit run" 2>/dev/null || true
pkill -f "uvicorn.*api.app" 2>/dev/null || true
sleep 2

# Start FastAPI server
echo -e "${GREEN}Starting FastAPI server on port $FASTAPI_PORT...${NC}"
cd "$PROJECT_DIR"
nohup "$VENV_DIR/bin/python" -m uvicorn api.app:app \
    --host 0.0.0.0 \
    --port $FASTAPI_PORT \
    --log-level info \
    > /tmp/lumina_fastapi.log 2>&1 &
FASTAPI_PID=$!
echo -e "${GREEN}  ✓ FastAPI started (PID: $FASTAPI_PID)${NC}"

# Wait for FastAPI to start
sleep 3

# Start Streamlit
echo -e "${GREEN}Starting Streamlit on port $STREAMLIT_PORT...${NC}"
nohup "$VENV_DIR/bin/streamlit" run web/app.py \
    --server.port $STREAMLIT_PORT \
    --server.headless true \
    --server.address 0.0.0.0 \
    > /tmp/lumina_streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo -e "${GREEN}  ✓ Streamlit started (PID: $STREAMLIT_PID)${NC}"

# Wait for services to start
sleep 3

# Check status
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

# Check FastAPI
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$FASTAPI_PORT/health | grep -q "200"; then
    echo -e "${GREEN}  ✓ FastAPI:      http://localhost:$FASTAPI_PORT${NC}"
else
    echo -e "${RED}  ✗ FastAPI:      Failed to start (check /tmp/lumina_fastapi.log)${NC}"
fi

# Check Streamlit
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$STREAMLIT_PORT | grep -q "200"; then
    echo -e "${GREEN}  ✓ Streamlit:    http://localhost:$STREAMLIT_PORT${NC}"
else
    echo -e "${RED}  ✗ Streamlit:    Failed to start (check /tmp/lumina_streamlit.log)${NC}"
fi

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}For mobile app, connect to:${NC}"
echo -e "  ${GREEN}$(hostname -I | awk '{print $1}'):$FASTAPI_PORT${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Trap to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping servers...${NC}"
    kill $FASTAPI_PID 2>/dev/null || true
    kill $STREAMLIT_PID 2>/dev/null || true
    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
