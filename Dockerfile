FROM python:3.12-slim

# Установка системных зависимостей включая git
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создание пользователя для безопасности
RUN groupadd -r bratishka && useradd -r -g bratishka -m bratishka

WORKDIR /app

# Копирование зависимостей и установка
COPY requirements.txt .

# Устанавливаем зависимости с правильными флагами для llama-cpp-python
RUN pip install --no-cache-dir --upgrade pip && \
    CMAKE_ARGS="-DGGML_CPU_ALL_VARIANTS=ON -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF" pip install --no-cache-dir llama-cpp-python==0.3.9 && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY app/ ./app/

# Создание директорий и установка прав
RUN mkdir -p models && \
    chown -R bratishka:bratishka /app

# Переключаемся на непривилегированного пользователя
USER bratishka

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Запуск
CMD ["python", "-m", "app.main"]
