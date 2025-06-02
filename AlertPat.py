import psutil
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "7993011175:AAGb9Pji1jgBeENd0TsfqgcfyAeVTTYrZxI"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для мониторинга сервера.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent  
    
    alert = ""
    if cpu > 90:
        alert += "⚠️ CPU перегружен!\n"
    if ram > 90:
        alert += "⚠️ RAM перегружена!\n"
    if disk > 90:
        alert += "⚠️ Диск почти заполнен!\n"
    
    message = f"📊 Статус сервера:\nCPU: {cpu}%\nRAM: {ram}%\nДиск: {disk}%\n{alert}"
    await update.message.reply_text(message)

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()