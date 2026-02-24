from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncpg
import redis
import asyncio
import datetime

app = FastAPI()

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

DB_CONFIG = dict(
    host="postgres",
    user="market",
    password="market",
    database="market"
)


@app.get("/price")
def get_price():
    return {"price": redis_client.get("BTCUSDT:latest_price")}


@app.get("/candles")
async def get_candles(limit: int = 50):
    conn = await asyncpg.connect(**DB_CONFIG)
    rows = await conn.fetch(
        "SELECT * FROM candles_10s ORDER BY id DESC LIMIT $1", limit
    )
    await conn.close()

    # Переворачиваем, чтобы были по времени
    rows = list(reversed(rows))

    return [
    {
        "time": datetime.datetime.utcfromtimestamp(
            r["window_start"]
        ).isoformat(),
        "open": float(r["open"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
        "close": float(r["close"])
    }
    for r in rows
]

@app.get("/current-candle")
def get_current_candle():
    data = redis_client.hgetall("BTCUSDT:current_candle")
    if not data:
        return {}

    return {
        "time": int(data["window_start"]),
        "open": float(data["open"]),
        "high": float(data["high"]),
        "low": float(data["low"]),
        "close": float(data["close"])
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>BTC Live Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
</head>
<body style="background:#111;color:white;font-family:Arial;">

<h2>BTCUSDT Live Chart</h2>
<h3 id="price">Loading price...</h3>
<div id="chart" style="width:100%; height:500px;"></div>

<script>
    const chart = LightweightCharts.createChart(
        document.getElementById('chart'),
        {
            layout: {
                background: { color: '#111' },
                textColor: '#DDD'
            },
            grid: {
                vertLines: { color: '#333' },
                horzLines: { color: '#333' }
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: true,
                rightBarStaysOnScroll: true
            },
            localization: {
                locale: 'ru-RU',
                timeFormatter: (time) => {
                    const date = new Date(time * 1000);
                    return date.toLocaleTimeString();
                }
            }
        }
    );

    const candleSeries = chart.addCandlestickSeries();

    let lastCandleTime = null;

    async function loadInitialCandles() {
        const response = await fetch('/candles');
        const data = await response.json();

        const formatted = data.map(c => ({
            time: Number(c.time),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        }));

        candleSeries.setData(formatted);

        if (formatted.length > 0) {
            lastCandleTime = formatted[formatted.length - 1].time;
        }
    }

    async function updateCurrentCandle() {
        const response = await fetch('/current-candle');
        const candle = await response.json();

        if (!candle.time) return;

        const formatted = {
            time: Number(candle.time),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close
        };

        candleSeries.update(formatted);
        lastCandleTime = formatted.time;
    }

    async function updatePrice() {
        const response = await fetch('/price');
        const data = await response.json();
        document.getElementById('price').innerText =
            "Current Price: " + data.price;
    }

    loadInitialCandles();
    updatePrice();

    setInterval(updateCurrentCandle, 1000);
    setInterval(updatePrice, 1000);
</script>

</body>
</html>
""" 