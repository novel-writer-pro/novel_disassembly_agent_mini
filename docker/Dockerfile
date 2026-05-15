FROM node:20-bookworm-slim AS web-builder

WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/web/ ./
RUN npm run build && npm prune --omit=dev


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_MAJOR=20 \
    NOVEL_ANALYZER_API_HOST=0.0.0.0 \
    NOVEL_ANALYZER_API_PORT=8011 \
    NOVEL_ANALYZER_WEB_PORT=4173 \
    NOVEL_ANALYZER_DB_DIALECT=postgresql \
    NOVEL_ANALYZER_DB_HOST=postgres \
    NOVEL_ANALYZER_DB_PORT=5432 \
    NOVEL_ANALYZER_DB_NAME=novel_analyzer \
    NOVEL_ANALYZER_DB_USER=d2 \
    NOVEL_ANALYZER_DB_ADMIN_NAME=postgres \
    NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx \
    NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3 \
    NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=/models/bge-m3-onnx \
    NOVEL_ANALYZER_EMBEDDING_CACHE_DIR=/data/cache/embeddings

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg supervisor postgresql-client tini \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install "uvicorn[standard]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY apps ./apps
COPY novel_analyzer ./novel_analyzer
COPY rag ./rag
COPY scripts ./scripts
COPY skills_dir ./skills_dir
COPY docker/supervisord.conf /etc/supervisor/conf.d/novel-analyzer.conf
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

COPY --from=web-builder /build/.next        ./apps/web/.next
COPY --from=web-builder /build/node_modules ./apps/web/node_modules
COPY --from=web-builder /build/package.json ./apps/web/package.json

RUN mkdir -p /data/cache/embeddings /data/runs /data/output /data/logs /models \
    && chmod +x /usr/local/bin/entrypoint.sh

VOLUME ["/data", "/models"]

EXPOSE 8011 4173

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/novel-analyzer.conf", "-n"]
