#!/bin/bash

# Script to set Telegram webhook after deployment
set -e

echo "=== Set Telegram Webhook ==="
echo ""

# Check if terraform has been applied
if [ ! -f "terraform.tfstate" ]; then
    echo "ERROR: terraform.tfstate not found!"
    echo "Please run ./deploy.sh first to deploy the function."
    exit 1
fi

# Get webhook URL from Terraform output
WEBHOOK_URL=$(terraform output -raw webhook_url 2>/dev/null)
if [ -z "$WEBHOOK_URL" ]; then
    echo "ERROR: Could not get webhook URL from Terraform output"
    exit 1
fi

echo "Webhook URL: $WEBHOOK_URL"
echo ""

# Prompt for bot token
read -p "Enter your Telegram Bot Token: " BOT_TOKEN
if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: Bot token cannot be empty"
    exit 1
fi

# Set the webhook
echo ""
echo "Setting webhook..."
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${WEBHOOK_URL}\"}")

echo "Response from Telegram:"
echo "$RESPONSE" | python3 -m json.tool

# Check if successful
if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo ""
    echo "✅ Webhook set successfully!"
    echo ""
    echo "You can now send audio files to your bot and they will be transcribed."
else
    echo ""
    echo "❌ Failed to set webhook. Please check the error message above."
    exit 1
fi
