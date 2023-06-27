import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
from config.config import settings

from handlers import start, add_words, user_progress_handler, repeat_handler, \
    learn_handler, repeat_learn_words_handler

logger.add('debug.log', format="{time} {level} {message}", level="DEBUG", enqueue=True)

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(settings.BOT_TOKEN)
dp.include_routers(start.router, add_words.router, user_progress_handler.router, learn_handler.router,
                   repeat_handler.router, repeat_learn_words_handler.router,
                   )


@logger.catch
async def main():
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    logger.info("Запускаем бота")
    asyncio.run(main())
