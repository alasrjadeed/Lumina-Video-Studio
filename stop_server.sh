#!/bin/bash
# ============================================================
# Lumina Video Studio - Stop Script
# Stops all running servers
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping Lumina Video Studio servers...${NC}"

# Stop Streamlit
pkill -f "streamlit run" 2>/dev/null && echo -e "${GREEN}  ✓ Streamlit stopped${NC}" || echo -e "  - Streamlit not running"

# Stop FastAPI
pkill -f "uvicorn.*api.app" 2>/dev/null && echo -e "${GREEN}  ✓ FastAPI stopped${NC}" || echo -e "  - FastAPI not running"

# Stop any remaining Python processes from this project
pkill -f "lumina" 2>/dev/null || true

sleep 1
echo -e "${GREEN}All servers stopped.${NC}"
