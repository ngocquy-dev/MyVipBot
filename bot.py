from flask import Flask
import threading
import os
import json
import sqlite3
import random
import string
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv

# -----------------------
# LOAD ENV
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# -----------------------
# DATABASE
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Lưu các nhóm media
cursor.execute('''
CREATE TABLE IF NOT EXISTS media_groups (
    code TEXT PRIMARY KEY,
    file_ids TEXT,
    types TEXT
)
''')
conn.commit()

# Lưu tạm files trước khi /done
temp_uploads = {}  # {admin_id: {"file_ids": [], "types": []}}

# -----------------------
# HELPERS
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def save_media_group(file_ids, types):
    code = generate_code()
    cursor.execute(
        "INSERT INTO media_groups (code, file_ids, types) VALUES (?, ?, ?)",
        (code, json.dumps(file_ids), json.dumps(types))
    )
    conn.commit()
    return code

def get_media_group(code):
    cursor.execute("SELECT file_ids, types FROM media_groups WHERE code=?", (code,))
    row = cursor.fetchone()
    if row:
        file_ids = json.loads(row[0])
        types = json.loads(row[1])
        return file_ids, types
    return [], []

# -----------------------
# HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        code = args[0]
        file_ids, types = get_media_group(code)
        if file_ids:
            media = []
            for fid, ftype in zip(file_ids, types):
                if ftype == "video":
                    media.append(InputMediaVideo(fid))
                elif ftype == "photo":
                    media.append(InputMediaPhoto(fid))
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media)
        else:
            await update.message.reply_text("Mã không hợp lệ hoặc đã hết hạn.")
    else:
        await update.message.reply_text("Chào bạn! Nếu bạn là admin, gửi file rồi dùng /done để tạo link. Người dùng bấm link sẽ nhận tất cả file.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return  # Không phải admin

    if user_id not in temp_uploads:
        temp_uploads[user_id] = {"file_ids": [], "types": []}

    # Video
    if update.message.video:
        temp_uploads[user_id]["file_ids"].append(update.message.video.file_id)
        temp_uploads[user_id]["types"].append("video")
    # Photo
    if update.message.photo:
        temp_uploads[user_id]["file_ids"].append(update.message.photo[-1].file_id)
        temp_uploads[user_id]["types"].append("photo")

    await update.message.reply_text("File được lưu tạm, gửi tiếp hoặc dùng /done để tạo link.")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return

    if user_id not in temp_uploads or not temp_uploads[user_id]["file_ids"]:
        await update.message.reply_text("Không có file nào để tạo link.")
        return

    file_ids = temp_uploads[user_id]["file_ids"]
    types = temp_uploads[user_id]["types"]

    code = save_media_group(file_ids, types)
    await update.message.reply_text(
        f"Upload hoàn tất! Link nhận file: https://t.me/{context.bot.username}?start={code}"
    )

    # Xóa tạm
    temp_uploads[user_id] = {"file_ids": [], "types": []}

# -----------------------
# -----------------------
# KEEP ALIVE (Replit)
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running"

def run_web():
    web_app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

# MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("done", done))
app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))

if __name__ == "__main__":
    print("Bot đang chạy…")
    app.run_polling(close_loop=False)
