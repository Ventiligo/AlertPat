import psutil
import pandas as pd
from sklearn.cluster import DBSCAN
import telegram
from datetime import datetime, timedelta
import logging
import pickle
import os
import time

TOKEN = "7993011175:AAGb9Pji1jgBeENd0TsfqgcfyAeVTTYrZxI"
CHAT_ID = "1917929126" 
DATA_FILE = "metrics.pkl"
LOG_FILE = "bot.log"
REPORT_INTERVAL = 3600 

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

bot = telegram.Bot(token=TOKEN)

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

def send_report():
    storage.add_metrics()
    last = storage.df.iloc[-1]
    
    msg = (
        "📊 Отчёт:\n"
        f"CPU: {last['cpu']}%\n"
        f"RAM: {last['ram']}%\n"
        f"Диск: {last['disk']}%"
    )
    
    if anomaly := detect_anomalies():
        msg += (
            "\n\n⚠️ Аномалия:\n"
            f"Время: {anomaly['timestamp']}\n"
            f"CPU: {anomaly['cpu']}%\n"
            f"RAM: {anomaly['ram']}%"
        )
    
    bot.send_message(chat_id=CHAT_ID, text=msg)
    logging.info(f"Отчёт отправлен: {msg[:50]}...")

def handle_command(update):
    text = update.message.text
    if text == '/start':
        bot.send_message(chat_id=update.message.chat_id, text="Мониторинг сервера запущен. Отчёты приходят ежечасно.")
    elif text == '/stats':
        stats = storage.df.describe().to_string()
        bot.send_message(chat_id=update.message.chat_id, text=f"📈 Статистика:\n{stats}")

def main():
    last_report_time = 0
    
    bot.send_message(chat_id=CHAT_ID, text="🔄 Бот мониторинга запущен")
    
    while True:
        try:
            current_time = time.time()
            if current_time - last_report_time >= REPORT_INTERVAL:
                send_report()
                last_report_time = current_time
            
            updates = bot.get_updates(offset=(bot.get_updates()[-1].update_id + 1)) if bot.get_updates() else []
            for update in updates:
                handle_command(update)
            
            time.sleep(10)
            
        except Exception as e:
            logging.error(f"Ошибка: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()