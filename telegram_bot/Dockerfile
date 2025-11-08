# --- telegram_bot/Dockerfile (FULL) ---
FROM python:3.11-slim

ENV TZ=Asia/Phnom_Penh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Ensure relative imports like `import api_client` work
ENV PYTHONPATH=/app

# Install deps from project root copy
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot sources
COPY ./telegram_bot .

CMD ["python", "bot.py"]
