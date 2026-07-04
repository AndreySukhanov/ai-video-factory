# Deployment Guide for DigitalOcean

## Server information

- **IP**: SERVER_IP
- **OS**: Ubuntu 22.04 LTS
- **User**: root

## Step 1: Initial server setup

### 1.1 Connect to the server

```bash
ssh root@SERVER_IP
```

Password: set separately (do not store it in the repository)

### 1.2 Run the server setup script

```bash
# Run on the server:
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get install -y docker-compose-plugin

# Configure the firewall
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp

# Create the application directory
mkdir -p /opt/microdrama-ai
```

## Step 2: Uploading the code to the server

### Option A: Via Git (recommended)

```bash
# On the server
cd /opt/microdrama-ai
git clone https://github.com/AndreySukhanov/ai-video-factory.git .

# Or, if the repository is private, upload it as a ZIP
```

### Option B: Upload from your local machine

```bash
# From your local machine (Windows)
# Use WinSCP or scp to upload the files
scp -r C:\Users\Пользователь\Desktop\X4\AI_VIDEO\microdrama-ai root@SERVER_IP:/opt/microdrama-ai
```

## Step 3: Environment setup

```bash
# On the server
cd /opt/microdrama-ai

# Create the .env file for the backend
cp backend/.env.example backend/.env
nano backend/.env

# Add your API keys:
# OPENROUTER_API_KEY=sk-or-v1-xxxxx
# REPLICATE_API_TOKEN=r8_xxxxx
# FAL_KEY=xxxxx (if used)
```

## Step 4: Starting the application

```bash
# On the server
cd /opt/microdrama-ai

# Copy the production config
cp docker-compose.prod.yml docker-compose.yml

# Start the application
docker compose up -d --build

# Check the status
docker compose ps

# View the logs
docker compose logs -f
```

## Step 5: Health check

Open in a browser:
- Frontend: http://SERVER_IP
- Backend API: http://SERVER_IP/api/v1/docs

## Managing the application

### Viewing logs

```bash
# All services
docker compose logs -f

# A specific service
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f worker
```

### Restart

```bash
# Restart everything
docker compose restart

# Restart a specific service
docker compose restart backend
```

### Updating the code

```bash
cd /opt/microdroma-ai
git pull origin main
docker compose down
docker compose up -d --build
```

### Stopping

```bash
docker compose down
```

### Cleanup (deletes data)

```bash
docker compose down -v
```

## SSL setup (HTTPS)

### Option 1: Let's Encrypt (recommended)

```bash
# Install certbot
apt-get install -y certbot python3-certbot-nginx

# Obtain a certificate (replace your-domain.com)
certbot --nginx -d your-domain.com

# Certbot will update the nginx configuration automatically
```

### Option 2: Cloudflare (if you use it)

1. Add the domain to Cloudflare
2. Enable Proxy (orange cloud)
3. SSL/TLS mode: "Full" or "Full (strict)"
4. In Cloudflare DNS add an A record: `@` → `SERVER_IP`

## Resource monitoring

```bash
# Container usage
docker stats

# System resources
htop

# Disk space
df -h

# Docker usage
docker system df
```

## Troubleshooting

### Containers won't start

```bash
# Check the logs
docker compose logs

# Check the configuration
docker compose config

# Recreate the containers
docker compose down
docker compose up -d --build --force-recreate
```

### Not enough memory

```bash
# Add swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Ports are in use

```bash
# Check which ports are being used
netstat -tulpn | grep LISTEN

# Or
ss -tulpn | grep LISTEN

# Stop conflicting processes
sudo systemctl stop apache2  # if Apache is running
sudo systemctl stop nginx    # if the system Nginx is running
```

## Backup

### Creating a backup

```bash
# Stop the application
docker compose down

# Create a backup
cd /opt
tar -czf microdrama-ai-backup-$(date +%Y%m%d).tar.gz microdrama-ai/

# Download to your local machine
# scp root@SERVER_IP:/opt/microdrama-ai-backup-*.tar.gz ./
```

### Restore

```bash
# Upload the backup to the server
scp ./microdrama-ai-backup-*.tar.gz root@SERVER_IP:/opt/

# On the server
cd /opt
tar -xzf microdrama-ai-backup-*.tar.gz
cd microdrama-ai
docker compose up -d
```

## Security

### Recommendations:

1. **Change the root password**:
```bash
passwd
```

2. **Create a dedicated user**:
```bash
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy
```

3. **Set up SSH keys** instead of a password

4. **Disable root login over SSH**:
```bash
nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
systemctl restart sshd
```

5. **Use fail2ban**:
```bash
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

## Support

If you run into problems:
1. Check the logs: `docker compose logs -f`
2. Check the status: `docker compose ps`
3. Check the .env files
4. Check available resources: `free -h`, `df -h`
