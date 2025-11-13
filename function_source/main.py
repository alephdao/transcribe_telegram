import os
import json
import logging
import base64
import tempfile
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import google.generativeai as genai
import aiohttp
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import gc
from contextlib import contextmanager
import functions_framework
from flask import Request

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_deployment_mode():
    """Get deployment mode from environment variable"""
    return os.getenv('DEPLOYMENT_MODE', 'local')

DEPLOYMENT_MODE = get_deployment_mode()

def get_credentials():
    """
    Get credentials from environment variables (populated by Cloud Function from Secret Manager)
    Returns tuple of (bot_token, google_ai_api_key)
    """
    bot_token = os.getenv("galebach_transcriber_bot_token")
    google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")

    if not bot_token or not google_ai_api_key:
        raise ValueError("Missing required credentials")

    return bot_token, google_ai_api_key

BOT_TOKEN, GOOGLE_AI_API_KEY = get_credentials()

# Initialize Gemini
genai.configure(api_key=GOOGLE_AI_API_KEY)

# Add a context manager for model handling
@contextmanager
def model_context():
    """
    Context manager to handle model initialization and cleanup with safety settings
    """
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash',
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
        )
        yield model
    finally:
        del model
        gc.collect()

# Update the prompt to be more specific
TRANSCRIPTION_PROMPT = """Transcribe this audio accurately in its original language.

If there are multiple speakers, identify and label them as 'Speaker 1:', 'Speaker 2:', etc.

Do not include any headers, titles, or additional text - only the transcription itself.

When transcribing, add line breaks between different paragraphs or distinct segments of speech to improve readability."""

# Supported audio MIME types
SUPPORTED_AUDIO_TYPES = {
    'audio/mpeg',        # .mp3
    'audio/wav',         # .wav
    'audio/ogg',         # .ogg
    'audio/x-m4a',       # .m4a
    'audio/mp4',         # .mp4 audio
    'audio/x-wav',       # alternative wav
    'audio/webm',        # .webm
    'audio/aac',         # .aac
    'audio/x-aac',       # alternative aac
}

async def transcribe_audio(audio_data):
    """
    Transcribe audio data using Gemini API with proper cleanup
    """
    try:
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        content_parts = [
            {"text": TRANSCRIPTION_PROMPT},
            {
                "inline_data": {
                    "mime_type": "audio/mp4",
                    "data": audio_base64
                }
            }
        ]

        with model_context() as current_model:
            response = current_model.generate_content(content_parts)
            transcript = response.text

            # Log original transcript
            logger.info("Original transcript from Gemini:")
            logger.info("-" * 50)
            logger.info(transcript)
            logger.info("-" * 50)

            # Remove any variations of transcription headers
            transcript = transcript.replace("# Transcription\n\n", "")
            transcript = transcript.replace("Okay, here is the transcription:\n", "")
            transcript = transcript.replace("Here's the transcription:\n", "")
            transcript = transcript.strip()

            # Count actual speaker labels using a more precise pattern
            speaker_labels = set()
            for line in transcript.split('\n'):
                if line.strip().startswith(('Speaker ', '**Speaker ')):
                    for i in range(1, 10):
                        if f"Speaker {i}:" in line or f"**Speaker {i}:**" in line:
                            speaker_labels.add(i)

            # Log number of speakers detected
            logger.info(f"Number of unique speakers detected: {len(speaker_labels)}")
            logger.info(f"Speaker numbers found: {sorted(list(speaker_labels))}")

            # Only remove speaker labels if there's exactly one speaker
            if len(speaker_labels) == 1:
                transcript = transcript.replace("**Speaker 1:**", "")
                transcript = transcript.replace("Speaker 1:", "")
                transcript = transcript.strip()

            # Log cleaned transcript
            logger.info("Cleaned transcript:")
            logger.info("-" * 50)
            logger.info(transcript)
            logger.info("-" * 50)

            return transcript

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise
    finally:
        gc.collect()

async def start(update, context):
    """
    Handle the /start command.
    """
    welcome_message = (
        "Hello! I can transcribe audio files for you.\n\n"
        "Supported formats:\n"
        "- Voice messages\n"
        "- Audio files (.mp3, .wav, .ogg, .m4a, .aac, etc.)\n\n"
        "Just send me any audio file and I'll transcribe it for you!"
    )
    await update.message.reply_text(welcome_message)

async def download_file(file):
    """
    Download a file from Telegram servers.
    """
    file_obj = await file.get_file()
    async with aiohttp.ClientSession() as session:
        async with session.get(file_obj.file_path) as response:
            return await response.read()

async def send_transcript(update, transcript):
    """
    Send transcript either as a message or file depending on length.
    Max Telegram message length is 4096 characters.
    """
    message = update.message if update.message else update.callback_query.message

    if len(transcript) <= 4096:
        escaped_transcript = transcript.replace('.', '\\.').replace('-', '\\-').replace('!', '\\!').replace('(', '\\(').replace(')', '\\)')

        await message.reply_text(
            escaped_transcript,
            parse_mode='MarkdownV2'
        )
        return

    # Otherwise, send as file
    if hasattr(message, 'voice'):
        original_filename = f"voice_message_{message.date.strftime('%Y%m%d_%H%M%S')}"
    else:
        original_filename = os.path.splitext(message.audio.file_name)[0] if hasattr(message, 'audio') else "transcript"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
        temp_file.write(transcript)
        temp_file_path = temp_file.name

    try:
        await message.reply_document(
            document=open(temp_file_path, 'rb'),
            filename=f"{original_filename}.md",
            caption="Here's your transcript as a markdown file."
        )
    finally:
        os.unlink(temp_file_path)

async def handle_audio(update, context):
    """
    Handle incoming audio files and voice messages.
    """
    try:
        if update.message.audio and update.message.audio.mime_type not in SUPPORTED_AUDIO_TYPES:
            await update.message.reply_text(
                f"Sorry, the format {update.message.audio.mime_type} is not supported. "
                "Please send a common audio format like MP3, WAV, OGG, or M4A."
            )
            return

        audio_file = update.message.voice or update.message.audio
        file_type = "voice message" if update.message.voice else f"audio file ({update.message.audio.mime_type})"

        processing_msg = await update.message.reply_text(
            f"Processing your {file_type}... Please wait."
        )

        try:
            logger.info("Downloading audio file")
            audio_data = await download_file(audio_file)
            logger.info(f"Downloaded audio file, size: {len(audio_data)} bytes")

            logger.info("Starting transcription")
            transcript = await transcribe_audio(audio_data)
            logger.info("Transcription completed")

            await processing_msg.delete()
            await send_transcript(update, transcript)

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            error_message = (
                "Sorry, there was an error processing your audio file.\n"
                f"Error: {str(e)}\n\n"
                "Note: telegram bots have a 20MB file limit. telegram API allows 2GB."
            )
            await processing_msg.edit_text(error_message)

    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        await update.message.reply_text(
            f"Sorry, there was an error processing your audio file. Error: {str(e)}"
        )

# Global application instance
application = None

def get_application():
    """Get or create the Application instance"""
    global application
    if application is None:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    return application

@functions_framework.http
def webhook(request: Request):
    """
    Cloud Function entry point for handling Telegram webhooks
    """
    try:
        # Only accept POST requests
        if request.method != 'POST':
            return {'statusCode': 405, 'body': 'Method Not Allowed'}

        # Get the update from Telegram
        update_data = request.get_json()
        logger.info(f"Received update: {update_data}")

        # Process the update
        app = get_application()
        update = Update.de_json(update_data, app.bot)

        # Run the update handler asynchronously
        async def process_update():
            async with app:
                await app.initialize()
                await app.process_update(update)

        asyncio.run(process_update())

        return {'statusCode': 200, 'body': 'OK'}

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': f'Internal Server Error: {str(e)}'}
