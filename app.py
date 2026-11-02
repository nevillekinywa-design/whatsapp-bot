import os

import anthropic
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM_PROMPT = (
    "You are a helpful assistant chatting on WhatsApp. "
    "Keep replies short and conversational. Avoid heavy markdown."
)
MAX_TURNS = 20

app = Flask(__name__)
claude = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
histories: dict[str, list[dict]] = {}  # resets when the app restarts


def ask_claude(user: str, text: str) -> str:
    history = histories.setdefault(user, [])
    history.append({"role": "user", "content": text})
    del history[:-MAX_TURNS]
    while history and history[0]["role"] != "user":
        history.pop(0)

    resp = claude.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=history,
    )
    reply = "".join(b.text for b in resp.content if b.type == "text")
    history.append({"role": "assistant", "content": reply})
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
            twiml.message(ask_claude(sender, text)[:1500])
        except Exception:
            app.logger.exception("Claude error")
            twiml.message("Sorry, something went wrong. Try again in a moment.")
    return str(twiml), 200, {"Content-Type": "application/xml"}


@app.get("/")
def health():
    return "Bot is running", 200


if __name__ == "__main__":
    app.run(port=5000)
