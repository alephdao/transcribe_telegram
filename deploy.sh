#!/bin/bash

# Deploy script for Telegram transcription bot

# Make script exit on error
set -e

echo "Deploying Telegram Transcription Bot..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    sudo apt update
    sudo apt install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "Docker installed successfully. Please log out and log back in, then run this script again."
    exit 0
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create an .env file with your configuration."
    echo "You can use .env.example as a template."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Build and start the container
echo "Building and starting Docker container..."
docker-compose up -d --build

echo "Checking container status..."
docker-compose ps

echo "Deployment complete! Your Telegram bot should now be running."
echo "Check the logs with: docker-compose logs -f"
