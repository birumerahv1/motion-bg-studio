FROM python:3.12-slim

# tini for clean PID 1 signal handling
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps first for better Docker layer caching
COPY bot/requirements.txt /app/bot/requirements.txt
RUN pip install --no-cache-dir -r /app/bot/requirements.txt

# Then the bot source
COPY bot /app/bot

# Persistent state lives under /app/data; mount a volume here in prod
ENV DB_PATH=/app/data/bot.db
RUN mkdir -p /app/data

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "bot"]
