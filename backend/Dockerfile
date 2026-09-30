FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data DATABASE_URL=sqlite:////data/fde.db FDE_SECRETS_DIR=/data/.secrets

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install ".[postgres]"
COPY alembic.ini ./
COPY alembic ./alembic
COPY seeds ./seeds
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN useradd --system --uid 10001 fde && mkdir -p /data && chown fde /data && chmod +x /usr/local/bin/docker-entrypoint.sh
USER fde
VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
