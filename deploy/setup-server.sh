#!/bin/bash

# Script to set up DigitalOcean server for deployment
# Run this script on the server as root

set -e

echo "=== Starting Server Setup ==="

# Update system packages
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install essential tools
echo "Installing essential tools..."
apt-get install -y \
    curl \
    git \
    wget \
    vim \
    htop \
    ufw \
    ca-certificates \
    gnupg \
    lsb-release

# Install Docker
echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add the repository to Apt sources
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo "Docker installed successfully!"
else
    echo "Docker already installed"
fi

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Configure firewall
echo "Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
echo "y" | ufw enable

# Create deployment directory
echo "Creating deployment directory..."
mkdir -p /opt/microdrama-ai
chown -R $USER:$USER /opt/microdrama-ai

# Configure Docker to run without sudo
echo "Adding user to docker group..."
usermod -aG docker $USER

# Set up swap (if not exists)
if [ ! -f /swapfile ]; then
    echo "Setting up swap space..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
fi

# Optimize system for Docker
echo "Optimizing system..."
sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" >> /etc/sysctl.conf

echo ""
echo "=== Server Setup Complete! ==="
echo "Please log out and log back in for group changes to take effect"
echo "Then you can proceed with application deployment"
