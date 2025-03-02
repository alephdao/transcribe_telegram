import os
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import asyncio
from deepgram import DeepgramClient, PrerecordedOptions
import aiohttp
from dotenv import load_dotenv
import logging
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()  

# Get environment variables
BOT_TOKEN = os.getenv("galebach_transcriber_bot_token")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Initialize Deepgram client
deepgram = DeepgramClient(DEEPGRAM_API_KEY)

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

async def create_markdown_transcript(response):
    """
    Create a markdown formatted transcript from the Deepgram response.
    """
    transcript = response.results.channels[0].alternatives[0]
    words = transcript.words

    markdown_content = "# Transcription\n\n"
    current_speaker = None
    current_paragraph = ""

    for word in words:
        if word.speaker != current_speaker:
            if current_paragraph:
                markdown_content += f"## Speaker {current_speaker}\n\n{current_paragraph.strip()}\n\n"
                current_paragraph = ""
            current_speaker = word.speaker

        current_paragraph += f"{word.punctuated_word} "

    if current_paragraph:
        markdown_content += f"## Speaker {current_speaker}\n\n{current_paragraph.strip()}\n\n"

    return markdown_content

async def transcribe_audio(audio_data):
    """
    Transcribe audio data using Deepgram API.
    """
    try:
        source = {
            "buffer": audio_data,
        }

        options = PrerecordedOptions(
            smart_format=True,
            model='general',
            language='en',
            punctuate=True,
            diarize=True
        )

        logger.info("Transcribing audio")
        response = await deepgram.listen.asyncrest.v("1").transcribe_file(
            source=source,
            options=options
        )
        
        transcript = await create_markdown_transcript(response)
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
    Save and send transcript as a markdown file.
    
    Args:
        update: Telegram update object
        transcript (str): The complete transcript text
    """
    import tempfile
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
        temp_file.write(transcript)
        temp_file_path = temp_file.name
    
    # Send file
    try:
        await update.message.reply_document(
            document=open(temp_file_path, 'rb'),
            filename='transcript.md',
            caption="Here's your transcript as a markdown file."
        )
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)

async def handle_audio(update, context):
    """
    Handle incoming audio files and voice messages and transcribe them.
    """
    try:
        # Determine the type of audio message
        if update.message.voice:
            audio_file = update.message.voice
            file_type = "voice message"
        elif update.message.audio:
            audio_file = update.message.audio
            file_type = f"audio file ({audio_file.mime_type})"
        else:
            await update.message.reply_text("Please send an audio file or voice message.")
            return

        # Check if audio format is supported
        if (not update.message.voice and 
            audio_file.mime_type not in SUPPORTED_AUDIO_TYPES):
            await update.message.reply_text(
                f"Sorry, the format {audio_file.mime_type} is not supported. "
                "Please send a common audio format like MP3, WAV, OGG, or M4A."
            )
            return

        # Send processing message
        processing_msg = await update.message.reply_text(
            f"Processing your {file_type}... Please wait."
        )

        # Download and transcribe the audio
        audio_data = await download_file(audio_file)
        transcript = await transcribe_audio(audio_data)
        
        # Delete the processing message
        await processing_msg.delete()
        
        # Always send as markdown file
        await send_transcript_file(update, transcript)
        
    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        error_message = (
            "Sorry, there was an error processing your audio file. "
            f"Error: {str(e)}"
        )
        await update.message.reply_text(error_message)

if __name__ == '__main__':
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
        application.run_polling(allowed_updates=["message"])
        
    except KeyboardInterrupt:
        logger.info("\nBot stopped gracefully")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
