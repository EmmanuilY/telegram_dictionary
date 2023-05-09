from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from keyboards.simple_row import make_row_keyboard
from model.db import DB

import re

db = DB()

router = Router()

# Эти значения далее будут подставляться в итоговый текст, отсюда
# такая на первый взгляд странная форма прилагательных
available_term_types = ["term", "english_word"]
available_drink_sizes = ["Маленькую", "Среднюю", "Большую"]


class AddTerms(StatesGroup):
    choosing_term_type = State()
    add_terms = State()

def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)

@router.message(Command("add_terms"))
async def cmd_add_terms(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите тип изучаемого объекта",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает название"
    await state.set_state(AddTerms.choosing_term_type)

# Этап выбора блюда #


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
    term_definition_pattern = r'^(\w+)\s*:\s*(.+)$'
    term_and_definition = escape_special_characters(message.text)
    match = re.match(term_definition_pattern, term_and_definition)
    if match:
        term, definition = match.groups()

        answer = await db.add_term(term=term.lower(), definition=definition.lower(),type= user_data['chosen_type'], telegram_id=str(message.from_user.id))
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
async def drink_size_chosen_incorrectly(message: Message):
    await message.answer(
        text="Вы нарушили шаблон\n\n"
             "Пожалуйста, введите заново термин и определение",
    )
