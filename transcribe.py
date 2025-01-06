import os
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import asyncio
import google.generativeai as genai
import aiohttp
from dotenv import load_dotenv
import logging
from telegram import Update
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("galebach_transcriber_bot_token")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not BOT_TOKEN or not GOOGLE_API_KEY:
    raise ValueError("Missing required environment variables")

# Initialize Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash-exp')

TRANSCRIPTION_PROMPT = """Please transcribe this audio accurately in its original language. 
If there are multiple speakers, identify and label them.
Format the output as a markdown document with speaker labels."""

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
    Transcribe audio data using Gemini API
    """
    try:
        # Convert audio data to base64
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
        
        response = model.generate_content(content_parts)
        transcript = f"# Transcription\n\n{response.text}"
        return transcript
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise

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

async def send_transcript_file(update, transcript):
    """
    Save and send transcript as a markdown file using the original audio filename.
    """
    import tempfile
    
    # Handle both direct messages and callback queries
    message = update.message if update.message else update.callback_query.message
    
    # Get original filename from stored user data
    if hasattr(message, 'voice'):
        original_filename = f"voice_message_{message.date.strftime('%Y%m%d_%H%M%S')}"
    else:
        # Remove file extension from original filename
        original_filename = os.path.splitext(message.audio.file_name)[0] if hasattr(message, 'audio') else "transcript"
    
    # Create temporary file
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
        # Clean up temporary file
        os.unlink(temp_file_path)

async def handle_audio(update, context):
    """
    Handle incoming audio files and voice messages.
    """
    try:
        # Check if audio format is supported
        if update.message.audio and update.message.audio.mime_type not in SUPPORTED_AUDIO_TYPES:
            await update.message.reply_text(
                f"Sorry, the format {update.message.audio.mime_type} is not supported. "
                "Please send a common audio format like MP3, WAV, OGG, or M4A."
            )
            return
        
        # Get the audio file
        audio_file = update.message.voice or update.message.audio
        file_type = "voice message" if update.message.voice else f"audio file ({update.message.audio.mime_type})"
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"Processing your {file_type}... Please wait."
        )
        
        try:
            # Download and transcribe the audio
            logger.info("Downloading audio file")
            audio_data = await download_file(audio_file)
            logger.info(f"Downloaded audio file, size: {len(audio_data)} bytes")
            
            logger.info("Starting transcription")
            transcript = await transcribe_audio(audio_data)
            logger.info("Transcription completed")
            
            # Delete the processing message
            await processing_msg.delete()
            
            # Send transcript
            await send_transcript_file(update, transcript)
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            error_message = (
                "Sorry, there was an error processing your audio file.\n"
                f"Error: {str(e)}\n\n"
                "Please try again or contact support if the issue persists."
            )
            await processing_msg.edit_text(error_message)
            
    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        await update.message.reply_text(
            f"Sorry, there was an error processing your audio file. Error: {str(e)}"
        )

def main():
    """Run the bot."""
    try:
        # Create and run the application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(
            filters.VOICE | filters.AUDIO, 
            handle_audio
        ))
        
        # Run the bot
        logger.info("Bot is running...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        logger.info("\nBot stopped gracefully")
    except Exception as e:
        logger.error(f"Error occurred: {e}")

if __name__ == '__main__':
    main()
