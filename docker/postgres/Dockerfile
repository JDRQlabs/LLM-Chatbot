# PostgreSQL 16 with pgvector extension
# Used for business logic database with vector similarity search

FROM postgres:16

# Install build dependencies and pgvector
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

# Clone and install pgvector v0.5.1
RUN git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make \
    && make install \
    && rm -rf /tmp/pgvector

# Clean up build dependencies to reduce image size
RUN apt-get purge -y --auto-remove \
    build-essential \
    git \
    && apt-get clean

# The extension will be enabled in the database via init scripts
# mounted to /docker-entrypoint-initdb.d/
