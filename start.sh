#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Function to kill background processes on exit
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"
    pids="$(jobs -p)"
    if [ -n "$pids" ]; then kill $pids 2>/dev/null || true; fi
}

trap cleanup EXIT
trap 'exit 130' SIGINT
trap 'exit 143' SIGTERM

# Validate setup was completed
if [ ! -d "backend/venv" ]; then
    echo -e "${RED}Error: Virtual environment not found.${NC}"
    echo -e "Please run ${GREEN}./setup.sh${NC} first."
    exit 1
fi

if [ ! -f "backend/.env" ]; then
    echo -e "${RED}Error: backend/.env not found.${NC}"
    echo -e "Please run ${GREEN}./setup.sh${NC} and configure your API keys."
    exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${RED}Error: Frontend dependencies not installed.${NC}"
    echo -e "Please run ${GREEN}./setup.sh${NC} first."
    exit 1
fi

echo -e "${GREEN}Starting Blog-Gen...${NC}"

# Activate virtual env and start Backend
echo -e "${BLUE}Starting Backend (Port 8000)...${NC}"
cd backend
source venv/bin/activate
docker compose up -d --wait --wait-timeout 60 db
alembic upgrade head || exit 1
python -m app.worker &
uvicorn app.main:app --reload &
BACKEND_PID=$!
cd ..

# Start Frontend
echo -e "${BLUE}Starting Frontend (Port 5173)...${NC}"
cd frontend
node node_modules/vite/bin/vite.js &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}Application is running!${NC}"
echo -e "Frontend: http://localhost:5173"
echo -e "Backend:  http://localhost:8000/docs"
echo -e "Press Ctrl+C to stop."

wait
