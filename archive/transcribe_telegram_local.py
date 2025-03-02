import os
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler
import asyncio
from deepgram import DeepgramClient, PrerecordedOptions
import aiohttp
from dotenv import load_dotenv
import logging
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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

# Add this to your global variables
LANGUAGE_OPTIONS = {
    'english': 'en',
    'spanish': 'es'
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

async def transcribe_audio(audio_data, language='en'):
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
            language=language,
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

async def ask_language(update, context):
    """
    Ask user to select the audio language using inline keyboard.
    """
    keyboard = [[
        InlineKeyboardButton("English", callback_data="lang_en"),
        InlineKeyboardButton("Spanish", callback_data="lang_es")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the audio message details in user_data for later processing
    if update.message.voice:
        context.user_data['audio_file'] = update.message.voice
        context.user_data['file_type'] = "voice message"
    else:
        context.user_data['audio_file'] = update.message.audio
        context.user_data['file_type'] = f"audio file ({update.message.audio.mime_type})"
    
    await update.message.reply_text(
        "Please select the language of the audio:",
        reply_markup=reply_markup
    )

async def language_callback(update, context):
    """
    Handle the language selection callback and proceed with transcription.
    """
    query = update.callback_query
    await query.answer()
    
    # Extract language code from callback data
    language = query.data.split('_')[1]
    
    # Get stored audio file details
    audio_file = context.user_data.get('audio_file')
    file_type = context.user_data.get('file_type')
    
    if not audio_file:
        await query.message.reply_text("Sorry, there was an error processing your request. Please try sending the audio file again.")
        return
    
    # Send processing message
    processing_msg = await query.message.reply_text(
        f"Processing your {file_type}... Please wait."
    )
    
    try:
        # Download and transcribe the audio
        audio_data = await download_file(audio_file)
        transcript = await transcribe_audio(audio_data, language)
        
        # Delete the processing message and language selection message
        await processing_msg.delete()
        await query.message.delete()
        
        # Send transcript using the original message context
        await send_transcript_file(update, transcript)
        
    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        await query.message.reply_text(
            f"Sorry, there was an error processing your audio file. Error: {str(e)}"
        )

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
        
        # Proceed to language selection
        await ask_language(update, context)
        
    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        await update.message.reply_text(
            f"Sorry, there was an error processing your audio file. Error: {str(e)}"
        )

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
        application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
        
        # Run the bot
        logger.info("Bot is running...")
        application.run_polling(allowed_updates=["message", "callback_query"])
        
    except KeyboardInterrupt:
        logger.info("\nBot stopped gracefully")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
