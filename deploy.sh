#!/bin/bash
set -e

echo "=== Synclavix Deploy Script ==="

# Check .env
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Please create it first."
  exit 1
fi

# Create logs dir
mkdir -p logs

# Down existing stack
echo "Stopping existing containers..."
docker compose down --remove-orphans 2>/dev/null || true

# Build
echo "Building images..."
docker compose build --no-cache

# Start
echo "Starting stack..."
docker compose up -d

# Wait and verify
sleep 5
echo ""
echo "=== Container Status ==="
docker compose ps

echo ""
echo "=== Deploy Complete ==="
echo "Dashboard: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP'):80"
