import re
from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from keyboards.simple_row import make_row_keyboard
from db.db import db
from loguru import logger

from state.states import AddTerms

router = Router()

AVAILABLE_TERM_TYPES = ["term", "english_word"]
TERM_DEFINITION_PATTERN = re.compile('^[\d\.\)\s]*([\w\s]+)\s*:\s*(.+)$')


@router.message(Command("add_terms"))
async def chose_term_type(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите тип изучаемого объекта",
        reply_markup=make_row_keyboard(AVAILABLE_TERM_TYPES)
    )
    await state.set_state(AddTerms.term_type_chosen)


@router.message(AddTerms.term_type_chosen, F.text.in_(AVAILABLE_TERM_TYPES))
async def term_type_chosen(message: Message, state: FSMContext):
    await state.update_data(chosen_type=message.text.lower())
    await message.answer(
        text="Теперь добавь слова, которые хочешь учить.\n"
             "Добавить нужно по шаблону 'термин : определение'",
        ReplyKeyboardRemove=True
    )
    await state.set_state(AddTerms.add_terms)


async def form_terms_and_definitions_from_stroke(message: Message, terms_and_definitions: str,
                                                 terms_to_add: list) -> list:
    terms_lines = terms_and_definitions.split('\n')
    for line in terms_lines:
        if line.count(":") > 1:
            await message.answer(
                text=f"Слишком много двоеточий ':' в строке '{line}'. Введите термин и определение в формате 'термин : определение'."
            )
            return []
        match = TERM_DEFINITION_PATTERN.match(line)
        if not match:
            await message.answer(
                text=f"Неверный формат в строке '{line}'. Введите термин и определение в формате 'термин : определение'."
            )
            return []
        term, definition = match.groups()
        terms_to_add.append((term.lower().strip(), definition.lower().strip()))
    return terms_to_add


@router.message(AddTerms.add_terms)
async def add_new_term(message: Message, state: FSMContext):
    user_data = await state.get_data()
    terms_and_definitions = message.text
    terms_to_add = []
    check_correct_template = await form_terms_and_definitions_from_stroke(message, terms_and_definitions, terms_to_add)
    if check_correct_template:
        for term, definition in terms_to_add:
            answer = await db.add_term(term=term, definition=definition, type=user_data['chosen_type'],
                                       telegram_id=str(message.from_user.id))
            if not answer:
                logger.error(f"что-то пошло не так. Термин {term} определение {definition}")
                return

        await message.answer(
            text="Все термины успешно добавлены. Хотите еще добавить?",
            reply_markup=ReplyKeyboardRemove()
        )
