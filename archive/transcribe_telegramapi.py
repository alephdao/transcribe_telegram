import os
import logging
import base64
import boto3
from botocore.exceptions import ClientError
from telethon import TelegramClient, events
import google.generativeai as genai
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_aws_parameter(parameter_name):
    """
    Retrieve a parameter from AWS Parameter Store
    Returns None if not running on EC2 or parameter not found
    """
    try:
        try:
            ssm = boto3.client('ssm', region_name='us-east-1')
        except:
            logger.info("No AWS credentials found - skipping Parameter Store")
            return None
            
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
        
    except Exception as e:
        logger.info(f"Could not retrieve parameter from AWS: {e}")
        return None

def get_credentials():
    """
    Get credentials from either AWS Parameter Store or environment variables
    Returns tuple of (api_id, api_hash, google_ai_api_key)
    """
    # Try AWS Parameter Store first
    api_id = get_aws_parameter('telegram_api_id')
    api_hash = get_aws_parameter('telegram_api_hash')
    google_ai_api_key = get_aws_parameter('GOOGLE_AI_API_KEY')
    
    # Fall back to environment variables if AWS params not available
    if not all([api_id, api_hash, google_ai_api_key]):
        logger.info("Using environment variables for credentials")
        load_dotenv()
        api_id = int(os.getenv("telegram_api_id"))  # API ID must be an integer
        api_hash = os.getenv("telegram_api_hash")
        google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
    else:
        logger.info("Using AWS Parameter Store for credentials")

    if not all([api_id, api_hash, google_ai_api_key]):
        raise ValueError("Missing required credentials from both AWS and environment variables")
        
    return api_id, api_hash, google_ai_api_key

# Get credentials
API_ID, API_HASH, GOOGLE_AI_API_KEY = get_credentials()

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

async def transcribe_audio(audio_data):
    """
    Transcribe audio data using Gemini API
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
        
        response = model.generate_content(content_parts)
        transcript = f"# Transcription\n\n{response.text}"
        return transcript
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise

async def main():
    """Run the client."""
    try:
        # Create the client and connect
        client = TelegramClient('transcription_session', API_ID, API_HASH)
        await client.start()

        @client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            """Handle the /start command."""
            welcome_message = (
                "Hello! I can transcribe audio files for you.\n\n"
                "Supported formats:\n"
                "- Voice messages\n"
                "- Audio files (.mp3, .wav, .ogg, .m4a, .aac, etc.)\n\n"
                "Just send me any audio file and I'll transcribe it for you!"
            )
            await event.respond(welcome_message)

        @client.on(events.NewMessage)
        async def message_handler(event):
            """Handle incoming messages."""
            try:
                message = event.message
                
                # Check if message contains audio or voice
                if message.voice or message.audio:
                    # Send processing message
                    processing_msg = await event.respond("Processing your audio... Please wait.")
                    
                    try:
                        # Download the audio file
                        audio_data = await client.download_media(message, bytes)
                        
                        # Transcribe the audio
                        transcript = await transcribe_audio(audio_data)
                        
                        # Delete processing message
                        await processing_msg.delete()
                        
                        # Save transcript to temporary file and send it
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
                            temp_file.write(transcript)
                            temp_file_path = temp_file.name
                        
                        try:
                            # Get original filename
                            if message.voice:
                                original_filename = f"voice_message_{message.date.strftime('%Y%m%d_%H%M%S')}"
                            else:
                                original_filename = os.path.splitext(message.audio.attributes[0].file_name)[0]
                            
                            # Send transcript file
                            await client.send_file(
                                event.chat_id,
                                temp_file_path,
                                caption="Here's your transcript as a markdown file.",
                                force_document=True,
                                attributes=[{"file_name": f"{original_filename}.md"}]
                            )
                        finally:
                            os.unlink(temp_file_path)
                            
                    except Exception as e:
                        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
                        error_message = (
                            "Sorry, there was an error processing your audio file.\n"
                            f"Error: {str(e)}\n\n"
                            "Please try again or contact support if the issue persists."
                        )
                        await processing_msg.edit(error_message)

            except Exception as e:
                logger.error(f"Error handling message: {str(e)}")
                await event.respond(f"Sorry, there was an error processing your message. Error: {str(e)}")

        # Run the client
        logger.info("Client is running...")
        await client.run_until_disconnected()
        
    except KeyboardInterrupt:
        logger.info("\nClient stopped gracefully")
    except Exception as e:
        logger.error(f"Error occurred: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
