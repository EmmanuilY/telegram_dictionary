import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
from config.config import settings

from handlers import start, learn_words, add_words, progress


logger.add('debug.log', format="{time} {level} {message}", level="DEBUG", enqueue=True)



@logger.catch
async def main():
    # Если не указать storage, то по умолчанию всё равно будет MemoryStorage
    # Но явное лучше неявного =]
    dp = Dispatcher(storage=MemoryStorage())
    # Для выбора другой стратегии FSM:
    # dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
    bot = Bot(settings.BOT_TOKEN)

    dp.include_routers(start.router, learn_words.router, add_words.router,progress.router )
    # сюда импортируйте ваш собственный роутер для напитков

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    logger.info("Запускаем бота")
    asyncio.run(main())