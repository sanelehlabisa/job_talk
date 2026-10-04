FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh .

RUN addgroup --system jobtalk \
    && adduser --system --ingroup jobtalk jobtalk \
    && mkdir -p /run/jobtalk \
    && chown jobtalk:jobtalk /run/jobtalk \
    && chown -R jobtalk:jobtalk /app \
    && chmod +x /app/docker-entrypoint.sh

USER jobtalk

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--uds", "/run/jobtalk/api.sock"]
