# Transcribe Telegram

A Telegram bot that transcribes voice messages and audio files using AWS services and Google's Generative AI.

## Features

- Transcribes voice messages and audio files sent to the bot in their original language. Eg, English audio returns English and Spanish audio returns Spanish. 
- Supports Telegram's native audio formats
- Uses AWS services for processing
- Integrates with Google's Generative AI for enhanced transcription
- Places speakers names next to the audio

## Future Features
- better formatting of the transcript
- ability to specify the output language
- ability to kickoff a cleaning step of the transcript like formatting it as an email. 

## Prerequisites

- Python 3.7+
- AWS account with appropriate credentials
- Telegram Bot Token
- Google AI API credentials

## Installation

1. Clone the repository:
```bash
git clone https://github.com/alephdao/transcribe_telegram.git
cd transcribe_telegram
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
Create a `.env` file with the following variables:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `GOOGLE_API_KEY`: Google AI API key
-  `AWS_ACCESS_KEY_ID`: AWS access key (OPTIONAL: if hosting on AWS)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (OPTIONAL: if hosting on AWS)

## Usage

1. Start the bot:
```bash
python main.py
```

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

[License information pending]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
