FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py ./
COPY app.py ./
COPY templates/ templates/

EXPOSE 5000

CMD ["python", "app.py"]
