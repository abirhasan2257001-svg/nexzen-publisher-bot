import os
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "NexzenLabsPublisherBot"
CHANNEL_ID = "@NexzenLabs"

PHOTO, APP_NAME, VERSION, INFO, FILE, GITHUB = range(6)

async def process_update(update_json):
    app = ApplicationBuilder().token(TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello Owner! Send /create to start making a post.")

    async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Step 1: Send the Cover Photo for the post.")
        return PHOTO

    async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['photo'] = update.message.photo[-1].file_id
        await update.message.reply_text("Step 2: Enter App Name (e.g., Besura):")
        return APP_NAME

    async def get_app_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['app_name'] = update.message.text
        await update.message.reply_text("Step 3: Enter App Version (e.g., v1.0):")
        return VERSION

    async def get_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['version'] = update.message.text
        await update.message.reply_text("Step 4: Enter App Features / Info (each feature in a new line):")
        return INFO

    async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        raw_info = update.message.text.split('\n')
        formatted_info = "\n".join([f"• {item.strip()}" for item in raw_info if item.strip()])
        context.user_data['info'] = formatted_info
        await update.message.reply_text("Step 5: Send or Upload the APK file now:")
        return FILE

    async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
        file_id = update.message.document.file_id
        context.user_data['file_id'] = file_id
        await update.message.reply_text("Step 6: Send the GitHub link:")
        return GITHUB

    async def get_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
        github_link = update.message.text
        app_name = context.user_data['app_name']
        version = context.user_data['version']
        
        caption_text = (
            f"⬛ <b>NEXZEN LABS</b> ⬜ presents\n"
            f"<b>{app_name} {version}</b> ✅\n\n"
            f"<blockquote expandable>📦 <b>App Info</b>\n\n"
            f"{context.user_data['info']}</blockquote>\n\n"
            f"⬇️ <b>OFFICIAL DOWNLOAD</b> ⬇️"
        )
        
        bot_deep_link = f"https://t.me/{BOT_USERNAME}"
        
        keyboard = [
            [InlineKeyboardButton("⬇️ Direct Download", url=bot_deep_link)],
            [InlineKeyboardButton("⚡ GitHub Download", url=github_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=context.user_data['photo'],
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text("✅ Successfully posted to your channel!")
        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Process cancelled.")
        return ConversationHandler.END

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_post)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            APP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_app_name)],
            VERSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version)],
            INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_info)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
            GITHUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_github)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    await app.initialize()
    update = Update.de_json(update_json, app.bot)
    await app.process_update(update)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update_json = json.loads(post_data.decode('utf-8'))

        import asyncio
        asyncio.run(process_update(update_json))

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
