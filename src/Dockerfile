FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .

RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock \
    && groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

COPY app ./app
COPY configs ./configs
COPY config.py run.py seed.py entrypoint.sh ./

RUN mkdir -p /app/execution_data /app/models/mp /app/models/yolo /tmp/matplotlib /tmp/ultralytics \
    && chmod 755 /app/entrypoint.sh \
    && chown -R appuser:appgroup /app/execution_data /app/models /tmp/matplotlib /tmp/ultralytics \
    && chmod -R u+rwX,g-rwx,o-rwx /app/execution_data /app/models /tmp/matplotlib /tmp/ultralytics
USER appuser

EXPOSE 5000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
