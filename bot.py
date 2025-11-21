import os
import json
import sqlite3
import random
import string
from telegram import Update, InputMediaVideo
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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
    file_ids TEXT
)
''')
conn.commit()

# -----------------------
# HELPERS
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def save_media_group(file_ids):
    code = generate_code()
    cursor.execute("INSERT INTO media_groups (code, file_ids) VALUES (?, ?)", (code, json.dumps(file_ids)))
    conn.commit()
    return code

def get_media_group(code):
    cursor.execute("SELECT file_ids FROM media_groups WHERE code=?", (code,))
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return []

# -----------------------
# HANDLERS
def start(update: Update, context: CallbackContext):
    args = context.args
    if args:
        code = args[0]
        file_ids = get_media_group(code)
        if file_ids:
            media = [InputMediaVideo(fid) for fid in file_ids]
            context.bot.send_media_group(chat_id=update.effective_chat.id, media=media)
        else:
            update.message.reply_text("Mã không hợp lệ hoặc hết hạn.")
    else:
        update.message.reply_text("Chào bạn! Gửi link rút gọn với mã để nhận file.")

def handle_media(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        return  # Không phải admin
    file_ids = []

    # Nếu là MediaGroup (nhiều video)
    if update.message.media_group_id:
        # Lấy tất cả message cùng media_group_id
        chat_id = update.effective_chat.id
        messages = context.bot.get_chat(chat_id).get_history(limit=10)  # giới hạn 10 message gần đây
        for msg in messages:
            if getattr(msg, 'media_group_id', None) == update.message.media_group_id and msg.video:
                file_ids.append(msg.video.file_id)
    elif update.message.video:
        file_ids.append(update.message.video.file_id)

    if file_ids:
        code = save_media_group(file_ids)
        update.message.reply_text(
            f"Upload thành công! Link nhận file: https://t.me/{context.bot.username}?start={code}"
        )

# -----------------------
# MAIN
updater = Updater(BOT_TOKEN)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.video | Filters.media_group, handle_media))

print("Bot đang chạy…")
updater.start_polling()
updater.idle()