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

def ultra_raw_menu():
    return {"inline_keyboard": [
        [{"text": "📄 PDF / Document", "callback_data": "add_pdf"}, {"text": "📱 APK File", "callback_data": "add_apk"}],
        [{"text": "📦 ZIP / Other File", "callback_data": "add_other"}, {"text": "🔗 Link / URL", "callback_data": "add_link"}],
        [{"text": "📝 Text Prompt", "callback_data": "add_text"}, {"text": "🖼️ Image", "callback_data": "add_image"}],
        [{"text": "🎬 Video", "callback_data": "add_video"}],
        [{"text": "✅ Done Uploading Items", "callback_data": "ultra_done"}]
    ]}

def handle_update(update):
    save_bot_user(update.get("message", {}).get("from", {}).get("id") or update.get("callback_query", {}).get("from", {}).get("id"))

    if "callback_query" in update:
        query = update["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        user_id = query["from"]["id"]
        data = query["data"]

        # ADMIN ONLY - regular users cannot use any buttons
        if user_id != ADMIN_ID:
            return

        if data == "type_app":
            USER_STATES[chat_id] = {"type": "APP", "step": "PHOTO"}
            send_message(chat_id, "<b>App Mode Selected</b>\nStep 1: Send Cover Photo.")
        elif data == "type_prompt":
            USER_STATES[chat_id] = {"type": "PROMPT", "step": "MEDIA", "media": []}
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Media", "callback_data": "media_done"}]]}
            send_message(chat_id, "<b>Prompt Mode Selected</b>\nSend images/videos. Click Done when finished.", keyboard)
        elif data == "type_raw":
            USER_STATES[chat_id] = {"type": "RAW", "step": "MEDIA"}
            send_message(chat_id, "<b>Raw Mode Selected</b>\nStep 1: Send Cover Photo or Video for the post.")
        elif data == "type_full_prompt":
            USER_STATES[chat_id] = {"type": "FULL_PROMPT", "step": "MAIN_MEDIA", "items": []}
            send_message(chat_id, "<b>🔥 Full Prompt Ultra Mode Selected</b>\nStep 1: Send Main Cover Photo or Video.")
        elif data == "type_ultra_raw":
            USER_STATES[chat_id] = {"type": "ULTRA_RAW", "step": "MAIN_MEDIA", "items": []}
            send_message(chat_id, "<b>⚡ Ultra Raw Mode Selected</b>\nStep 1: Send Main Cover Photo or Video.")
        elif data == "add_pdf":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_DOC"
                state["doc_intent"] = "pdf"
                send_message(chat_id, "📄 Please send the PDF / Document file.")
        elif data == "add_apk":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_DOC"
                state["doc_intent"] = "apk"
                send_message(chat_id, "📱 Please send the APK file.")
        elif data == "add_other":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_DOC"
                state["doc_intent"] = "other"
                send_message(chat_id, "📦 Please send the ZIP, RAR, Text File, or any other Document.")
        elif data == "add_link":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_LINK"
                send_message(chat_id, "🔗 Please send the Link / URL.")
        elif data == "add_text":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_TEXT"
                send_message(chat_id, "📝 Please send the Text Prompt.")
        elif data == "add_image":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_IMAGE"
                send_message(chat_id, "🖼️ Please send the Image.")
        elif data == "add_video":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                state["step"] = "AWAIT_VIDEO"
                send_message(chat_id, "🎬 Please send the Video.")
        elif data == "ultra_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "ULTRA_RAW":
                if not state.get("items"):
                    send_message(chat_id, "⚠️ Send at least one item before clicking Done!")
                    return
                
                buttons = []
                for item in state["items"]:
                    target_link = ""
                    intent = item.get("intent", "")
                    default_title = "🔗 Open Link"

                    if item["type"] == "link":
                        target_link = item["url"]
                        default_title = "🌐 Visit Link"
                    elif item["type"] == "photo":
                        doc_res = requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": STORAGE_CHANNEL_ID, "photo": item["id"]}).json()
                        msg_id = doc_res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=msg_{msg_id}"
                        default_title = "🖼️ View Image"
                    elif item["type"] == "video":
                        doc_res = requests.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": STORAGE_CHANNEL_ID, "video": item["id"]}).json()
                        msg_id = doc_res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=msg_{msg_id}"
                        default_title = "🎬 View Video"
                    elif item["type"] == "document":
                        doc_res = requests.post(f"{TELEGRAM_API}/sendDocument", json={"chat_id": STORAGE_CHANNEL_ID, "document": item["id"], "caption": f"<b>{item.get('name', 'File')}</b>", "parse_mode": "HTML"}).json()
                        msg_id = doc_res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=msg_{msg_id}"
                        if intent == "apk":
                            default_title = "📱 Download APK"
                        elif intent == "other":
                            default_title = f"📦 Download File ({item.get('name', 'File')})"
                        else:
                            default_title = f"📄 Download File ({item.get('name', 'Doc')})"
                    elif item["type"] == "text":
                        res = send_message(STORAGE_CHANNEL_ID, f"<b>PROMPT DATA:</b>\n\n<code>{item['text']}</code>")
                        msg_id = res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=prompt_{msg_id}"
                        default_title = "📋 Copy Prompt"

                    btn_title = item.get("custom_name") or default_title
                    buttons.append([{"text": btn_title, "url": target_link}])

                keyboard = {"inline_keyboard": buttons}
                caption_text = f"{state['caption']}\n\n⬇️ <b>GET MEDIA / PROMPTS BELOW</b> ⬇️"

                if state.get("main_media_type") == "photo":
                    requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": PUBLIC_CHANNEL_ID, "photo": state["main_media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})
                else:
                    requests.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": PUBLIC_CHANNEL_ID, "video": state["main_media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})

                send_message(chat_id, "✅ Ultra Raw post published successfully!")
                USER_STATES.pop(chat_id, None)
        elif data == "btn_no":
            state = USER_STATES.get(chat_id)
            if state and state.get("step") == "ASK_CUSTOM":
                state["pending_item"]["custom_name"] = None
                if state.get("type") == "RAW":
                    state["files"].append(state["pending_item"])
                    state["step"] = "FILES"
                    keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "raw_files_done"}]]}
                    send_message(chat_id, "Added item with default title. Send next item or click Done.", keyboard)
                elif state.get("type") == "FULL_PROMPT":
                    state["items"].append(state["pending_item"])
                    state["step"] = "ITEMS"
                    keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "full_prompt_done"}]]}
                    send_message(chat_id, "Added item with default title. Send next file/media/prompt or click Done.", keyboard)
                elif state.get("type") == "ULTRA_RAW":
                    state["items"].append(state["pending_item"])
                    state["step"] = "MENU"
                    send_message(chat_id, "Added item with default title. Choose next item or click Done.", ultra_raw_menu())
        elif data == "btn_yes":
            state = USER_STATES.get(chat_id)
            if state and state.get("step") == "ASK_CUSTOM":
                state["step"] = "ENTER_CUSTOM"
                send_message(chat_id, "Enter the custom button title for this item:")
        elif data == "media_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "PROMPT" and state.get("step") == "MEDIA":
                if not state.get("media"):
                    send_message(chat_id, "⚠️ Send at least one media file!")
                    return
                state["step"] = "CAPTION"
                send_message(chat_id, "Next Step: Send Caption for post.")
        elif data == "raw_files_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "RAW":
                if not state.get("files"):
                    send_message(chat_id, "⚠️ Send at least one file or text prompt!")
                    return
                buttons = []
                for f in state["files"]:
                    if f["item_type"] == "doc":
                        doc_payload = {"chat_id": STORAGE_CHANNEL_ID, "document": f["id"], "caption": f"<b>{f['name']}</b>", "parse_mode": "HTML"}
                        doc_res = requests.post(f"{TELEGRAM_API}/sendDocument", json=doc_payload).json()
                        msg_id = doc_res["result"]["message_id"]
                        deep_link = f"https://t.me/{BOT_USERNAME}?start=msg_{msg_id}"
                        default_name = f"📄 Download {f['name']}"
                    else:
                        res = send_message(STORAGE_CHANNEL_ID, f"<b>PROMPT DATA:</b>\n\n<code>{f['text']}</code>")
                        msg_id = res["result"]["message_id"]
                        deep_link = f"https://t.me/{BOT_USERNAME}?start=prompt_{msg_id}"
                        default_name = "📋 Get Prompt"

                    btn_title = f.get("custom_name") or default_name
                    buttons.append([{"text": btn_title, "url": deep_link}])

                keyboard = {"inline_keyboard": buttons}
                caption_text = f"{state['caption']}\n\n⬇️ <b>OFFICIAL LINKS / DOWNLOADS</b> ⬇️"

                if state["media_type"] == "photo":
                    requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": PUBLIC_CHANNEL_ID, "photo": state["media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})
                else:
                    requests.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": PUBLIC_CHANNEL_ID, "video": state["media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})

                send_message(chat_id, "✅ Raw post published successfully!")
                USER_STATES.pop(chat_id, None)

        elif data == "full_prompt_done":
            state = USER_STATES.get(chat_id)
            if state and state.get("type") == "FULL_PROMPT":
                if not state.get("items"):
                    send_message(chat_id, "⚠️ Send at least one media/file/prompt item!")
                    return
                
                buttons = []
                for item in state["items"]:
                    target_link = ""
                    default_title = "🔗 Open Link"

                    if item["type"] == "link":
                        target_link = item["url"]
                        default_title = "🌐 Visit Link"
                    elif item["type"] in ["photo", "video", "document"]:
                        media_kind = item["type"]
                        endpoint = "sendPhoto" if media_kind == "photo" else ("sendVideo" if media_kind == "video" else "sendDocument")
                        doc_res = requests.post(f"{TELEGRAM_API}/{endpoint}", json={"chat_id": STORAGE_CHANNEL_ID, media_kind: item["id"]}).json()
                        msg_id = doc_res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=msg_{msg_id}"
                        
                        if media_kind == "photo": default_title = "🖼️ View Image"
                        elif media_kind == "video": default_title = "🎬 View Video"
                        else: default_title = f"📄 Download File ({item.get('name', 'Doc')})"
                    elif item["type"] == "text":
                        res = send_message(STORAGE_CHANNEL_ID, f"<b>PROMPT DATA:</b>\n\n<code>{item['text']}</code>")
                        msg_id = res["result"]["message_id"]
                        target_link = f"https://t.me/{BOT_USERNAME}?start=prompt_{msg_id}"
                        default_title = "📋 Copy Prompt"

                    btn_title = item.get("custom_name") or default_title
                    buttons.append([{"text": btn_title, "url": target_link}])

                keyboard = {"inline_keyboard": buttons}
                caption_text = f"{state['caption']}\n\n⬇️ <b>GET MEDIA / PROMPTS BELOW</b> ⬇️"

                if state["main_media_type"] == "photo":
                    requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": PUBLIC_CHANNEL_ID, "photo": state["main_media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})
                else:
                    requests.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": PUBLIC_CHANNEL_ID, "video": state["main_media"], "caption": caption_text, "parse_mode": "HTML", "reply_markup": json.dumps(keyboard)})

                send_message(chat_id, "✅ Full Prompt Ultra post published successfully!")
                USER_STATES.pop(chat_id, None)
        return

    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    # Force Join Verification (for non-admin users only)
    if user_id != ADMIN_ID and not check_channel_membership(user_id):
        start_args = text.split()
        start_param = start_args[1] if len(start_args) > 1 else "home"
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": f"https://t.me/{PUBLIC_CHANNEL_ID.replace('@', '')}"}],
                [{"text": "🔄 Try Again", "url": f"https://t.me/{BOT_USERNAME}?start={start_param}"}]
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
                send_message(chat_id, "📦 <b>Here is your file/media!</b> (Auto-deletes in 60s)")
                res = copy_message(chat_id, STORAGE_CHANNEL_ID, msg_id)
                if res.get("ok"):
                    file_msg_id = res["result"]["message_id"]
                    Thread(target=auto_delete_task, args=(chat_id, file_msg_id, 60)).start()
                return
            elif param.startswith("prompt_"):
                prompt_msg_id = int(param.replace("prompt_", ""))
                send_message(chat_id, "✨ <b>Here is your Prompt!</b> (Auto-deletes in 60s)")
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

    # BLOCK ALL NON-ADMIN USERS FROM ANY CONTROL/PUBLISH FEATURES
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
                [{"text": "🎬 Publish Prompt & Media", "callback_data": "type_prompt"}],
                [{"text": "📁 Publish Raw (Docs & Text Prompts)", "callback_data": "type_raw"}],
                [{"text": "🔥 Publish Full Prompt Ultra", "callback_data": "type_full_prompt"}],
                [{"text": "⚡ Publish Ultra Raw (Menu Based)", "callback_data": "type_ultra_raw"}]
            ]
        }
        send_message(chat_id, "What type of post do you want to create?", keyboard)
        return

    if not state:
        return

    post_type = state.get("type")
    current_step = state.get("step")

    # --- ULTRA RAW FLOW ---
    if post_type == "ULTRA_RAW":
        if current_step == "MAIN_MEDIA":
            if "photo" in message:
                state["main_media"] = message["photo"][-1]["file_id"]
                state["main_media_type"] = "photo"
            elif "video" in message:
                state["main_media"] = message["video"]["file_id"]
                state["main_media_type"] = "video"
            else:
                send_message(chat_id, "Please send a valid Photo or Video for main cover.")
                return

            state["step"] = "CAPTION"
            send_message(chat_id, "Step 2: Send Main Caption for post.")

        elif current_step == "CAPTION":
            state["caption"] = text
            state["step"] = "MENU"
            send_message(chat_id, "Step 3: Choose what you want to add from the menu below:", ultra_raw_menu())

        elif current_step == "AWAIT_DOC":
            if "document" in message:
                doc = message["document"]
                pending = {"type": "document", "id": doc["file_id"], "name": doc.get("file_name", "File"), "intent": state.get("doc_intent", "pdf")}
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "⚠️ Please send a valid Document/APK file.")

        elif current_step == "AWAIT_LINK":
            if text.startswith("http://") or text.startswith("https://"):
                pending = {"type": "link", "url": text, "intent": "link"}
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "⚠️ Please send a valid URL (starting with http:// or https://).")

        elif current_step == "AWAIT_TEXT":
            if text:
                pending = {"type": "text", "text": text, "intent": "text"}
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "⚠️ Please send a valid text prompt.")

        elif current_step == "AWAIT_IMAGE":
            if "photo" in message:
                pending = {"type": "photo", "id": message["photo"][-1]["file_id"], "intent": "image"}
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "⚠️ Please send a valid Image.")

        elif current_step == "AWAIT_VIDEO":
            if "video" in message:
                pending = {"type": "video", "id": message["video"]["file_id"], "intent": "video"}
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "⚠️ Please send a valid Video.")

        elif current_step == "ENTER_CUSTOM":
            state["pending_item"]["custom_name"] = text
            state["items"].append(state["pending_item"])
            state["pending_item"] = None
            state["step"] = "MENU"
            send_message(chat_id, f"Custom button saved: <b>{text}</b>. Choose next item or click <b>Done Uploading Items</b>.", ultra_raw_menu())

    # --- FULL PROMPT ULTRA FLOW ---
    elif post_type == "FULL_PROMPT":
        if current_step == "MAIN_MEDIA":
            if "photo" in message:
                state["main_media"] = message["photo"][-1]["file_id"]
                state["main_media_type"] = "photo"
            elif "video" in message:
                state["main_media"] = message["video"]["file_id"]
                state["main_media_type"] = "video"
            else:
                send_message(chat_id, "Please send a valid Photo or Video for main cover.")
                return

            state["step"] = "CAPTION"
            send_message(chat_id, "Step 2: Send Main Caption for post.")

        elif current_step == "CAPTION":
            state["caption"] = text
            state["step"] = "ITEMS"
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "full_prompt_done"}]]}
            send_message(chat_id, "Step 3: Send any Photo, Video, Document/PDF, Text Prompt, or HTTP Link for Button 1:", keyboard)

        elif current_step == "ITEMS":
            pending = None
            if "photo" in message:
                pending = {"type": "photo", "id": message["photo"][-1]["file_id"]}
            elif "video" in message:
                pending = {"type": "video", "id": message["video"]["file_id"]}
            elif "document" in message:
                doc = message["document"]
                pending = {"type": "document", "id": doc["file_id"], "name": doc.get("file_name", "File")}
            elif text.startswith("http://") or text.startswith("https://"):
                pending = {"type": "link", "url": text}
            elif text:
                pending = {"type": "text", "text": text}

            if pending:
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Button Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "Please send a photo, video, document, text prompt, or valid link.")

        elif current_step == "ENTER_CUSTOM":
            state["pending_item"]["custom_name"] = text
            state["items"].append(state["pending_item"])
            state["pending_item"] = None
            state["step"] = "ITEMS"
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "full_prompt_done"}]]}
            send_message(chat_id, f"Custom button saved: <b>{text}</b>. Send next item or click <b>Done Uploading Items</b>.", keyboard)

    # --- RAW MODE FLOW ---
    elif post_type == "RAW":
        if current_step == "MEDIA":
            if "photo" in message:
                state["media"] = message["photo"][-1]["file_id"]
                state["media_type"] = "photo"
            elif "video" in message:
                state["media"] = message["video"]["file_id"]
                state["media_type"] = "video"
            else:
                send_message(chat_id, "Please send a valid Photo or Video.")
                return

            state["step"] = "CAPTION"
            send_message(chat_id, "Step 2: Send Caption/Description for the post.")

        elif current_step == "CAPTION":
            state["caption"] = text
            state["step"] = "FILES"
            state["files"] = []
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "raw_files_done"}]]}
            send_message(chat_id, "Step 3: Send Document files or Text Prompts one by one.", keyboard)

        elif current_step == "FILES":
            pending = None
            if "document" in message:
                doc = message["document"]
                pending = {"item_type": "doc", "id": doc["file_id"], "name": doc.get("file_name", "File")}
            elif text:
                pending = {"item_type": "text", "text": text}

            if pending:
                state["pending_item"] = pending
                state["step"] = "ASK_CUSTOM"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "✏️ Yes (Set Custom Title)", "callback_data": "btn_yes"}],
                        [{"text": "❌ No (Use Default Title)", "callback_data": "btn_no"}]
                    ]
                }
                send_message(chat_id, "Item received! Do you want to set a custom title for this button?", keyboard)
            else:
                send_message(chat_id, "Please upload a valid Document or Text Prompt.")

        elif current_step == "ENTER_CUSTOM":
            state["pending_item"]["custom_name"] = text
            state["files"].append(state["pending_item"])
            state["pending_item"] = None
            state["step"] = "FILES"
            keyboard = {"inline_keyboard": [[{"text": "✅ Done Uploading Items", "callback_data": "raw_files_done"}]]}
            send_message(chat_id, f"Custom title saved! Send next item or click <b>Done Uploading Items</b>.", keyboard)

    # --- APP FLOW ---
    elif post_type == "APP":
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

    # --- PROMPT FLOW ---
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
