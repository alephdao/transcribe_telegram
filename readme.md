# Transcribe Telegram

A Telegram bot that transcribes voice messages and audio files using AWS services and Google's Generative AI.

## Features

- Transcribes voice messages and audio files sent to the bot
- Supports Telegram's native audio formats
- Uses AWS services for processing
- Integrates with Google's Generative AI for enhanced transcription

## Prerequisites

- Python 3.7+
- AWS account with appropriate credentials
- Telegram Bot Token
- Google AI API credentials

## Installation

1. Clone the repository:

git clone https://github.com/alephdao/transcribe_telegram.git
cd transcribe_telegram


2. Install dependencies:

pip install -r requirements.txt


3. Configure environment variables:
Create a `.env` file with the following variables:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `GOOGLE_API_KEY`: Google AI API key

## Usage

1. Start the bot:

python main.py

2. Send a voice message or audio file to your bot on Telegram
3. The bot will process the audio and return the transcription

## Dependencies

- python-telegram-bot: Telegram Bot API wrapper
- python-dotenv: Environment variable management
- google.generativeai: Google AI integration
- boto3: AWS SDK for Python
- aiohttp: Async HTTP client/server
- telethon: Telegram client library

## License

Free to use for personal or commercial use. However you feel like. 

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
