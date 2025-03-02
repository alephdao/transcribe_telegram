# Audio Note Transcriber Telegram Bot

A Telegram bot that transcribes voice messages and audio files using Google's Generative AI. It's free to run. You can host it on AWS EC2, Hetzner, or any other cloud provider using Docker.

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

- Telegram Bot Token
- Google AI API credentials
- Docker and Docker Compose (for Docker deployment)
- Python 3.7+ (for local development)

## Installation

### Option 1: Docker Deployment (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/alephdao/transcribe_telegram.git
cd transcribe_telegram
```

2. Create an environment file:
```bash
cp .env.example .env
```

3. Edit the `.env` file with your credentials:
```
galebach_transcriber_bot_token=your_telegram_bot_token
GOOGLE_AI_API_KEY=your_google_api_key
# Add other variables as needed
```

4. Deploy using Docker:
```bash
./deploy.sh
```

This will:
- Install Docker if it's not already installed
- Build the Docker image
- Start the container
- Configure it to restart automatically

### Option 2: Local Development

1. Clone the repository:
```bash
git clone https://github.com/alephdao/transcribe_telegram.git
cd transcribe_telegram
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a Telegram bot:
- Open Telegram and search for "BotFather"
- Send "/newbot" to BotFather
- Follow the prompts to name your bot
- BotFather will give you an API token - save this securely

4. Configure environment variables:
Create a `.env` file with your credentials (use `.env.example` as a template)

## Usage

### Docker Deployment
```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

### Local Development
```bash
python transcribe.py
```

2. Send a voice message or audio file to your bot on Telegram
3. The bot will process the audio and return the transcription

## Dependencies

- python-telegram-bot: Telegram Bot API wrapper
- python-dotenv: Environment variable management
- google.generativeai: Google AI integration
- boto3: AWS SDK for Python
- aiohttp: Async HTTP client/server

## Deployment Options

### Hetzner Cloud (Recommended)

1. Create a Hetzner Cloud account and create a new server (CX11 or CX21 is sufficient)
2. Choose Ubuntu as the operating system
3. Set up SSH keys for secure access
4. SSH into your server:
   ```bash
   ssh root@your_server_ip
   ```
5. Clone the repository and follow the Docker deployment instructions above

### AWS EC2

1. Create an EC2 instance (t2.micro or t3.micro should be sufficient)
2. Choose Ubuntu as the operating system
3. Configure security groups to allow SSH access
4. SSH into your instance:
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```
5. Clone the repository and follow the Docker deployment instructions above

## License

[License information pending]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
