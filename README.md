# 🤖 Bratishka AI Agent

Корпоративный AI-помощник на базе DeepSeek R1 для автоматизации рабочих процессов в Telegram.

## ✨ Возможности

- 📋 **Автоматическое создание протоколов** встреч и переписки
- 📅 **Планирование встреч** с отправкой календарных приглашений
- 📧 **Отправка протоколов** всем участникам по email
- 🔍 **Поиск по истории** сообщений и документов
- 👥 **LDAP аутентификация** корпоративных пользователей
- 🚀 **Оптимизировано для высоких нагрузок** (10k+ пользователей)

## 🏗️ Архитектура

- **LLM**: DeepSeek R1-0528-Qwen3-8B (локально)
- **База данных**: PostgreSQL 16 с партиционированием
- **Фреймворк**: FastAPI + python-telegram-bot
- **Кэширование**: In-memory кэш + PostgreSQL
- **Миграции**: Alembic
- **Контейнеризация**: Docker Compose

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- Git
- Telegram Bot Token
- LDAP сервер (опционально)

### Установка

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd bratishka-agent
```

2. **Настройка окружения**
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

3. **Развертывание**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Основные переменные окружения

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=bratishka

# База данных
POSTGRES_PASSWORD=secure_password

# LDAP (опционально)
LDAP_SERVER=ldap://your.ldap.server:389
LDAP_BASE_DN=dc=company,dc=com

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_USER=your_email@company.com
EMAIL_PASSWORD=your_app_password
```

## 📝 Использование

### Создание протокола
```
@bratishka подведи итог за последние 2 часа
```

### Планирование встречи
```
@bratishka сделай встречу на завтра в 14:00 по проекту
```

### Отправка протокола
```
@bratishka отправь протокол всем участникам
```

## 🔧 Управление

### Мониторинг
```bash
./scripts/monitor.sh
docker-compose logs -f bratishka-agent
```

### Резервное копирование
```bash
./scripts/backup.sh
```

### Обновление
```bash
docker-compose pull
docker-compose up -d --force-recreate
```

## 🏃‍♂️ Разработка

### Локальная разработка
```bash
# Создание виртуального окружения
python3.13 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python -m app.main
```

## 🐛 Решение проблем

### Проверка состояния сервисов
```bash
docker-compose ps
docker-compose logs bratishka-agent
```

### Перезапуск при ошибках
```bash
docker-compose restart bratishka-agent
```

### Очистка и пересборка
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 📄 Лицензия

MIT License

## 🤝 Поддержка

Для вопросов и предложений создавайте Issues в репозитории.

---

**Bratishka AI Agent** - ваш надежный помощник для автоматизации корпоративных процессов! 🚀