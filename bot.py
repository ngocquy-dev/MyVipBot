import sqlite3
import uuid
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------------------
# CONFIG
# -------------------------------
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 123456789   # Thay bằng ID Telegram của bạn

# -------------------------------
# DATABASE
# -------------------------------
def init_db():
    conn = sqlite3.connect("files.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            code TEXT PRIMARY KEY,
            files TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Lưu batch vào DB
def save_batch(code, files):
    conn = sqlite3.connect("files.db")
    c = conn.cursor()
    c.execute("INSERT INTO batches (code, files) VALUES (?,?)", (code, ",".join(files)))
    conn.commit()
    conn.close()

# Lấy batch từ DB
def get_batch(code):
    conn = sqlite3.connect("files.db")
    c = conn.cursor()
    c.execute("SELECT files FROM batches WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()

    if row:
        return row[0].split(",")
    return None

# -------------------------------
# BỘ NHỚ TẠM THỜI CHO ADMIN
# -------------------------------
admin_files = {}  # { admin_id : [file_ids] }

# -------------------------------
# COMMAND: /start
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # Nếu user bấm link start kèm code
    if args:
        code = args[0]
        files = get_batch(code)
        if not files:
            await update.message.reply_text("Link không hợp lệ hoặc đã hết hạn!")
            return

        # Trả về tất cả file
        media = []
        for f in files:
            if f.startswith("photo_"):
                media.append(InputMediaPhoto(f.replace("photo_", "")))
            else:
                media.append(InputMediaVideo(f.replace("video_", "")))

        if len(media) == 1:
            if media[0].type == "photo":
                await update.message.reply_photo(media[0].media)
            else:
                await update.message.reply_video(media[0].media)
        else:
            await update.message.reply_media_group(media)

        return

    # Nếu user bấm start bình thường
    await update.message.reply_text("Chào bạn! Gửi link hợp lệ để nhận files.")

# -------------------------------
# NHẬN FILE (CHỈ ADMIN)
# -------------------------------
async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Bạn không có quyền upload files!")
        return

    file_id = None

    if update.message.photo:
        file_id = "photo_" + update.message.photo[-1].file_id

    elif update.message.video:
        file_id = "video_" + update.message.video.file_id

    else:
        await update.message.reply_text("Chỉ hỗ trợ ảnh và video!")
        return

    # Thêm file vào bộ nhớ tạm của admin
    admin_files.setdefault(ADMIN_ID, []).append(file_id)

    await update.message.reply_text("Đã nhận file! Gõ /done khi upload xong.")

# -------------------------------
# /done – tạo 1 link duy nhất
# -------------------------------
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Bạn không có quyền dùng lệnh này!")
        return

    files = admin_files.get(ADMIN_ID, [])

    if len(files) == 0:
        await update.message.reply_text("Bạn chưa upload file nào!")
        return

    # Tạo mã duy nhất
    code = uuid.uuid4().hex[:8]

    # Lưu vào DB
    save_batch(code, files)

    # Reset danh sách để tránh dồn file
    admin_files[ADMIN_ID] = []

    link = f"https://t.me/{context.bot.username}?start={code}"

    await update.message.reply_text(f"Upload hoàn tất!\nLink nhận files: {link}")

# -------------------------------
# MAIN
# -------------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("done", done))
app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, receive_file))

app.run_polling()