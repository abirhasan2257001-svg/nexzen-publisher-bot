import os
import json
import time
from threading import Thread
from http.server import BaseHTTPRequestHandler
import requests

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "NexzenLabsPublisherBot"
PUBLIC_CHANNEL_ID = "@NexzenLabs"
STORAGE_CHANNEL_ID = "-1003861196242"
ADMIN_ID = 7762727296

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

USER_STATES = {}
BOT_USERS_FILE = "/tmp/bot_users.json"

def get_bot_users():
    if os.path.exists(BOT_USERS_FILE):
        try:
            with open(BOT_USERS_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_bot_user(user_id):
    users = get_bot_users()
    if user_id not in users:
        users.add(user_id)
        try:
            with open(BOT_USERS_FILE, "w") as f:
                json.dump(list(users), f)
        except:
            pass

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

def delete_message(chat_id, message_id):
    payload = {"chat_id": chat_id, "message_id": message_id}
    requests.post(f"{TELEGRAM_API}/deleteMessage", json=payload)

def auto_delete_task(chat_id, message_id, delay=60):
    time.sleep(delay)
    delete_message(chat_id, message_id)

def check_channel_membership(user_id):
    try:
        res = requests.post(f"{TELEGRAM_API}/getChatMember", json={
            "chat_id": PUBLIC_CHANNEL_ID,
            "user_id": user_id
        }).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["creator", "administrator", "member"]
    except:
        pass
    return False

def handle_update(update):
    save_bot_user(update.get("message", {}).get("from", {}).get("id") or update.get("callback_query", {}).get("from", {}).get("id"))

    if "callback_query" in update:
        query = update["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        user_id = query["from"]["id"]
        data = query["data"]

        if user_id != ADMIN_ID:
            return

        if data == "type_app":
            USER_STATES[chat_id] = {"type": "APP", "step": "PHOTO"}
            send_message(chat_id, "<b>App Mode Selected</b>\nStep 1: Send Cover Photo.")
        elif data == "type_prompt":
            USER_STATES[chat_id] = {"type": "PROMPT", "step": "MEDIA", "media": []}
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Media", "callback_data": "media_done"}]]}
            send_message(chat_id, "<b>Prompt Mode Selected</b>\nSend images/videos. Click Done when finished.", keyboard)
        elif data == "media_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "PROMPT" and state.get("step") == "MEDIA":
                if not state.get("media"):
                    send_message(chat_id, "⚠️ Send at least one media file!")
                    return
                state["step"] = "CAPTION"
                send_message(chat_id, "Next Step: Send Caption for post.")
        return

    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    # Force Join Verification
    if user_id != ADMIN_ID and not check_channel_membership(user_id):
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": f"https://t.me/{PUBLIC_CHANNEL_ID.replace('@', '')}"}],
                [{"text": "🔄 Try Again", "url": f"https://t.me/{BOT_USERNAME}?start={text.replace('/start ', '')}"}]
            ]
        }
        send_message(chat_id, "⚠️ <b>Access Denied!</b>\n\nYou must join our official channel to download files or get prompts.", keyboard)
        return

    if text.startswith("/start"):
        args = text.split(" ")
        if len(args) > 1:
            param = args[1]
            if param.startswith("msg_"):
                msg_id = int(param.replace("msg_", ""))
                n_msg = send_message(chat_id, "📦 <b>Here is your file!</b> (Auto-deletes in 60s)")
                res = copy_message(chat_id, STORAGE_CHANNEL_ID, msg_id)
                if res.get("ok"):
                    file_msg_id = res["result"]["message_id"]
                    Thread(target=auto_delete_task, args=(chat_id, file_msg_id, 60)).start()
                return
            elif param.startswith("prompt_"):
                prompt_msg_id = int(param.replace("prompt_", ""))
                n_msg = send_message(chat_id, "✨ <b>Here is your Prompt!</b> (Auto-deletes in 60s)")
                res = copy_message(chat_id, STORAGE_CHANNEL_ID, prompt_msg_id)
                if res.get("ok"):
                    file_msg_id = res["result"]["message_id"]
                    Thread(target=auto_delete_task, args=(chat_id, file_msg_id, 60)).start()
                return

        if user_id == ADMIN_ID:
            USER_STATES.pop(chat_id, None)
            send_message(chat_id, "Hello Owner! Use /create to post or /broadcast to send news.")
        else:
            send_message(chat_id, "Welcome to Nexzen Labs Bot!")
        return

    if user_id != ADMIN_ID:
        return

    if text == "/cancel":
        USER_STATES.pop(chat_id, None)
        send_message(chat_id, "Process cancelled.")
        return

    if text == "/broadcast":
        USER_STATES[chat_id] = {"step": "BROADCAST"}
        send_message(chat_id, "📢 Send the message/photo/video you want to broadcast to all bot users:")
        return

    state = USER_STATES.get(chat_id)
    if state and state.get("step") == "BROADCAST":
        users = get_bot_users()
        count = 0
        for uid in users:
            try:
                copy_message(uid, chat_id, message["message_id"])
                count += 1
            except:
                pass
        send_message(chat_id, f"✅ Broadcast sent successfully to {count} users!")
        USER_STATES.pop(chat_id, None)
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

    if not state:
        return

    post_type = state.get("type")
    current_step = state.get("step")

    if post_type == "APP":
        if current_step == "PHOTO":
            if "photo" in message:
                state["photo"] = message["photo"][-1]["file_id"]
                state["step"] = "APP_NAME"
                send_message(chat_id, "Step 2: Enter App Name:")
        elif current_step == "APP_NAME":
            state["app_name"] = text
            state["step"] = "VERSION"
            send_message(chat_id, "Step 3: Enter App Version:")
        elif current_step == "VERSION":
            state["version"] = text
            state["step"] = "INFO"
            send_message(chat_id, "Step 4: Enter Features:")
        elif current_step == "INFO":
            raw_info = text.split('\n')
            state["info"] = "\n".join([f"• {item.strip()}" for item in raw_info if item.strip()])
            state["step"] = "FILE"
            send_message(chat_id, "Step 5: Send APK File:")
        elif current_step == "FILE":
            if "document" in message:
                state["file_id"] = message["document"]["file_id"]
                state["step"] = "GITHUB"
                send_message(chat_id, "Step 6: Send GitHub Link:")
        elif current_step == "GITHUB":
            doc_payload = {"chat_id": STORAGE_CHANNEL_ID, "document": state["file_id"], "caption": f"<b>{state['app_name']} {state['version']} APK</b>", "parse_mode": "HTML"}
            doc_res = requests.post(f"{TELEGRAM_API}/sendDocument", json=doc_payload).json()
            storage_msg_id = doc_res["result"]["message_id"]

            bot_deep_link = f"https://t.me/{BOT_USERNAME}?start=msg_{storage_msg_id}"
            caption_text = f"⬛ <b>NEXZEN LABS</b> ⬜ presents\n<b>{state['app_name']} {state['version']}</b> ✅\n\n<blockquote expandable>📦 <b>App Info</b>\n\n{state['info']}</blockquote>\n\n⬇️ <b>OFFICIAL DOWNLOAD</b> ⬇️"
            keyboard = {"inline_keyboard": [[{"text": "⬇️ Direct Download", "url": bot_deep_link}], [{"text": "⚡ GitHub Download", "url": text}]]}

            requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": PUBLIC_CHANNEL_ID, "photo": state["photo"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})
            send_message(chat_id, "✅ App post published!")
            USER_STATES.pop(chat_id, None)

    elif post_type == "PROMPT":
        if current_step == "MEDIA":
            if "photo" in message:
                state["media"].append({"type": "photo", "media": message["photo"][-1]["file_id"]})
            elif "video" in message:
                state["media"].append({"type": "video", "media": message["video"]["file_id"]})
        elif current_step == "CAPTION":
            state["caption"] = text
            state["step"] = "PROMPT_TEXT"
            send_message(chat_id, "Final Step: Send Prompt(s):")
        elif current_step == "PROMPT_TEXT":
            prompt_res = send_message(STORAGE_CHANNEL_ID, f"<b>PROMPT DATA:</b>\n\n<code>{text}</code>")
            prompt_msg_id = prompt_res["result"]["message_id"]

            prompt_deep_link = f"https://t.me/{BOT_USERNAME}?start=prompt_{prompt_msg_id}"
            caption_full = f"{state['caption']}\n\n⬇️ <b>GET PROMPT BELOW</b> ⬇️"
            keyboard = {"inline_keyboard": [[{"text": "📋 Get Prompt", "url": prompt_deep_link}]]}

            media_list = state["media"]
            if len(media_list) == 1:
                item = media_list[0]
                endpoint = "sendPhoto" if item["type"] == "photo" else "sendVideo"
                requests.post(f"{TELEGRAM_API}/{endpoint}", json={"chat_id": PUBLIC_CHANNEL_ID, item["type"]: item["media"], "caption": caption_full, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})
            else:
                formatted_media = []
                for idx, m in enumerate(media_list):
                    obj = {"type": m["type"], "media": m["media"]}
                    if idx == len(media_list) - 1:
                        obj["caption"] = caption_full
                        obj["parse_mode"] = "HTML"
                    formatted_media.append(obj)
                requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={"chat_id": PUBLIC_CHANNEL_ID, "media": json.dumps(formatted_media)})
                send_message(PUBLIC_CHANNEL_ID, "👇 Click button to get prompt:", keyboard)

            send_message(chat_id, "✅ Prompt post published!")
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
