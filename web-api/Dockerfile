FROM python:3.13.15-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

# Baked-in defaults so STORAGE_DIR/DB_PATH are always correct inside this
# image regardless of how it's launched (docker-compose, plain `docker run`,
# or another orchestrator) — config.py's own path-derived fallback is only
# correct for local (non-containerized) dev and must not be relied on here.
ENV STORAGE_DIR=/storage
ENV DB_PATH=/storage/app.db
ENV REDIS_URL=redis://redis:6379/0
VOLUME ["/storage"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
