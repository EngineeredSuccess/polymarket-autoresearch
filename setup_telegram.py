#!/usr/bin/env python3
"""
Setup Telegram for Polymarket Bot
Run this script to configure your Telegram bot
"""

import os
import requests

BOT_TOKEN = "8482994614:AAGkOcFQgTiQJFDm6Bw0e0A4e5QiHHtztz0"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_updates():
    """Get updates from Telegram bot."""
    url = f"{API_URL}/getUpdates"
    response = requests.get(url, timeout=10)
    return response.json()


def send_message(chat_id, text):
    """Send test message."""
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=data, timeout=10)
    return response.json()


def setup_chat_id():
    """Get your chat ID by checking updates."""
    print("=" * 60)
    print("TELEGRAM SETUP")
    print("=" * 60)

    # Check if bot has received any messages
    updates = get_updates()

    if updates.get("ok"):
        results = updates.get("result", [])
        if results:
            # Get the chat ID from the latest message
            latest = results[-1]
            chat = latest.get("message", {}).get("chat", {})
            chat_id = chat.get("id")
            username = chat.get("username", "Unknown")
            first_name = chat.get("first_name", "Unknown")

            print(f"\n[+] Found your chat!")
            print(f"    Chat ID: {chat_id}")
            print(f"    Username: @{username}")
            print(f"    Name: {first_name}")

            # Save to file
            with open("telegram_config.env", "w") as f:
                f.write(f"# Telegram Configuration\n")
                f.write(f"TELEGRAM_BOT_TOKEN={BOT_TOKEN}\n")
                f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")

            print(f"\n[+] Saved to telegram_config.env")

            # Send test message
            print(f"\n[*] Sending test message...")
            result = send_message(
                chat_id,
                "Hello from Polymarket Bot!\n\n"
                "Your Telegram alerts are configured successfully!\n"
                "You'll receive trading signals here.",
            )

            if result.get("ok"):
                print("[+] Test message sent successfully!")
            else:
                print(f"[-] Failed to send message: {result}")

            return chat_id
        else:
            print("\n[!] No messages found.")
            print("\nTo get your Chat ID:")
            print("1. Open Telegram and search for @codepolybot")
            print("2. Click Start or send any message")
            print("3. Run this script again")
            return None
    else:
        print(f"[-] Error: {updates}")
        return None


if __name__ == "__main__":
    setup_chat_id()
