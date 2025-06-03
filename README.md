# 🤖 Bratishka Bot

AI-powered Telegram bot для создания сводок по сообщениям в чатах с использованием локальных LLM моделей и векторной базы данных.

## ✨ Возможности

- **Умные сводки**: Анализ переписки с помощью продвинутых LLM
- **Гибкие временные интервалы**: От "последние 10 минут" до "всё время"
- **Векторный поиск**: ChromaDB для эффективного хранения и поиска сообщений  
- **Локальные модели**: Полная приватность, никаких внешних API
- **Prod-ready**: Docker, health checks, graceful shutdown
- **Модульная архитектура**: Легко расширяемый и поддерживаемый код

## 🏗️ Архитектура

```
app/
├── config/          # Единая конфигурация приложения
├── core/            # Базовая логика (логирование, NLP)
├── services/        # Сервисы (ChromaDB, LLM)
├── telegram/        # Telegram бот и обработчики
└── main.py          # Точка входа
```

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- Docker & Docker Compose
- Локальная LLM модель (рекомендуется DeepSeek или Qwen)

### 1. Клонирование и настройка

```bash
git clone <repository>
cd bratishka-bot

# Копируем и настраиваем конфигурацию
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

### 2. Скачивание модели

```bash
# Создайте директорию для моделей
mkdir -p models

# Скачайте модель (пример с DeepSeek)
# Разместите файл модели в models/
```

### 3. Запуск для разработки

```bash
# Установка зависимостей
pip install -r requirements-dev.txt

# Запуск в dev режиме (автоматически поднимает ChromaDB)
chmod +x scripts/run_dev.sh
./scripts/run_dev.sh
```

### 4. Запуск в продакшне

```bash
# Запуск всех сервисов в Docker
chmod +x scripts/run_prod.sh
./scripts/run_prod.sh
```

## ⚙️ Конфигурация

### Основные переменные окружения

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
BOT_USERNAME=your_bot_username

# Модель
MODEL_PATH=./models/model.gguf
MODEL_CTX=8192
MODEL_THREADS=8
MODEL_GPU_LAYERS=0

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Приложение
DEBUG=0
LOG_LEVEL=INFO
DEFAULT_TIME_HOURS=2
```

## 🤖 Использование

### Команды бота

- `/start` - информация о боте
- `/help` - справка по командам
- `/stats` - статистика чата

### Запрос сводки

Обращайтесь к боту через @ упоминание:

```
@your_bot_username сводка
@your_bot_username о чём договорились?
@your_bot_username что обсуждали за час?
@your_bot_username сводка за вчера
@your_bot_username что это было сейчас?
```

### Временные интервалы

- **"сейчас"** → последние 10 минут
- **"за X минут/часов/дней"** → точный интервал
- **"вчера"** → весь вчерашний день
- **"всё время"** → вся история чата
- **По умолчанию** → последние 2 часа

## 🔧 Разработка

### Структура проекта

```
bratishka-bot/
├── app/                     # Основной код
│   ├── config/             # Конфигурация
│   ├── core/               # Базовая логика
│   ├── services/           # Сервисы
│   ├── telegram/           # Telegram бот
│   └── main.py             # Точка входа
├── docker/                 # Docker конфигурация
├── scripts/                # Скрипты запуска
├── requirements.txt        # Зависимости
├── requirements-dev.txt    # Dev зависимости
└── README.md
```

### Добавление новых возможностей

1. **Новые типы намерений**: Расширьте `IntentRecognizer`
2. **Новые команды**: Добавьте обработчики в `TelegramHandlers`
3. **Новые сервисы**: Создайте в `app/services/`

### Тестирование

```bash
# Запуск тестов
pytest

# С покрытием
pytest --cov=app

# Только быстрые тесты
pytest -m "not slow"
```

### Качество кода

```bash
# Форматирование
black app/
isort app/

# Линтинг
flake8 app/
mypy app/
```

## 🐳 Docker

### Развертывание

```bash
cd docker
docker-compose up -d
```

### Мониторинг

```bash
# Логи
docker-compose logs -f bratishka-bot

# Статус
docker-compose ps

# Остановка
docker-compose down
```

### Health Checks

Автоматические проверки:
- ChromaDB heartbeat
- LLM модель работоспособность
- Telegram Bot API подключение

## 🔍 Мониторинг и отладка

### Логирование

Настраиваемые уровни:
- `DEBUG` - подробная отладка
- `INFO` - общая информация
- `WARNING` - предупреждения
- `ERROR` - ошибки

### Метрики

- Количество обработанных сообщений
- Время генерации сводок
- Использование памяти и CPU
- Статус подключений к сервисам

## 🛠️ Устранение проблем

### Частые проблемы

1. **Модель не загружается**
   ```bash
   # Проверьте путь к модели
   ls -la models/
   # Проверьте права доступа
   chmod 644 models/*.gguf
   ```

2. **ChromaDB недоступен**
   ```bash
   # Проверьте статус
   curl http://localhost:8000/api/v1/heartbeat
   # Перезапустите сервис
   docker-compose restart chromadb
   ```

3. **Бот не отвечает**
   ```bash
   # Проверьте токен
   curl "https://api.telegram.org/bot<TOKEN>/getMe"
   # Проверьте логи
   docker-compose logs bratishka-bot
   ```

### Производительность

- **Память**: 4-8GB для работы с моделями 8B параметров
- **CPU**: 4+ ядра для комфортной работы
- **GPU**: Опционально, настраивается через `MODEL_GPU_LAYERS`

## 📝 TODO

- [ ] Веб-интерфейс для управления
- [ ] Поддержка нескольких языков
- [ ] Интеграция с внешними LLM API
- [ ] Экспорт сводок в различные форматы
- [ ] Планировщик автоматических сводок
- [ ] Система плагинов

## 🤝 Участие в разработке

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для деталей.

## 👥 Авторы

- **Bratishka Team** - *Начальная работа*

## 🙏 Благодарности

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - отличная библиотека для Telegram
- [ChromaDB](https://github.com/chroma-core/chroma) - мощная векторная база данных
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) - Python bindings для llama.cpp
- 