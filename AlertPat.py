import psutil
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import logging
import pickle
import os
import asyncio

# Настройки
TOKEN = "7993011175:AAGb9Pji1jgBeENd0TsfqgcfyAeVTTYrZxI"
CHAT_ID = "1917929126" 
DATA_FILE = "metrics.pkl"
LOG_FILE = "bot.log"
REPORT_INTERVAL = 3600  # 1 час

# Логирование
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

class MetricsStorage:
    def __init__(self):
        self.df = pd.DataFrame(columns=['timestamp', 'cpu', 'ram', 'disk', 'network'])
        try:
            self.load_data()
        except (FileNotFoundError, EOFError, pickle.PickleError):
            self.df = pd.DataFrame(columns=['timestamp', 'cpu', 'ram', 'disk', 'network'])
            self.save_data()

    def add_metrics(self):
        new_data = {
            'timestamp': datetime.now(),
            'cpu': psutil.cpu_percent(),
            'ram': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'network': psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_data])], ignore_index=True)
        self.clean_data()
        self.save_data()

    def clean_data(self):
        cutoff = datetime.now() - timedelta(days=7)
        self.df = self.df[self.df['timestamp'] >= cutoff]

    def save_data(self):
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(self.df, f)

    def load_data(self):
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, 'rb') as f:
                self.df = pickle.load(f)

storage = MetricsStorage()

def detect_anomalies():
    if len(storage.df) < 10:
        return None
    last_24h = storage.df[storage.df['timestamp'] >= datetime.now() - timedelta(hours=24)]
    if len(last_24h) < 5:
        return None
    X = last_24h[['cpu', 'ram', 'network']].values
    model = DBSCAN(eps=2.5, min_samples=3).fit(X)
    anomalies = last_24h[model.labels_ == -1]
    return anomalies.iloc[-1] if not anomalies.empty else None

async def send_report(application):
    storage.add_metrics()
    last = storage.df.iloc[-1]

    msg = (
        "📊 Отчёт:\n"
        f"CPU: {last['cpu']}%\n"
        f"RAM: {last['ram']}%\n"
        f"Диск: {last['disk']}%"
    )

    anomaly = detect_anomalies()
    if anomaly is not None:
        msg += (
            "\n\n⚠️ Аномалия:\n"
            f"Время: {anomaly['timestamp']}\n"
            f"CPU: {anomaly['cpu']}%\n"
            f"RAM: {anomaly['ram']}%"
        )

    await application.bot.send_message(chat_id=CHAT_ID, text=msg)
    logging.info(f"Отчёт отправлен: {msg[:50]}...")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Добро пожаловать в серверный мониторинг!\n\n"
        "Доступные команды:\n"
        "/start — приветствие и список команд\n"
        "/stats — общая статистика\n"
        "/report — текущий отчёт\n"
        "/plot_cpu — график CPU\n"
        "/plot_ram — график RAM\n"
        "/plot_disk — график диска\n"
        "/plot_net — график сети\n"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if storage.df.empty:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⛔️ Нет доступных данных для отображения статистики. Подождите, пока бот соберёт первые метрики."
        )
        return

    desc = storage.df.describe().round(2)
    desc = desc[['cpu', 'ram', 'disk', 'network']]  # Ограничиваем нужные метрики

    headers = "| Показатель | CPU (%) | RAM (%) | Диск (%) | Сеть (байт) |\n"
    headers += "|------------|---------|----------|-----------|--------------|\n"

    rows = ""
    for index, row in desc.iterrows():
        rows += f"| {index.capitalize():<10} | {row['cpu']:>7} | {row['ram']:>8} | {row['disk']:>9} | {int(row['network']):>12} |\n"

    table_md = headers + rows

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📈 <b>Сводная статистика</b>\n<pre>{table_md}</pre>",
        parse_mode="HTML"
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.add_metrics()
    last = storage.df.iloc[-1]

    msg = (
        "📊 Отчёт:\n"
        f"CPU: {last['cpu']}%\n"
        f"RAM: {last['ram']}%\n"
        f"Диск: {last['disk']}%"
    )

    anomaly = detect_anomalies()
    if anomaly is not None:
        msg += (
            "\n\n⚠️ Аномалия:\n"
            f"Время: {anomaly['timestamp']}\n"
            f"CPU: {anomaly['cpu']}%\n"
            f"RAM: {anomaly['ram']}%"
        )

    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def create_plot(column: str, filename: str):
    df = storage.df.copy()
    df = df[df['timestamp'] >= datetime.now() - timedelta(days=2)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    plt.figure(figsize=(10, 4))
    plt.plot(df['timestamp'], df[column], marker='o', linestyle='-')
    plt.title(f"{column.upper()} за последние 2 дня")
    plt.xlabel("Время")
    plt.ylabel(column.upper())
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

async def send_plot(update: Update, context: ContextTypes.DEFAULT_TYPE, column: str):
    filename = f"{column}.png"
    create_plot(column, filename)
    with open(filename, "rb") as img:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(img))

async def plot_cpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_plot(update, context, "cpu")

async def plot_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_plot(update, context, "ram")

async def plot_disk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_plot(update, context, "disk")

async def plot_net(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_plot(update, context, "network")

async def periodic_report(application):
    while True:
        await send_report(application)
        await asyncio.sleep(REPORT_INTERVAL)

async def on_startup(application):
    await application.bot.send_message(chat_id=CHAT_ID, text="🔄 Бот мониторинга запущен")
    application.create_task(periodic_report(application))

def main():
    application = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("plot_cpu", plot_cpu))
    application.add_handler(CommandHandler("plot_ram", plot_ram))
    application.add_handler(CommandHandler("plot_disk", plot_disk))
    application.add_handler(CommandHandler("plot_net", plot_net))

    application.run_polling()

if __name__ == "__main__":
    main()
