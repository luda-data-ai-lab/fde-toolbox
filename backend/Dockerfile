FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data DATABASE_URL=sqlite:////data/fde.db FDE_SECRETS_DIR=/data/.secrets

# WITH_MSSQL=true adds Microsoft ODBC Driver 18 and pyodbc (fetched at build time, not at runtime).
ARG WITH_MSSQL=false
RUN if [ "$WITH_MSSQL" = "true" ]; then \
      . /etc/os-release \
      && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
      && curl -fsSL -o /tmp/ms.deb "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb" \
      && dpkg -i /tmp/ms.deb && rm /tmp/ms.deb \
      && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 libgssapi-krb5-2 \
      && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN if [ "$WITH_MSSQL" = "true" ]; then pip install ".[postgres,mssql]"; else pip install ".[postgres]"; fi
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
