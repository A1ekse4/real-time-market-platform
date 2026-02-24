import asyncio
import json
import time
from aiokafka import AIOKafkaConsumer
import asyncpg
import redis

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
TOPIC = "trades"

DB_HOST = "postgres"
DB_USER = "market"
DB_PASSWORD = "market"
DB_NAME = "market"

REDIS_HOST = "redis"
REDIS_PORT = 6379

WINDOW_SIZE = 10  # seconds


# -------------------- RETRY HELPERS --------------------

async def wait_for_kafka(consumer, retries=20):
    for i in range(retries):
        try:
            await consumer.start()
            print("Connected to Kafka")
            return
        except Exception:
            print(f"Kafka not ready, retry {i+1}/{retries}")
            await asyncio.sleep(3)
    raise Exception("Kafka not available")


async def wait_for_postgres(retries=20):
    for i in range(retries):
        try:
            conn = await asyncpg.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            print("Connected to Postgres")
            return conn
        except Exception:
            print(f"Postgres not ready, retry {i+1}/{retries}")
            await asyncio.sleep(3)
    raise Exception("Postgres not available")


def wait_for_redis(retries=20):
    for i in range(retries):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            r.ping()
            print("Connected to Redis")
            return r
        except Exception:
            print(f"Redis not ready, retry {i+1}/{retries}")
            time.sleep(3)
    raise Exception("Redis not available")


# -------------------- DB SETUP --------------------

async def create_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS candles_10s (
            id SERIAL PRIMARY KEY,
            symbol TEXT,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume NUMERIC,
            window_start BIGINT
        );
    """)


# -------------------- MAIN CONSUMER --------------------

async def consume():
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="trade-group",
        auto_offset_reset="latest"
    )

    await wait_for_kafka(consumer)

    conn = await wait_for_postgres()
    await create_table(conn)

    redis_client = wait_for_redis()

    trades_buffer = []

    # Выравниваем окно по 10-секундной границе
    window_start = (int(time.time()) // WINDOW_SIZE) * WINDOW_SIZE

    try:
        async for msg in consumer:
            data = json.loads(msg.value.decode("utf-8"))

            symbol = data["s"]
            price = float(data["p"])
            quantity = float(data["q"])

            # Обновляем latest price в Redis
            redis_client.set(f"{symbol}:latest_price", price)

            trades_buffer.append((price, quantity))

            current_time = int(time.time())
            aligned_time = (current_time // WINDOW_SIZE) * WINDOW_SIZE

            # Если окно сменилось — закрываем прошлое
            if aligned_time > window_start:

                if trades_buffer:
                    prices = [t[0] for t in trades_buffer]
                    volumes = [t[1] for t in trades_buffer]

                    open_price = prices[0]
                    close_price = prices[-1]
                    high_price = max(prices)
                    low_price = min(prices)
                    total_volume = sum(volumes)

                    # Сохраняем в Postgres
                    await conn.execute("""
                        INSERT INTO candles_10s
                        (symbol, open, high, low, close, volume, window_start)
                        VALUES($1, $2, $3, $4, $5, $6, $7)
                    """,
                    symbol,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    total_volume,
                    window_start
                    )

                    print("Saved candle:",
                          open_price, high_price,
                          low_price, close_price)

                    # Сохраняем закрытую свечу в Redis
                    redis_client.hset(f"{symbol}:last_closed_candle", mapping={
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": total_volume,
                        "window_start": window_start
                    })

                # Сбрасываем буфер
                trades_buffer = []
                window_start = aligned_time

            # Обновляем текущую незакрытую свечу в Redis
            if trades_buffer:
                prices = [t[0] for t in trades_buffer]
                volumes = [t[1] for t in trades_buffer]

                redis_client.hset(f"{symbol}:current_candle", mapping={
                    "open": prices[0],
                    "high": max(prices),
                    "low": min(prices),
                    "close": prices[-1],
                    "volume": sum(volumes),
                    "window_start": window_start
                })

    finally:
        await consumer.stop()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(consume())