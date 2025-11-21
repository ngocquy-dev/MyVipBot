import os
import sqlite3
import random
import string
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]

# Setup database
DB_FILE = "database.db"
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS files
             (code TEXT PRIMARY KEY, file_id TEXT, file_type TEXT)''')
conn.commit()

# Helper: generate random code
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Check admin
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Admin upload file
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Bạn không phải admin.")
        return

    file = None
    file_type = None

    if update.message.photo:
        file = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.video:
        file = update.message.video.file_id
        file_type = "video"
    else:
        await update.message.reply_text("Chỉ chấp nhận ảnh hoặc video.")
        return

    code = generate_code()
    # Save to DB
    c.execute("INSERT INTO files(code, file_id, file_type) VALUES (?, ?, ?)", (code, file, file_type))
    conn.commit()

    link = f"https://t.me/myviptoolbot?start={code}"
    await update.message.reply_text(f"File đã lưu với mã: {code}\nLink bot: {link}")

# User start bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Xin chào! Bạn chưa có mã nào để nhận file.")
        return

    code = args[0]
    c.execute("SELECT file_id, file_type FROM files WHERE code=?", (code,))
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("Mã không hợp lệ hoặc file đã bị xóa.")
        return

    await update.message.reply_text("Đang gửi file…")
    for file_id, file_type in rows:
        if file_type == "photo":
            await update.message.reply_photo(file_id)
        elif file_type == "video":
            await update.message.reply_video(file_id)

    await update.message.reply_text("Hoàn tất!")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Admin:\n- Upload ảnh/video → bot trả link\n\n"
        "User:\n- Bấm link bot → bot tự gửi file tương ứng"
    )

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_file))

    print("Bot đang chạy…")
    app.run_polling()

if __name__ == "__main__":
    main()