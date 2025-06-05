import psutil
import pandas as pd
from sklearn.cluster import DBSCAN
from datetime import datetime, timedelta
import logging
import pickle
import os

DATA_FILE = "metrics.pkl" 
LOG_FILE = "monitor.log" 

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

class MetricsStorage:
    def __init__(self):
        self.df = pd.DataFrame(columns=['timestamp', 'cpu', 'ram', 'disk', 'network'])
        try:
            self.load_data()
        except (FileNotFoundError, EOFError, pickle.PickleError) as e:
            logging.warning(f"Не удалось загрузить данные из {DATA_FILE}: {e}. Создан новый пустой DataFrame.")
            self.df = pd.DataFrame(columns=['timestamp', 'cpu', 'ram', 'disk', 'network'])
            self.save_data()

    def add_metrics(self):
        """
        Собирает текущие метрики системы и добавляет их в DataFrame.
        """
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
        cutoff = datetime.now() - timedelta(days=30)
        self.df = self.df[self.df['timestamp'] >= cutoff]

    def save_data(self):
        try:
            with open(DATA_FILE, 'wb') as f:
                pickle.dump(self.df, f)
        except Exception as e:
            logging.error(f"Ошибка при сохранении данных в {DATA_FILE}: {e}")

    def load_data(self):
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, 'rb') as f:
                self.df = pickle.load(f)
        else:
            raise FileNotFoundError(f"Файл данных {DATA_FILE} не найден или пуст.")


storage = MetricsStorage()

def detect_anomalies():

    if len(storage.df) < 10:
        logging.info("Недостаточно данных для обнаружения аномалий (требуется минимум 10 записей).")
        return None

    last_24h = storage.df[storage.df['timestamp'] >= datetime.now() - timedelta(hours=240)]
    if len(last_24h) < 5:
        logging.info("Недостаточно данных за последние 24 часа для обнаружения аномалий (требуется минимум 5 записей).")
        return None

    X = last_24h[['cpu', 'ram', 'network']].values

    try:
        model = DBSCAN(eps=2.5, min_samples=3).fit(X)
        anomalies = last_24h[model.labels_ == -1]

        return anomalies.iloc[-1] if not anomalies.empty else None
    except Exception as e:
        logging.error(f"Ошибка при выполнении обнаружения аномалий: {e}")
        return None

def generate_and_log_report():
    storage.add_metrics()
    last = storage.df.iloc[-1]

    msg = (
        "📊 Отчёт о состоянии сервера:\n"
        f"Время: {last['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"CPU: {last['cpu']}%\n"
        f"RAM: {last['ram']}%\n"
        f"Диск: {last['disk']}%"
    )

    if anomaly := detect_anomalies():
        msg += (
            "\n\n⚠️ Обнаружена аномалия!\n"
            f"Время: {anomaly['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"CPU: {anomaly['cpu']}%\n"
            f"RAM: {anomaly['ram']}%"
        )

    logging.info(msg)
    print(msg)       

def get_overall_statistics():
    if not storage.df.empty:
        stats = storage.df.describe().to_string()
        full_stats_msg = f"📈 Общая статистика за период:\n{stats}"
        logging.info(full_stats_msg)
        print("\n" + full_stats_msg)
    else:
        no_stats_msg = "📈 Статистика недоступна: нет собранных метрик."
        logging.info(no_stats_msg)
        print("\n" + no_stats_msg)

if __name__ == "__main__":
    print("Запуск скрипта мониторинга сервера...")

    generate_and_log_report()
    get_overall_statistics()

    print(f"\nДанные метрик хранятся в файле: {DATA_FILE}")
    print(f"Подробные логи доступны в файле: {LOG_FILE}")
    print("Скрипт завершил работу. Для обновления данных запустите его снова.")