#!/bin/bash

# Deployment script for microdrama-ai on DigitalOcean
# Run this script from your local machine

set -e

SERVER_IP="64.23.158.28"
SERVER_USER="root"
APP_DIR="/opt/microdrama-ai"
REPO_URL="https://github.com/AndreySukhanov/ai-video-factory.git"

echo "=== Starting Deployment to $SERVER_IP ==="

# Function to run commands on remote server
remote_exec() {
    ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP "$@"
}

# Function to copy files to remote server
remote_copy() {
    scp -o StrictHostKeyChecking=no -r "$1" $SERVER_USER@$SERVER_IP:"$2"
}

echo "Step 1: Checking server connection..."
if remote_exec "echo 'Connected successfully'"; then
    echo "✓ Server connection successful"
else
    echo "✗ Failed to connect to server"
    exit 1
fi

echo ""
echo "Step 2: Setting up application directory..."
remote_exec "mkdir -p $APP_DIR"

echo ""
echo "Step 3: Copying application files..."
# Copy necessary files
remote_copy "../docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"
remote_copy "../nginx" "$APP_DIR/"
remote_copy "../frontend" "$APP_DIR/"
remote_copy "../backend" "$APP_DIR/"

echo ""
echo "Step 4: Setting up environment variables..."
echo "Please configure .env files on the server at: $APP_DIR/backend/.env"
echo "Required variables:"
echo "  - OPENROUTER_API_KEY"
echo "  - REPLICATE_API_TOKEN"
echo ""
read -p "Press enter when .env is configured..."

echo ""
echo "Step 5: Building and starting containers..."
remote_exec "cd $APP_DIR && docker compose down || true"
remote_exec "cd $APP_DIR && docker compose build"
remote_exec "cd $APP_DIR && docker compose up -d"

echo ""
echo "Step 6: Checking container status..."
sleep 5
remote_exec "cd $APP_DIR && docker compose ps"

echo ""
echo "Step 7: Viewing logs..."
remote_exec "cd $APP_DIR && docker compose logs --tail=50"

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Your application should be accessible at:"
echo "  - Frontend: http://$SERVER_IP"
echo "  - Backend API: http://$SERVER_IP/api"
echo ""
echo "Useful commands:"
echo "  - View logs: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose logs -f'"
echo "  - Restart: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose restart'"
echo "  - Stop: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose down'"
echo "  - Update: ./deploy.sh"
