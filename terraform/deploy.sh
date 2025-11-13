#!/bin/bash

# Deployment script for Telegram Transcribe Bot on GCP
set -e

echo "=== Telegram Transcribe Bot - GCP Deployment ==="
echo ""

# Check if terraform.tfvars exists
if [ ! -f "terraform.tfvars" ]; then
    echo "ERROR: terraform.tfvars not found!"
    echo "Please copy terraform.tfvars.example to terraform.tfvars and fill in your credentials."
    echo ""
    echo "  cp terraform.tfvars.example terraform.tfvars"
    echo "  nano terraform.tfvars  # Edit with your actual values"
    echo ""
    exit 1
fi

# Check GCP authentication
echo "Checking GCP authentication..."
CURRENT_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$CURRENT_ACCOUNT" ]; then
    echo "ERROR: Not authenticated with GCP"
    echo "Please run: gcloud auth login"
    exit 1
fi
echo "Authenticated as: $CURRENT_ACCOUNT"

# Check project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
echo "Current project: $CURRENT_PROJECT"
echo ""

# Confirm deployment
read -p "Do you want to proceed with deployment to phil-apps? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Set project
echo "Setting GCP project..."
gcloud config set project phil-apps

# Initialize Terraform
echo ""
echo "Initializing Terraform..."
terraform init

# Plan
echo ""
echo "Planning Terraform deployment..."
terraform plan -out=tfplan

# Apply
echo ""
read -p "Review the plan above. Apply these changes? (yes/no): " APPLY_CONFIRM
if [ "$APPLY_CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    rm -f tfplan
    exit 0
fi

echo ""
echo "Applying Terraform configuration..."
terraform apply tfplan
rm -f tfplan

# Get the webhook URL
echo ""
echo "Getting function URL..."
WEBHOOK_URL=$(terraform output -raw webhook_url)

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Webhook URL: $WEBHOOK_URL"
echo ""
echo "IMPORTANT: You need to set this webhook URL in Telegram:"
echo ""
echo "Run this command to set the webhook:"
echo ""
echo "  curl -X POST \"https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"url\": \"$WEBHOOK_URL\"}'"
echo ""
echo "Or use the helper script:"
echo "  ./set_webhook.sh"
echo ""
