import asyncio
import json
import websockets
from aiokafka import AIOKafkaProducer

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
TOPIC = "trades"

BINANCE_WS = "wss://stream.binance.com:9443/ws/btcusdt@trade"


async def wait_for_kafka(producer, retries=20):
    for i in range(retries):
        try:
            await producer.start()
            print("Connected to Kafka")
            return
        except Exception as e:
            print(f"Kafka not ready, retry {i+1}/{retries}")
            await asyncio.sleep(3)
    raise Exception("Kafka not available after retries")


async def stream_trades():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
    )

    await wait_for_kafka(producer)

    try:
        async with websockets.connect(BINANCE_WS) as ws:
            print("Connected to Binance WebSocket")

            while True:
                message = await ws.recv()
                data = json.loads(message)

                # Отправляем в Kafka
                await producer.send_and_wait(
                    TOPIC,
                    json.dumps(data).encode("utf-8")
                )

                print("Trade sent:", data["p"])  # цена

    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(stream_trades())