FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py sqs_client.py ./
COPY notif_sender/ notif_sender/

CMD ["python", "-m", "notif_sender.notif_sender"]
