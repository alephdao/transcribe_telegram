import requests
import os
from dotenv import load_dotenv

load_dotenv()

def verify_webhook():
    BOT_TOKEN = os.getenv("galebach_transcriber_bot_token")  # Replace with your actual bot token
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN environment variable not set.")
        return

    try:
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        webhook_info = response.json()

        if webhook_info['ok']:
            result = webhook_info['result']
            print("Webhook Info:")
            print(f"  URL: {result.get('url', 'Not set')}")
            print(f"  Pending Update Count: {result.get('pending_update_count', 0)}")

            last_error_date = result.get('last_error_date')
            if last_error_date:
                import datetime
                last_error_datetime = datetime.datetime.fromtimestamp(last_error_date)
                print(f"  Last Error Date: {last_error_datetime} (Timestamp: {last_error_date})")
                print(f"  Last Error Message: {result.get('last_error_message', 'No message provided')}")

            else:
                print("  No recent errors.")

            # Compare URL if it's set
            expected_url = "https://vaebgjdjdg.execute-api.us-east-1.amazonaws.com/production" # replace with your url
            if result.get('url') and result['url'] != expected_url:
                print(f"WARNING: Webhook URL does not match expected URL. Expected: {expected_url} Actual: {result['url']}")
            elif not result.get('url'):
                print("WARNING: Webhook URL is not set. Please set the webhook.")

            if result.get('pending_update_count', 0) > 0:
                print("WARNING: There are pending updates. This might indicate issues with your webhook processing.")

            return result # Return the webhook info for further use if needed.
        else:
            print(f"Error getting webhook info: {webhook_info.get('description', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Telegram API: {e}")
        return None
    except Exception as e:
      print(f"An unexpected error occurred: {e}")
      return None

if __name__ == "__main__":
    webhook_information = verify_webhook()
    if webhook_information:
      print("Webhook verification complete")
    else:
      print("Webhook verification failed")
