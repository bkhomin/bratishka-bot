"""
Точка входа в приложение
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import config
from app.config.logging import setup_logging
from app.bot.bot import TelegramBot


async def main():
    """Главная функция приложения"""
    # Настраиваем логирование
    logger = setup_logging(
        level=config.log_level,
        debug=config.debug
    )

    logger.info("Запуск Bratishka Bot...")
    logger.info(f"Debug режим: {config.debug}")
    logger.info(f"Уровень логирования: {config.log_level}")

    try:
        # Создаем и инициализируем бота
        bot = TelegramBot()

        # Запускаем бота
        await bot.run_async()

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Работа приложения завершена")


def run_sync():
    """Синхронная обертка для запуска"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_sync()
