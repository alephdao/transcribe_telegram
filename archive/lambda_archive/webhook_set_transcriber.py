import requests

bot_token = "7626456528:AAFo6Yl2RSzHKtaL_QUOQDVp0rWLoifL3Zw"
webhook_url = "https://msf7ga9f9a.execute-api.us-east-1.amazonaws.com/transcribe_telegram"

# First, delete the existing webhook
delete_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
delete_response = requests.get(delete_url)
print("Webhook Deletion Response:")
print(delete_response.json())

# Then set the webhook again
url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
data = {
    "url": webhook_url,
    "allowed_updates": ["message", "callback_query"],
    "drop_pending_updates": True
}

response = requests.post(url, json=data)
print("\nWebhook Set Response:")
print(response.json())

# Verify the configuration
info_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
info_response = requests.get(info_url)
print("\nCurrent Webhook Configuration:")
print(info_response.json())
