import os
import json
import sqlite3
import random
import string
from telegram import Update, InputMediaVideo, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, filters
)
from dotenv import load_dotenv

# -----------------------
# LOAD CONFIG
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DB_PATH = "database.db"

# -----------------------
# DATABASE
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS media_group (
    admin_id INTEGER PRIMARY KEY,
    code TEXT,
    file_ids TEXT,
    types TEXT
)
''')
conn.commit()

# -----------------------
# HELPERS
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def save_or_append_media(admin_id, new_file_ids, new_types):
    cursor.execute("SELECT code, file_ids, types FROM media_group WHERE admin_id=?", (admin_id,))
    row = cursor.fetchone()
    if row:
        # admin đã có code → append file mới
        code, file_ids_json, types_json = row
        file_ids = json.loads(file_ids_json)
        types = json.loads(types_json)
        file_ids.extend(new_file_ids)
        types.extend(new_types)
        cursor.execute(
            "UPDATE media_group SET file_ids=?, types=? WHERE admin_id=?",
            (json.dumps(file_ids), json.dumps(types), admin_id)
        )
        conn.commit()
        return code
    else:
        # admin chưa có code → tạo code mới
        code = generate_code()
        cursor.execute(
            "INSERT INTO media_group (admin_id, code, file_ids, types) VALUES (?, ?, ?, ?)",
            (admin_id, code, json.dumps(new_file_ids), json.dumps(new_types))
        )
        conn.commit()
        return code

def get_media_group_by_code(code):
    cursor.execute("SELECT file_ids, types FROM media_group WHERE code=?", (code,))
    row = cursor.fetchone()
    if row:
        file_ids = json.loads(row[0])
        types = json.loads(row[1])
        return file_ids, types
    return [], []

# -----------------------
# HANDLERS
async def start(update: Update, context: CallbackContext):
    args = context.args
    if args:
        code = args[0]
        file_ids, types = get_media_group_by_code(code)
        if file_ids:
            # Gửi media group theo chunks 10 file (Telegram max)
            for i in range(0, len(file_ids), 10):
                media = []
                for fid, ftype in zip(file_ids[i:i+10], types[i:i+10]):
                    if ftype == "video":
                        media.append(InputMediaVideo(fid))
                    elif ftype == "photo":
                        media.append(InputMediaPhoto(fid))
                await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media)
        else:
            await update.message.reply_text("Mã không hợp lệ hoặc chưa có file nào.")
    else:
        await update.message.reply_text("Chào bạn! Gửi link rút gọn với mã để nhận file.")

async def handle_media(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        return  # Không phải admin

    new_file_ids = []
    new_types = []

    # Video
    if update.message.video:
        new_file_ids.append(update.message.video.file_id)
        new_types.append("video")

    # Photo
    if update.message.photo:
        new_file_ids.append(update.message.photo[-1].file_id)  # lấy file lớn nhất
        new_types.append("photo")

    if new_file_ids:
        code = save_or_append_media(user_id, new_file_ids, new_types)
        await update.message.reply_text(
            f"Upload thành công! Link nhận file: https://t.me/{context.bot.username}?start={code}"
        )

# -----------------------
# MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))

print("Bot đang chạy…")
app.run_polling()