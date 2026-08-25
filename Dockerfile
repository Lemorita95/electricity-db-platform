FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --only-upgrade libgnutls30 && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip==26.1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/src

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]