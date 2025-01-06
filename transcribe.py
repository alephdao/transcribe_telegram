import os
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import asyncio
import google.generativeai as genai
import aiohttp
from dotenv import load_dotenv
import logging
from telegram import Update
import base64
import boto3
from botocore.exceptions import ClientError
from io import BytesIO
import math

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_aws_parameter(parameter_name):
    """
    Retrieve a parameter from AWS Parameter Store
    Returns None if not running on EC2 or parameter not found
    """
    try:
        # Try to create SSM client - will fail fast if no AWS credentials
        try:
            ssm = boto3.client('ssm', region_name='us-east-1')
        except:
            logger.info("No AWS credentials found - skipping Parameter Store")
            return None
            
        # Try to get parameter
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
        
    except Exception as e:
        logger.info(f"Could not retrieve parameter from AWS: {e}")
        return None

def get_credentials():
    """
    Get credentials from either AWS Parameter Store or environment variables
    Returns tuple of (bot_token, google_ai_api_key)
    """
    # Try AWS Parameter Store first
    bot_token = get_aws_parameter('galebach_transcriber_bot_token')
    google_ai_api_key = get_aws_parameter('GOOGLE_AI_API_KEY')
    
    # Fall back to environment variables if AWS params not available
    if not bot_token or not google_ai_api_key:
        logger.info("Using environment variables for credentials")
        load_dotenv()
        bot_token = os.getenv("galebach_transcriber_bot_token")
        google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
    else:
        logger.info("Using AWS Parameter Store for credentials")

    if not bot_token or not google_ai_api_key:
        raise ValueError("Missing required credentials from both AWS and environment variables")
        
    return bot_token, google_ai_api_key

# Replace the credential loading section with the new method
BOT_TOKEN, GOOGLE_AI_API_KEY = get_credentials()

# Initialize Gemini
genai.configure(api_key=GOOGLE_AI_API_KEY)
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

# Add constant
MAX_CHUNK_SIZE = 19 * 1024 * 1024  # 20MB in bytes

async def chunk_audio_data(audio_data):
    """
    Split audio data into 20MB chunks
    Returns list of BytesIO objects containing chunks
    """
    total_size = len(audio_data)
    num_chunks = math.ceil(total_size / MAX_CHUNK_SIZE)
    chunks = []
    
    for i in range(num_chunks):
        start = i * MAX_CHUNK_SIZE
        end = min(start + MAX_CHUNK_SIZE, total_size)
        chunk = BytesIO(audio_data[start:end])
        chunks.append(chunk)
    
    return chunks

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
        # Get the audio file
        audio_file = update.message.voice or update.message.audio
        file_type = "voice message" if update.message.voice else f"audio file ({update.message.audio.mime_type})"
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"Processing your {file_type}... Please wait."
        )
        
        try:
            # Download the audio
            logger.info("Downloading audio file")
            audio_data = await download_file(audio_file)
            logger.info(f"Downloaded audio file, size: {len(audio_data)} bytes")
            
            # Process in chunks if file is large
            if len(audio_data) > MAX_CHUNK_SIZE:
                logger.info("File exceeds 20MB, processing in chunks")
                chunks = await chunk_audio_data(audio_data)
                
                # Process each chunk and combine transcripts
                full_transcript = []
                for i, chunk in enumerate(chunks, 1):
                    await processing_msg.edit_text(
                        f"Processing chunk {i} of {len(chunks)}... Please wait."
                    )
                    chunk_transcript = await transcribe_audio(chunk.getvalue())
                    # Remove the "# Transcription" header from subsequent chunks
                    if i > 1:
                        chunk_transcript = chunk_transcript.replace("# Transcription\n\n", "")
                    full_transcript.append(chunk_transcript)
                
                transcript = "\n\n".join(full_transcript)
            else:
                # Process normally if file is small
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
