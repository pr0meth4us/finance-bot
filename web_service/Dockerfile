FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y tzdata &&

ln -sf /usr/share/zoneinfo/Asia/Phnom_Penh /etc/localtime &&

echo "Asia/Phnom_Penh" > /etc/timezone &&

apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY web_service/ .

EXPOSE 8000

ENV PYTHONPATH=/app
ENV FLASK_APP=run.py
ENV TZ=Asia/Phnom_Penh

CMD ["python", "run.py"]