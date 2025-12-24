#!/bin/bash

# Quick deployment script for microdrama-ai
# This script will automatically deploy the application to DigitalOcean

set -e

# Server configuration
SERVER_IP="SERVER_IP"
SERVER_USER="root"
SERVER_PASS="prM9R6WGdhKkG"
APP_DIR="/opt/microdrama-ai"

echo "=========================================="
echo "  Microdrama AI - Quick Deploy"
echo "=========================================="
echo ""
echo "Server: $SERVER_IP"
echo "Target directory: $APP_DIR"
echo ""

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo "Installing sshpass for password authentication..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y sshpass
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass
    else
        echo "Please install sshpass manually or use SSH keys"
        exit 1
    fi
fi

# Function to execute commands on remote server
remote_exec() {
    sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "$@"
}

# Function to copy files to remote server
remote_copy() {
    sshpass -p "$SERVER_PASS" scp -o StrictHostKeyChecking=no -r "$1" "$SERVER_USER@$SERVER_IP:$2"
}

echo "[1/8] Testing server connection..."
if remote_exec "echo 'Connection successful'" > /dev/null 2>&1; then
    echo "✓ Connected to server successfully"
else
    echo "✗ Failed to connect to server"
    exit 1
fi

echo ""
echo "[2/8] Installing Docker and dependencies..."
remote_exec "
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq

    # Install Docker if not installed
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sh /tmp/get-docker.sh
        rm /tmp/get-docker.sh
    fi

    # Install Docker Compose plugin
    apt-get install -y -qq docker-compose-plugin git

    echo '✓ Docker installed'
"

echo ""
echo "[3/8] Configuring firewall..."
remote_exec "
    ufw --force enable
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp
    echo 'y' | ufw reload > /dev/null 2>&1 || true
    echo '✓ Firewall configured'
"

echo ""
echo "[4/8] Creating application directory..."
remote_exec "
    mkdir -p $APP_DIR
    echo '✓ Directory created: $APP_DIR'
"

echo ""
echo "[5/8] Uploading application files..."
echo "  Uploading docker-compose.prod.yml..."
remote_copy "docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"

echo "  Uploading nginx configuration..."
remote_copy "nginx" "$APP_DIR/"

echo "  Uploading backend..."
remote_copy "backend" "$APP_DIR/"

echo "  Uploading frontend..."
remote_copy "frontend" "$APP_DIR/"

echo "✓ Files uploaded successfully"

echo ""
echo "[6/8] Setting up environment variables..."

# Check if .env file exists locally
if [ -f "backend/.env" ]; then
    echo "  Using existing backend/.env file"
    remote_copy "backend/.env" "$APP_DIR/backend/.env"
else
    echo "  Creating .env from example..."
    remote_exec "
        cd $APP_DIR/backend
        if [ ! -f .env ]; then
            cp .env.example .env
        fi
    "
    echo ""
    echo "⚠️  WARNING: Please configure API keys in backend/.env file!"
    echo "   You need to add:"
    echo "   - OPENROUTER_API_KEY"
    echo "   - REPLICATE_API_TOKEN"
    echo ""
    read -p "Press Enter after you've configured the .env file on the server, or Ctrl+C to exit and configure later..."
fi

echo ""
echo "[7/8] Building Docker images..."
remote_exec "
    cd $APP_DIR
    docker compose build
"

echo ""
echo "[8/8] Starting application..."
remote_exec "
    cd $APP_DIR
    docker compose down || true
    docker compose up -d
"

echo ""
echo "Waiting for services to start..."
sleep 10

echo ""
echo "[Final] Checking deployment status..."
remote_exec "
    cd $APP_DIR
    echo '=== Container Status ==='
    docker compose ps
    echo ''
    echo '=== Recent Logs ==='
    docker compose logs --tail=20
"

echo ""
echo "=========================================="
echo "  Deployment Complete! 🚀"
echo "=========================================="
echo ""
echo "Your application is now running at:"
echo "  Frontend: http://$SERVER_IP"
echo "  Backend API: http://$SERVER_IP/api/v1/docs"
echo ""
echo "Useful commands:"
echo "  View logs: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose logs -f'"
echo "  Restart: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose restart'"
echo "  Stop: ssh $SERVER_USER@$SERVER_IP 'cd $APP_DIR && docker compose down'"
echo ""
