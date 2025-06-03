# ==========================================
# Оптимизированный single-stage Dockerfile
# ==========================================

FROM python:3.12-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаем пользователя
RUN groupadd -r bratishka && useradd -r -g bratishka -m bratishka

# Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

WORKDIR /app

# ==========================================
# Копирование слоями по частоте изменений
# (от наименее изменяемых к наиболее)
# ==========================================

# 1. Зависимости (изменяются редко) - кэшируется
COPY requirements.txt .
RUN CMAKE_ARGS="-DGGML_CPU_ALL_VARIANTS=ON -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF" \
    pip install --no-cache-dir llama-cpp-python==0.3.9 && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY app/ ./app/

# Удаляем build-зависимости для уменьшения размера
RUN apt-get purge -y --auto-remove \
    build-essential \
    cmake \
    pkg-config \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаем директории и права
RUN mkdir -p models && \
    chown -R bratishka:bratishka /app

USER bratishka

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

# Простой healthcheck - проверяем только успешный импорт основного модуля
# Если приложение может импортировать TelegramBot, значит все зависимости работают
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); from app.telegram.bot import TelegramBot; print('OK')" || exit 1

CMD ["python", "-m", "app.main"]