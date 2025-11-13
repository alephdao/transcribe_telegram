# Local Webhook Testing Plan

## Goal
Test the webhook-based bot implementation locally before deploying to GCP to debug the rate limit issues faster.

## Current Problem
- **Polling mode** (local): Works perfectly ✅
- **Webhook mode** (GCP): Rate limit errors ❌
- **Issue**: Can't debug quickly because each deploy to GCP takes 2+ minutes

## Solution: Test Webhooks Locally

### Architecture

```
Telegram API
    ↓
ngrok (public URL)
    ↓
Local Flask/FastAPI server (webhook endpoint)
    ↓
Bot handler (same code as GCP)
```

## Implementation Steps

### 1. Install ngrok
```bash
# Install ngrok
brew install ngrok

# Or download from https://ngrok.com/download

# Authenticate (if not already done)
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 2. Create Local Webhook Server

Create `local_webhook_server.py`:

```python
from flask import Flask, request, jsonify
import asyncio
from transcribe import handle_audio, start, BOT_TOKEN
from telegram import Update
from telegram.ext import Application
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot application
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        update_data = request.get_json()
        logger.info(f"Received update: {update_data}")

        # Process the update
        update = Update.de_json(update_data, application.bot)

        # Run async handler
        asyncio.run(application.process_update(update))

        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    # Run on port 5000
    app.run(port=5000, debug=True)
```

### 3. Test Workflow

```bash
# Terminal 1: Start local webhook server
python3 local_webhook_server.py

# Terminal 2: Start ngrok tunnel
ngrok http 5000

# Terminal 3: Set webhook
NGROK_URL="https://YOUR-NGROK-URL.ngrok-free.app"
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${NGROK_URL}/webhook\"}"

# Verify webhook
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

### 4. Debug Strategy

**Test scenarios:**
1. ✅ Send single audio file
2. ✅ Send multiple audio files rapidly (test rate limiting)
3. ✅ Send very short audio (< 1 second)
4. ✅ Send long audio (> 1 minute)
5. ✅ Test retry logic by forcing errors

**Key differences to investigate:**
- **Polling**: Bot pulls updates sequentially
- **Webhook**: Telegram pushes updates simultaneously (parallel processing!)

**Hypothesis**: Webhook receives multiple updates at once → multiple parallel transcription requests → rate limit exceeded

### 5. Potential Fixes

#### Option A: Add Request Queue
```python
import asyncio
from asyncio import Queue

transcription_queue = Queue()

async def queue_processor():
    """Process transcription requests sequentially"""
    while True:
        update = await transcription_queue.get()
        try:
            await process_transcription(update)
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            transcription_queue.task_done()

@app.route('/webhook', methods=['POST'])
def webhook():
    update_data = request.get_json()
    # Add to queue instead of processing immediately
    asyncio.create_task(transcription_queue.put(update_data))
    return jsonify({'ok': True})
```

#### Option B: Add Rate Limiter
```python
from asyncio import Semaphore

# Limit to 1 concurrent transcription
transcription_semaphore = Semaphore(1)

async def transcribe_with_limit(audio_data):
    async with transcription_semaphore:
        return await transcribe_audio(audio_data)
```

#### Option C: Add Delay Between Requests
```python
import time

last_request_time = 0
MIN_REQUEST_INTERVAL = 5  # seconds

async def handle_audio_with_delay(update, context):
    global last_request_time

    # Wait if needed
    time_since_last = time.time() - last_request_time
    if time_since_last < MIN_REQUEST_INTERVAL:
        await asyncio.sleep(MIN_REQUEST_INTERVAL - time_since_last)

    last_request_time = time.time()
    return await handle_audio(update, context)
```

### 6. Expected Outcomes

**If local webhook works:**
- ✅ Deploy same code to GCP
- ✅ Should work identically

**If local webhook fails with rate limits:**
- ✅ We've reproduced the issue locally
- ✅ Can debug 10x faster
- ✅ Test fixes immediately
- ✅ Deploy proven solution to GCP

### 7. Rollback Plan

If webhooks don't work reliably:
1. Delete webhook: `curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"`
2. Run locally in polling mode (current working solution)
3. Consider Cloud Run with polling instead of Cloud Functions with webhooks

## Timeline

- **Setup**: 15 minutes
- **Initial testing**: 15 minutes
- **Debug & fix**: 30-60 minutes
- **Deploy to GCP**: 10 minutes
- **Total**: ~1.5-2 hours

## Benefits

✅ **Fast iteration**: Test in seconds, not minutes
✅ **Full control**: See all logs in real-time
✅ **Same environment**: Use exact same code as GCP
✅ **Cost-effective**: No GCP charges during testing
✅ **Educational**: Understand webhook vs polling differences

## Next Steps

1. Create `local_webhook_server.py`
2. Test with ngrok
3. Identify root cause of rate limits
4. Implement fix
5. Deploy proven solution to GCP

---

**Decision**: Do you want to proceed with local webhook testing?
