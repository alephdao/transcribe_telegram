import os
import asyncio
import logging
import base64
import gc
from datetime import datetime, timedelta
import tempfile
import aiohttp
from telegram.ext import Application, MessageHandler, filters, CommandHandler
from telegram import Update
import google.generativeai as genai
from dotenv import load_dotenv
from boto3.session import Session

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionBot:
    IDLE_TIMEOUT = 2  # 5 seconds timeout for testing
    last_activity = None
    is_sleeping = True
    model = None
    
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
    
    TRANSCRIPTION_PROMPT = """Please transcribe this audio accurately in its original language. 
If there are multiple speakers, identify and label them.
Format the output as a markdown document with speaker labels."""

    @classmethod
    def get_deployment_mode(cls):
        """Get deployment mode from AWS Parameter Store or default to local"""
        try:
            session = Session()
            ssm = session.client('ssm', region_name='us-east-1')
            response = ssm.get_parameter(
                Name='transcribe_telegram_deployment_mode',
                WithDecryption=False
            )
            mode = response['Parameter']['Value'].lower()
            logger.info(f"Found deployment mode in AWS: {mode}")
            return mode
        except Exception as e:
            logger.info(f"Defaulting to local mode: {e}")
            return 'local'

    @classmethod
    def get_aws_parameter(cls, parameter_name):
        """Retrieve a parameter from AWS Parameter Store"""
        if cls.get_deployment_mode() != 'aws':
            return None
            
        try:
            session = Session()
            ssm = session.client('ssm', region_name='us-east-1')
            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            return response['Parameter']['Value']
        except Exception as e:
            logger.info(f"Could not retrieve parameter from AWS: {e}")
            return None

    @classmethod
    def get_credentials(cls):
        """Get bot credentials based on deployment mode"""
        if cls.get_deployment_mode() == 'aws':
            logger.info("Running in AWS mode - checking Parameter Store")
            bot_token = cls.get_aws_parameter('galebach_transcriber_bot_token')
            google_ai_api_key = cls.get_aws_parameter('GOOGLE_AI_API_KEY')
            
            if not bot_token or not google_ai_api_key:
                logger.warning("AWS Parameter Store failed - falling back to environment variables")
                load_dotenv()
                bot_token = os.getenv("galebach_transcriber_bot_token")
                google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
        else:
            logger.info("Running in local mode - using environment variables")
            load_dotenv()
            bot_token = os.getenv("galebach_transcriber_bot_token")
            google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")

        if not bot_token or not google_ai_api_key:
            raise ValueError("Missing required credentials")
            
        return bot_token, google_ai_api_key

    @classmethod
    async def initialize_model(cls):
        """Initialize the Gemini model if not already initialized"""
        if cls.model is None:
            _, google_ai_api_key = cls.get_credentials()
            genai.configure(api_key=google_ai_api_key)
            cls.model = genai.GenerativeModel('models/gemini-2.0-flash-exp')

    @classmethod
    async def sleep(cls):
        """Put the bot to sleep by releasing heavy resources"""
        logger.info("Bot entering sleep mode")
        cls.is_sleeping = True
        cls.model = None
        gc.collect()

    @classmethod
    async def wake_up(cls):
        """Wake up the bot by reinitializing necessary components"""
        logger.info("Bot waking up")
        await cls.initialize_model()
        cls.is_sleeping = False

    @classmethod
    async def check_idle(cls):
        """Periodically check if the bot should go to sleep"""
        while True:
            if (cls.last_activity and 
                datetime.now() - cls.last_activity > timedelta(seconds=cls.IDLE_TIMEOUT) and 
                not cls.is_sleeping):
                await cls.sleep()
            await asyncio.sleep(1)  # Check every second for testing

    @staticmethod
    async def download_file(file):
        """Download a file from Telegram servers with streaming"""
        file_obj = await file.get_file()
        async with aiohttp.ClientSession() as session:
            async with session.get(file_obj.file_path) as response:
                chunks = []
                async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                    chunks.append(chunk)
        return b''.join(chunks)

    @classmethod
    async def transcribe_audio(cls, audio_data):
        """Transcribe audio data using Gemini API"""
        try:
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            content_parts = [
                {"text": cls.TRANSCRIPTION_PROMPT},
                {
                    "inline_data": {
                        "mime_type": "audio/mp4",
                        "data": audio_base64
                    }
                }
            ]
            
            response = cls.model.generate_content(content_parts)
            transcript = f"# Transcription\n\n{response.text}"
            return transcript
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    @classmethod
    async def send_transcript_file(cls, update, transcript):
        """Save and send transcript as a markdown file"""
        message = update.message if update.message else update.callback_query.message
        
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

    @classmethod
    async def start(cls, update, context):
        """Handle the /start command"""
        welcome_message = (
            "Hello! I can transcribe audio files for you.\n\n"
            "Supported formats:\n"
            "- Voice messages\n"
            "- Audio files (.mp3, .wav, .ogg, .m4a, .aac, etc.)\n\n"
            "Just send me any audio file and I'll transcribe it for you!"
        )
        await update.message.reply_text(welcome_message)

    @classmethod
    async def handle_audio(cls, update, context):
        """Handle incoming audio files and voice messages"""
        try:
            if cls.is_sleeping:
                await cls.wake_up()
            
            cls.last_activity = datetime.now()
            
            if update.message.audio and update.message.audio.mime_type not in cls.SUPPORTED_AUDIO_TYPES:
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
                audio_data = await cls.download_file(audio_file)
                logger.info(f"Downloaded audio file, size: {len(audio_data)} bytes")
                
                logger.info("Starting transcription")
                transcript = await cls.transcribe_audio(audio_data)
                logger.info("Transcription completed")
                
                await processing_msg.delete()
                await cls.send_transcript_file(update, transcript)
                
                del audio_data
                gc.collect()
                
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

    @classmethod
    async def shutdown(cls):
        """Cleanup method to properly shut down the bot."""
        try:
            # Ensure the bot is sleeping
            if not cls.is_sleeping:
                await cls.sleep()
            
            # Cancel any pending tasks
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            logger.info("Bot successfully shut down")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

async def main():
    """Run the bot"""
    application = None
    idle_checker = None
    
    try:
        # Get credentials
        bot_token, _ = TranscriptionBot.get_credentials()
        
        # Create application
        application = Application.builder().token(bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", TranscriptionBot.start))
        application.add_handler(MessageHandler(
            filters.VOICE | filters.AUDIO, 
            TranscriptionBot.handle_audio
        ))
        
        # Initialize application
        await application.initialize()
        await application.start()
        
        # Start idle checker in background
        idle_checker = asyncio.create_task(TranscriptionBot.check_idle())
        
        logger.info("Bot is running...")
        
        # Set up stop signals
        stop_signal = asyncio.Event()
        
        # Handle shutdown signals
        def signal_handler():
            logger.info("Received stop signal")
            stop_signal.set()
            
        # Run the application with signal handling
        await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        # Ensure proper cleanup
        try:
            if idle_checker:
                idle_checker.cancel()
                try:
                    await idle_checker
                except asyncio.CancelledError:
                    pass
                    
            if application:
                logger.info("Shutting down application...")
                await TranscriptionBot.shutdown()
                if application.running:
                    await application.stop()
                await application.shutdown()
                
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

if __name__ == '__main__':
    try:
        # Set up asyncio policy for proper signal handling
        if os.name == 'posix':
            import uvloop
            uvloop.install()
        
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
