from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from keyboards.simple_row import make_row_keyboard
from model.db import DB
from loguru import logger

import re

db = DB()

router = Router()


available_term_types = ["term", "english_word"]



class UserProgress(StatesGroup):
    choosing_term_type = State()
    type_chosen = State()




@router.message(Command("check_progress"))
async def cmd_check_progress(message: Message, state: FSMContext):
    progress = await db.get_terms_progress(telegram_id=str(message.from_user.id))
    logger.debug(f'{progress}')
    await message.answer(
        text=f"Вы изучили столько слов: {progress['learned']}\n"
             f"у вас в стадии повторении столько слов: {progress['repeat']}\n"
             f"у вас неизучено слов: {progress['learning']} \n",
    )
    await message.answer(
        text="Выберите тип изучаемого объекта чтобы посмотреть слова",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(UserProgress.type_chosen)


@router.message(UserProgress.type_chosen, F.text.in_(available_term_types))
async def term_type_chosen(message: Message, state: FSMContext):
    await state.update_data(chosen_type=message.text.lower())
    await message.answer(
        text="Окей, выбери теперь какие слвоа ты хочешь посмотреть",
        reply_markup=make_row_keyboard(['learned', 'repeat', 'learning'])
    )

@router.message(UserProgress.type_chosen, F.text.in_(['learned', 'repeat', 'learning']))
async def term_type_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    type = user_data['chosen_type']
    progress = message.text.lower()
    telegram_id = str(message.from_user.id)
    terms = await db.get_terms_learning(telegram_id=telegram_id, type=type, progress=progress)
    logger.debug(f'{terms}')
    terms_text = "\n".join([f"{i + 1}. {term}: {definition}" for i, (term, definition) in enumerate(terms.items())])
    await message.answer(
        text=f"{terms_text}",
    )