FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libcurl4-openssl-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py sqs_client.py ./
COPY flight_searcher/ flight_searcher/

CMD ["python", "-m", "flight_searcher.flight_searcher"]
