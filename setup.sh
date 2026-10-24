#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}   Blog-Gen Setup Script              ${NC}"
echo -e "${GREEN}======================================${NC}"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Error: Docker is not installed. Please install Docker and try again.${NC}"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Error: Python 3 is not installed.${NC}"
    exit 1
fi

# Check for Node
if ! command -v npm &> /dev/null; then
    echo -e "${YELLOW}Error: npm is not installed.${NC}"
    exit 1
fi

# --- Backend Setup ---
echo -e "\n${GREEN}>>> Setting up Backend...${NC}"
cd backend

# Create .env if missing
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    python3 generate_secret.py
    echo -e "${YELLOW}IMPORTANT: Please update backend/.env with your API keys after this script finishes!${NC}"
else
    echo ".env file already exists."
fi

# Start Database
echo "Starting PostgreSQL container..."
docker compose up -d --wait --wait-timeout 60 db

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run Migrations
echo "Running database migrations..."
alembic upgrade head

cd ..

# --- Frontend Setup ---
echo -e "\n${GREEN}>>> Setting up Frontend...${NC}"
cd frontend

echo "Installing Node dependencies..."
npm ci

cd ..

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}   Setup Complete!                    ${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "1. Update ${YELLOW}backend/.env${NC} with your API keys."
echo -e "2. Run ${YELLOW}./start.sh${NC} to launch the application."
