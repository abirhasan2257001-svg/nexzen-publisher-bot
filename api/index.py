import os
import json
from http.server import BaseHTTPRequestHandler
import requests

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "NexzenLabsPublisherBot"
CHANNEL_ID = "@NexzenLabs"
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

USER_STATES = {}

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def send_document(chat_id, document_id, caption=None):
    payload = {"chat_id": chat_id, "document": document_id}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"
    requests.post(f"{TELEGRAM_API}/sendDocument", json=payload)

def send_photo_to_channel(channel_id, photo_id, caption, reply_markup):
    payload = {
        "chat_id": channel_id,
        "photo": photo_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(reply_markup)
    }
    requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload)

def handle_update(update):
    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # Handle /start or Deep Link when clicking Direct Download
    if text.startswith("/start"):
        args = text.split(" ")
        if len(args) > 1 and args[1].startswith("file_"):
            # Extract file_id from deep link parameter
            file_id = args[1].replace("file_", "")
            send_document(chat_id, file_id, caption="Here is your requested APK file! 📦")
            return
        
        USER_STATES.pop(chat_id, None)
        send_message(chat_id, "Hello Owner! Send /create to start making a post.")
        return

    if text == "/cancel":
        USER_STATES.pop(chat_id, None)
        send_message(chat_id, "Process cancelled.")
        return

    if text == "/create":
        USER_STATES[chat_id] = {"step": "PHOTO"}
        send_message(chat_id, "Step 1: Send the Cover Photo for the post.")
        return

    state = USER_STATES.get(chat_id)
    if not state:
        send_message(chat_id, "Please send /create to start generating a post.")
        return

    current_step = state.get("step")

    if current_step == "PHOTO":
        if "photo" in message:
            photo_id = message["photo"][-1]["file_id"]
            state["photo"] = photo_id
            state["step"] = "APP_NAME"
            send_message(chat_id, "Step 2: Enter App Name (e.g., Besura):")
        else:
            send_message(chat_id, "Please send a valid photo.")

    elif current_step == "APP_NAME":
        state["app_name"] = text
        state["step"] = "VERSION"
        send_message(chat_id, "Step 3: Enter App Version (e.g., v1.0):")

    elif current_step == "VERSION":
        state["version"] = text
        state["step"] = "INFO"
        send_message(chat_id, "Step 4: Enter App Features / Info (each feature in a new line):")

    elif current_step == "INFO":
        raw_info = text.split('\n')
        formatted_info = "\n".join([f"• {item.strip()}" for item in raw_info if item.strip()])
        state["info"] = formatted_info
        state["step"] = "FILE"
        send_message(chat_id, "Step 5: Send or Upload the APK file now:")

    elif current_step == "FILE":
        if "document" in message:
            state["file_id"] = message["document"]["file_id"]
            state["step"] = "GITHUB"
            send_message(chat_id, "Step 6: Send the GitHub link:")
        else:
            send_message(chat_id, "Please send/upload the APK file (as document).")

    elif current_step == "GITHUB":
        github_link = text
        app_name = state["app_name"]
        version = state["version"]
        photo_id = state["photo"]
        file_id = state["file_id"]
        info_text = state["info"]

        caption_text = (
            f"⬛ <b>NEXZEN LABS</b> ⬜ presents\n"
            f"<b>{app_name} {version}</b> ✅\n\n"
            f"<blockquote expandable>📦 <b>App Info</b>\n\n"
            f"{info_text}</blockquote>\n\n"
            f"⬇️ <b>OFFICIAL DOWNLOAD</b> ⬇️"
        )

        # Deep link attached directly with Telegram File ID
        bot_deep_link = f"https://t.me/{BOT_USERNAME}?start=file_{file_id}"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "⬇️ Direct Download", "url": bot_deep_link}],
                [{"text": "⚡ GitHub Download", "url": github_link}]
            ]
        }

        send_photo_to_channel(CHANNEL_ID, photo_id, caption_text, keyboard)
        send_message(chat_id, "✅ Successfully posted to your channel! Direct download for APK is now functional.")
        USER_STATES.pop(chat_id, None)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data.decode('utf-8'))

        try:
            handle_update(update)
        except Exception as e:
            print("Error:", e)

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
