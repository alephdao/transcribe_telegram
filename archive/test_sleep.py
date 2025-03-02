import asyncio
import logging
from datetime import datetime, timedelta
from archive.transcription_bot import TranscriptionBot

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def monitor_bot_state():
    """Monitor and log the bot's sleep state."""
    while True:
        state = "sleeping" if TranscriptionBot.is_sleeping else "awake"
        logger.info(f"Bot is currently {state}")
        await asyncio.sleep(1)  # Check every second

async def simulate_activity():
    """Simulate periodic bot activity."""
    # First wake up the bot
    logger.info("Initial bot wake up")
    await TranscriptionBot.wake_up()
    
    # Wait 2 seconds to ensure bot is awake
    await asyncio.sleep(2)
    
    # Simulate some activity
    logger.info("Simulating activity")
    TranscriptionBot.last_activity = datetime.now()
    
    # Wait just over the idle timeout to see if bot sleeps
    wait_time = TranscriptionBot.IDLE_TIMEOUT + 2
    logger.info(f"Waiting {wait_time} seconds to check sleep behavior")
    await asyncio.sleep(wait_time)

async def main():
    try:
        # Start the monitoring task
        monitor_task = asyncio.create_task(monitor_bot_state())
        
        # Start the idle checker
        idle_checker = asyncio.create_task(TranscriptionBot.check_idle())
        
        # Run the activity simulation
        await simulate_activity()
        
        # Wait a bit more to see the final state
        await asyncio.sleep(2)
        
        # Cancel the monitoring tasks
        monitor_task.cancel()
        idle_checker.cancel()
        
        try:
            await monitor_task
            await idle_checker
        except asyncio.CancelledError:
            pass
            
        # Add proper cleanup
        logger.info("Shutting down bot...")
        await TranscriptionBot.shutdown()
        
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        # Ensure cleanup happens even on error
        await TranscriptionBot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
