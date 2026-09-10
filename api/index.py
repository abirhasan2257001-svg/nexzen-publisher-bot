import os
import json
from http.server import BaseHTTPRequestHandler
import requests

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "NexzenLabsPublisherBot"
PUBLIC_CHANNEL_ID = "@NexzenLabs"
STORAGE_CHANNEL_ID = "-1003861196242"
ADMIN_ID = 7762727296

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

USER_STATES = {}

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return requests.post(f"{TELEGRAM_API}/sendMessage", json=payload).json()

def copy_message(chat_id, from_chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id
    }
    return requests.post(f"{TELEGRAM_API}/copyMessage", json=payload).json()

def send_media_group_to_channel(channel_id, media_list):
    payload = {
        "chat_id": channel_id,
        "media": json.dumps(media_list)
    }
    return requests.post(f"{TELEGRAM_API}/sendMediaGroup", json=payload).json()

def handle_update(update):
    # Callback query handling for buttons
    if "callback_query" in update:
        query = update["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        user_id = query["from"]["id"]
        data = query["data"]

        if user_id != ADMIN_ID:
            return

        if data == "type_app":
            USER_STATES[chat_id] = {"type": "APP", "step": "PHOTO"}
            send_message(chat_id, "<b>App Mode Selected</b>\nStep 1: Send the Cover Photo for the post.")
        elif data == "type_prompt":
            USER_STATES[chat_id] = {"type": "PROMPT", "step": "MEDIA", "media": []}
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Media", "callback_data": "media_done"}]]}
            send_message(chat_id, "<b>Prompt Mode Selected</b>\nSend images/videos one by one or as album. Click <b>Done Uploading Media</b> when finished.", keyboard)
        elif data == "media_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "PROMPT" and state.get("step") == "MEDIA":
                if not state.get("media"):
                    send_message(chat_id, "⚠️ Please send at least one image or video first!")
                    return
                state["step"] = "CAPTION"
                send_message(chat_id, "Next Step: Send the Caption/Description for the post.")
        return

    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    # Public Users Start Link Handling
    if text.startswith("/start"):
        args = text.split(" ")
        if len(args) > 1:
            param = args[1]
            if param.startswith("msg_"):
                msg_id = int(param.replace("msg_", ""))
                send_message(chat_id, "📦 <b>Here is your requested file:</b>")
                copy_message(chat_id, STORAGE_CHANNEL_ID, msg_id)
                return
            elif param.startswith("prompt_"):
                prompt_msg_id = int(param.replace("prompt_", ""))
                send_message(chat_id, "✨ <b>Requested Prompt(s):</b>")
                copy_message(chat_id, STORAGE_CHANNEL_ID, prompt_msg_id)
                return

        if user_id == ADMIN_ID:
            USER_STATES.pop(chat_id, None)
            send_message(chat_id, "Hello Owner! Send /create to make a new post.")
        else:
            send_message(chat_id, "Welcome to Nexzen Labs Bot! Use channel buttons to download files or get prompts.")
        return

    if user_id != ADMIN_ID:
        return

    if text == "/cancel":
        USER_STATES.pop(chat_id, None)
        send_message(chat_id, "Process cancelled.")
        return

    if text == "/create":
        keyboard = {
            "inline_keyboard": [
                [{"text": "📱 Publish App", "callback_data": "type_app"}],
                [{"text": "🎬 Publish Prompt & Media", "callback_data": "type_prompt"}]
            ]
        }
        send_message(chat_id, "What type of post do you want to create?", keyboard)
        return

    state = USER_STATES.get(chat_id)
    if not state:
        send_message(chat_id, "Send /create to start generating a post.")
        return

    post_type = state.get("type")
    current_step = state.get("step")

    # --- APP FLOW ---
    if post_type == "APP":
        if current_step == "PHOTO":
            if "photo" in message:
                state["photo"] = message["photo"][-1]["file_id"]
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
            state["info"] = "\n".join([f"• {item.strip()}" for item in raw_info if item.strip()])
            state["step"] = "FILE"
            send_message(chat_id, "Step 5: Send or Upload the APK file now:")

        elif current_step == "FILE":
            if "document" in message:
                state["file_id"] = message["document"]["file_id"]
                state["step"] = "GITHUB"
                send_message(chat_id, "Step 6: Send the GitHub link:")
            else:
                send_message(chat_id, "Please send/upload the APK file.")

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
            requests.post(f"{TELEGRAM_API}/sendPhoto", json={
                "chat_id": PUBLIC_CHANNEL_ID,
                "photo": photo_id,
                "caption": caption_text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard)
            })
            send_message(chat_id, "✅ App post published successfully!")
            USER_STATES.pop(chat_id, None)

    # --- PROMPT FLOW ---
    elif post_type == "PROMPT":
        if current_step == "MEDIA":
            if "photo" in message:
                state["media"].append({"type": "photo", "media": message["photo"][-1]["file_id"]})
                send_message(chat_id, f"Added Photo ({len(state['media'])} media total). Send more or click Done.")
            elif "video" in message:
                state["media"].append({"type": "video", "media": message["video"]["file_id"]})
                send_message(chat_id, f"Added Video ({len(state['media'])} media total). Send more or click Done.")

        elif current_step == "CAPTION":
            state["caption"] = text
            state["step"] = "PROMPT_TEXT"
            send_message(chat_id, "Final Step: Send the Prompt(s). You can send multiple lines or text for multiple prompts.")

        elif current_step == "PROMPT_TEXT":
            prompts_text = text

            # 1. Store Prompts text to Storage Channel
            prompt_res = send_message(STORAGE_CHANNEL_ID, f"<b>PROMPT DATA:</b>\n\n<code>{prompts_text}</code>")
            prompt_msg_id = prompt_res["result"]["message_id"]

            prompt_deep_link = f"https://t.me/{BOT_USERNAME}?start=prompt_{prompt_msg_id}"

            caption_full = f"{state['caption']}\n\n⬇️ <b>GET PROMPT BELOW</b> ⬇️"
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📋 Get Prompt", "url": prompt_deep_link}]
                ]
            }

            media_list = state["media"]
            # Add caption and button to last item or single item
            if len(media_list) == 1:
                item = media_list[0]
                if item["type"] == "photo":
                    requests.post(f"{TELEGRAM_API}/sendPhoto", json={
                        "chat_id": PUBLIC_CHANNEL_ID,
                        "photo": item["media"],
                        "caption": caption_full,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard)
                    })
                else:
                    requests.post(f"{TELEGRAM_API}/sendVideo", json={
                        "chat_id": PUBLIC_CHANNEL_ID,
                        "video": item["media"],
                        "caption": caption_full,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard)
                    })
            else:
                # Multiple media group
                formatted_media = []
                for idx, m in enumerate(media_list):
                    obj = {"type": m["type"], "media": m["media"]}
                    if idx == len(media_list) - 1:
                        obj["caption"] = caption_full
                        obj["parse_mode"] = "HTML"
                    formatted_media.append(obj)
                
                send_media_group_to_channel(PUBLIC_CHANNEL_ID, formatted_media)
                # Send a follow-up button for media group since media groups don't support inline buttons directly
                send_message(PUBLIC_CHANNEL_ID, "👇 Click button to get prompt:", keyboard)

            send_message(chat_id, "✅ Prompt post published successfully!")
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
