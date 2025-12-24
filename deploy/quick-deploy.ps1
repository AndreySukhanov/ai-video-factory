# PowerShell deployment script for Windows
# Quick deployment to DigitalOcean

$SERVER_IP = "64.23.158.28"
$SERVER_USER = "root"
$SERVER_PASS = "prM9R6WGdhKkG"
$APP_DIR = "/opt/microdrama-ai"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Microdrama AI - Quick Deploy (Windows)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server: $SERVER_IP"
Write-Host "Target directory: $APP_DIR"
Write-Host ""

# Function to execute SSH commands
function Invoke-SSH {
    param([string]$Command)

    $plink = Get-Command plink.exe -ErrorAction SilentlyContinue
    if ($plink) {
        # Using PuTTY's plink
        echo y | plink.exe -ssh -pw $SERVER_PASS "$SERVER_USER@$SERVER_IP" $Command
    } else {
        # Using OpenSSH
        $env:SSHPASS = $SERVER_PASS
        ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SERVER_USER@$SERVER_IP" $Command
    }
}

# Function to copy files via SCP
function Copy-ToServer {
    param(
        [string]$LocalPath,
        [string]$RemotePath
    )

    $pscp = Get-Command pscp.exe -ErrorAction SilentlyContinue
    if ($pscp) {
        # Using PuTTY's pscp
        pscp.exe -pw $SERVER_PASS -r $LocalPath "$SERVER_USER@${SERVER_IP}:$RemotePath"
    } else {
        # Using OpenSSH scp
        scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r $LocalPath "$SERVER_USER@${SERVER_IP}:$RemotePath"
    }
}

Write-Host "[1/8] Testing server connection..." -ForegroundColor Yellow
try {
    Invoke-SSH "echo 'Connection successful'" | Out-Null
    Write-Host "✓ Connected to server successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to connect to server" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/8] Installing Docker and dependencies..." -ForegroundColor Yellow
Invoke-SSH @"
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
"@

Write-Host ""
Write-Host "[3/8] Configuring firewall..." -ForegroundColor Yellow
Invoke-SSH @"
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
echo 'y' | ufw reload > /dev/null 2>&1 || true
echo '✓ Firewall configured'
"@

Write-Host ""
Write-Host "[4/8] Creating application directory..." -ForegroundColor Yellow
Invoke-SSH "mkdir -p $APP_DIR"
Write-Host "✓ Directory created: $APP_DIR" -ForegroundColor Green

Write-Host ""
Write-Host "[5/8] Uploading application files..." -ForegroundColor Yellow
Write-Host "  Uploading docker-compose.prod.yml..."
Copy-ToServer "docker-compose.prod.yml" "$APP_DIR/docker-compose.yml"

Write-Host "  Uploading nginx configuration..."
Copy-ToServer "nginx" "$APP_DIR/"

Write-Host "  Uploading backend..."
Copy-ToServer "backend" "$APP_DIR/"

Write-Host "  Uploading frontend..."
Copy-ToServer "frontend" "$APP_DIR/"

Write-Host "✓ Files uploaded successfully" -ForegroundColor Green

Write-Host ""
Write-Host "[6/8] Setting up environment variables..." -ForegroundColor Yellow

if (Test-Path "backend\.env") {
    Write-Host "  Using existing backend/.env file"
    Copy-ToServer "backend\.env" "$APP_DIR/backend/.env"
} else {
    Write-Host "  Creating .env from example..."
    Invoke-SSH @"
cd $APP_DIR/backend
if [ ! -f .env ]; then
    cp .env.example .env
fi
"@
    Write-Host ""
    Write-Host "⚠️  WARNING: Please configure API keys in backend/.env file!" -ForegroundColor Yellow
    Write-Host "   You need to add:"
    Write-Host "   - OPENROUTER_API_KEY"
    Write-Host "   - REPLICATE_API_TOKEN"
    Write-Host ""
    Read-Host "Press Enter after you've configured the .env file on the server, or Ctrl+C to exit"
}

Write-Host ""
Write-Host "[7/8] Building Docker images..." -ForegroundColor Yellow
Invoke-SSH "cd $APP_DIR && docker compose build"

Write-Host ""
Write-Host "[8/8] Starting application..." -ForegroundColor Yellow
Invoke-SSH "cd $APP_DIR && docker compose down || true && docker compose up -d"

Write-Host ""
Write-Host "Waiting for services to start..."
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "[Final] Checking deployment status..." -ForegroundColor Yellow
Invoke-SSH @"
cd $APP_DIR
echo '=== Container Status ==='
docker compose ps
echo ''
echo '=== Recent Logs ==='
docker compose logs --tail=20
"@

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete! 🚀" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your application is now running at:"
Write-Host "  Frontend: http://$SERVER_IP" -ForegroundColor Cyan
Write-Host "  Backend API: http://$SERVER_IP/api/v1/docs" -ForegroundColor Cyan
Write-Host ""
