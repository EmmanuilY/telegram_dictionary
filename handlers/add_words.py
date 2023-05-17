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



class AddTerms(StatesGroup):
    choosing_term_type = State()
    add_terms = State()



@router.message(Command("add_terms"))
async def cmd_add_terms(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите тип изучаемого объекта",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(AddTerms.choosing_term_type)


@router.message(AddTerms.choosing_term_type, F.text.in_(available_term_types))
async def term_type_chosen(message: Message, state: FSMContext):
    await state.update_data(chosen_type=message.text.lower())
    await message.answer(
        text="Окей, теперь добавь слова, которые хочешь изучить. Добавить нужно по шаблону 'термин : определение'",
    )
    await state.set_state(AddTerms.add_terms)

@router.message(AddTerms.add_terms)
async def add_new_term(message: Message, state: FSMContext):
    user_data = await state.get_data()
    term_definition_pattern = r'^([\w\s]+)\s*:\s*(.+)$'
    match = re.match(term_definition_pattern, message.text)
    if match:
        term, definition = match.groups()
        answer = await db.add_term(term=term.lower(), definition=definition.lower(),type= user_data['chosen_type'], telegram_id=str(message.from_user.id))
        logger.info(f' добавили {term} с определением {definition} , пользователь')
        await message.answer(
            text=f"Полный {answer}\n"
                 f"Хотите еще добавить?",
            reply_markup=ReplyKeyboardRemove()
        )


    else:
        # Логика при несоответствии шаблону
        await message.answer(
            text="Неверный формат. Введите термин и определение в формате 'термин : определение'."
        )


@router.message(AddTerms.add_terms)
async def term_added_incorrectly(message: Message):
    await message.answer(
        text="Вы нарушили шаблон\n\n"
             "Пожалуйста, введите заново термин и определение",
    )
