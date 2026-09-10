import os
import json
from http.server import BaseHTTPRequestHandler
import requests

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "NexzenLabsPublisherBot"
PUBLIC_CHANNEL_ID = "@NexzenLabs"
STORAGE_CHANNEL_ID = "-1003861196242"

# 🔒 ONLY YOU (OWNER) CAN CREATE POSTS
ADMIN_ID = 7762727296

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

USER_STATES = {}

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def copy_message(chat_id, from_chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id
    }
    return requests.post(f"{TELEGRAM_API}/copyMessage", json=payload).json()

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
    user_id = message["from"]["id"]
    text = message.get("text", "")

    # 1. ALLOW PUBLIC USERS TO DOWNLOAD FILES VIA DEEP LINK
    if text.startswith("/start"):
        args = text.split(" ")
        if len(args) > 1 and args[1].startswith("msg_"):
            try:
                msg_id = int(args[1].replace("msg_", ""))
                send_message(chat_id, " Here is your requested file!")
                res = copy_message(chat_id, STORAGE_CHANNEL_ID, msg_id)
                if not res.get("ok"):
                    send_message(chat_id, "⚠️ File not found or expired.")
            except Exception as e:
                send_message(chat_id, "⚠️ Error retrieving file.")
            return

        if user_id == ADMIN_ID:
            USER_STATES.pop(chat_id, None)
            send_message(chat_id, "Hello Owner! Send /create to start making a post.")
        else:
            send_message(chat_id, "Welcome to Nexzen Labs Bot! Click on channel download buttons to get APK files.")
        return

    # 2. BLOCK NON-ADMIN USERS FROM CREATING POSTS
    if user_id != ADMIN_ID:
        # Silently ignore or show access denied to other users
        return

    # 3. ADMIN-ONLY CONVERSATION FLOW
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
        send_message(chat_id, "Send /create to start generating a post.")
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

        doc_payload = {
            "chat_id": STORAGE_CHANNEL_ID,
            "document": file_id,
            "caption": f"<b>{app_name} {version} APK File</b>",
            "parse_mode": "HTML"
        }
        doc_res = requests.post(f"{TELEGRAM_API}/sendDocument", json=doc_payload).json()
        
        if not doc_res.get("ok"):
            send_message(chat_id, "❌ Error saving file to storage channel.")
            return

        storage_msg_id = doc_res["result"]["message_id"]
        bot_deep_link = f"https://t.me/{BOT_USERNAME}?start=msg_{storage_msg_id}"

        caption_text = (
            f"⬛ <b>NEXZEN LABS</b> ⬜ presents\n"
            f"<b>{app_name} {version}</b> ✅\n\n"
            f"<blockquote expandable>📦 <b>App Info</b>\n\n"
            f"{info_text}</blockquote>\n\n"
            f"⬇️ <b>OFFICIAL DOWNLOAD</b> ⬇️"
        )

        keyboard = {
            "inline_keyboard": [
                [{"text": "⬇️ Direct Download", "url": bot_deep_link}],
                [{"text": "⚡ GitHub Download", "url": github_link}]
            ]
        }

        send_photo_to_channel(PUBLIC_CHANNEL_ID, photo_id, caption_text, keyboard)
        send_message(chat_id, "✅ Posted successfully to public channel!")
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
