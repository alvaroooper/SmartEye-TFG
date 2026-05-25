FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

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

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup configs ./configs
COPY --chown=appuser:appgroup config.py run.py seed.py entrypoint.sh ./

RUN mkdir -p /app/execution_data /app/models/mp /app/models/yolo \
    && chmod +x /app/entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
