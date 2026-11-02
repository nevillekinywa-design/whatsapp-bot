import os

import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
SYSTEM_PROMPT = (
    "You are a helpful assistant chatting on WhatsApp. "
    "Keep replies short and conversational. Avoid heavy markdown."
)
MAX_TURNS = 20

app = Flask(__name__)
histories: dict[str, list[dict]] = {}  # resets when the app restarts


def ask_gemini(user: str, text: str) -> str:
    history = histories.setdefault(user, [])
    history.append({"role": "user", "parts": [{"text": text}]})
    del history[:-MAX_TURNS]
    while history and history[0]["role"] != "user":
        history.pop(0)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    r = requests.post(
        url,
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": history,
        },
        timeout=12,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    reply = "".join(p.get("text", "") for p in parts).strip()
    history.append({"role": "model", "parts": [{"text": reply}]})
    return reply


@app.post("/whatsapp")
def whatsapp():
    sender = request.form.get("From", "")
    text = request.form.get("Body", "").strip()

    twiml = MessagingResponse()
    if not text:
        twiml.message("I can only read text messages for now.")
    else:
        try:
            twiml.message(ask_gemini(sender, text)[:1500])
        except Exception:
            app.logger.exception("Gemini error")
            twiml.message("Sorry, something went wrong. Try again in a moment.")
    return str(twiml), 200, {"Content-Type": "application/xml"}


@app.get("/")
def health():
    return "Bot is running", 200


if __name__ == "__main__":
    app.run(port=5000)
