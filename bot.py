import os
import json
import sqlite3
import random
import string
from dotenv import load_dotenv
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, filters

# -----------------------
# LOAD ENV
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("BOT_TOKEN hoặc ADMIN_IDS chưa thiết lập đúng trong .env!")

# -----------------------
# DATABASE
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS media_group (
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

def save_or_append_media(file_ids, types):
    """
    Nếu đã có code (admin chỉ 1 code duy nhất) -> append
    Nếu chưa -> tạo code mới
    """
    cursor.execute("SELECT code, file_ids, types FROM media_group LIMIT 1")
    row = cursor.fetchone()
    if row:
        code, existing_file_ids, existing_types = row[0], json.loads(row[1]), json.loads(row[2])
        existing_file_ids.extend(file_ids)
        existing_types.extend(types)
        cursor.execute(
            "UPDATE media_group SET file_ids=?, types=? WHERE code=?",
            (json.dumps(existing_file_ids), json.dumps(existing_types), code)
        )
        conn.commit()
        return code
    else:
        code = generate_code()
        cursor.execute(
            "INSERT INTO media_group (code, file_ids, types) VALUES (?, ?, ?)",
            (code, json.dumps(file_ids), json.dumps(types))
        )
        conn.commit()
        return code

def get_media_group(code):
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
        file_ids, types = get_media_group(code)
        if file_ids:
            # Telegram media group chỉ gửi max 10 file 1 lần
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
        await update.message.reply_text("Chào bạn! Admin upload file sẽ nhận 1 link duy nhất. User bấm link để nhận file.")

async def handle_media(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("Bạn không có quyền upload file.")
        return

    file_ids = []
    types = []

    # Lấy video
    if update.message.video:
        file_ids.append(update.message.video.file_id)
        types.append("video")

    # Lấy tất cả ảnh
    if update.message.photo:
        for photo in update.message.photo:
            file_ids.append(photo.file_id)
            types.append("photo")

    if file_ids:
        code = save_or_append_media(file_ids, types)
        await update.message.reply_text(
            f"Upload thành công! Link duy nhất: https://t.me/{context.bot.username}?start={code}"
        )

# -----------------------
# MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))

print("Bot đang chạy…")
app.run_polling()