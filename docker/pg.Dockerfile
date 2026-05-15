FROM postgres:17-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release \
        build-essential git cmake \
        postgresql-server-dev-17 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg \
    && echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*

RUN cd /tmp && git clone --depth 1 https://github.com/jaiminpan/pg_jieba.git \
    && cd pg_jieba \
    && git submodule update --init --recursive \
    && mkdir build && cd build \
    && cmake .. && make -j$(nproc) && make install \
    && cd /tmp && rm -rf pg_jieba

RUN cd /tmp && git clone --depth 1 https://github.com/postgrespro/pg_textsearch_pre.git pg_textsearch \
    || git clone --depth 1 https://github.com/postgrespro/rum.git pg_textsearch \
    ; if [ -d /tmp/pg_textsearch ]; then \
        cd /tmp/pg_textsearch && make USE_PGXS=1 && make USE_PGXS=1 install || true; \
        cd /tmp && rm -rf pg_textsearch; \
      fi

RUN apt-get purge -y build-essential git cmake postgresql-server-dev-17 \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /tmp/*
