FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir requests ccxt pandas numpy python-dotenv yfinance httpx "pydantic>=2.0.0" matplotlib python-dateutil aiohttp ta
COPY . .
RUN mkdir -p logs
CMD ["python", "bot.py"]
