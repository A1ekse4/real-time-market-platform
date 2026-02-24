# Real-Time Market Streaming Platform

Реализация потоковой торговой платформы с обработкой данных в реальном времени.

Проект демонстрирует архитектуру стриминговой системы:
- получение сделок в реальном времени
- обработка через Kafka
- агрегация свечей (OHLC)
- хранение истории в PostgreSQL
- хранение текущего состояния в Redis
- REST API и live-график через FastAPI


# Стек технологий

Backend:
- Python 3.11
- FastAPI
- AIOKafka
- asyncpg
- redis-py

Инфраструктура:
- Apache Kafka
- Zookeeper
- PostgreSQL
- Redis
- Docker
- Docker Compose

Frontend:
- Lightweight Charts (библиотека TradingView)
- Vanilla JavaScript
- Live обновление графика


# Архитектура

        Binance WebSocket
               │
               ▼
        market-producer
               │
               ▼
         Kafka (topic: trades)
               │
               ▼
        trade-processor
         │            │
         ▼            ▼
    PostgreSQL       Redis
  (история)      (live состояние)
               │
               ▼
            FastAPI
               │
               ▼
         Live Dashboard


# Основные возможности

✔ Потоковая обработка сделок  
Producer получает сделки и публикует их в Kafka.

✔ Агрегация 10-секундных свечей  
Trade processor:
- буферизует сделки
- выравнивает время по границе окна
- рассчитывает:
  - Open
  - High
  - Low
  - Close
  - Volume

Redis как hot storage  
Redis хранит:
- текущую цену
- текущую (незакрытую) свечу
- последнюю закрытую свечу

PostgreSQL как persistent storage  
Все закрытые свечи сохраняются в таблице candles_10s.

REST API  

Доступные эндпоинты:
GET /price
GET /candles?limit=50
GET /current-candle
GET /dashboard

Live-график  
- отображение свечей
- автоматическое обновление
- корректная временная шкала
- темный интерфейс


# Логика агрегации по времени

Свечи выравниваются по 10-секундным границам:

window_start = (int(time.time()) // WINDOW_SIZE) * WINDOW_SIZE

Это гарантирует строгие интервалы:
12:00:00
12:00:10
12:00:20


# Модель данных

Таблица PostgreSQL: candles_10s

Поля:
- id (SERIAL)
- symbol (TEXT)
- open (NUMERIC)
- high (NUMERIC)
- low (NUMERIC)
- close (NUMERIC)
- volume (NUMERIC)
- window_start (BIGINT)


# Запуск проекта

1. Клонирование:

git clone https://github.com/YOUR_USERNAME/real-time-market-platform.git
cd real-time-market-platform

2. Запуск сервисов:

docker compose up --build

3. Открыть дашборд:

http://localhost:8000/dashboard


# Отладка и проверка

Проверить контейнеры:
docker ps

Логи процессора:
docker logs trade-processor

Проверка Redis:
docker exec -it redis redis-cli
HGETALL BTCUSDT:current_candle

Проверка PostgreSQL:
docker exec -it postgres psql -U market -d market
SELECT * FROM candles_10s ORDER BY id DESC LIMIT 5;


# Что демонстрирует проект

- Event-driven архитектуру
- Kafka consumer groups
- Stateful stream processing
- Time-window агрегацию
- Использование Redis как in-memory state store
- PostgreSQL как хранилище истории
- Docker networking
- Микросервисную архитектуру
- Реализацию live-интерфейса поверх стриминговой системы