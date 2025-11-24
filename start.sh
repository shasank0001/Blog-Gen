#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Function to kill background processes on exit
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

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
uvicorn app.main:app --reload &
BACKEND_PID=$!
cd ..

# Start Frontend
echo -e "${BLUE}Starting Frontend (Port 5173)...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}Application is running!${NC}"
echo -e "Frontend: http://localhost:5173"
echo -e "Backend:  http://localhost:8000/docs"
echo -e "Press Ctrl+C to stop."

wait
