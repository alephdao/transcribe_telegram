# Deployment Guide: Telegram Transcribe Bot on GCP

This guide walks you through deploying the Telegram Transcribe Bot as a serverless Cloud Function on Google Cloud Platform using Terraform.

## Prerequisites

1. **GCP Account**: `philip.galebach@gmail.com` with project `phil-apps`
2. **Google Cloud CLI**: Already installed at `/opt/homebrew/bin/gcloud`
3. **Terraform**: Installed on your system
4. **Credentials**:
   - Telegram Bot Token
   - Google AI API Key (for Gemini)

## Architecture Changes

**Important**: This deployment converts the bot from **polling mode** to **webhook mode**.

- **Before**: Bot continuously polls Telegram servers for new messages
- **After**: Telegram sends messages directly to your Cloud Function via webhooks

This is necessary for serverless deployment and reduces costs.

## Deployment Steps

### 1. Authenticate with GCP

```bash
# Verify you're logged in as the correct account
gcloud auth list

# If not logged in or wrong account
gcloud auth login

# Set the project
gcloud config set project phil-apps
```

### 2. Prepare Credentials

Create a `terraform.tfvars` file with your credentials:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and add your actual credentials:

```hcl
project_id          = "phil-apps"
region              = "us-central1"
telegram_bot_token  = "YOUR_ACTUAL_BOT_TOKEN"
google_ai_api_key   = "YOUR_ACTUAL_GOOGLE_AI_KEY"
```

**⚠️ IMPORTANT**: Never commit `terraform.tfvars` to git. It's already in `.gitignore`.

### 3. Deploy Using Terraform

```bash
cd terraform

# Make deployment script executable
chmod +x deploy.sh set_webhook.sh

# Run deployment
./deploy.sh
```

This script will:
1. Enable required GCP APIs
2. Create Secret Manager secrets for your credentials
3. Create a Cloud Storage bucket for function source
4. Deploy the Cloud Function
5. Set up IAM permissions
6. Output the webhook URL

### 4. Set Telegram Webhook

After deployment, you need to tell Telegram where to send updates:

```bash
./set_webhook.sh
```

Enter your bot token when prompted. The script will automatically configure the webhook.

**Manual alternative**:

```bash
WEBHOOK_URL=$(cd terraform && terraform output -raw webhook_url)
BOT_TOKEN="your_bot_token_here"

curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${WEBHOOK_URL}\"}"
```

### 5. Verify Deployment

Test your bot:
1. Open Telegram and find your bot
2. Send `/start` command
3. Send a voice message or audio file
4. Bot should transcribe it and send back the text

View logs:

```bash
# View Cloud Function logs
gcloud functions logs read telegram-transcribe-bot --region=us-central1 --limit=50

# Real-time logs
gcloud logging tail --resource-type=cloud_function
```

## What Gets Deployed

### GCP Resources Created

1. **Cloud Function (Gen 2)**: `telegram-transcribe-bot`
   - Runtime: Python 3.11
   - Memory: 512MB
   - Timeout: 540 seconds (9 minutes)
   - Region: us-central1

2. **Secret Manager Secrets**:
   - `telegram-bot-token`: Your Telegram bot token
   - `google-ai-api-key`: Your Google AI API key

3. **Cloud Storage Bucket**: `phil-apps-telegram-bot-functions`
   - Stores function source code

4. **Service Account**: `telegram-transcribe-bot-sa`
   - Has access to secrets
   - Runs the Cloud Function

5. **IAM Bindings**:
   - Public access to invoke the function (for Telegram webhooks)
   - Service account access to secrets

### APIs Enabled

- Cloud Functions API
- Cloud Build API
- Secret Manager API
- Artifact Registry API

## Cost Estimates

With moderate usage (assuming ~100 transcriptions/day):

- **Cloud Functions**: ~$0.50-2.00/month
  - First 2 million invocations free
  - Compute time charges minimal

- **Secret Manager**: ~$0.06/month
  - 2 secrets with 6 versions each

- **Cloud Storage**: <$0.10/month
  - Small storage for function source

- **Gemini API**: Pay per use
  - Check Google AI Studio pricing

**Total estimated cost**: $1-3/month (excluding Gemini API usage)

## Updating the Bot

To update the bot code:

1. Modify `function_source/main.py`
2. Run `./deploy.sh` again
3. Terraform will detect changes and redeploy

## Rollback

To destroy all resources:

```bash
cd terraform
terraform destroy
```

⚠️ This will delete all resources including secrets. Make sure you have backups of your credentials.

## Monitoring

### View Logs

```bash
# Function logs
gcloud functions logs read telegram-transcribe-bot --region=us-central1 --limit=100

# Real-time monitoring
gcloud logging tail --resource-type=cloud_function

# Filter by severity
gcloud logging read "resource.type=cloud_function AND severity>=ERROR" --limit=50
```

### Check Function Status

```bash
# List functions
gcloud functions list --region=us-central1

# Describe function
gcloud functions describe telegram-transcribe-bot --region=us-central1

# Check webhook status
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

## Troubleshooting

### Bot Not Responding

1. Check webhook is set:
   ```bash
   curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
   ```

2. Check function logs for errors:
   ```bash
   gcloud functions logs read telegram-transcribe-bot --region=us-central1 --limit=50
   ```

3. Verify secrets are accessible:
   ```bash
   gcloud secrets versions access latest --secret=telegram-bot-token
   ```

### Permission Errors

Ensure your GCP account has necessary permissions:
```bash
gcloud projects get-iam-policy phil-apps \
  --flatten="bindings[].members" \
  --filter="bindings.members:$(gcloud config get-value account)"
```

### Function Timeouts

If transcriptions timeout:
1. Increase function timeout in `terraform/main.tf`:
   ```hcl
   timeout_seconds = 900  # 15 minutes max
   ```
2. Redeploy: `./deploy.sh`

## Security Notes

1. **Secrets**: Stored in Google Secret Manager, not in environment variables
2. **IAM**: Function uses dedicated service account with minimal permissions
3. **HTTPS**: All communication encrypted via HTTPS
4. **Public Access**: Function is publicly accessible (required for Telegram webhooks)

## Switching Back to Local/Polling Mode

If you want to run the bot locally again:

1. Stop the Cloud Function:
   ```bash
   cd terraform
   terraform destroy
   ```

2. Delete the webhook:
   ```bash
   curl "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"
   ```

3. Run locally:
   ```bash
   cd ..
   python3 transcribe.py
   ```

## Support

For issues:
1. Check logs first
2. Verify webhook configuration
3. Test with simple audio files
4. Check GCP quotas and billing

## Additional Resources

- [Terraform GCP Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Google AI Gemini API](https://ai.google.dev/docs)
