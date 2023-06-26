import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
from config.config import settings

from handlers import start, learn_words, add_words, progress, repeat_words, repeat_learned_words, repeat_handler, \
    learn_handler, repeat_learn_words_handler

logger.add('debug.log', format="{time} {level} {message}", level="DEBUG", enqueue=True)

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(settings.BOT_TOKEN)
dp.include_routers(start.router, add_words.router, progress.router,  test_learn.router, test_repeat.router, test_repeat_learn_words.router,
                  )


@logger.catch
async def main():
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    logger.info("Запускаем бота")
    asyncio.run(main())
