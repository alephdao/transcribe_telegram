import requests

bot_token = "7626456528:AAFo6Yl2RSzHKtaL_QUOQDVp0rWLoifL3Zw"  # Retype it here manually
webhook_url = "https://p078n8vpke.execute-api.us-east-1.amazonaws.com/demo_21dec2024"

url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
data = {"url": webhook_url}

response = requests.post(url, json=data)

print(response.json())
print(response.status_code)
if response.status_code != 200:
    print(response.text)
