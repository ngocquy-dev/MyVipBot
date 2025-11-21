import os
import json
import sqlite3
import random
import string
from telegram import Update, InputMediaVideo, InputMediaPhoto
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, filters

# -----------------------
# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]

DB_PATH = "database.db"

# -----------------------
# DATABASE
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS media_groups (
    code TEXT PRIMARY KEY,
    file_ids TEXT,
    types TEXT
)
''')
conn.commit()

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
def start(update: Update, context: CallbackContext):
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
            context.bot.send_media_group(chat_id=update.effective_chat.id, media=media)
        else:
            update.message.reply_text("Mã không hợp lệ hoặc hết hạn.")
    else:
        update.message.reply_text("Chào bạn! Gửi link rút gọn với mã để nhận file.")

def handle_media(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        return  # Không phải admin

    file_ids = []
    types = []

    # Nếu gửi video
    if update.message.video:
        file_ids.append(update.message.video.file_id)
        types.append("video")
    # Nếu gửi ảnh
    if update.message.photo:
        # Telegram gửi ảnh dưới dạng list, lấy file_id lớn nhất
        file_ids.append(update.message.photo[-1].file_id)
        types.append("photo")

    # Nếu gửi media group, PTB sẽ gọi handle_media cho từng message riêng
    if file_ids:
        code = save_media_group(file_ids, types)
        update.message.reply_text(
            f"Upload thành công! Link nhận file: https://t.me/{context.bot.username}?start={code}"
        )

# -----------------------
# MAIN
updater = Updater(BOT_TOKEN)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))

print("Bot đang chạy…")
updater.start_polling()
updater.idle()