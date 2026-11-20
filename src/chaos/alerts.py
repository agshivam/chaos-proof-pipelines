"""Alerts: print, remember for tests, and post to Telegram when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
import json
import os
import urllib.request

SENT: list[str] = []


def alert(message: str) -> None:
    SENT.append(message)
    print(f"ALERT: {message}")
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": message}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:  # an alert failure must never break the pipeline
            print(f"alert delivery failed: {exc}")
