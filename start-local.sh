#!/bin/bash

# Local Development Startup Script for Phase 1 Batch Processing
# Usage: ./start-local.sh
# This script starts both backend and frontend for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}Dr. Mohan's Sentiment Analysis - Phase 1${NC}"
echo -e "${GREEN}Local Batch Processing Setup${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Please run: cp .env.example .env"
    echo "Then edit .env with your API keys"
    exit 1
fi

# Check if required API keys are set
if grep -q "your_sarvam_api_key_here\|your_groq_api_key_here\|your_openrouter_api_key_here\|changeme" .env | grep -v "ADMIN_PASSWORD"; then
    echo -e "${YELLOW}⚠ Warning: Some API keys may not be configured${NC}"
    echo "Please ensure SARVAM_API_KEY, GROQ_API_KEY, and OPENROUTER_API_KEY are set"
    echo ""
fi

echo "Creating necessary directories..."
mkdir -p data/uploads
mkdir -p data/reports
mkdir -p backend/logs
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Start Backend
echo -e "${YELLOW}Starting Backend...${NC}"
cd backend

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

# Install requirements
echo "Checking Python dependencies..."
pip install -q -r requirements.txt

# Start backend in background
echo "Starting FastAPI server on http://localhost:8000..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
        echo -e "${RED}✗ Backend failed to start${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done
echo -e "${GREEN}✓ Backend is ready${NC}"
echo ""

# Start Frontend
echo -e "${YELLOW}Starting Frontend...${NC}"
cd ../frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies (this may take a minute)..."
    npm install -q
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    cat > .env.local << EOF
VITE_API_URL=http://localhost:8000/api
VITE_ADMIN_USERNAME=admin
VITE_ADMIN_PASSWORD=changeme
EOF
    echo -e "${GREEN}✓ Frontend .env.local created${NC}"
fi

# Start frontend in background
echo "Starting Vite dev server on http://localhost:5173..."
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"

echo ""
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}✓ Phase 1 Local Setup Started!${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""
echo "Services running:"
echo -e "  Backend:  ${GREEN}http://localhost:8000${NC}"
echo -e "  Frontend: ${GREEN}http://localhost:5173${NC}"
echo -e "  API Docs: ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo "To use the application:"
echo "  1. Open http://localhost:5173 in your browser"
echo "  2. Go to 'Batch Processing' tab"
echo "  3. Upload 5+ audio files"
echo "  4. Enter batch name and start processing"
echo "  5. Watch progress on Dashboard tab"
echo ""
echo "To stop services, press Ctrl+C"
echo ""

# Trap to kill both processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✓ Services stopped${NC}"
}

trap cleanup EXIT

# Wait for both processes
wait
