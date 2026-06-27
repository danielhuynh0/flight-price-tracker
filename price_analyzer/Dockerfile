FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py sqs_client.py ./
COPY price_analyzer/ price_analyzer/

CMD ["python", "-m", "price_analyzer.price_analyzer"]
