FROM python:3.13-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Копирование зависимостей и установка
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY app/ ./app/

# Создание пользователя для безопасности
RUN useradd -m -u 1000 bratishka && \
    chown -R bratishka:bratishka /app
USER bratishka

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import asyncio; import sys; sys.exit(0)" || exit 1

# Запуск
CMD ["python", "-m", "app.main"]